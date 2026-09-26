import logging
from typing import List, Optional
from flask import current_app
from redis import Redis

logger = logging.getLogger(__name__)


def get_session_redis_client() -> Optional[Redis]:
    """
    Retourne le client Redis configuré pour Flask-Session.
    Tente de récupérer le client depuis current_app.config['SESSION_REDIS'],
    ou instancie une connexion vers REDIS_DB_SESSION via redis_queue.
    """
    try:
        if current_app and current_app.config.get("SESSION_REDIS"):
            return current_app.config.get("SESSION_REDIS")
    except Exception:
        pass

    try:
        from services.common.redis_queue import get_redis_connection
        db_index = int(current_app.config.get("REDIS_DB_SESSION", 2)) if current_app else 2
        return get_redis_connection(db_index=db_index)
    except Exception as err:
        logger.debug(f"Client Redis de session indisponible : {err}")
        return None


def register_user_session(user_id: int, sid: Optional[str] = None, ttl_seconds: int = 43200) -> bool:
    """
    Associe un identifiant de session serveur (sid) à un utilisateur dans Redis.
    Permet la révocation ciblée et instantanée de toutes les sessions actives d'un utilisateur.
    """
    if not user_id or not sid:
        return False

    client = get_session_redis_client()
    if not client:
        return False

    try:
        key = f"bv_user_sessions:{user_id}"
        client.sadd(key, sid)
        client.expire(key, ttl_seconds)
        logger.debug(f"Session {sid} enregistrée pour l'utilisateur {user_id}")
        return True
    except Exception as err:
        logger.warning(f"Impossible d'enregistrer la session pour l'utilisateur {user_id} : {err}")
        return False


def unregister_user_session(user_id: int, sid: Optional[str] = None) -> bool:
    """
    Retire un identifiant de session de l'ensemble des sessions actives d'un utilisateur.
    """
    if not user_id or not sid:
        return False

    client = get_session_redis_client()
    if not client:
        return False

    try:
        key = f"bv_user_sessions:{user_id}"
        client.srem(key, sid)
        return True
    except Exception as err:
        logger.warning(f"Impossible de désenregistrer la session {sid} pour l'utilisateur {user_id} : {err}")
        return False


def get_user_active_sessions(user_id: int) -> List[str]:
    """
    Retourne la liste des identifiants de session serveur actifs pour un utilisateur donné.
    """
    if not user_id:
        return []

    client = get_session_redis_client()
    if not client:
        return []

    try:
        key = f"bv_user_sessions:{user_id}"
        members = client.smembers(key)
        result = []
        for m in members:
            sid_str = m.decode("utf-8") if isinstance(m, bytes) else str(m)
            result.append(sid_str)
        return result
    except Exception as err:
        logger.warning(f"Erreur lors de la lecture des sessions pour l'utilisateur {user_id} : {err}")
        return []


def invalidate_user_sessions(user_id: int) -> int:
    """
    Révoque immédiatement toutes les sessions actives d'un utilisateur.
    Supprime chaque clé de session Flask-Session (bv_session:<sid>) dans Redis et nettoie l'index.
    Retourne le nombre de sessions supprimées.
    """
    if not user_id:
        return 0

    client = get_session_redis_client()
    if not client:
        return 0

    try:
        key = f"bv_user_sessions:{user_id}"
        members = client.smembers(key)
        count = 0

        if members:
            prefix = "bv_session:"
            if current_app:
                prefix = current_app.config.get("SESSION_KEY_PREFIX", "bv_session:")

            keys_to_delete = []
            for m in members:
                sid_str = m.decode("utf-8") if isinstance(m, bytes) else str(m)
                keys_to_delete.append(f"{prefix}{sid_str}")

            if keys_to_delete:
                count = client.delete(*keys_to_delete)

        client.delete(key)
        logger.info(f"🔒 {count} session(s) révoquée(s) immédiatement pour l'utilisateur {user_id}")
        return count
    except Exception as err:
        logger.warning(f"Erreur lors de la révocation des sessions de l'utilisateur {user_id} : {err}")
        return 0
