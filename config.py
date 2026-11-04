import os
from datetime import timedelta
from pathlib import Path


class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key_belle_vitesse_2026")

    # Base URL & Host
    APP_BASE_URL = os.getenv("APP_BASE_URL")
    BASE_URL = os.getenv("BASE_URL") or APP_BASE_URL or "http://localhost:5000"
    SERVER_NAME = os.getenv("SERVER_NAME", None)
    PREFERRED_URL_SCHEME = "https"
    PERMANENT_SESSION_LIFETIME = timedelta(days=90)
    SESSION_COOKIE_NAME = "session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_KEY_PREFIX = "bv_session:"
    SESSION_USE_SIGNER = True
    SESSION_PERMANENT = True
    RATELIMIT_SWALLOW_ERRORS = True
    # 10 MB (permet les photos haute résolution et documents volumineux)
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024

    # Security & Tokens
    HASH_SECRET_KEY = os.getenv("HASH_SECRET_KEY") or SECRET_KEY or "dev_secret_key"
    PDF_ACCESS_TOKEN_TTL_MINUTES = int(os.getenv("PDF_ACCESS_TOKEN_TTL_MINUTES", "120"))
    ADMIN_CACHE_TOKEN = os.getenv("ADMIN_CACHE_TOKEN", "secret-token")
    CHECK_API_TOKEN = os.getenv("CHECK_API_TOKEN", "")

    # Airtable
    AIRTABLE_SECRET_TOKEN = os.getenv("AIRTABLE_SECRET_TOKEN", "")
    AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "")

    # kDrive Infomaniak
    KDRIVE_API_TOKEN = os.getenv("KDRIVE_API_TOKEN", "")
    KDRIVE_DRIVE_ID = os.getenv("KDRIVE_DRIVE_ID", "")
    KDRIVE_ROOT_FOLDER_ID = os.getenv("KDRIVE_ROOT_FOLDER_ID", "")
    KDRIVE_SQL_BACKUP_FOLDER_ID = os.getenv("KDRIVE_SQL_BACKUP_FOLDER_ID", "")
    KDRIVE_TIMEOUT = int(os.getenv("KDRIVE_TIMEOUT", "30"))
    KDRIVE_MAX_RETRIES = int(os.getenv("KDRIVE_MAX_RETRIES", "3"))

    # Mail Settings
    MAIL_SERVER = os.getenv("MAIL_SERVER", "mail.infomaniak.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() in ("true", "1", "yes")
    MAIL_NOREPLY_USERNAME = os.getenv("MAIL_NOREPLY_USERNAME", "noreply@bellevitesse.com")
    MAIL_NOREPLY_PASSWORD = os.getenv("MAIL_NOREPLY_PASSWORD", "")
    MAIL_CONTACT_USERNAME = os.getenv("MAIL_CONTACT_USERNAME", "contact@bellevitesse.com")
    MAIL_CONTACT_PASSWORD = os.getenv("MAIL_CONTACT_PASSWORD", "")
    MAIL_ADMIN_USERNAME = os.getenv("MAIL_ADMIN_USERNAME", "admin@bellevitesse.com")
    MAIL_ADMIN_PASSWORD = os.getenv("MAIL_ADMIN_PASSWORD", "")

    # Backups & Logs
    BACKUP_RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))
    SQL_LOGGER_ACTIVATED = os.getenv("SQL_LOGGER_ACTIVATED", "false").lower() in ("true", "1", "yes")
    SQL_LOGGER_THRESHOLD_MS = float(os.getenv("SQL_LOGGER_THRESHOLD_MS", "50.0"))

    # Static & App Mode
    STATIC_VERSION = os.getenv("STATIC_VERSION", "2.3")
    LAUNCH_MODE = os.getenv("LAUNCH_MODE", "false").lower() in ("true", "1", "yes")

    # Cache settings
    CACHE_KEY_PREFIX = "bv_cache_"
    CACHE_DEFAULT_TIMEOUT = 86400

    # Database settings
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_POOL_PRE_PING = True
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 10,
        "pool_recycle": 60,
        "pool_pre_ping": True,
        "connect_args": {
            "connect_timeout": 5,
            "read_timeout": 30,
            "write_timeout": 30,
        },
    }

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True
    PREFERRED_URL_SCHEME = "http"
    CACHE_TYPE = "SimpleCache"
    SESSION_TYPE = os.getenv("SESSION_TYPE", None)
    REDIS_DB_SESSION = int(os.getenv("REDIS_DB_SESSION", 2))
    RATELIMIT_STORAGE_URI = "memory://"
    SEND_FILE_MAX_AGE_DEFAULT = timedelta(seconds=0)

    # Path settings
    BASE_DIR = Path(__file__).parent
    OUTPUT_FOLDER = BASE_DIR / "output"
    BACKUPS_FOLDER = BASE_DIR / "backups"
    LOGS_FOLDER = BASE_DIR / "logs"

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "SQLALCHEMY_DATABASE_URI",
        f"mysql+mysqldb://{os.getenv('MYSQL_USER', 'root')}:{os.getenv('MYSQL_PASSWORD', '')}@{os.getenv('MYSQL_HOST', '127.0.0.1')}:3306/{os.getenv('MYSQL_DATABASE', 'bellevitesse')}"
    )


class ProductionConfig(Config):
    DEBUG = False
    PREFERRED_URL_SCHEME = "https"
    CACHE_TYPE = "RedisCache"
    SESSION_COOKIE_SECURE = True
    SEND_FILE_MAX_AGE_DEFAULT = timedelta(days=365)

    REDIS_HOST = os.getenv("REDIS_HOST", "bv_redis")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB_FLASK_CACHING", 0))
    REDIS_DB_SESSION = int(os.getenv("REDIS_DB_SESSION", 2))
    REDIS_URL = os.getenv(
        "REDIS_URL", f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")

    SESSION_TYPE = os.getenv("SESSION_TYPE", "redis")
    SESSION_REDIS_URL = os.getenv(
        "SESSION_REDIS_URL", f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_SESSION}"
    )

    CACHE_REDIS_URL = REDIS_URL
    CACHE_OPTIONS = {
        "socket_timeout": 3.0,
        "socket_connect_timeout": 3.0,
        "socket_keepalive": True,
        "health_check_interval": 30,
    }

    RATELIMIT_STORAGE_URI = REDIS_URL
    RATELIMIT_STORAGE_OPTIONS = {
        "socket_timeout": 3.0,
        "socket_connect_timeout": 3.0,
        "socket_keepalive": True,
        "health_check_interval": 30,
    }

    # Path settings (Docker paths)
    OUTPUT_FOLDER = Path("/app/output")
    BACKUPS_FOLDER = Path("/app/backups")
    LOGS_FOLDER = Path("/app/logs")

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "SQLALCHEMY_DATABASE_URI",
        f"mysql+mysqldb://{os.getenv('MYSQL_USER', 'Maxcongi')}:{os.getenv('MYSQL_PASSWORD', '')}@{os.getenv('MYSQL_HOST', 'bv_mysql')}:3306/{os.getenv('MYSQL_DATABASE', 'BelleVitesse')}"
    )


class TestingConfig(DevelopmentConfig):
    TESTING = True
    SESSION_TYPE = None
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig
}
