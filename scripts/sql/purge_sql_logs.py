import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

# Setup path for local imports
_root = Path(__file__).parent.parent.parent
sys.path.append(str(_root))

# Load environment variables
load_dotenv(_root / '.env')


def build_minimal_app():
    from flask import Flask
    from models import db

    mysql_user = os.getenv("MYSQL_USER", "root")
    mysql_pass = os.getenv("MYSQL_PASSWORD", "")
    mysql_host = os.getenv("MYSQL_HOST", "localhost")
    mysql_port = 3306
    mysql_db = os.getenv("MYSQL_DATABASE", "bellevitesse")

    is_prod = os.getenv("FLASK_ENV") == "production"
    use_ssh = os.getenv("USE_SSH_TUNNEL", "false").lower() == "true"
    tunnel = None

    if use_ssh and not is_prod:
        from sshtunnel import SSHTunnelForwarder
        try:
            tunnel = SSHTunnelForwarder(
                (os.getenv("SSH_HOST"), 22),
                ssh_username=os.getenv("SSH_USER"),
                ssh_password=os.getenv("SSH_PASSWORD"),
                remote_bind_address=(mysql_host, 3306),
            )
            tunnel.start()
            mysql_host = "127.0.0.1"
            mysql_port = tunnel.local_bind_port
            print(
                f"[{datetime.now()}] ✅ SSH Tunnel démarré sur le port {mysql_port}")
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Erreur SSH Tunnel : {e}")

    default_uri = (
        f"mysql+mysqlconnector://{mysql_user}:{mysql_pass}"
        f"@{mysql_host}:{mysql_port}/{mysql_db}"
    )

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "SQLALCHEMY_DATABASE_URI", default_uri)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_POOL_RECYCLE"] = 280
    app.config["SQLALCHEMY_POOL_PRE_PING"] = True
    db.init_app(app)

    return app, tunnel


def purge_logs():
    from models import db, SqlQueryLog

    app, tunnel = build_minimal_app()

    try:
        with app.app_context():
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=60)
            print(
                f"[{datetime.now()}] Purge des sql_query_logs antérieurs au {cutoff_date.strftime('%d/%m/%Y')}...")

            try:
                result = db.session.query(SqlQueryLog).filter(
                    SqlQueryLog.timestamp < cutoff_date
                ).delete()
                db.session.commit()
                print(
                    f"[{datetime.now()}] ✅ Purge terminée. {result} ligne(s) supprimée(s).")
            except Exception as e:
                print(f"[{datetime.now()}] ❌ Erreur pendant la purge : {e}")
                db.session.rollback()
    finally:
        if tunnel and tunnel.is_active:
            tunnel.stop()
            print(f"[{datetime.now()}] 🔌 SSH Tunnel fermé.")


if __name__ == "__main__":
    purge_logs()
