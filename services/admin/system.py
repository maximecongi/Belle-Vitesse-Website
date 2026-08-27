"""
Service d'administration Système, Maintenance et Diagnostics pour Belle Vitesse.
"""
import os
import sys
import shutil
import platform
import logging
from typing import Dict, Any, List
from flask import current_app
from sqlalchemy import text
from models import db, McpApiToken, McpAuditLog
from services.public.newsletter import list_newsletter_subscribers

logger = logging.getLogger(__name__)


def get_system_status() -> Dict[str, Any]:
    """
    Récupère un bilan de santé complet du serveur et de ses dépendances.
    """
    # 1. Vérification MySQL
    mysql_status = "error"
    mysql_latency_ms = None
    try:
        import time
        t0 = time.time()
        db.session.execute(text("SELECT 1"))
        mysql_latency_ms = round((time.time() - t0) * 1000, 2)
        mysql_status = "connected"
    except Exception as e:
        logger.error(f"❌ Erreur de ping MySQL : {e}")
        mysql_status = f"error: {str(e)}"

    # 2. Métriques Système (Espace disque, charge)
    disk_total_gb = 0
    disk_free_gb = 0
    disk_used_percent = 0
    try:
        total, used, free = shutil.disk_usage("/")
        disk_total_gb = round(total / (1024 ** 3), 2)
        disk_free_gb = round(free / (1024 ** 3), 2)
        disk_used_percent = round((used / total) * 100, 1)
    except Exception as e:
        logger.warning(f"⚠️ Erreur lecture disque : {e}")

    # Charge CPU
    cpu_load = None
    try:
        if hasattr(os, "getloadavg"):
            loads = os.getloadavg()
            cpu_load = [round(x, 2) for x in loads]
    except Exception:
        pass

    # 3. Statistiques MCP
    active_mcp_tokens = 0
    total_mcp_audits = 0
    try:
        active_mcp_tokens = McpApiToken.query.filter_by(is_active=True).count()
        total_mcp_audits = McpAuditLog.query.count()
    except Exception:
        pass

    return {
        "status": "healthy" if mysql_status == "connected" else "degraded",
        "mysql": mysql_status,
        "mysql_latency_ms": mysql_latency_ms,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "flask_env": os.getenv("FLASK_ENV", "production"),
        "disk": {
            "total_gb": disk_total_gb,
            "free_gb": disk_free_gb,
            "used_percent": disk_used_percent,
        },
        "cpu_load_avg": cpu_load,
        "mcp_stats": {
            "active_tokens": active_mcp_tokens,
            "total_audit_entries": total_mcp_audits,
        }
    }


def purge_system_cache() -> bool:
    """
    Purge les caches de templates Jinja2 et les résidus temporaires.
    """
    try:
        if hasattr(current_app, "jinja_env") and hasattr(current_app.jinja_env, "cache"):
            if current_app.jinja_env.cache is not None:
                current_app.jinja_env.cache.clear()
        logger.info("✅ Cache système Flask/Jinja2 purgé avec succès.")
        return True
    except Exception as e:
        logger.error(f"❌ Erreur lors de la purge du cache : {e}")
        return False


def get_newsletter_subscribers() -> List[Dict[str, Any]]:
    """
    Récupère la liste formatée des abonnés à la newsletter.
    """
    try:
        subs = list_newsletter_subscribers()
        formatted = []
        for s in subs:
            if hasattr(s, "to_dict"):
                formatted.append(s.to_dict())
            elif isinstance(s, dict):
                formatted.append(s)
            else:
                formatted.append({
                    "id": getattr(s, "id", None),
                    "email": getattr(s, "email", None),
                    "created_at": str(getattr(s, "created_at", "")),
                })
        return formatted
    except Exception as e:
        logger.error(f"❌ Erreur récupération abonnés newsletter : {e}")
        return []
