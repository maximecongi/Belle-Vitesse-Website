import os
import time
import logging
import re
import ast
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import event, insert
from flask import request, session, has_request_context

from models import SqlQueryLog

# ── File logger setup ─────────────────────────────────────────────────────────
_log_dir = Path(__file__).parent.parent / "logs/sql_logs"
_log_dir.mkdir(parents=True, exist_ok=True)

file_handler = logging.FileHandler(
    _log_dir / "sql_queries.log", encoding="utf-8")
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))

logger = logging.getLogger("sql_logger")
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.propagate = False  # Ne pas remonter vers le root logger Flask


def render_query(query: str, parameters) -> str:
    """Reconstitue la requête SQL avec ses paramètres injectés pour les logs fichier."""
    if not parameters:
        return query

    # parameters peut être un dict ou tuple directement (pas encore stringifié)
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
                return f"'{val}'"
            return str(val)
        return re.sub(r'%\((\w+)\)s', replace, query)

    if isinstance(params, (list, tuple)):
        it = iter(params)

        def replace(_):
            val = next(it, None)
            if val is None:
                return "NULL"
            if isinstance(val, str):
                return f"'{val}'"
            return str(val)
        return re.sub(r'%s', replace, query)

    return query


def init_sql_logger(app, db):
    """
    Initialise the SQL logger.
    Attaches SQLAlchemy events to log queries.
    Logs to both the SQL table and a rotating file.
    Table creation is handled via models.py.
    """
    # Check if logger is activated via environment variable
    activated = os.getenv("SQL_LOGGER_ACTIVATED", "false").lower() in (
        "true", "1", "t", "y", "yes")

    if not activated:
        app.logger.info(
            "ℹ️ SQL Logger is disabled (SQL_LOGGER_ACTIVATED=false)")
        return

    with app.app_context():
        @event.listens_for(db.engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            context._query_start_time = time.time()

        @event.listens_for(db.engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            duration_ms = (time.time() - context._query_start_time) * 1000

            # Anti-recursion: ignore queries on our log table
            if "sql_query_logs" in statement.lower():
                return

            # Ignore DESCRIBE queries from the system user
            if statement.strip().upper().startswith("DESCRIBE"):
                is_system = True
                if request:
                    try:
                        if session.get("admin_user_firstname") or session.get("user"):
                            is_system = False
                    except RuntimeError:
                        pass
                if is_system:
                    return

            # Truncate query to prevent massive logs
            safe_query = statement[:500]

            # Convert parameters to string safely (truncate if huge)
            safe_params = str(parameters)[:500] if parameters else None

            # Extract context from Flask request if available
            user = "system"
            endpoint = None
            method = None
            ip_address = None

            if request:
                try:
                    endpoint = request.endpoint
                    method = request.method

                    ip_address = request.headers.get(
                        'X-Forwarded-For', request.remote_addr)
                    if ip_address:
                        ip_address = ip_address.split(',')[0].strip()

                    session_firstname = session.get("admin_user_firstname")
                    session_lastname = session.get("admin_user_lastname")

                    if session_firstname and session_lastname:
                        user = f"{session_firstname} {session_lastname}"
                    elif session_firstname:
                        user = session_firstname
                    else:
                        user = session.get("user", "anonymous")

                    if isinstance(user, dict) and "email" in user:
                        user = user["email"]
                    elif isinstance(user, dict) and "id" in user:
                        user = str(user["id"])
                except RuntimeError:
                    pass

            ts = datetime.now(timezone.utc)

            # ── Insert into SQL table ─────────────────────────────────────────
            try:
                stmt = insert(SqlQueryLog).values(
                    timestamp=ts,
                    user=str(user),
                    ip_address=ip_address,
                    endpoint=endpoint,
                    method=method,
                    query=safe_query,
                    parameters=safe_params,
                    duration_ms=duration_ms
                )
                conn.execute(stmt)
            except Exception as e:
                app.logger.error(f"sql_logger failed to insert log: {e}")

            try:
                readable_query = render_query(safe_query, parameters)
                logger.info(
                    f"user={user} | ip={ip_address} | "
                    f"endpoint={endpoint} | method={method} | "
                    f"duration={duration_ms:.2f}ms | query={readable_query}"
                )
            except Exception as e:
                app.logger.error(f"sql_logger failed to write file log: {e}")
