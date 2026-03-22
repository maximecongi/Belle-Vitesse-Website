import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from sqlalchemy import insert

from models import SqlQueryLog

# ─────────────────────────────────────────────────────────────────────────────
# Logger setup for File Output
# ─────────────────────────────────────────────────────────────────────────────

LOG_DIR = Path(__file__).parent.parent.parent / os.getenv("LOGS_DIR", "logs")
if not LOG_DIR.exists():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "sql_queries.log"
MAX_LOG_SIZE = 10_000_000
BACKUP_COUNT = 5

file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=MAX_LOG_SIZE,
    backupCount=BACKUP_COUNT,
    encoding="utf-8"
)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s"
))

worker_logger = logging.getLogger("sql_logger_worker")
worker_logger.setLevel(logging.INFO)
if not worker_logger.handlers:
    worker_logger.addHandler(file_handler)
worker_logger.propagate = False


def process_sql_log(record, app=None):
    """
    Fonction appelée :
    - directement en dev (thread)
    - via RQ en prod
    """
    if not app:
        try:
            from app import app as flask_app
            app = flask_app
        except Exception:
            pass

    ctx = None
    if app:
        ctx = app.app_context()
        ctx.push()

    try:
        from models import db  # import lazy

        # ── DB Insert ──
        try:
            # On utilise db.session car on est dans le context_app
            stmt = insert(SqlQueryLog).values(**record["db"])
            db.session.execute(stmt)
            db.session.commit()
        except Exception as e:
            if db.session:
                db.session.rollback()
            msg = f"DB insert failed: {e}"
            worker_logger.error(msg)

        # ── File Log ──
        try:
            worker_logger.log(record["level"], record["message"])
        except Exception as e:
            msg = f"File log failed: {e}"
            worker_logger.error(msg)

    except Exception:
        pass

    finally:
        if ctx:
            ctx.pop()
