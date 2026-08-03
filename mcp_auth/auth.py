import logging
from datetime import datetime, timezone
from functools import wraps

from flask import g
from models import McpApiToken, User, db

logger = logging.getLogger(__name__)

ROLE_LEVELS = {
    "user": 1,
    "commercial": 2,
    "manager": 3,
    "administrator": 4,
    "super administrator": 5,
}


def authenticate_mcp_token(raw_token: str) -> User | None:
    """
    Vérifie un token API MCP brut :
    - Hache le token brut avec SHA-256
    - Recherche le token dans la table mcp_api_tokens
    - Vérifie is_active et expires_at
    - Met à jour last_used_at
    - Retourne l'instance User si valide, None sinon.
    """
    if not raw_token or not raw_token.startswith("bv_mcp_"):
        return None

    token_hash = McpApiToken.hash_token(raw_token)
    token_rec = McpApiToken.query.filter_by(token_hash=token_hash, is_active=True).first()

    if not token_rec:
        logger.warning("⚠️ Token MCP invalide ou inactif.")
        return None

    # Vérification d'expiration
    if token_rec.expires_at:
        exp_at = token_rec.expires_at
        if exp_at.tzinfo is None:
            exp_at = exp_at.replace(tzinfo=timezone.utc)
        if exp_at < datetime.now(timezone.utc):
            logger.warning(f"⚠️ Token MCP #{token_rec.id} expiré pour l'utilisateur {token_rec.user_id}.")
            return None

    # Mise à jour traçabilité last_used_at
    try:
        token_rec.last_used_at = datetime.now(timezone.utc)
        db.session.commit()
    except Exception as e:
        logger.error(f"❌ Impossible de mettre à jour last_used_at pour token #{token_rec.id}: {e}")
        db.session.rollback()

    user = token_rec.user
    if not user:
        logger.warning(f"⚠️ Token MCP #{token_rec.id} référencie un utilisateur introuvable.")
        return None

    return user


def check_user_has_role(user: User, min_role: str) -> bool:
    """
    Vérifie si l'utilisateur possède au moins le niveau du rôle spécifié.
    """
    if not user:
        return False
    user_role = (user.role or "user").lower()
    min_role_clean = min_role.lower()

    user_level = ROLE_LEVELS.get(user_role, 1)
    min_level = ROLE_LEVELS.get(min_role_clean, 1)

    return user_level >= min_level
