import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .security import EncryptedText, utcnow


class StaffRole(str, enum.Enum):
    admin = "admin"
    operator = "operator"  # مستخدم التسيير (الديوان)


class QStatus(str, enum.Enum):
    submitted = "submitted"      # مُرسل من النائب
    under_review = "under_review"  # قيد المراجعة لدى الديوان
    returned = "returned"        # أُعيد للنائب لتعديله
    confirmed = "confirmed"      # أكّده الديوان
    referred = "referred"        # أُحيل إلى الجهاز التنفيذي (الوالي)
    answered = "answered"        # وصل الرد (ممسوح ضوئياً)


class NotifKind(str, enum.Enum):
    meeting = "meeting"
    targeted = "targeted"
    info = "info"


class TargetType(str, enum.Enum):
    all = "all"
    committees = "committees"
    deputies = "deputies"


deputy_committee = Table(
    "deputy_committee",
    Base.metadata,
    Column("deputy_id", ForeignKey("deputies.id", ondelete="CASCADE"), primary_key=True),
    Column("committee_id", ForeignKey("committees.id", ondelete="CASCADE"), primary_key=True),
)


class StaffUser(Base):
    __tablename__ = "staff_users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[StaffRole] = mapped_column(Enum(StaffRole))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Mandate(Base):
    """الدورة الانتخابية (5 سنوات)."""

    __tablename__ = "mandates"
    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(64))
    start_year: Mapped[int] = mapped_column(Integer)
    end_year: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=False)

    committees: Mapped[list["Committee"]] = relationship(back_populates="mandate")
    deputies: Mapped[list["Deputy"]] = relationship(back_populates="mandate")


class Committee(Base):
    __tablename__ = "committees"
    id: Mapped[int] = mapped_column(primary_key=True)
    mandate_id: Mapped[int] = mapped_column(ForeignKey("mandates.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(128))
    __table_args__ = (UniqueConstraint("mandate_id", "name"),)

    mandate: Mapped[Mandate] = relationship(back_populates="committees")
    deputies: Mapped[list["Deputy"]] = relationship(secondary=deputy_committee, back_populates="committees")


class Deputy(Base):
    __tablename__ = "deputies"
    id: Mapped[int] = mapped_column(primary_key=True)
    mandate_id: Mapped[int] = mapped_column(ForeignKey("mandates.id", ondelete="CASCADE"))
    full_name: Mapped[str] = mapped_column(String(128))
    title: Mapped[str | None] = mapped_column(String(64))  # رئيس المجلس، نائب الرئيس، رئيس لجنة...
    phone: Mapped[str] = mapped_column(String(20), index=True)
    photo_path: Mapped[str | None] = mapped_column(String(128))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("mandate_id", "phone"),)

    mandate: Mapped[Mandate] = relationship(back_populates="deputies")
    committees: Mapped[list[Committee]] = relationship(secondary=deputy_committee, back_populates="deputies")
    devices: Mapped[list["Device"]] = relationship(back_populates="deputy")


class Invitation(Base):
    __tablename__ = "invitations"
    id: Mapped[int] = mapped_column(primary_key=True)
    deputy_id: Mapped[int] = mapped_column(ForeignKey("deputies.id", ondelete="CASCADE"), index=True)
    code_digest: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Device(Base):
    """جهاز النائب المربوط. جهاز نشط واحد لكل نائب."""

    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    deputy_id: Mapped[int] = mapped_column(ForeignKey("deputies.id", ondelete="CASCADE"), index=True)
    device_uid: Mapped[str] = mapped_column(String(128))
    platform: Mapped[str] = mapped_column(String(16))
    fcm_token: Mapped[str | None] = mapped_column(String(512))
    refresh_digest: Mapped[str] = mapped_column(String(64), index=True)
    refresh_expires: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # الرمز السابق يبقى صالحاً دقائق قليلة: إن ضاع رد التجديد على شبكة الهاتف لا تضيع الجلسة
    prev_refresh_digest: Mapped[str | None] = mapped_column(String(64), index=True)
    prev_refresh_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    bound_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    deputy: Mapped[Deputy] = relationship(back_populates="devices")


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[NotifKind] = mapped_column(Enum(NotifKind))
    title: Mapped[str] = mapped_column(EncryptedText)
    body: Mapped[str] = mapped_column(EncryptedText)
    meeting_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    target_type: Mapped[TargetType] = mapped_column(Enum(TargetType))
    created_by: Mapped[int] = mapped_column(ForeignKey("staff_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    recipients: Mapped[list["NotificationRecipient"]] = relationship(
        back_populates="notification", cascade="all, delete-orphan"
    )


class NotificationRecipient(Base):
    __tablename__ = "notification_recipients"
    notification_id: Mapped[int] = mapped_column(
        ForeignKey("notifications.id", ondelete="CASCADE"), primary_key=True
    )
    deputy_id: Mapped[int] = mapped_column(ForeignKey("deputies.id", ondelete="CASCADE"), primary_key=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    notification: Mapped[Notification] = relationship(back_populates="recipients")
    deputy: Mapped[Deputy] = relationship()


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    deputy_id: Mapped[int] = mapped_column(ForeignKey("deputies.id"), index=True)
    subject: Mapped[str] = mapped_column(EncryptedText)
    text: Mapped[str] = mapped_column(EncryptedText)  # النسخة الحالية
    status: Mapped[QStatus] = mapped_column(Enum(QStatus), default=QStatus.submitted, index=True)
    return_note: Mapped[str | None] = mapped_column(EncryptedText)
    reply_path: Mapped[str | None] = mapped_column(String(128))
    reply_mime: Mapped[str | None] = mapped_column(String(32))
    reply_filename: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    deputy: Mapped[Deputy] = relationship()
    versions: Mapped[list["QuestionVersion"]] = relationship(
        back_populates="question", order_by="QuestionVersion.id", cascade="all, delete-orphan"
    )
    events: Mapped[list["QuestionEvent"]] = relationship(
        back_populates="question", order_by="QuestionEvent.id", cascade="all, delete-orphan"
    )


class QuestionVersion(Base):
    """كل صياغة للسؤال تُحفظ (الأصلية ثم تعديلات النائب)."""

    __tablename__ = "question_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    subject: Mapped[str] = mapped_column(EncryptedText)
    text: Mapped[str] = mapped_column(EncryptedText)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    question: Mapped[Question] = relationship(back_populates="versions")


class QuestionEvent(Base):
    __tablename__ = "question_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    status: Mapped[QStatus] = mapped_column(Enum(QStatus))
    note: Mapped[str | None] = mapped_column(EncryptedText)
    actor_type: Mapped[str] = mapped_column(String(16))  # deputy | staff
    actor_id: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    question: Mapped[Question] = relationship(back_populates="events")


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_type: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[int | None] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(64), index=True)
    target: Mapped[str | None] = mapped_column(String(128))
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class AppSetting(Base):
    """إعدادات عامة بسيطة (مثل اسم الولاية الاختياري)."""

    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(String(256))
