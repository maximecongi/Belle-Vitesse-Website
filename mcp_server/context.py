"""ContextVars et conteneurs utilisateur pour la traçabilité asynchrone sécurisée."""
import contextvars
from typing import Any


# ContextVars pour l'isolation asynchrone par requête (compatible Uvicorn / Starlette)
CURRENT_MCP_USER: contextvars.ContextVar[Any] = contextvars.ContextVar("CURRENT_MCP_USER", default=None)
CURRENT_MCP_IP: contextvars.ContextVar[str] = contextvars.ContextVar("CURRENT_MCP_IP", default="unknown")


class DummyGuestUser:
    """Utilisateur invité par défaut pour les sondages sans token."""
    id = 1
    mail = "admin@bellevitesse.com"
    firstname = "Admin"
    lastname = "MCP"
    role = "super administrator"
    mcp_scope = "admin"

    def to_dict(self):
        return {
            "id": self.id,
            "mail": self.mail,
            "role": self.role,
            "scope": self.mcp_scope,
        }
