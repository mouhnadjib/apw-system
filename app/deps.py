from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .db import get_db
from .security import decode_token, password_version

bearer = HTTPBearer(auto_error=False)


def _unauthorized(msg: str = "غير مصرّح"):
    return HTTPException(status.HTTP_401_UNAUTHORIZED, msg, headers={"WWW-Authenticate": "Bearer"})


def _payload(creds: HTTPAuthorizationCredentials | None, typ: str) -> dict:
    if not creds:
        raise _unauthorized()
    try:
        payload = decode_token(creds.credentials)
    except Exception:
        raise _unauthorized("رمز الدخول غير صالح أو منتهي")
    if payload.get("typ") != typ:
        raise _unauthorized()
    return payload


def current_staff(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> models.StaffUser:
    payload = _payload(creds, "staff")
    user = db.get(models.StaffUser, int(payload["sub"]))
    if not user or not user.active:
        raise _unauthorized()
    # تغيير كلمة المرور يُسقط الرموز القديمة فوراً
    if payload.get("pv") != password_version(user.password_hash):
        raise _unauthorized("انتهت الجلسة، سجّل الدخول من جديد")
    return user


def require_admin(user: models.StaffUser = Depends(current_staff)) -> models.StaffUser:
    if user.role != models.StaffRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "هذه العملية للأدمن فقط")
    return user


def current_device(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> models.Device:
    payload = _payload(creds, "deputy")
    device = db.get(models.Device, int(payload.get("dev", 0)))
    # الإلغاء فوري: إذا عُطّل الجهاز أو النائب يسقط الرمز قبل انتهائه
    if not device or not device.active or device.deputy_id != int(payload["sub"]):
        raise _unauthorized("الجلسة ملغاة")
    deputy = db.get(models.Deputy, device.deputy_id)
    if not deputy or not deputy.active:
        raise _unauthorized("الحساب معطّل")
    mandate = db.get(models.Mandate, deputy.mandate_id)
    if not mandate or not mandate.active:
        raise _unauthorized("انتهت صلاحية الدورة")
    return device


def current_deputy(
    device: models.Device = Depends(current_device), db: Session = Depends(get_db)
) -> models.Deputy:
    return db.get(models.Deputy, device.deputy_id)


_LOOPBACK = {"127.0.0.1", "::1"}


def client_ip(request: Request) -> str | None:
    """عنوان العميل. رأس cf-connecting-ip لا يُصدَّق إلا إذا جاء الطلب من الجهاز نفسه
    (أي من النفق cloudflared)؛ أي اتصال آخر (شبكة محلية مثلاً) لا يستطيع انتحال العنوان."""
    peer = request.client.host if request.client else None
    if peer in _LOOPBACK:
        cf = request.headers.get("cf-connecting-ip", "").strip()
        if cf and len(cf) <= 45:
            return cf
    return peer


def audit(
    db: Session,
    request: Request,
    actor_type: str,
    actor_id: int | None,
    action: str,
    target: str | None = None,
) -> None:
    db.add(
        models.AuditLog(
            actor_type=actor_type, actor_id=actor_id, action=action, target=target, ip=client_ip(request)
        )
    )


def active_mandate(db: Session) -> models.Mandate:
    m = db.scalar(select(models.Mandate).where(models.Mandate.active.is_(True)))
    if not m:
        raise HTTPException(status.HTTP_409_CONFLICT, "لا توجد دورة نشطة")
    return m
