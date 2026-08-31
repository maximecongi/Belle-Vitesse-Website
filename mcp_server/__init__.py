"""Package principal mcp_server pour BV-MCP."""
from mcp_server.config import logger, MCP_SERVER_PORT
from mcp_server.core import mcp, flask_app
from mcp_server.middleware import PureAsgiAuthMiddleware
from mcp_server.context import CURRENT_MCP_USER, CURRENT_MCP_IP, DummyGuestUser
from mcp_server import tools
from mcp_server import resources
from mcp_server import prompts

__all__ = [
    "mcp",
    "flask_app",
    "PureAsgiAuthMiddleware",
    "CURRENT_MCP_USER",
    "CURRENT_MCP_IP",
    "DummyGuestUser",
    "logger",
    "MCP_SERVER_PORT",
    "tools",
    "resources",
    "prompts",
]
