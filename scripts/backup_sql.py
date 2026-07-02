import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Setup path for local imports
_root = Path(__file__).parent.parent
sys.path.append(str(_root))

from utils.ssh_helper import get_ssh_tunnel

# Load environment variables
load_dotenv(_root / '.env')

MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_DB = os.getenv("MYSQL_DATABASE")

# Add common Homebrew paths to PATH for mysqldump
os.environ["PATH"] += os.pathsep + "/opt/homebrew/bin" + os.pathsep + \
    "/usr/local/bin" + os.pathsep + "/opt/homebrew/Cellar/mysql-client/9.6.0/bin"

if not all([MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB]):
    print("❌ Missing MySQL environment variables.")
    exit(1)

# Setup backup directory
TIMESTAMP = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
BACKUP_DIR = _root / "backups" / "sql"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_FILE = BACKUP_DIR / f"dump_{TIMESTAMP}.sql"


def run_backup(host, port):
    cmd = [
        "mysqldump",
        f"-h{host}",
        f"-P{port}",
        f"-u{MYSQL_USER}",
        f"-p{MYSQL_PASSWORD}",
        "--skip-ssl" if os.getenv(
            "FLASK_ENV") == "production" else "--ssl-mode=DISABLED",
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


from utils.cron_helper import monitor_cron_job


def main():
    if os.getenv("FLASK_ENV", "production").lower() != "production":
        print("🔗 Ensuring SSH Tunnel via centralized helper...")
        tunnel, local_port = get_ssh_tunnel()
        if tunnel:
            run_backup("127.0.0.1", local_port)
        else:
            print("⚠️ SSH Tunnel not available, attempting direct connection...")
            run_backup(MYSQL_HOST, 3306)
    else:
        run_backup(MYSQL_HOST, 3306)


if __name__ == "__main__":
    with monitor_cron_job("backup_sql"):
        main()
