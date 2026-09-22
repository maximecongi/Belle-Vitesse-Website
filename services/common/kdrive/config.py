import os

# Configuration kDrive Infomaniak
KDRIVE_API_BASE = os.getenv("KDRIVE_API_BASE", "https://api.infomaniak.com").rstrip("/")
KDRIVE_API_TOKEN = os.getenv("KDRIVE_API_TOKEN") or os.getenv("N8N_API_TOKEN", "")
KDRIVE_DRIVE_ID = os.getenv("KDRIVE_DRIVE_ID") or os.getenv("N8N_DRIVE_ID", "2312158")
KDRIVE_ROOT_FOLDER_ID = int(os.getenv("KDRIVE_ROOT_FOLDER_ID") or os.getenv("N8N_ROOT_DIR_ID", "48"))

# Racine logique pour affichage et diagnostic
KDRIVE_BASE_PATH = "Common documents/BELLE VITESSE/7_ADMINISTRATION/1_TOURNAGES"

# Paramètres réseau
KDRIVE_TIMEOUT = int(os.getenv("KDRIVE_TIMEOUT", "30"))
KDRIVE_MAX_RETRIES = int(os.getenv("KDRIVE_MAX_RETRIES", "3"))
KDRIVE_UPLOAD_WORKERS = int(os.getenv("KDRIVE_UPLOAD_WORKERS", "4"))
