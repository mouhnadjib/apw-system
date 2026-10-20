from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas, services
from ..db import get_db
from ..deps import audit, current_deputy, current_device
from ..models import QStatus
from ..security import utcnow

router = APIRouter(prefix="/me", tags=["deputy"])


# ---------- الملف الشخصي والجهاز ----------
@router.get("/profile", response_model=schemas.ProfileOut)
def profile(me: models.Deputy = Depends(current_deputy), db: Session = Depends(get_db)):
    mandate = db.get(models.Mandate, me.mandate_id)
    return schemas.ProfileOut(
        id=me.id,
        full_name=me.full_name,
        title=me.title,
        has_photo=bool(me.photo_path),
        committees=[c.name for c in me.committees],
        mandate_label=mandate.label,
        wilaya_name=services.get_setting(db, "wilaya_name"),
    )


@router.post("/fcm-token", status_code=status.HTTP_204_NO_CONTENT)
def set_fcm_token(
    body: schemas.FcmIn, device: models.Device = Depends(current_device), db: Session = Depends(get_db)
):
    device.fcm_token = body.fcm_token
    db.commit()


# ---------- نواب الدورة ----------
@router.get("/deputies", response_model=list[schemas.DeputyPublicOut])
def directory(me: models.Deputy = Depends(current_deputy), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(models.Deputy)
        .where(models.Deputy.mandate_id == me.mandate_id, models.Deputy.active.is_(True))
        .order_by(models.Deputy.full_name)
    ).all()
    return [
        schemas.DeputyPublicOut(
            id=d.id,
            full_name=d.full_name,
            title=d.title,
            has_photo=bool(d.photo_path),
            committees=[c.name for c in d.committees],
        )
        for d in rows
    ]


@router.get("/deputies/{deputy_id}/photo")
def photo(deputy_id: int, me: models.Deputy = Depends(current_deputy), db: Session = Depends(get_db)):
    d = db.get(models.Deputy, deputy_id)
    if not d or d.mandate_id != me.mandate_id or not d.active:
        raise HTTPException(404, "غير موجود")
    return services.photo_response(d)


# ---------- الإشعارات ----------
def _notif_out(r: models.NotificationRecipient) -> schemas.NotificationDeputyOut:
    n = r.notification
    return schemas.NotificationDeputyOut(
        id=n.id,
        kind=n.kind,
        title=n.title,
        body=n.body,
        meeting_at=n.meeting_at,
        created_at=n.created_at,
        read=r.read_at is not None,
    )


@router.get("/notifications", response_model=list[schemas.NotificationDeputyOut])
def my_notifications(
    limit: int = Query(100, le=300), me: models.Deputy = Depends(current_deputy), db: Session = Depends(get_db)
):
    rows = db.scalars(
        select(models.NotificationRecipient)
        .where(models.NotificationRecipient.deputy_id == me.id)
        .order_by(models.NotificationRecipient.notification_id.desc())
        .limit(limit)
    ).all()
    return [_notif_out(r) for r in rows]


@router.post("/notifications/{notif_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(notif_id: int, me: models.Deputy = Depends(current_deputy), db: Session = Depends(get_db)):
    r = db.get(models.NotificationRecipient, (notif_id, me.id))
    if not r:
        raise HTTPException(404, "غير موجود")
    if r.read_at is None:
        r.read_at = utcnow()
        db.commit()


# ---------- الأسئلة الكتابية ----------
def _mine(db: Session, me: models.Deputy, qid: int) -> models.Question:
    q = db.get(models.Question, qid)
    if not q or q.deputy_id != me.id:  # 404 حتى لا يُكشف وجود أسئلة غيره
        raise HTTPException(404, "السؤال غير موجود")
    return q


@router.post("/questions", response_model=schemas.QuestionDetailOut, status_code=201)
def create_question(
    body: schemas.QuestionIn,
    request: Request,
    me: models.Deputy = Depends(current_deputy),
    db: Session = Depends(get_db),
):
    q = models.Question(deputy_id=me.id, subject=body.subject, text=body.text, status=QStatus.submitted)
    q.versions.append(models.QuestionVersion(subject=body.subject, text=body.text))
    q.events.append(models.QuestionEvent(status=QStatus.submitted, actor_type="deputy", actor_id=me.id))
    db.add(q)
    db.flush()
    audit(db, request, "deputy", me.id, "question_created", f"question:{q.id}")
    db.commit()
    return services.question_detail_out(q)


@router.get("/questions", response_model=list[schemas.QuestionListOut])
def my_questions(me: models.Deputy = Depends(current_deputy), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(models.Question)
        .where(models.Question.deputy_id == me.id)
        .order_by(models.Question.updated_at.desc())
    ).all()
    return [services.question_list_out(q) for q in rows]


@router.get("/questions/{qid}", response_model=schemas.QuestionDetailOut)
def my_question(qid: int, me: models.Deputy = Depends(current_deputy), db: Session = Depends(get_db)):
    return services.question_detail_out(_mine(db, me, qid))


@router.put("/questions/{qid}", response_model=schemas.QuestionDetailOut)
def edit_question(
    qid: int,
    body: schemas.QuestionIn,
    request: Request,
    me: models.Deputy = Depends(current_deputy),
    db: Session = Depends(get_db),
):
    """يعدّل النائب سؤاله بعد أن يعيده الديوان؛ ويُعاد إرساله تلقائياً."""
    q = _mine(db, me, qid)
    if q.status != QStatus.returned:
        raise HTTPException(409, "لا يمكن تعديل السؤال إلا بعد إعادته من الديوان")
    q.subject = body.subject
    q.text = body.text
    q.versions.append(models.QuestionVersion(subject=body.subject, text=body.text))
    q.status = QStatus.submitted
    q.return_note = None
    q.updated_at = utcnow()
    q.events.append(
        models.QuestionEvent(
            status=QStatus.submitted, note="أُعيد إرساله بعد تعديل النائب", actor_type="deputy", actor_id=me.id
        )
    )
    audit(db, request, "deputy", me.id, "question_edited", f"question:{q.id}")
    db.commit()
    return services.question_detail_out(q)


@router.get("/questions/{qid}/reply")
def my_reply(qid: int, me: models.Deputy = Depends(current_deputy), db: Session = Depends(get_db)) -> Response:
    q = _mine(db, me, qid)
    if q.status != QStatus.answered or not q.reply_path:
        raise HTTPException(404, "لا يوجد رد بعد")
    return services.file_response(q.reply_path, q.reply_mime, f"reply-{q.id}.{services.reply_ext(q.reply_mime)}")
