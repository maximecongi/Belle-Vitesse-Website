import logging
import os
from typing import Dict, Optional, Tuple

from redis import Redis
from rq import Queue as RQQueue

logger = logging.getLogger("redis_queue")

_redis_connections: Dict[int, Optional[Redis]] = {}
_rq_queues: Dict[Tuple[str, int], Optional[RQQueue]] = {}


def get_redis_connection(db_index: Optional[int] = None) -> Optional[Redis]:
    """
    Retourne une connexion Redis poolée et testée par ping.
    En cas d'indisponibilité ou d'erreur de connexion, journalise un avertissement et renvoie None.
    """
    global _redis_connections

    if db_index is None:
        db_index = int(os.getenv("REDIS_DB_DEFAULT", "1"))

    if db_index in _redis_connections:
        conn = _redis_connections[db_index]
        if conn is not None:
            return conn

    flask_env = os.getenv("FLASK_ENV", "production")
    host = os.getenv(
        "REDIS_HOST", "bv_redis" if flask_env == "production" else "localhost"
    )
    port = int(os.getenv("REDIS_PORT", 6379))
    password = os.getenv("REDIS_PASSWORD", None) or None

    try:
        conn = Redis(
            host=host,
            port=port,
            db=db_index,
            password=password,
            socket_connect_timeout=2,
            socket_timeout=3,
        )
        conn.ping()
        _redis_connections[db_index] = conn
        return conn
    except Exception as err:
        logger.warning(
            f"⚠️ Redis non disponible (host={host}:{port}, db={db_index}): {err}"
        )
        _redis_connections[db_index] = None
        return None


def get_rq_queue(name: str = "default", db_index: Optional[int] = None) -> Optional[RQQueue]:
    """
    Retourne une file d'attente RQQueue connectée à Redis.
    Si Redis est indisponible, renvoie None pour permettre un repli synchrone ou thread daemon.
    """
    global _rq_queues

    if db_index is None:
        if name == "emails":
            db_index = int(os.getenv("REDIS_DB_EMAILS", "1"))
        elif name == "kdrive":
            db_index = int(os.getenv("REDIS_DB_KDRIVE", "1"))
        elif name == "sql_logs":
            db_index = int(os.getenv("REDIS_DB_SQLLOG", "1"))
        else:
            db_index = int(os.getenv("REDIS_DB_DEFAULT", "1"))

    cache_key = (name, db_index)
    if cache_key in _rq_queues:
        return _rq_queues[cache_key]

    conn = get_redis_connection(db_index=db_index)
    if conn:
        queue = RQQueue(name, connection=conn)
        _rq_queues[cache_key] = queue
        return queue

    return None


def clear_redis_cache() -> None:
    """Vide le cache des connexions et des files d'attente (utile pour les tests unitaires)."""
    global _redis_connections, _rq_queues
    _redis_connections.clear()
    _rq_queues.clear()
