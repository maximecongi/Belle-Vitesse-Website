"""Auto-enregistrement de tous les sous-modules d'outils MCP par domaine."""
from mcp_server.tools import projects
from mcp_server.tools import inspections
from mcp_server.tools import contacts
from mcp_server.tools import productions
from mcp_server.tools import users
from mcp_server.tools import pricing
from mcp_server.tools import pre_quotes
from mcp_server.tools import calendars
from mcp_server.tools import documents
from mcp_server.tools import system
from mcp_server.tools import vehicles
from mcp_server.tools import incidents

__all__ = [
    "projects",
    "inspections",
    "contacts",
    "productions",
    "users",
    "pricing",
    "pre_quotes",
    "calendars",
    "documents",
    "system",
    "vehicles",
    "incidents",
]
