import os
import secrets
from datetime import timedelta
from zoneinfo import ZoneInfo


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


DATABASE_URL = os.getenv("DATABASE_URL") or "sqlite:///attendance.db"
LOCAL_TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Tokyo"))
CSV_EXPORT_MAX_DAYS = max(1, int(os.getenv("CSV_EXPORT_MAX_DAYS", "365")))
WEEKDAY_JA = ["月", "火", "水", "木", "金", "土", "日"]


def build_base_config():
    session_cookie_secure = env_bool("SESSION_COOKIE_SECURE", False)
    remember_cookie_days = max(1, env_int("REMEMBER_COOKIE_DAYS", 14))
    return {
        "SECRET_KEY": os.getenv("SECRET_KEY") or secrets.token_urlsafe(32),
        "SQLALCHEMY_DATABASE_URI": DATABASE_URL,
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        # Dev-only helpers. Keep disabled by default.
        "ALLOW_DEV_LOGIN": env_bool("ALLOW_DEV_LOGIN", False),
        "DEV_SEED_RESET_PASSWORDS": env_bool("DEV_SEED_RESET_PASSWORDS", False),
        "DEV_ADMIN_USERNAME": os.getenv("DEV_ADMIN_USERNAME", "admin"),
        "DEV_ADMIN_PASSWORD": os.getenv("DEV_ADMIN_PASSWORD", "adminpass123"),
        "DEV_ADMIN_EMAIL": os.getenv("DEV_ADMIN_EMAIL", "admin@example.com"),
        "DEV_ADMIN_NAME": os.getenv("DEV_ADMIN_NAME", "Admin User"),
        "DEV_TEST_USERNAME": os.getenv("DEV_TEST_USERNAME", "testuser"),
        "DEV_TEST_PASSWORD": os.getenv("DEV_TEST_PASSWORD", "testpass123"),
        "DEV_TEST_EMAIL": os.getenv("DEV_TEST_EMAIL", "test@example.com"),
        "DEV_TEST_NAME": os.getenv("DEV_TEST_NAME", "Test User"),
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": session_cookie_secure,
        "REMEMBER_COOKIE_DURATION": timedelta(days=remember_cookie_days),
        "REMEMBER_COOKIE_HTTPONLY": True,
        "REMEMBER_COOKIE_SAMESITE": "Lax",
        "REMEMBER_COOKIE_SECURE": env_bool("REMEMBER_COOKIE_SECURE", session_cookie_secure),
        "TRUST_X_FORWARDED_FOR": env_bool("TRUST_X_FORWARDED_FOR", False),
        "WTF_CSRF_ENABLED": True,
    }
