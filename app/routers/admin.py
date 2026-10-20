from datetime import timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .. import models, schemas, services
from ..config import get_settings
from ..db import get_db
from ..deps import active_mandate, audit, require_admin
from ..security import (
    delete_file,
    hash_password,
    new_invite_code,
    normalize_code,
    normalize_phone,
    save_encrypted,
    sniff_mime,
    token_digest,
    utcnow,
)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def deputy_out(d: models.Deputy) -> schemas.DeputyStaffOut:
    return schemas.DeputyStaffOut(
        id=d.id,
        mandate_id=d.mandate_id,
        full_name=d.full_name,
        title=d.title,
        phone=d.phone,
        active=d.active,
        has_photo=bool(d.photo_path),
        committees=[schemas.CommitteeOut.model_validate(c) for c in d.committees],
    )


# ---------- الموظفون ----------
@router.post("/staff", response_model=schemas.StaffOut, status_code=201)
def create_staff(
    body: schemas.StaffCreate,
    request: Request,
    admin: models.StaffUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.scalar(select(models.StaffUser).where(models.StaffUser.username == body.username)):
        raise HTTPException(status.HTTP_409_CONFLICT, "اسم المستخدم مستعمل")
    user = models.StaffUser(
        username=body.username,
        full_name=body.full_name,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    db.flush()
    audit(db, request, "staff", admin.id, "staff_created", f"staff:{user.id}")
    db.commit()
    return user


@router.get("/staff", response_model=list[schemas.StaffOut])
def list_staff(db: Session = Depends(get_db)):
    return db.scalars(select(models.StaffUser).order_by(models.StaffUser.id)).all()


@router.patch("/staff/{staff_id}", response_model=schemas.StaffOut)
def update_staff(
    staff_id: int,
    body: schemas.StaffUpdate,
    request: Request,
    admin: models.StaffUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(models.StaffUser, staff_id)
    if not user:
        raise HTTPException(404, "غير موجود")
    if body.active is False and user.id == admin.id:
        raise HTTPException(400, "لا يمكنك تعطيل حسابك")
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.password is not None:
        user.password_hash = hash_password(body.password)
        user.failed_logins = 0
        user.locked_until = None
    if body.active is not None:
        user.active = body.active
    audit(db, request, "staff", admin.id, "staff_updated", f"staff:{user.id}")
    db.commit()
    return user


# ---------- الدورة واللجان ----------
@router.post("/mandates", response_model=schemas.MandateOut, status_code=201)
def create_mandate(
    body: schemas.MandateCreate,
    request: Request,
    admin: models.StaffUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    m = models.Mandate(**body.model_dump())
    if m.active:
        db.execute(update(models.Mandate).values(active=False))
    db.add(m)
    db.flush()
    if m.active:
        # نواب الدورات السابقة تُقطع جلساتهم فوراً
        old_ids = select(models.Deputy.id).where(models.Deputy.mandate_id != m.id)
        db.execute(update(models.Device).where(models.Device.deputy_id.in_(old_ids)).values(active=False))
    audit(db, request, "staff", admin.id, "mandate_created", f"mandate:{m.id}")
    db.commit()
    return m


@router.get("/mandates", response_model=list[schemas.MandateOut])
def list_mandates(db: Session = Depends(get_db)):
    return db.scalars(select(models.Mandate).order_by(models.Mandate.start_year.desc())).all()


@router.post("/committees", response_model=schemas.CommitteeOut, status_code=201)
def create_committee(
    body: schemas.CommitteeCreate,
    request: Request,
    admin: models.StaffUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    mandate = active_mandate(db)
    if db.scalar(
        select(models.Committee).where(
            models.Committee.mandate_id == mandate.id, models.Committee.name == body.name
        )
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "اللجنة موجودة")
    c = models.Committee(mandate_id=mandate.id, name=body.name)
    db.add(c)
    db.flush()
    audit(db, request, "staff", admin.id, "committee_created", f"committee:{c.id}")
    db.commit()
    return c


# ---------- النواب ----------
def _resolve_committees(db: Session, mandate_id: int, ids: list[int]) -> list[models.Committee]:
    if not ids:
        return []
    found = db.scalars(
        select(models.Committee).where(
            models.Committee.id.in_(ids), models.Committee.mandate_id == mandate_id
        )
    ).all()
    if len(found) != len(set(ids)):
        raise HTTPException(400, "لجنة غير موجودة في الدورة الحالية")
    return list(found)


@router.post("/deputies", response_model=schemas.DeputyStaffOut, status_code=201)
def create_deputy(
    body: schemas.DeputyCreate,
    request: Request,
    admin: models.StaffUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    mandate = active_mandate(db)
    phone = normalize_phone(body.phone)
    if db.scalar(
        select(models.Deputy).where(models.Deputy.mandate_id == mandate.id, models.Deputy.phone == phone)
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "رقم الهاتف مسجّل لنائب آخر")
    d = models.Deputy(
        mandate_id=mandate.id,
        full_name=body.full_name,
        title=body.title,
        phone=phone,
        committees=_resolve_committees(db, mandate.id, body.committee_ids),
    )
    db.add(d)
    db.flush()
    audit(db, request, "staff", admin.id, "deputy_created", f"deputy:{d.id}")
    db.commit()
    return deputy_out(d)


@router.patch("/deputies/{deputy_id}", response_model=schemas.DeputyStaffOut)
def update_deputy(
    deputy_id: int,
    body: schemas.DeputyUpdate,
    request: Request,
    admin: models.StaffUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    d = db.get(models.Deputy, deputy_id)
    if not d:
        raise HTTPException(404, "غير موجود")
    if body.full_name is not None:
        d.full_name = body.full_name
    if body.title is not None:
        d.title = body.title
    if body.phone is not None:
        phone = normalize_phone(body.phone)
        clash = db.scalar(
            select(models.Deputy).where(
                models.Deputy.mandate_id == d.mandate_id,
                models.Deputy.phone == phone,
                models.Deputy.id != d.id,
            )
        )
        if clash:
            raise HTTPException(status.HTTP_409_CONFLICT, "رقم الهاتف مسجّل لنائب آخر")
        d.phone = phone
    if body.committee_ids is not None:
        d.committees = _resolve_committees(db, d.mandate_id, body.committee_ids)
    if body.active is not None:
        d.active = body.active
        if not body.active:
            db.execute(update(models.Device).where(models.Device.deputy_id == d.id).values(active=False))
    audit(db, request, "staff", admin.id, "deputy_updated", f"deputy:{d.id}")
    db.commit()
    return deputy_out(d)


@router.put("/deputies/{deputy_id}/photo", status_code=status.HTTP_204_NO_CONTENT)
async def upload_photo(
    deputy_id: int,
    request: Request,
    file: UploadFile = File(...),
    admin: models.StaffUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    d = db.get(models.Deputy, deputy_id)
    if not d:
        raise HTTPException(404, "غير موجود")
    limit = get_settings().max_photo_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"حجم الصورة يتجاوز {get_settings().max_photo_mb} ميغابايت")
    if sniff_mime(data) not in ("image/jpeg", "image/png"):
        raise HTTPException(415, "الصورة يجب أن تكون JPEG أو PNG")
    old = d.photo_path
    d.photo_path = save_encrypted(data, "photos")
    audit(db, request, "staff", admin.id, "deputy_photo", f"deputy:{d.id}")
    db.commit()
    delete_file(old)


@router.post("/deputies/{deputy_id}/invite", response_model=schemas.InviteOut, status_code=201)
def create_invite(
    deputy_id: int,
    request: Request,
    admin: models.StaffUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    d = db.get(models.Deputy, deputy_id)
    if not d or not d.active:
        raise HTTPException(404, "نائب غير موجود أو معطّل")
    db.execute(
        update(models.Invitation)
        .where(models.Invitation.deputy_id == d.id, models.Invitation.used_at.is_(None))
        .values(revoked=True)
    )
    code = new_invite_code()
    expires = utcnow() + timedelta(hours=get_settings().invite_hours)
    db.add(
        models.Invitation(
            deputy_id=d.id,
            code_digest=token_digest(normalize_code(code)),
            expires_at=expires,
            created_by=admin.id,
        )
    )
    audit(db, request, "staff", admin.id, "invite_created", f"deputy:{d.id}")
    db.commit()
    return schemas.InviteOut(code=code, expires_at=expires)


@router.post("/deputies/{deputy_id}/reset-device", status_code=status.HTTP_204_NO_CONTENT)
def reset_device(
    deputy_id: int,
    request: Request,
    admin: models.StaffUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if not db.get(models.Deputy, deputy_id):
        raise HTTPException(404, "غير موجود")
    db.execute(update(models.Device).where(models.Device.deputy_id == deputy_id).values(active=False))
    audit(db, request, "staff", admin.id, "device_reset", f"deputy:{deputy_id}")
    db.commit()


# ---------- الإعدادات ----------
@router.put("/settings", response_model=schemas.PublicInfoOut)
def update_settings(
    body: schemas.SettingsIn,
    request: Request,
    admin: models.StaffUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    services.set_setting(db, "wilaya_name", body.wilaya_name)
    audit(db, request, "staff", admin.id, "settings_updated", "wilaya_name")
    db.commit()
    return schemas.PublicInfoOut(wilaya_name=body.wilaya_name)


# ---------- سجل العمليات ----------
@router.get("/audit")
def audit_log(limit: int = Query(100, le=500), db: Session = Depends(get_db)):
    rows = db.scalars(select(models.AuditLog).order_by(models.AuditLog.id.desc()).limit(limit)).all()
    return [
        {
            "id": r.id,
            "at": r.created_at,
            "actor_type": r.actor_type,
            "actor_id": r.actor_id,
            "action": r.action,
            "target": r.target,
            "ip": r.ip,
        }
        for r in rows
    ]
