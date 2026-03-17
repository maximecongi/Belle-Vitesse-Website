from .queue import enqueue, start_dev_worker
import os


def init_sql_logger(app, db):

    activated = os.getenv("SQL_LOGGER_ACTIVATED", "false").lower() in (
        "true", "1", "yes"
    )

    if not activated:
        app.logger.info("SQL Logger disabled")
        return

    app.logger.info("SQL Logger enabled")

    # ✅ DEV → démarre thread local
    if os.getenv("FLASK_ENV") == "development":
        start_dev_worker(app)

    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    @event.listens_for(Engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        import time
        context._query_start_time = time.perf_counter()

    @event.listens_for(Engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):

        import time
        import logging
        from datetime import datetime
        import zoneinfo

        start = getattr(context, "_query_start_time", None)
        if start is None:
            return

        duration_ms = (time.perf_counter() - start) * 1000

        if duration_ms < 10:
            return

        # ⚠️ simplifié ici (tu peux garder tes helpers existants)
        record = {
            "db": {
                "timestamp": datetime.now(zoneinfo.ZoneInfo("Europe/Paris")),
                "query": statement[:500],
                "duration_ms": duration_ms
            },
            "message": f"{duration_ms:.2f}ms | {statement[:200]}",
            "level": logging.INFO
        }

        enqueue("process_sql_log", record)
