import os
import subprocess
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sshtunnel import SSHTunnelForwarder

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_DB = os.getenv("MYSQL_DATABASE")

SSH_HOST = os.getenv("SSH_HOST")
SSH_USER = os.getenv("SSH_USER")
SSH_PASSWORD = os.getenv("SSH_PASSWORD")

# Add common Homebrew paths to PATH for mysqldump
os.environ["PATH"] += os.pathsep + "/opt/homebrew/bin" + os.pathsep + \
    "/usr/local/bin" + os.pathsep + "/opt/homebrew/Cellar/mysql-client/9.6.0/bin"

if not all([MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB]):
    print("❌ Missing MySQL environment variables.")
    exit(1)

# Setup backup directory
TIMESTAMP = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
BACKUP_DIR = Path(__file__).parent.parent / "backups" / "sql"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_FILE = BACKUP_DIR / f"dump_{TIMESTAMP}.sql"


def run_backup(host, port):
    cmd = [
        "mysqldump",
        f"-h{host}",
        f"-P{port}",
        f"-u{MYSQL_USER}",
        f"-p{MYSQL_PASSWORD}",
        "--ssl-mode=DISABLED",
        MYSQL_DB
    ]
    print(f"📦 Starting MySQL backup to {BACKUP_FILE} via port {port}...")
    try:
        with open(BACKUP_FILE, 'w') as f:
            subprocess.check_call(cmd, stdout=f)
        print("✅ Backup successful!")
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        if BACKUP_FILE.exists():
            BACKUP_FILE.unlink()
        exit(1)


if os.getenv("FLASK_ENV", "production").lower() != "production":
    print(f"🔗 Establishing SSH Tunnel to {SSH_HOST}...")
    try:
        with SSHTunnelForwarder(
            (SSH_HOST, 22),
            ssh_username=SSH_USER,
            ssh_password=SSH_PASSWORD,
            remote_bind_address=(MYSQL_HOST, 3306)
        ) as tunnel:
            run_backup("127.0.0.1", tunnel.local_bind_port)
    except Exception as e:
        print(f"❌ SSH Tunnel failed: {e}")
        exit(1)
else:
    run_backup(MYSQL_HOST, 3306)
