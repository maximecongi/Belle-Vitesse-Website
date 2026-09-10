"""ContextVars et conteneurs utilisateur pour la traçabilité asynchrone sécurisée."""
import contextvars
from typing import Any


# ContextVars pour l'isolation asynchrone par requête (compatible Uvicorn / Starlette)
CURRENT_MCP_USER: contextvars.ContextVar[Any] = contextvars.ContextVar("CURRENT_MCP_USER", default=None)
CURRENT_MCP_IP: contextvars.ContextVar[str] = contextvars.ContextVar("CURRENT_MCP_IP", default="unknown")


class DummyGuestUser:
    """Utilisateur invité anonyme sans privilège (Fail-Safe)."""
    id = None
    mail = "guest@bellevitesse.com"
    firstname = "Guest"
    lastname = "Anonymous"
    role = "guest"
    mcp_scope = "none"

    def to_dict(self):
        return {
            "id": self.id,
            "mail": self.mail,
            "role": self.role,
            "scope": self.mcp_scope,
        }
