"""Micro-cache en mémoire avec TTL pour les outils de consultation fréquente MCP."""
import time
from functools import wraps
from typing import Dict, Any, Tuple

# Registre mémoire : { cache_key: (timestamp, cached_result) }
_MCP_TOOL_CACHE: Dict[str, Tuple[float, Any]] = {}


def mcp_cache(ttl_seconds: int = 60):
    """
    Décorateur de mise en cache en mémoire pour les outils MCP de consultation intensive.
    Évite les requêtes SQL et calculs redondants lors des raisonnements multi-étapes de l'IA.
    - ttl_seconds: Durée de rétention en secondes (défaut : 60s).
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Construction d'une clé de cache stable basée sur le nom de l'outil et ses arguments
            sorted_kwargs = tuple(sorted((k, str(v)) for k, v in kwargs.items()))
            cache_key = f"{func.__name__}:{str(args)}:{str(sorted_kwargs)}"
            now = time.time()

            if cache_key in _MCP_TOOL_CACHE:
                cached_time, cached_val = _MCP_TOOL_CACHE[cache_key]
                if now - cached_time < ttl_seconds:
                    return cached_val

            result = func(*args, **kwargs)

            # Ne pas mettre en cache les erreurs
            is_error = False
            if isinstance(result, dict):
                if result.get("status") in ("error", "blocked_403") or result.get("success") is False:
                    is_error = True

            if not is_error:
                _MCP_TOOL_CACHE[cache_key] = (now, result)

            return result
        return wrapper
    return decorator


def invalidate_mcp_cache(prefix: str = None):
    """
    Invalide tout ou partie du micro-cache MCP.
    - prefix: Préfixe du nom de fonction (ex: 'get_equipment_rates' ou 'pricing'). Si None, vide tout le cache.
    """
    global _MCP_TOOL_CACHE
    if prefix:
        _MCP_TOOL_CACHE = {k: v for k, v in _MCP_TOOL_CACHE.items() if not k.startswith(prefix)}
    else:
        _MCP_TOOL_CACHE.clear()


def get_mcp_cache_stats() -> Dict[str, Any]:
    """Retourne des statistiques sur le micro-cache MCP pour l'audit ou le monitoring."""
    now = time.time()
    active_entries = sum(1 for ts, _ in _MCP_TOOL_CACHE.values() if now - ts < 60)
    return {
        "total_entries": len(_MCP_TOOL_CACHE),
        "active_entries": active_entries,
    }
