import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from sshtunnel import SSHTunnelForwarder

env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_DB = os.getenv("MYSQL_DATABASE")

SSH_HOST = os.getenv("SSH_HOST")
SSH_USER = os.getenv("SSH_USER")
SSH_PASSWORD = os.getenv("SSH_PASSWORD")

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

if os.getenv("USE_SSH_TUNNEL", "false").lower() == "true":
    print(f"🔗 Establishing SSH Tunnel to {SSH_HOST}...")
    try:
        with SSHTunnelForwarder(
            (SSH_HOST, 22),
            ssh_username=SSH_USER,
            ssh_password=SSH_PASSWORD,
            remote_bind_address=(MYSQL_HOST, 3306)
        ) as tunnel:
            execute_sql("127.0.0.1", tunnel.local_bind_port)
    except Exception as e:
        print(f"❌ SSH Tunnel failed: {e}")
        exit(1)
else:
    execute_sql(MYSQL_HOST, 3306)
