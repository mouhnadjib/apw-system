"""التشفير والمصادقة.

- كلمات مرور الموظفين: Argon2id.
- رموز الدعوة والتحديث: تُخزَّن كبصمة HMAC-SHA256 فقط.
- نصوص الأسئلة والإشعارات: AES-256-GCM على مستوى الحقل داخل قاعدة البيانات.
- الملفات (صور النواب، الردود الممسوحة): AES-256-GCM على القرص.
"""
import base64
import hashlib
import hmac
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from .config import get_settings

_ph = PasswordHasher()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(dt: datetime) -> datetime:
    """SQLite يُرجع تواريخ بلا منطقة زمنية؛ نعتبرها UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------- كلمات المرور ----------
def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def validate_password_strength(password: str) -> None:
    if len(password) < 12:
        raise ValueError("كلمة المرور يجب ألا تقل عن 12 حرفاً")


def password_version(password_hash: str) -> str:
    """بصمة قصيرة لكلمة المرور الحالية تُضمَّن في رمز الموظف لإبطاله عند تغييرها."""
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


# ---------- المفاتيح ----------
def _load_key(value: str, name: str) -> bytes:
    if not value:
        raise RuntimeError(f"المفتاح {name} غير مضبوط في الإعدادات")
    try:
        raw = base64.b64decode(value, validate=True)
    except Exception as e:
        raise RuntimeError(f"المفتاح {name} ليس base64 صالحاً") from e
    if len(raw) != 32:
        raise RuntimeError(f"المفتاح {name} يجب أن يكون 32 بايت (base64)")
    return raw


def _file_aead() -> AESGCM:
    return AESGCM(_load_key(get_settings().file_key, "APW_FILE_KEY"))


def _field_aead() -> AESGCM:
    return AESGCM(_load_key(get_settings().field_key, "APW_FIELD_KEY"))


def _secret() -> bytes:
    s = get_settings().jwt_secret
    if len(s) < 32:
        raise RuntimeError("APW_JWT_SECRET يجب ألا يقل عن 32 حرفاً")
    return s.encode()


def validate_config() -> None:
    """يفشل مبكراً عند الإقلاع إن كان أي مفتاح غير مضبوط أو معطوباً."""
    s = get_settings()
    _load_key(s.file_key, "APW_FILE_KEY")
    _load_key(s.field_key, "APW_FIELD_KEY")
    _secret()


# ---------- تشفير الحقول ----------
_PREFIX = "v1:"


def encrypt_text(plain: str) -> str:
    nonce = os.urandom(12)
    ct = _field_aead().encrypt(nonce, plain.encode("utf-8"), None)
    return _PREFIX + base64.b64encode(nonce + ct).decode()


def decrypt_text(blob: str) -> str:
    if not blob.startswith(_PREFIX):
        raise ValueError("صيغة حقل مشفّر غير معروفة")
    raw = base64.b64decode(blob[len(_PREFIX):])
    try:
        return _field_aead().decrypt(raw[:12], raw[12:], None).decode("utf-8")
    except InvalidTag as e:
        raise ValueError("فشل فك تشفير الحقل (مفتاح خاطئ أو بيانات تالفة)") from e


class EncryptedText(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else encrypt_text(value)

    def process_result_value(self, value, dialect):
        return None if value is None else decrypt_text(value)


# ---------- تشفير الملفات ----------
MAGIC = {
    "application/pdf": (b"%PDF-",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
}


def sniff_mime(data: bytes) -> str | None:
    for mime, sigs in MAGIC.items():
        if any(data.startswith(s) for s in sigs):
            return mime
    return None


def _storage_root() -> Path:
    root = get_settings().data_dir / "files"
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_encrypted(data: bytes, kind: str) -> str:
    """يحفظ الملف مشفّراً باسم عشوائي ويُرجع المسار النسبي."""
    rel = f"{kind}/{uuid.uuid4().hex}.enc"
    path = _storage_root() / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    nonce = os.urandom(12)
    ct = _file_aead().encrypt(nonce, data, rel.encode())
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(nonce + ct)
    os.replace(tmp, path)
    return rel


def read_encrypted(rel: str) -> bytes:
    if not re.fullmatch(r"[a-z_]+/[0-9a-f]{32}\.enc", rel):
        raise ValueError("مسار ملف غير صالح")
    raw = (_storage_root() / rel).read_bytes()
    try:
        return _file_aead().decrypt(raw[:12], raw[12:], rel.encode())
    except InvalidTag as e:
        raise ValueError("فشل فك تشفير الملف") from e


def delete_file(rel: str | None) -> None:
    if rel and re.fullmatch(r"[a-z_]+/[0-9a-f]{32}\.enc", rel):
        try:
            (_storage_root() / rel).unlink()
        except FileNotFoundError:
            pass


# ---------- الرموز العشوائية ----------
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # بلا حروف ملتبسة


def new_invite_code() -> str:
    raw = "".join(secrets.choice(_ALPHABET) for _ in range(10))
    return f"{raw[:5]}-{raw[5:]}"


def normalize_code(code: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", code.upper())


def token_digest(value: str) -> str:
    return hmac.new(_secret(), value.encode(), hashlib.sha256).hexdigest()


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def normalize_phone(phone: str) -> str:
    """يوحّد الأرقام الجزائرية إلى الصيغة 0XXXXXXXXX."""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("00213"):
        digits = "0" + digits[5:]
    elif digits.startswith("213"):
        digits = "0" + digits[3:]
    return digits


# ---------- JWT ----------
def make_access_token(sub: int, typ: str, minutes: int, **extra) -> str:
    now = utcnow()
    payload = {
        "sub": str(sub),
        "typ": typ,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
        "jti": uuid.uuid4().hex,
        **extra,
    }
    return jwt.encode(payload, _secret(), algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, _secret(), algorithms=["HS256"], options={"require": ["exp", "sub", "typ"]})
