import os

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, push, schemas, services
from ..config import get_settings
from ..db import get_db
from ..deps import active_mandate, audit, current_staff
from ..models import QStatus, TargetType
from ..security import delete_file, save_encrypted, sniff_mime
from .admin import deputy_out

router = APIRouter(prefix="/staff", tags=["staff"])


# ---------- قراءة النواب واللجان ----------
@router.get("/committees", response_model=list[schemas.CommitteeOut])
def committees(user=Depends(current_staff), db: Session = Depends(get_db)):
    m = active_mandate(db)
    return db.scalars(select(models.Committee).where(models.Committee.mandate_id == m.id)).all()


@router.get("/deputies", response_model=list[schemas.DeputyStaffOut])
def deputies(user=Depends(current_staff), db: Session = Depends(get_db)):
    m = active_mandate(db)
    rows = db.scalars(
        select(models.Deputy).where(models.Deputy.mandate_id == m.id).order_by(models.Deputy.full_name)
    ).all()
    return [deputy_out(d) for d in rows]


@router.get("/deputies/{deputy_id}/photo")
def deputy_photo(deputy_id: int, user=Depends(current_staff), db: Session = Depends(get_db)):
    d = db.get(models.Deputy, deputy_id)
    if not d:
        raise HTTPException(404, "غير موجود")
    return services.photo_response(d)


# ---------- الإشعارات ----------
def _resolve_recipients(db: Session, body: schemas.NotificationCreate) -> list[int]:
    m = active_mandate(db)
    base = select(models.Deputy.id).where(models.Deputy.mandate_id == m.id, models.Deputy.active.is_(True))
    if body.target_type == TargetType.all:
        return list(db.scalars(base).all())
    if body.target_type == TargetType.committees:
        valid = db.scalars(
            select(models.Committee.id).where(
                models.Committee.id.in_(body.committee_ids), models.Committee.mandate_id == m.id
            )
        ).all()
        if len(valid) != len(set(body.committee_ids)):
            raise HTTPException(400, "لجنة غير موجودة في الدورة الحالية")
        q = base.join(models.deputy_committee, models.deputy_committee.c.deputy_id == models.Deputy.id).where(
            models.deputy_committee.c.committee_id.in_(body.committee_ids)
        )
        return list(dict.fromkeys(db.scalars(q).all()))
    ids = list(db.scalars(base.where(models.Deputy.id.in_(body.deputy_ids))).all())
    if len(ids) != len(set(body.deputy_ids)):
        raise HTTPException(400, "نائب غير موجود أو معطّل")
    return ids


@router.post("/notifications", response_model=schemas.NotificationStaffOut, status_code=201)
def send_notification(
    body: schemas.NotificationCreate,
    request: Request,
    bg: BackgroundTasks,
    user: models.StaffUser = Depends(current_staff),
    db: Session = Depends(get_db),
):
    recipients = _resolve_recipients(db, body)
    if not recipients:
        raise HTTPException(400, "لا يوجد مستلمون لهذا الاستهداف")
    n = models.Notification(
        kind=body.kind,
        title=body.title,
        body=body.body,
        meeting_at=body.meeting_at,
        target_type=body.target_type,
        created_by=user.id,
        recipients=[models.NotificationRecipient(deputy_id=i) for i in recipients],
    )
    db.add(n)
    db.flush()
    audit(db, request, "staff", user.id, "notification_sent", f"notification:{n.id}")
    tokens = push.tokens_for(db, recipients)
    db.commit()
    bg.add_task(push.send_generic, tokens)
    return _notif_staff_out(n)


def _notif_staff_out(n: models.Notification) -> schemas.NotificationStaffOut:
    return schemas.NotificationStaffOut(
        id=n.id,
        kind=n.kind,
        title=n.title,
        body=n.body,
        meeting_at=n.meeting_at,
        target_type=n.target_type,
        created_at=n.created_at,
        recipients=len(n.recipients),
        read=sum(1 for r in n.recipients if r.read_at),
    )


@router.get("/notifications", response_model=list[schemas.NotificationStaffOut])
def list_notifications(
    limit: int = Query(50, le=200), user=Depends(current_staff), db: Session = Depends(get_db)
):
    rows = db.scalars(select(models.Notification).order_by(models.Notification.id.desc()).limit(limit)).all()
    return [_notif_staff_out(n) for n in rows]


@router.get("/notifications/{notif_id}/receipts", response_model=list[schemas.ReceiptOut])
def receipts(notif_id: int, user=Depends(current_staff), db: Session = Depends(get_db)):
    n = db.get(models.Notification, notif_id)
    if not n:
        raise HTTPException(404, "غير موجود")
    return [
        schemas.ReceiptOut(deputy_id=r.deputy_id, full_name=r.deputy.full_name, read_at=r.read_at)
        for r in n.recipients
    ]


