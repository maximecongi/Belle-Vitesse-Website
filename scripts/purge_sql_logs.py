import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from utils.scripts_helper import build_minimal_app

# Setup path for local imports
_root = Path(__file__).parent.parent.parent
sys.path.append(str(_root))

# Load environment variables
load_dotenv(_root / '.env')


# No more build_minimal_app here, it's imported at the top.


def purge_logs():
    from models import SqlQueryLog, db

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
