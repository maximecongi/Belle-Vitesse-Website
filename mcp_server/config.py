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

# Rate Limiter (30 requêtes / minute par client)
MCP_RATE_LIMITER: Dict[str, List[float]] = defaultdict(list)
MAX_MCP_REQUESTS_PER_MINUTE = 30

# Protection Anti-Brute-Force & Anti-Scan
# - MCP_FAILED_AUTH_IP : { ip: [timestamp_1, timestamp_2, ...] }
# - MCP_BANNED_IPS : { ip: unban_timestamp } (bannissement 15 minutes après 5 échecs consécutifs en 2 min)
MCP_FAILED_AUTH_IP: Dict[str, List[float]] = defaultdict(list)
MCP_BANNED_IPS: Dict[str, float] = {}
