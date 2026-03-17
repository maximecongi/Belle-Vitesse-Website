import os
import time
import logging
import re
import ast
import threading
import queue

from datetime import datetime
import zoneinfo
from pathlib import Path
from logging.handlers import RotatingFileHandler

from sqlalchemy import event, insert
from flask import request, session, has_request_context

from models import SqlQueryLog

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

LOG_DIR = Path(__file__).parent.parent / \
    os.getenv("LOGS_DIR", "logs") / "sql_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "sql_queries.log"

MAX_LOG_SIZE = 10_000_000
BACKUP_COUNT = 5

SLOW_QUERY_THRESHOLD_MS = int(os.getenv("SQL_LOGGER_THRESHOLD_MS", 10))
QUEUE_MAX_SIZE = int(os.getenv("SQL_LOGGER_QUEUE_SIZE", 1000))

IGNORED_PREFIXES = ("DESCRIBE", "SHOW", "PRAGMA", "SELECT 1")

SENSITIVE_KEYS = {"password", "token", "secret", "authorization", "cookie"}

# ─────────────────────────────────────────────────────────────────────────────
# Logger setup
# ─────────────────────────────────────────────────────────────────────────────

file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=MAX_LOG_SIZE,
    backupCount=BACKUP_COUNT,
    encoding="utf-8"
)

file_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s"
))

logger = logging.getLogger("sql_logger")
logger.setLevel(logging.INFO)

if not logger.handlers:
    logger.addHandler(file_handler)

logger.propagate = False

# ─────────────────────────────────────────────────────────────────────────────
# Queue + Worker
# ─────────────────────────────────────────────────────────────────────────────

log_queue = queue.Queue(maxsize=QUEUE_MAX_SIZE)


def log_worker(app, db):
    """Background worker that processes log queue."""
    with app.app_context():
        while True:
            try:
                record = log_queue.get()

                if record is None:
                    break  # graceful shutdown

                # ── DB insert ─────────────────────────────────────────────
                try:
                    stmt = insert(SqlQueryLog).values(**record["db"])
                    db.session.execute(stmt)
                    db.session.commit()
                except Exception as e:
                    app.logger.error(f"[sql_logger] DB insert failed: {e}")
                    db.session.rollback()

                # ── File logging ─────────────────────────────────────────
                try:
                    logger.log(record["level"], record["message"])
                except Exception as e:
                    app.logger.error(f"[sql_logger] File log failed: {e}")

                log_queue.task_done()

            except Exception as e:
                app.logger.error(f"[sql_logger] Worker error: {e}")


def start_worker(app, db):
    thread = threading.Thread(
        target=log_worker,
        args=(app, db),
        daemon=True
    )
    thread.start()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def escape_sql(value):
    return str(value).replace("'", "''")


def sanitize_params(params):
    if isinstance(params, dict):
        return {
            k: "***" if k.lower() in SENSITIVE_KEYS else v
            for k, v in params.items()
        }
    return params


def render_query(query: str, parameters) -> str:
    if not parameters:
        return query

    params = parameters

    if isinstance(params, str):
        try:
            params = ast.literal_eval(params)
        except Exception:
            return query

    if isinstance(params, dict):
        def replace(match):
            key = match.group(1)
            val = params.get(key)

            if val is None:
                return "NULL"
            if isinstance(val, str):
                return f"'{escape_sql(val)}'"
            return str(val)

        return re.sub(r'%\((\w+)\)s', replace, query)

    if isinstance(params, (list, tuple)):
        it = iter(params)

        def replace(_):
            val = next(it, None)

            if val is None:
                return "NULL"
            if isinstance(val, str):
                return f"'{escape_sql(val)}'"
            return str(val)

        return re.sub(r'%s', replace, query)

    return query


def get_request_context():
    if not has_request_context():
        return {
            "user": "system",
            "endpoint": None,
            "method": None,
            "ip_address": None
        }

    try:
        ip_address = request.headers.get("X-Forwarded-For")
        if ip_address:
            ip_address = ip_address.split(",")[0].strip()
        else:
            ip_address = request.remote_addr

        session_firstname = session.get("admin_user_firstname")
        session_lastname = session.get("admin_user_lastname")

        if session_firstname and session_lastname:
            user = f"{session_firstname} {session_lastname}"
        elif session_firstname:
            user = session_firstname
        else:
            user = session.get("user", "anonymous")

        if isinstance(user, dict):
            user = user.get("email") or str(user.get("id", "anonymous"))

        return {
            "user": str(user),
            "endpoint": request.endpoint,
            "method": request.method,
            "ip_address": ip_address
        }

    except Exception:
        return {
            "user": "unknown",
            "endpoint": None,
            "method": None,
            "ip_address": None
        }


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def init_sql_logger(app, db):
    activated = os.getenv("SQL_LOGGER_ACTIVATED", "false").lower() in (
        "true", "1", "t", "y", "yes"
    )

    if not activated:
        app.logger.info("SQL Logger disabled")
        return

    app.logger.info("SQL Logger enabled (async mode)")

    start_worker(app, db)

    # ✅ FIX CRITIQUE
    with app.app_context():

        engine = db.engine  # ← bind une fois dans le bon contexte

        @event.listens_for(engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            context._query_start_time = time.perf_counter()

        @event.listens_for(engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):

            start = getattr(context, "_query_start_time", None)
            if start is None:
                return

            duration_ms = (time.perf_counter() - start) * 1000

            if duration_ms < SLOW_QUERY_THRESHOLD_MS:
                return

            stmt_upper = statement.strip().upper()

            if stmt_upper.startswith(IGNORED_PREFIXES):
                return

            if SqlQueryLog.__tablename__ in statement.lower():
                return

            safe_query = statement[:500]
            sanitized_params = sanitize_params(parameters)

            ctx = get_request_context()

            tz = zoneinfo.ZoneInfo("Europe/Paris")
            ts = datetime.now(tz)

            try:
                readable_query = render_query(safe_query, sanitized_params)

                level = logging.WARNING if duration_ms > 500 else logging.INFO

                record = {
                    "db": {
                        "timestamp": ts,
                        "user": ctx["user"],
                        "ip_address": ctx["ip_address"],
                        "endpoint": ctx["endpoint"],
                        "method": ctx["method"],
                        "query": safe_query,
                        "parameters": str(sanitized_params)[:500],
                        "duration_ms": duration_ms
                    },
                    "message": (
                        f"user={ctx['user']} | ip={ctx['ip_address']} | "
                        f"endpoint={ctx['endpoint']} | method={ctx['method']} | "
                        f"duration={duration_ms:.2f}ms | rows={cursor.rowcount} | "
                        f"query={readable_query}"
                    ),
                    "level": level
                }

                try:
                    log_queue.put_nowait(record)
                except queue.Full:
                    pass

            except Exception as e:
                app.logger.error(f"[sql_logger] enqueue failed: {e}")
