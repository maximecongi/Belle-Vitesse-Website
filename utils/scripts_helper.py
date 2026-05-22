import os
import sys
from pathlib import Path

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

    return app, tunnel
