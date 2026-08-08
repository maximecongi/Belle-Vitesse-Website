"""Configuration et registres globaux pour le serveur BV-MCP."""
import os
import logging
from collections import defaultdict
from typing import Dict, Any, List

# Logger principal MCP
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BV-MCP")

# Port et paramètres réseau
MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", "8080"))

# Registres en mémoire
ACTIVE_MCP_SESSIONS: Dict[str, Any] = {}
RECENT_AUTH_BY_IP: Dict[str, Any] = {}

# Rate Limiter (30 requêtes / minute par client)
MCP_RATE_LIMITER: Dict[str, List[float]] = defaultdict(list)
MAX_MCP_REQUESTS_PER_MINUTE = 30
