import multiprocessing

bind = "0.0.0.0:5001"
workers = multiprocessing.cpu_count() * 2 + 1
threads = 2
timeout = 120
worker_class = "gthread"
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"


def post_fork(server, worker):
    """Dispose le pool de connexions DB hérité du processus master après le fork.

    Chaque worker Gunicorn est un fork du master. Les connexions MySQL du master
    sont copiées en mémoire mais les sockets réseau sous-jacents ne sont PAS
    dupliqués → ces connexions héritées sont mortes par définition.
    dispose() force chaque worker à créer ses propres connexions fraîches.
    """
    try:
        from app import app
        with app.app_context():
            from models import db
            db.engine.dispose()
            server.log.info(f"[Worker {worker.pid}] ✅ DB pool disposed after fork")
    except Exception as e:
        server.log.error(f"[Worker {worker.pid}] ❌ post_fork error: {e}")
