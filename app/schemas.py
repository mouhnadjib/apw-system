from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import NotifKind, QStatus, StaffRole, TargetType


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- المصادقة ----------
class StaffLogin(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class ActivateIn(BaseModel):
    phone: str = Field(min_length=8, max_length=20)
    code: str = Field(min_length=8, max_length=16)
    device_uid: str = Field(min_length=8, max_length=128)
    platform: str = Field(pattern="^(android|ios)$")
    fcm_token: str | None = Field(default=None, max_length=512)


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=200)
    device_uid: str = Field(min_length=8, max_length=128)
    fcm_token: str | None = Field(default=None, max_length=512)


class LogoutIn(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=200)


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int


# ---------- الإدارة ----------
class StaffCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    full_name: str = Field(min_length=2, max_length=128)
    password: str = Field(min_length=12, max_length=256)
    role: StaffRole


class StaffUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=128)
    password: str | None = Field(default=None, min_length=12, max_length=256)
    active: bool | None = None


class StaffOut(ORM):
    id: int
    username: str
    full_name: str
    role: StaffRole
    active: bool


class MandateCreate(BaseModel):
    label: str = Field(min_length=2, max_length=64)
    start_year: int = Field(ge=2000, le=2100)
    end_year: int = Field(ge=2000, le=2105)
    active: bool = True

    @model_validator(mode="after")
    def five_years(self):
        if self.end_year != self.start_year + 5:
            raise ValueError("مدة الدورة 5 سنوات")
        return self


class MandateOut(ORM):
    id: int
    label: str
    start_year: int
    end_year: int
    active: bool


class CommitteeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=128)


class CommitteeOut(ORM):
    id: int
    mandate_id: int
    name: str


class DeputyCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=128)
    title: str | None = Field(default=None, max_length=64)
    phone: str = Field(min_length=8, max_length=20)
    committee_ids: list[int] = []


class DeputyUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=128)
    title: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, min_length=8, max_length=20)
    committee_ids: list[int] | None = None
    active: bool | None = None


class DeputyStaffOut(ORM):
    id: int
    mandate_id: int
    full_name: str
    title: str | None
    phone: str
    active: bool
    has_photo: bool = False
    committees: list[CommitteeOut] = []


class DeputyPublicOut(BaseModel):
    id: int
    full_name: str
    title: str | None
    has_photo: bool
    committees: list[str]


class InviteOut(BaseModel):
    code: str
    expires_at: datetime
    note: str = "يُعرض الرمز مرة واحدة فقط؛ سلّمه للنائب مباشرة"


# ---------- الإشعارات ----------
class NotificationCreate(BaseModel):
    kind: NotifKind
    title: str = Field(min_length=2, max_length=200)
    body: str = Field(min_length=1, max_length=5000)
    meeting_at: datetime | None = None
    target_type: TargetType
    committee_ids: list[int] = []
    deputy_ids: list[int] = []

    @model_validator(mode="after")
    def check(self):
        if self.kind == NotifKind.meeting and self.meeting_at is None:
            raise ValueError("دعوة الاجتماع تتطلب تاريخ ووقت الاجتماع")
        if self.target_type == TargetType.committees and not self.committee_ids:
            raise ValueError("حدّد لجنة واحدة على الأقل")
        if self.target_type == TargetType.deputies and not self.deputy_ids:
            raise ValueError("حدّد نائباً واحداً على الأقل")
        return self


class NotificationStaffOut(BaseModel):
    id: int
    kind: NotifKind
    title: str
    body: str
    meeting_at: datetime | None
    target_type: TargetType
    created_at: datetime
    recipients: int
    read: int


class ReceiptOut(BaseModel):
    deputy_id: int
    full_name: str
    read_at: datetime | None


class NotificationDeputyOut(BaseModel):
    id: int
    kind: NotifKind
    title: str
    body: str
    meeting_at: datetime | None
    created_at: datetime
    read: bool


# ---------- الأسئلة ----------
class QuestionIn(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    text: str = Field(min_length=10, max_length=8000)

    @field_validator("subject", "text")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()


class ReturnIn(BaseModel):
    note: str = Field(min_length=3, max_length=2000)


class EventOut(BaseModel):
    status: QStatus
    note: str | None
    created_at: datetime


class VersionOut(BaseModel):
    subject: str
    text: str
    created_at: datetime


class QuestionListOut(BaseModel):
    id: int
    subject: str
    status: QStatus
    created_at: datetime
    updated_at: datetime
    deputy_id: int | None = None
    deputy_name: str | None = None


class QuestionDetailOut(QuestionListOut):
    text: str
    return_note: str | None
    has_reply: bool
    events: list[EventOut]
    versions: list[VersionOut] | None = None


# ---------- الإعدادات والملف الشخصي ----------
class SettingsIn(BaseModel):
    wilaya_name: str | None = Field(default=None, max_length=64)

    @field_validator("wilaya_name")
    @classmethod
    def blank_to_none(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        return v or None


class PublicInfoOut(BaseModel):
    app_name: str = "المجلس الشعبي الولائي"
    wilaya_name: str | None = None


class ProfileOut(BaseModel):
    id: int
    full_name: str
    title: str | None
    has_photo: bool
    committees: list[str]
    mandate_label: str
    wilaya_name: str | None


class FcmIn(BaseModel):
    fcm_token: str | None = Field(default=None, max_length=512)
