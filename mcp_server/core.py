"""Core de l'application MCP : Initialisation de Flask et FastMCP."""
import os
from mcp.server.fastmcp import FastMCP
from app import create_app
from mcp_server.config import MCP_SERVER_PORT

# Initialisation de l'application Flask
flask_app = create_app()

# Initialisation de FastMCP
mcp = FastMCP(
    "BV-MCP",
    host="0.0.0.0",
    port=MCP_SERVER_PORT,
)
