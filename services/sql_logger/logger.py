import os
import time
import logging
from datetime import datetime, timezone

from .queue import enqueue, start_dev_worker
from .helpers import (
    get_request_context,
    sanitize_params,
    render_query
)

SLOW_QUERY_THRESHOLD_MS = int(os.getenv("SQL_LOGGER_THRESHOLD_MS", 0))
IGNORED_PREFIXES = ("DESCRIBE", "SHOW", "PRAGMA", "SELECT 1")


def init_sql_logger(app, db):
    print(f"[sql_logger] init_sql_logger called (db={db})")

    activated = os.getenv("SQL_LOGGER_ACTIVATED", "false").lower() in (
        "true", "1", "yes"
    )

    if not activated:
        print("[sql_logger] SQL Logger is DISABLED in environment")
        app.logger.info("SQL Logger disabled")
        return

    print("[sql_logger] SQL Logger is ENABLED in environment")
    app.logger.info("SQL Logger (v2) enabled")

    # ✅ DEV → démarre thread local
    if os.getenv("FLASK_ENV") == "dev":
        print("[sql_logger] Starting dev worker thread")
        start_dev_worker(app)

    with app.app_context():
        from sqlalchemy import event
        # On écoute sur db.engine directement
        engine = db.engine

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

            if "sql_query_logs" in statement.lower():
                return

            safe_query = statement[:1000]
            sanitized_params = sanitize_params(parameters)
            ctx = get_request_context()
            ts = datetime.now(timezone.utc)

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
                        "parameters": str(sanitized_params)[:1000],
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

                enqueue("process_sql_log", record)

            except Exception as e:
                print(f"[sql_logger] Error preparing record: {e}")
                app.logger.error(f"[sql_logger] failed to prepare log: {e}")