# ---------- الأسئلة الكتابية ----------
def _get_question(db: Session, qid: int) -> models.Question:
    q = db.get(models.Question, qid)
    if not q:
        raise HTTPException(404, "السؤال غير موجود")
    return q


def _notify_deputy(db: Session, bg: BackgroundTasks, deputy_id: int) -> None:
    bg.add_task(push.send_generic, push.tokens_for(db, [deputy_id]))


@router.get("/questions", response_model=list[schemas.QuestionListOut])
def list_questions(
    status: QStatus | None = None,
    deputy_id: int | None = None,
    limit: int = Query(100, le=500),
    user=Depends(current_staff),
    db: Session = Depends(get_db),
):
    q = select(models.Question).order_by(models.Question.updated_at.desc()).limit(limit)
    if status:
        q = q.where(models.Question.status == status)
    if deputy_id:
        q = q.where(models.Question.deputy_id == deputy_id)
    return [services.question_list_out(x, staff_view=True) for x in db.scalars(q).all()]


@router.get("/questions/{qid}", response_model=schemas.QuestionDetailOut)
def get_question(qid: int, user=Depends(current_staff), db: Session = Depends(get_db)):
    return services.question_detail_out(_get_question(db, qid), staff_view=True)


def _act(action: str, qid: int, request, bg, user, db, note: str | None = None):
    q = _get_question(db, qid)
    services.apply_transition(db, q, action, "staff", user.id, note)
    audit(db, request, "staff", user.id, f"question_{action}", f"question:{q.id}")
    db.flush()
    _notify_deputy(db, bg, q.deputy_id)
    db.commit()
    return services.question_detail_out(q, staff_view=True)


@router.post("/questions/{qid}/start-review", response_model=schemas.QuestionDetailOut)
def start_review(
    qid: int, request: Request, bg: BackgroundTasks, user=Depends(current_staff), db: Session = Depends(get_db)
):
    return _act("start_review", qid, request, bg, user, db)


@router.post("/questions/{qid}/return", response_model=schemas.QuestionDetailOut)
def return_question(
    qid: int,
    body: schemas.ReturnIn,
    request: Request,
    bg: BackgroundTasks,
    user=Depends(current_staff),
    db: Session = Depends(get_db),
):
    """إعادة السؤال للنائب ليعدّله (التعديل يكون من النائب نفسه)."""
    return _act("return", qid, request, bg, user, db, note=body.note)


@router.post("/questions/{qid}/confirm", response_model=schemas.QuestionDetailOut)
def confirm_question(
    qid: int, request: Request, bg: BackgroundTasks, user=Depends(current_staff), db: Session = Depends(get_db)
):
    return _act("confirm", qid, request, bg, user, db)


@router.post("/questions/{qid}/refer", response_model=schemas.QuestionDetailOut)
def refer_question(
    qid: int, request: Request, bg: BackgroundTasks, user=Depends(current_staff), db: Session = Depends(get_db)
):
    """إحالة السؤال المؤكَّد إلى الجهاز التنفيذي (الوالي)."""
    return _act("refer", qid, request, bg, user, db)


@router.post("/questions/{qid}/reply", response_model=schemas.QuestionDetailOut)
async def upload_reply(
    qid: int,
    request: Request,
    bg: BackgroundTasks,
    file: UploadFile = File(...),
    user=Depends(current_staff),
    db: Session = Depends(get_db),
):
    """رفع رد الجهاز التنفيذي الممسوح ضوئياً (PDF أو صورة)."""
    q = _get_question(db, qid)
    s = get_settings()
    limit = s.max_scan_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"حجم الملف يتجاوز {s.max_scan_mb} ميغابايت")
    mime = sniff_mime(data)
    if mime is None:
        raise HTTPException(415, "الملف يجب أن يكون PDF أو صورة JPEG/PNG")
    services.apply_transition(db, q, "reply", "staff", user.id)  # يتحقق من الحالة قبل الكتابة
    old = q.reply_path
    q.reply_path = save_encrypted(data, "replies")
    q.reply_mime = mime
    q.reply_filename = os.path.basename(file.filename or "")[:128] or None
    audit(db, request, "staff", user.id, "question_reply", f"question:{q.id}")
    db.flush()
    _notify_deputy(db, bg, q.deputy_id)
    db.commit()
    delete_file(old)
    return services.question_detail_out(q, staff_view=True)


@router.get("/questions/{qid}/reply")
def download_reply(qid: int, user=Depends(current_staff), db: Session = Depends(get_db)) -> Response:
    q = _get_question(db, qid)
    if not q.reply_path:
        raise HTTPException(404, "لا يوجد رد")
    return services.file_response(q.reply_path, q.reply_mime, f"reply-{q.id}.{services.reply_ext(q.reply_mime)}")
