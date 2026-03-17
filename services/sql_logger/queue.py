import os
import queue
import threading

from redis import Redis
from rq import Queue as RQQueue

FLASK_ENV = os.getenv("FLASK_ENV", "production")

# ─────────────────────────────────────────────
# DEV → queue mémoire
# ─────────────────────────────────────────────

if FLASK_ENV == "dev":
    log_queue = queue.Queue(maxsize=1000)

    def enqueue(func, record):
        try:
            log_queue.put_nowait((func, record))
        except queue.Full:
            print("[sql_logger] queue full, log dropped")

    def start_dev_worker(app):
        def worker():
            from .worker import process_sql_log

            while True:
                func, record = log_queue.get()
                try:
                    process_sql_log(record, app=app)
                except Exception as e:
                    print(f"[sql_logger] worker error: {e}")
                finally:
                    log_queue.task_done()

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

# ─────────────────────────────────────────────
# PROD → Redis + RQ
# ─────────────────────────────────────────────

else:
    redis_conn = Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=int(os.getenv("REDIS_DB_SQLLOG", 1)),
        password=os.getenv("REDIS_PASSWORD", None)
    )

    rq_queue = RQQueue("sql_logs", connection=redis_conn)

    def enqueue(func, record):
        try:
            rq_queue.enqueue(
                "services.sql_logger.worker.process_sql_log",
                record,
                job_timeout=10,
                result_ttl=0
            )
        except Exception as e:
            print(f"[sql_logger] Redis enqueue failed: {e}")

    def start_dev_worker(app):
        """No-op in production (using RQ worker)"""
        pass
