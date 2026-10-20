"""إشعارات FCM.

لا يحمل الإشعار أي محتوى حساس: نص عام فقط، ثم يجلب التطبيق المحتوى
من الخادم بعد المصادقة.
"""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .config import get_settings

log = logging.getLogger("apw.push")

GENERIC_TITLE = "المجلس الشعبي الولائي"
GENERIC_BODY = "لديك تحديث جديد"

_app = None


def _firebase():
    global _app
    if _app is None:
        import firebase_admin
        from firebase_admin import credentials

        _app = firebase_admin.initialize_app(credentials.Certificate(get_settings().fcm_credentials))
    return _app


def tokens_for(db: Session, deputy_ids: list[int]) -> list[str]:
    if not deputy_ids:
        return []
    rows = db.scalars(
        select(models.Device.fcm_token).where(
            models.Device.deputy_id.in_(deputy_ids),
            models.Device.active.is_(True),
            models.Device.fcm_token.is_not(None),
        )
    ).all()
    return [t for t in rows if t]


def send_generic(tokens: list[str]) -> None:
    if not tokens:
        return
    if not get_settings().fcm_credentials:
        log.info("FCM معطّل (لا ملف اعتماد)؛ تخطّي إرسال %d إشعار", len(tokens))
        return
    try:
        from firebase_admin import messaging

        app = _firebase()
        for i in range(0, len(tokens), 500):
            batch = tokens[i : i + 500]
            msgs = [
                messaging.Message(
                    token=t,
                    notification=messaging.Notification(title=GENERIC_TITLE, body=GENERIC_BODY),
                    data={"type": "sync"},
                    android=messaging.AndroidConfig(priority="high"),
                )
                for t in batch
            ]
            messaging.send_each(msgs, app=app)
    except Exception:
        log.exception("فشل إرسال إشعارات FCM")
