from fastapi import HTTPException, Response
from sqlalchemy.orm import Session

from . import models, schemas
from .models import QStatus
from .security import read_encrypted, utcnow

S = QStatus

# الإجراء -> (الحالات المسموح الانطلاق منها، الحالة الناتجة)
TRANSITIONS: dict[str, tuple[set[QStatus], QStatus]] = {
    "start_review": ({S.submitted}, S.under_review),
    "return": ({S.submitted, S.under_review}, S.returned),
    "confirm": ({S.submitted, S.under_review}, S.confirmed),
    "refer": ({S.confirmed}, S.referred),
    "reply": ({S.referred}, S.answered),
}


def apply_transition(
    db: Session, q: models.Question, action: str, actor_type: str, actor_id: int, note: str | None = None
) -> None:
    allowed_from, target = TRANSITIONS[action]
    if q.status not in allowed_from:
        raise HTTPException(409, "لا يمكن تنفيذ هذا الإجراء في الحالة الحالية للسؤال")
    q.status = target
    q.updated_at = utcnow()
    q.return_note = note if target == S.returned else None
    db.add(models.QuestionEvent(question=q, status=target, note=note, actor_type=actor_type, actor_id=actor_id))


def question_list_out(q: models.Question, staff_view: bool = False) -> schemas.QuestionListOut:
    return schemas.QuestionListOut(
        id=q.id,
        subject=q.subject,
        status=q.status,
        created_at=q.created_at,
        updated_at=q.updated_at,
        deputy_id=q.deputy_id if staff_view else None,
        deputy_name=q.deputy.full_name if staff_view else None,
    )


def question_detail_out(q: models.Question, staff_view: bool = False) -> schemas.QuestionDetailOut:
    base = question_list_out(q, staff_view).model_dump()
    return schemas.QuestionDetailOut(
        **base,
        text=q.text,
        return_note=q.return_note,
        has_reply=bool(q.reply_path),
        events=[schemas.EventOut(status=e.status, note=e.note, created_at=e.created_at) for e in q.events],
        versions=(
            [schemas.VersionOut(subject=v.subject, text=v.text, created_at=v.created_at) for v in q.versions]
            if staff_view
            else None
        ),
    )


def file_response(rel: str, mime: str, name: str) -> Response:
    try:
        data = read_encrypted(rel)
    except FileNotFoundError:
        raise HTTPException(404, "الملف غير موجود")
    except ValueError:
        raise HTTPException(500, "تعذّر فك تشفير الملف")
    return Response(
        content=data,
        media_type=mime,
        headers={
            "Content-Disposition": f'inline; filename="{name}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


def photo_response(d: models.Deputy) -> Response:
    if not d.photo_path:
        raise HTTPException(404, "لا توجد صورة")
    data = read_encrypted(d.photo_path)
    mime = "image/png" if data.startswith(b"\x89PNG") else "image/jpeg"
    return file_response(d.photo_path, mime, f"deputy-{d.id}.{'png' if mime.endswith('png') else 'jpg'}")


def reply_ext(mime: str | None) -> str:
    return {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg"}.get(mime or "", "bin")


def get_setting(db: Session, key: str) -> str | None:
    row = db.get(models.AppSetting, key)
    return row.value if row else None


def set_setting(db: Session, key: str, value: str | None) -> None:
    row = db.get(models.AppSetting, key)
    if row is None:
        db.add(models.AppSetting(key=key, value=value))
    else:
        row.value = value
