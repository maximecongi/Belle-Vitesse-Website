import os
from datetime import timedelta
from pathlib import Path


class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv("SECRET_KEY", "bv_super_secret_key_2026")

    # Flask settings
    PREFERRED_URL_SCHEME = "https"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    RATELIMIT_SWALLOW_ERRORS = True

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

    # Arclight settings
    ARCLIGHT_SECRET = os.getenv("ARCLIGHT_SECRET", "ton_token_secret")

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True
    CACHE_TYPE = "SimpleCache"
    RATELIMIT_STORAGE_URI = "memory://"

    # Path settings
    BASE_DIR = Path(__file__).parent
    OUTPUT_FOLDER = BASE_DIR / "output"
    BACKUPS_FOLDER = BASE_DIR / "backups"
    LOGS_FOLDER = BASE_DIR / "logs"
    ARCLIGHT_UPLOAD_DIR = BASE_DIR / "arclight" / "videos"

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "SQLALCHEMY_DATABASE_URI",
        f"mysql+mysqldb://{os.getenv('MYSQL_USER', 'root')}:{os.getenv('MYSQL_PASSWORD', '')}@{os.getenv('MYSQL_HOST', '127.0.0.1')}:3306/{os.getenv('MYSQL_DATABASE', 'bellevitesse')}"
    )


class ProductionConfig(Config):
    DEBUG = False
    CACHE_TYPE = "RedisCache"

    REDIS_HOST = os.getenv("REDIS_HOST", "bv_redis")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB_FLASK_CACHING", 0))
    REDIS_URL = os.getenv(
        "REDIS_URL", f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")

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
    ARCLIGHT_UPLOAD_DIR = Path(
        os.getenv("ARCLIGHT_UPLOAD_DIR", "/srv/bellevitesse/arclight/videos"))

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "SQLALCHEMY_DATABASE_URI",
        f"mysql+mysqldb://{os.getenv('MYSQL_USER', 'Maxcongi')}:{os.getenv('MYSQL_PASSWORD', '')}@{os.getenv('MYSQL_HOST', 'bv_mysql')}:3306/{os.getenv('MYSQL_DATABASE', 'BelleVitesse')}"
    )


class TestingConfig(DevelopmentConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig
}
