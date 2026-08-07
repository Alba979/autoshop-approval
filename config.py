"""
Application configuration.

Reads from environment variables (see .env.example). Keeping configuration
in one place makes it obvious what has to change between a developer's
laptop, a staging box, and the shop's production server.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'shop.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:5000")
    APPROVAL_LINK_TTL_HOURS = int(os.environ.get("APPROVAL_LINK_TTL_HOURS", 72))
    WAITING_ON_CUSTOMER_TIMEOUT_HOURS = int(
        os.environ.get("WAITING_ON_CUSTOMER_TIMEOUT_HOURS", 24)
    )

    SMS_PROVIDER = os.environ.get("SMS_PROVIDER", "console")
    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "")

    PHOTO_STORAGE_BACKEND = os.environ.get("PHOTO_STORAGE_BACKEND", "local")
    UPLOAD_FOLDER = str(BASE_DIR / "instance" / "uploads" / "diagnostic_photos")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB per upload request
    ALLOWED_PHOTO_EXTENSIONS = {"png", "jpg", "jpeg", "heic", "webp"}
    S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "")
    AWS_REGION = os.environ.get("AWS_REGION", "")

    SHOP_NAME = os.environ.get("SHOP_NAME", "Ridgeline Auto Repair")
    SHOP_PHONE = os.environ.get("SHOP_PHONE", "+15555550123")
    DEFAULT_CUSTOMER_SPENDING_CAP = float(
        os.environ.get("DEFAULT_CUSTOMER_SPENDING_CAP", 500.00)
    )

    SCHEDULER_ENABLED = _bool(os.environ.get("SCHEDULER_ENABLED"), default=True)


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SCHEDULER_ENABLED = False
    SMS_PROVIDER = "console"


class ProductionConfig(Config):
    DEBUG = False


CONFIG_BY_NAME = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
