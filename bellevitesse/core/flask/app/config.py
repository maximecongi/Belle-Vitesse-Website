import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "bv_super_secret_key_2026")
    STATIC_FOLDER = os.getenv("STATIC_FOLDER", "static")
    STATIC_URL_PATH = os.getenv("STATIC_URL_PATH", "/static")
    
    # Cache settings
    CACHE_TYPE = "SimpleCache"
    CACHE_DEFAULT_TIMEOUT = 3600
    CACHE_KEY_PREFIX = "myapp_"
    
    # Mail settings
    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    
    # Airtable settings
    AIRTABLE_SECRET_TOKEN = os.getenv("AIRTABLE_SECRET_TOKEN")
    AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
    
    # Admin settings
    ADMIN_CACHE_TOKEN = os.getenv("ADMIN_CACHE_TOKEN")
    
    # Environment
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    TEMPLATES_AUTO_RELOAD = os.getenv("TEMPLATES_AUTO_RELOAD", "true").lower() == "true"
