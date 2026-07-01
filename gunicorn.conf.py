import multiprocessing

bind = "0.0.0.0:5001"
workers = max(multiprocessing.cpu_count(), 2)
threads = 4
keepalive = 65
timeout = 120
worker_class = "gthread"
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%({x-forwarded-for}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'


def post_fork(server, worker):
    """Dispose le pool de connexions DB hérité du processus master après le fork.

    Chaque worker Gunicorn est un fork du master. Les connexions MySQL du master
    sont copiées en mémoire mais les sockets réseau sous-jacents ne sont PAS
    dupliqués → ces connexions héritées sont mortes par définition.
    dispose() force chaque worker à créer ses propres connexions fraîches.
    """
    try:
        from app import app, warm_cache
        with app.app_context():
            from models import db
            db.engine.dispose()
            server.log.info(f"[Worker {worker.pid}] ✅ DB pool disposed after fork")
        
        # Lance le warmup du cache de manière sûre dans un thread après le fork du worker
        import threading
        threading.Thread(target=warm_cache, daemon=True).start()
        server.log.info(f"[Worker {worker.pid}] 🔥 Cache warmup started in background thread")
    except Exception as e:
        server.log.error(f"[Worker {worker.pid}] ❌ post_fork error: {e}")
