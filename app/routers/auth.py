from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import get_settings
from ..db import get_db
from ..deps import audit
from ..security import (
    as_utc,
    hash_password,
    make_access_token,
    new_refresh_token,
    normalize_code,
    normalize_phone,
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


@router.post("/staff/login", response_model=schemas.TokenOut)
def staff_login(body: schemas.StaffLogin, request: Request, db: Session = Depends(get_db)):
    s = get_settings()
    user = db.scalar(select(models.StaffUser).where(models.StaffUser.username == body.username))
    if user is None:
        verify_password(body.password, _DUMMY_HASH)  # تسوية زمن الاستجابة
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "اسم المستخدم أو كلمة المرور غير صحيحة")
    if user.locked_until and as_utc(user.locked_until) > utcnow():
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "الحساب مقفل مؤقتاً، حاول لاحقاً")
    if not user.active or not verify_password(body.password, user.password_hash):
        user.failed_logins += 1
        if user.failed_logins >= s.max_login_failures:
            user.locked_until = utcnow() + timedelta(minutes=s.lockout_minutes)
            user.failed_logins = 0
            audit(db, request, "staff", user.id, "login_locked", user.username)
        else:
            audit(db, request, "staff", user.id, "login_failed", user.username)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "اسم المستخدم أو كلمة المرور غير صحيحة")
    user.failed_logins = 0
    user.locked_until = None
    audit(db, request, "staff", user.id, "login", user.username)
    db.commit()
    token = make_access_token(user.id, "staff", s.access_minutes_staff, role=user.role.value)
    return schemas.TokenOut(access_token=token, expires_in=s.access_minutes_staff * 60)


@router.post("/activate", response_model=schemas.TokenOut)
def activate(body: schemas.ActivateIn, request: Request, db: Session = Depends(get_db)):
    """تفعيل حساب النائب برمز الدعوة وربط الجهاز."""
    s = get_settings()
    phone = normalize_phone(body.phone)
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
        raise HTTPException(status.HTTP_400_BAD_REQUEST, _BAD_ACTIVATION)

    if token_digest(normalize_code(body.code)) != inv.code_digest:
        inv.attempts += 1
        if inv.attempts >= s.max_invite_attempts:
            inv.revoked = True
            audit(db, request, "deputy", deputy.id, "invite_revoked_attempts", f"deputy:{deputy.id}")
        db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, _BAD_ACTIVATION)

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
def refresh(body: schemas.RefreshIn, db: Session = Depends(get_db)):
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
def logout(body: schemas.LogoutIn, db: Session = Depends(get_db)):
    device = db.scalar(
        select(models.Device).where(models.Device.refresh_digest == token_digest(body.refresh_token))
    )
    if device:
        device.active = False
        device.fcm_token = None
        db.commit()
