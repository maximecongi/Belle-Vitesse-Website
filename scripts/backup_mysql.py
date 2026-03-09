import os
import subprocess
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_DB = os.getenv("MYSQL_DATABASE")

if not all([MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST, MYSQL_DB]):
    print("❌ Missing MySQL environment variables.")
    exit(1)

# Setup backup directory
TIMESTAMP = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
BACKUP_DIR = Path(__file__).parent.parent / "private/backups/sql"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_FILE = BACKUP_DIR / f"dump_{TIMESTAMP}.sql"

# Construct command
# Note: This assumes mysqldump is in the PATH
cmd = [
    "mysqldump",
    f"-h{MYSQL_HOST}",
    f"-u{MYSQL_USER}",
    f"-p{MYSQL_PASSWORD}",
    "--ssl-mode=DISABLED",
    MYSQL_DB
]

print(f"📦 Starting MySQL backup to {BACKUP_FILE}...")

try:
    with open(BACKUP_FILE, 'w') as f:
        subprocess.check_call(cmd, stdout=f)
    print("✅ Backup successful!")
except subprocess.CalledProcessError as e:
    print(f"❌ Backup failed: {e}")
    if BACKUP_FILE.exists():
        BACKUP_FILE.unlink()
    exit(1)
except Exception as e:
    print(f"❌ An error occurred: {e}")
    exit(1)
