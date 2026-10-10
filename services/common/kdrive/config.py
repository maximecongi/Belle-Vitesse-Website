import os
from dotenv import load_dotenv

# Assurer le chargement des variables d'environnement locales
load_dotenv()

# Configuration kDrive Infomaniak
KDRIVE_API_BASE = os.getenv("KDRIVE_API_BASE", "https://api.infomaniak.com").rstrip("/")
KDRIVE_API_TOKEN = os.getenv("KDRIVE_API_TOKEN") or os.getenv("N8N_API_TOKEN", "")
KDRIVE_DRIVE_ID = os.getenv("KDRIVE_DRIVE_ID") or os.getenv("N8N_DRIVE_ID", "2312158")
KDRIVE_ROOT_FOLDER_ID = int(os.getenv("KDRIVE_ROOT_FOLDER_ID") or os.getenv("N8N_ROOT_DIR_ID", "48"))
KDRIVE_SQL_BACKUP_FOLDER_ID = int(os.getenv("KDRIVE_SQL_BACKUP_FOLDER_ID", "133270"))

# Racine logique pour affichage et diagnostic
KDRIVE_BASE_PATH = "Common documents/BELLE VITESSE/7_ADMINISTRATION/1_TOURNAGES"
KDRIVE_SQL_BACKUP_PATH = "Common documents/BELLE VITESSE/6_VPS/1_BACKUPS_SQL"

# Paramètres réseau
KDRIVE_TIMEOUT = int(os.getenv("KDRIVE_TIMEOUT", "30"))
KDRIVE_MAX_RETRIES = int(os.getenv("KDRIVE_MAX_RETRIES", "3"))
KDRIVE_UPLOAD_WORKERS = int(os.getenv("KDRIVE_UPLOAD_WORKERS", "4"))
