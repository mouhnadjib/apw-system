from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APW_", extra="ignore")

    database_url: str = "sqlite:///./apw.db"
    data_dir: Path = Path("./data")

    # مفاتيح التشفير: base64 لـ 32 بايت لكل منها. يجب تعيينها في الإنتاج.
    # توليد: python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"
    file_key: str = ""
    field_key: str = ""
    jwt_secret: str = ""

    access_minutes_staff: int = 480
    access_minutes_deputy: int = 30
    refresh_days: int = 90
    invite_hours: int = 72

    max_login_failures: int = 5
    lockout_minutes: int = 15
    max_invite_attempts: int = 5

    max_scan_mb: int = 15
    max_photo_mb: int = 3

    fcm_credentials: str = ""  # مسار ملف حساب الخدمة، فارغ = تعطيل الإرسال


@lru_cache
def get_settings() -> Settings:
    return Settings()
