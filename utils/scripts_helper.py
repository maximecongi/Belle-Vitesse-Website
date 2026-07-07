import os
import sys
from pathlib import Path

# En développement / scripts autonomes, utiliser PyMySQL comme pilote MySQLdb
# pour contourner l'erreur de chargement de mysql_native_password présente sur MySQL 9+
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    try:
        import MySQLdb
    except ImportError:
        print("\n❌ Erreur : Les packages de connexion MySQL (mysqlclient ou pymysql) ne sont pas installés.")
        print("Il semble que vous n'utilisez pas l'environnement virtuel du projet.")
        print("Veuillez lancer le script avec le Python de l'environnement virtuel :\n")
        if os.path.basename(os.getcwd()) == "scripts":
            print("  ../.venv/bin/python sync_airtable.py\n")
        else:
            print("  .venv/bin/python scripts/sync_airtable.py\n")
        sys.exit(1)

from dotenv import load_dotenv
from flask import Flask

from models import db
from utils.ssh_helper import get_ssh_tunnel

# Setup path for local imports (one level up from utils/)
_root = Path(__file__).parent.parent
sys.path.append(str(_root))


def build_minimal_app(template_folder=None):
    """
    Creates a minimal Flask app with SQLAlchemy and SSH tunnel support.
    Ideal for standalone scripts.
    """
    # Force reload of .env from root
    load_dotenv(_root / '.env')

    mysql_user = os.getenv("MYSQL_USER", "Maxcongi")
    mysql_pass = os.getenv("MYSQL_PASSWORD", "")
    mysql_host = os.getenv("MYSQL_HOST", "")
    mysql_port = 3306
    mysql_db = os.getenv("MYSQL_DATABASE", "BelleVitesse")

    # Handle SSH Tunnel
    tunnel, local_port = get_ssh_tunnel()
    if tunnel:
        mysql_host = "127.0.0.1"
        mysql_port = local_port

    default_uri = (
        f"mysql+mysqldb://{mysql_user}:{mysql_pass}"
        f"@{mysql_host}:{mysql_port}/{mysql_db}"
    )

    app = Flask(__name__, template_folder=template_folder or str(
        _root / "templates"))
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "SQLALCHEMY_DATABASE_URI", default_uri)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 280,
        "pool_pre_ping": True,
    }

    db.init_app(app)

    # TCP Keepalive sur les connexions DB
    from utils.keepalive import init_tcp_keepalive
    init_tcp_keepalive(app)

    return app, tunnel
