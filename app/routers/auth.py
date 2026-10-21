import hmac
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import get_settings
from ..db import get_db
from ..deps import audit, client_ip
from ..ratelimit import limiter
from ..security import (
    as_utc,
    hash_password,
    make_access_token,
    new_refresh_token,
    normalize_code,
    normalize_phone,
    password_version,
    token_digest,
    utcnow,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_DUMMY_HASH = hash_password("dummy-password-for-timing")
_BAD_ACTIVATION = "بيانات التفعيل غير صحيحة أو منتهية"


REFRESH_GRACE = timedelta(minutes=10)


def _issue_device_tokens(device: models.Device) -> schemas.TokenOut:
    s = get_settings()
    if device.refresh_digest:
        device.prev_refresh_digest = device.refresh_digest
        device.prev_refresh_until = utcnow() + REFRESH_GRACE
    refresh = new_refresh_token()
    device.refresh_digest = token_digest(refresh)
    device.refresh_expires = utcnow() + timedelta(days=s.refresh_days)
    access = make_access_token(device.deputy_id, "deputy", s.access_minutes_deputy, dev=device.id)
    return schemas.TokenOut(
        access_token=access, refresh_token=refresh, expires_in=s.access_minutes_deputy * 60
    )


def _too_many() -> HTTPException:
    return HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "محاولات كثيرة، حاول لاحقاً")


def _ip_gate(request: Request, scope: str, limit: int, window: float) -> str:
    ip = client_ip(request) or "?"
    if not limiter.hit(f"{scope}:{ip}", limit, window):
        raise _too_many()
    return ip


@router.post("/staff/login", response_model=schemas.TokenOut)
def staff_login(body: schemas.StaffLogin, request: Request, db: Session = Depends(get_db)):
    """حماية متعدّدة الطبقات:
    - حدّ عام لكل عنوان IP؛
    - قفل لكل زوج (اسم مستخدم، IP): لا يستطيع مهاجم من الإنترنت قفل حساب الأدمن على صاحبه؛
    - سقف إجمالي لكل اسم مستخدم ضد الهجوم الموزّع (أعلى بكثير فلا يُستعمل للتعطيل عملياً).
    """
    s = get_settings()
    ip = _ip_gate(request, "login-ip", 30, 600)
    uname = body.username.strip().lower()
    pair, total = f"login-fail:{uname}:{ip}", f"login-fail-total:{uname}"
    window = s.lockout_minutes * 60
    if limiter.count(pair, window) >= s.max_login_failures or limiter.count(total, window) >= s.max_login_failures * 6:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "الحساب مقفل مؤقتاً من هذا الجهاز، حاول لاحقاً")
    user = db.scalar(select(models.StaffUser).where(models.StaffUser.username == body.username))
    ok = False
    if user is None:
        verify_password(body.password, _DUMMY_HASH)  # تسوية زمن الاستجابة
    else:
        ok = verify_password(body.password, user.password_hash) and user.active
    if not ok:
        limiter.add(pair)
        limiter.add(total)
        audit(db, request, "staff", user.id if user else None, "login_failed", body.username[:64])
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "اسم المستخدم أو كلمة المرور غير صحيحة")
    limiter.clear(pair)
    audit(db, request, "staff", user.id, "login", user.username)
    db.commit()
    token = make_access_token(
        user.id, "staff", s.access_minutes_staff, role=user.role.value, pv=password_version(user.password_hash)
    )
    return schemas.TokenOut(access_token=token, expires_in=s.access_minutes_staff * 60)


@router.post("/activate", response_model=schemas.TokenOut)
def activate(body: schemas.ActivateIn, request: Request, db: Session = Depends(get_db)):
    """تفعيل حساب النائب برمز الدعوة وربط الجهاز."""
    s = get_settings()
    ip = _ip_gate(request, "activate-ip", 30, 600)
    phone = normalize_phone(body.phone)
    pair = f"activate-fail:{phone}:{ip}"
    # لا يستطيع غريب حرق رمز دعوة نائب بمحاولات خاطئة: الحدّ لكل (هاتف، IP)
    if limiter.count(pair, 900) >= 5:
        raise _too_many()
    deputy = db.scalar(
        select(models.Deputy)
        .join(models.Mandate)
        .where(
            models.Deputy.phone == phone,
            models.Deputy.active.is_(True),
            models.Mandate.active.is_(True),
        )
    )
    inv = None
    if deputy:
        inv = db.scalar(
            select(models.Invitation)
            .where(
                models.Invitation.deputy_id == deputy.id,
                models.Invitation.used_at.is_(None),
                models.Invitation.revoked.is_(False),
            )
            .order_by(models.Invitation.id.desc())
        )
    if not deputy or not inv or as_utc(inv.expires_at) <= utcnow():
        limiter.add(pair)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, _BAD_ACTIVATION)

    if not hmac.compare_digest(token_digest(normalize_code(body.code)), inv.code_digest):
        limiter.add(pair)
        inv.attempts += 1
        if inv.attempts >= s.max_invite_attempts:
            inv.revoked = True
            audit(db, request, "deputy", deputy.id, "invite_revoked_attempts", f"deputy:{deputy.id}")
        else:
            audit(db, request, "deputy", deputy.id, "activate_failed", f"deputy:{deputy.id}")
        db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, _BAD_ACTIVATION)

    limiter.clear(pair)
    inv.used_at = utcnow()
    for old in db.scalars(
        select(models.Device).where(models.Device.deputy_id == deputy.id, models.Device.active.is_(True))
    ):
        old.active = False
    device = models.Device(
        deputy_id=deputy.id,
        device_uid=body.device_uid,
        platform=body.platform,
        fcm_token=body.fcm_token,
        refresh_digest="",
        refresh_expires=utcnow(),
        last_seen=utcnow(),
    )
    db.add(device)
    db.flush()
    tokens = _issue_device_tokens(device)
    audit(db, request, "deputy", deputy.id, "device_bound", f"deputy:{deputy.id}")
    db.commit()
    return tokens


@router.post("/refresh", response_model=schemas.TokenOut)
def refresh(body: schemas.RefreshIn, request: Request, db: Session = Depends(get_db)):
    _ip_gate(request, "refresh-ip", 120, 60)
    digest = token_digest(body.refresh_token)
    device = db.scalar(select(models.Device).where(models.Device.refresh_digest == digest))
    if device is None:
        prev = db.scalar(select(models.Device).where(models.Device.prev_refresh_digest == digest))
        if prev and prev.prev_refresh_until and as_utc(prev.prev_refresh_until) > utcnow():
            device = prev
    bad = HTTPException(status.HTTP_401_UNAUTHORIZED, "الجلسة غير صالحة، يلزم تفعيل جديد")
    if (
        not device
        or not device.active
        or as_utc(device.refresh_expires) <= utcnow()
        or device.device_uid != body.device_uid
    ):
        raise bad
    deputy = db.get(models.Deputy, device.deputy_id)
    if not deputy or not deputy.active:
        raise bad
    if body.fcm_token:
        device.fcm_token = body.fcm_token
    device.last_seen = utcnow()
    tokens = _issue_device_tokens(device)  # تدوير رمز التحديث
    db.commit()
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: schemas.LogoutIn, request: Request, db: Session = Depends(get_db)):
    _ip_gate(request, "logout-ip", 60, 60)
    device = db.scalar(
        select(models.Device).where(models.Device.refresh_digest == token_digest(body.refresh_token))
    )
    if device:
        device.active = False
        device.fcm_token = None
        db.commit()
