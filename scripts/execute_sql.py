import os
import sys
import subprocess
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

# Add common Homebrew paths to PATH for mysql
os.environ["PATH"] += os.pathsep + "/opt/homebrew/bin" + os.pathsep + "/usr/local/bin" + os.pathsep + "/opt/homebrew/Cellar/mysql-client/9.6.0/bin"

# The first argument is the SQL file to execute
SQL_FILE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/migrate_projects.sql"


def execute_sql(host, port):
    cmd = [
        "mysql",
        f"-h{host}",
        f"-P{port}",
        f"-u{MYSQL_USER}",
        f"-p{MYSQL_PASSWORD}",
        MYSQL_DB
    ]
    print(f"🚀 Executing SQL from {SQL_FILE} via port {port}...")
    try:
        with open(SQL_FILE, 'r') as f:
            subprocess.check_call(cmd, stdin=f)
        print("✅ SQL execution successful!")
    except Exception as e:
        print(f"❌ SQL execution failed: {e}")
        exit(1)


if os.getenv("USE_SSH_TUNNEL", "false").lower() == "true" or os.getenv("FLASK_ENV") != "production":
    print("🔗 Ensuring SSH Tunnel via centralized helper...")
    tunnel, local_port = get_ssh_tunnel()
    if tunnel:
        execute_sql("127.0.0.1", local_port)
    else:
        print("⚠️ SSH Tunnel not available, attempting direct connection...")
        execute_sql(MYSQL_HOST, 3306)
else:
    execute_sql(MYSQL_HOST, 3306)
