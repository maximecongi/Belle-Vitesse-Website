import os
import time
import logging
import re
import ast
from datetime import datetime
from pathlib import Path
from sqlalchemy import event
from flask import request, session
from utils.async_tasks import run_async

from models import SqlQueryLog

# ── File logger setup ─────────────────────────────────────────────────────────
_log_dir = Path(__file__).parent.parent / \
    os.getenv("LOGS_DIR", "logs") / "sql_logs"
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


def _extract_user_from_session() -> str:
    """Extrait l'identifiant utilisateur depuis la session Flask."""
    try:
        firstname = session.get("admin_user_firstname")
        lastname = session.get("admin_user_lastname")

        if firstname and lastname:
            return f"{firstname} {lastname}"
        if firstname:
            return firstname

        user = session.get("user", "anonymous")
        if isinstance(user, dict):
            return user.get("email") or str(user.get("id", "anonymous"))
        return str(user)
    except RuntimeError:
        return "system"


def _extract_request_context() -> dict:
    """Extrait les infos de la requête Flask courante."""
    ctx = {
        "user": "system",
        "endpoint": None,
        "method": None,
        "ip_address": None,
    }

    if not request:
        return ctx

    try:
        ctx["endpoint"] = request.endpoint
        ctx["method"] = request.method

        forwarded_for = request.headers.get(
            "X-Forwarded-For", request.remote_addr)
        if forwarded_for:
            ctx["ip_address"] = forwarded_for.split(",")[0].strip()

        ctx["user"] = _extract_user_from_session()
    except RuntimeError:
        pass

    return ctx


def init_sql_logger(app, db):
    """
    Initialise le SQL logger.
    Attache les événements SQLAlchemy pour logger les requêtes.
    Logs dans la table SQL et dans un fichier rotatif.
    La création de la table est gérée via models.py.
    """
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

            # Anti-récursion : ignorer les requêtes sur notre table de logs
            if "sql_query_logs" in statement.lower():
                return

            # Ignorer les DESCRIBE émis par le système (pas par un user connecté)
            if statement.strip().upper().startswith("DESCRIBE"):
                req_ctx = _extract_request_context()
                if req_ctx["user"] == "system":
                    return

            safe_query = statement[:500]
            safe_params = str(parameters)[:500] if parameters else None

            req_ctx = _extract_request_context()

            ctx_data = {
                "ts": datetime.utcnow(),
                "user": req_ctx["user"],
                "ip_address": req_ctx["ip_address"],
                "endpoint": req_ctx["endpoint"],
                "method": req_ctx["method"],
                "safe_query": safe_query,
                "safe_params": safe_params,
                "duration_ms": duration_ms,
                "parameters": parameters,
            }

            def _log_async():
                # ── Insert en base ────────────────────────────────────────────
                try:
                    # Using ORM in background thread
                    log_entry = SqlQueryLog(
                        timestamp=ctx_data['ts'],
                        user=ctx_data['user'],
                        ip_address=ctx_data['ip_address'],
                        endpoint=ctx_data['endpoint'],
                        method=ctx_data['method'],
                        query=ctx_data['safe_query'],
                        parameters=ctx_data['safe_params'],
                        duration_ms=ctx_data['duration_ms']
                    )
                    db.session.add(log_entry)
                    db.session.commit()
                    db_status = "✅ DB OK"
                except Exception as e:
                    db_status = f"❌ DB FAIL: {str(e)}"
                    db.session.rollback()
                    app.logger.error(
                        f"❌ SQL Logger DB insert failed", exc_info=True)
                finally:
                    db.session.remove()

                # ── Log fichier ───────────────────────────────────────────────
                try:
                    readable_query = render_query(
                        ctx_data['safe_query'], ctx_data['parameters'])
                    logger.info(
                        f"user={ctx_data['user']} | ip={ctx_data['ip_address']} | "
                        f"endpoint={ctx_data['endpoint']} | method={ctx_data['method']} | "
                        f"duration={ctx_data['duration_ms']:.2f}ms | {db_status} | query={readable_query}"
                    )
                except Exception as e:
                    print(f"CRITICAL: sql_logger log write failed: {e}")

            run_async(app, _log_async)
