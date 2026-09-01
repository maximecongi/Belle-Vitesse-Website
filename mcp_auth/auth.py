import logging
from datetime import datetime, timezone
from functools import wraps

from flask import g
from models import McpApiToken, User, db

logger = logging.getLogger(__name__)

ROLE_LEVELS = {
    "technicien": 1,
    "user": 1,
    "commercial": 2,
    "manager": 3,
    "administrateur": 4,
    "administrator": 4,
    "super administrateur": 5,
    "super administrator": 5,
}


class McpUserContext:
    """Conteneur utilisateur léger et autonome sans dépendance à la session SQLAlchemy."""

    def __init__(self, user_id: int, mail: str, firstname: str, lastname: str, role: str, scope: str = "read_only", token_id: int = None):
        self.id = user_id
        self.mail = mail or "user@bellevitesse.com"
        self.firstname = firstname or "User"
        self.lastname = lastname or "MCP"
        self.role = role or "user"
        self.mcp_scope = scope or "read_only"
        self.current_token_id = token_id

    def to_dict(self):
        return {
            "id": self.id,
            "mail": self.mail,
            "firstname": self.firstname,
            "lastname": self.lastname,
            "role": self.role,
            "scope": self.mcp_scope,
        }

    def __repr__(self):
        return f"<McpUserContext id={self.id} mail={self.mail} role={self.role} scope={self.mcp_scope}>"


def authenticate_mcp_token(raw_token: str) -> McpUserContext | None:
    """
    Vérifie un token API MCP brut :
    - Hache le token brut avec SHA-256
    - Recherche le token dans la table mcp_api_tokens
    - Vérifie is_active et expires_at
    - Met à jour last_used_at
    - Retourne une instance McpUserContext si valide, None sinon.
    """
    if not raw_token or not raw_token.startswith("bv_mcp_"):
        return None

    token_hash = McpApiToken.hash_token(raw_token)
    token_rec = McpApiToken.query.filter_by(
        token_hash=token_hash, is_active=True).first()

    if not token_rec:
        logger.warning("⚠️ Token MCP invalide ou inactif.")
        return None

    # Vérification d'expiration
    if token_rec.expires_at:
        exp_at = token_rec.expires_at
        if exp_at.tzinfo is None:
            exp_at = exp_at.replace(tzinfo=timezone.utc)
        if exp_at < datetime.now(timezone.utc):
            logger.warning(
                f"⚠️ Token MCP #{token_rec.id} expiré pour l'utilisateur {token_rec.user_id}.")
            return None

    # Mise à jour traçabilité last_used_at
    try:
        token_rec.last_used_at = datetime.now(timezone.utc)
        db.session.commit()
    except Exception as e:
        logger.error(
            f"❌ Impossible de mettre à jour last_used_at pour token #{token_rec.id}: {e}")
        db.session.rollback()

    user = token_rec.user
    if not user:
        logger.warning(
            f"⚠️ Token MCP #{token_rec.id} référencie un utilisateur introuvable.")
        return None

    user_scope = getattr(token_rec, "scope", None) or "read_only"
    return McpUserContext(
        user_id=user.id,
        mail=user.mail,
        firstname=getattr(user, "firstname", ""),
        lastname=getattr(user, "lastname", ""),
        role=user.role,
        scope=user_scope,
        token_id=token_rec.id,
    )


SCOPE_LEVELS = {
    "read_only": 1,
    "write": 2,
    "admin": 3,
}


def check_mcp_scope(user, required_scope: str) -> bool:
    """
    Vérifie si le token de l'utilisateur a au moins le niveau de scope requis.
    - read_only: 1 (consultation uniquement)
    - write: 2 (création/modification)
    - admin: 3 (suppression/actions critiques)
    """
    if not user:
        return True
    user_scope = getattr(user, "mcp_scope", "admin") or "admin"
    user_level = SCOPE_LEVELS.get(user_scope, 3)
    req_level = SCOPE_LEVELS.get(required_scope, 1)
    return user_level >= req_level



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
