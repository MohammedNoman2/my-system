import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    APP_NAME: str = "ARP (Advanced Reservation Platform)"
    API_V1_STR: str = "/api"
    SECRET_KEY: str = "arp-secret-key-production-super-secure-change-in-env-2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CSRF_SECRET_KEY: str = "csrf-secret-key-arp-double-submit-2026"
    PASSWORD_RESET_SECRET: str = "password-reset-itsdangerous-secret-2026"
    PASSWORD_RESET_SALT: str = "password-reset-salt-2026"
    PASSWORD_RESET_TOKEN_EXPIRE_SECONDS: int = 3600  # 1 hour

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{(BASE_DIR / 'arp.db').as_posix()}"
    )

    # Redis & Celery
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

    # SMTP (aiosmtplib)
    SMTP_HOST: Optional[str] = os.getenv("SMTP_HOST", None)
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER: Optional[str] = os.getenv("SMTP_USER", None)
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD", None)
    SMTP_FROM: str = os.getenv("SMTP_FROM", "arp-noreply@example.com")
    SMTP_TLS: bool = True

    # Frontend URL (for password reset links)
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # Uploads
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")

    # Lockout configuration
    MAX_FAILED_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


from datetime import date, datetime, time, timezone, timedelta

OFFICE_TZ = timezone(timedelta(hours=3))  # توقيت صنعاء الرسمي (UTC+3)


def office_now() -> datetime:
    """يرجع الوقت الحالي بتوقيت المكتب (UTC+3)."""
    return datetime.now(OFFICE_TZ)


def office_today() -> date:
    """يرجع تاريخ اليوم التجاري الحالي بتوقيت المكتب (UTC+3)."""
    return datetime.now(OFFICE_TZ).date()


def to_office_time(dt: Optional[datetime]) -> Optional[datetime]:
    """يحول أي كائن datetime مخزن بـ UTC إلى توقيت المكتب (UTC+3) للعرض والطباعة."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(OFFICE_TZ)


def format_office_dt(dt: Optional[datetime], fmt: str = "%Y-%m-%d %H:%M") -> str:
    """ينسق التاريخ والوقت بتوقيت المكتب (UTC+3)."""
    odt = to_office_time(dt)
    return odt.strftime(fmt) if odt else "--"


def office_date_range_utc(
    start_d: Optional[date], end_d: Optional[date]
) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    يحول نطاق التاريخ المحلي للمكتب (UTC+3) إلى حدود UTC معرفة المنطقة الزمنية (timezone.utc)
    لمطابقة الأعمدة المخزنة بصيغة UTC في SQLite وPostgreSQL (timestamptz) بدقة تامة.
    مثال: يوم 2026-11-02 بتوقيت صنعاء يمتد من 2026-11-01 21:00:00+00:00 إلى 2026-11-02 20:59:59.999999+00:00.
    """
    start_utc = None
    end_utc = None
    if start_d:
        start_utc = datetime.combine(start_d, time.min, tzinfo=OFFICE_TZ).astimezone(
            timezone.utc
        )
    if end_d:
        end_utc = datetime.combine(end_d, time.max, tzinfo=OFFICE_TZ).astimezone(
            timezone.utc
        )
    return start_utc, end_utc


settings = Settings()
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
