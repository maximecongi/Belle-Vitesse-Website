"""Décorateurs de sécurité et d'exécution dans le contexte Flask pour les outils MCP."""
import json
import time
from functools import wraps
from typing import Any, Dict

from mcp_auth.auth import check_mcp_scope
from mcp_server.context import CURRENT_MCP_USER, CURRENT_MCP_IP


def get_flask_app():
    """Import dynamique réutilisable de l'instance de l'application Flask."""
    from mcp_server.core import flask_app
    return flask_app


def require_mcp_scope(required_scope: str = "read_only"):
    """
    Décorateur de sécurité MCP : Vérifie que la clé API possède le scope nécessaire.
    - 'read_only' : consultation des données
    - 'write' : création et édition de données
    - 'admin' : suppressions et modifications système
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            flask_app = get_flask_app()
            user = CURRENT_MCP_USER.get() or getattr(flask_app, "current_mcp_user", None)
            if user and not check_mcp_scope(user, required_scope):
                user_scope = getattr(user, "mcp_scope", "read_only")
                return {
                    "status": "error",
                    "error_code": 403,
                    "message": (
                        f"⛔ ACCÈS REFUSÉ : L'outil '{func.__name__}' exige le niveau de privilège MCP '{required_scope}'. "
                        f"Votre clé d'accès possède actuellement le scope '{user_scope}'. "
                        "Veuillez utiliser une clé API IA avec des privilèges supérieurs."
                    )
                }
            return func(*args, **kwargs)
        return wrapper
    return decorator


def run_in_flask_context(func):
    """Exécute une fonction d'outil MCP dans le contexte Flask avec enregistrement automatique d'audit."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        flask_app = get_flask_app()
        user = CURRENT_MCP_USER.get() or getattr(flask_app, "current_mcp_user", None)
        client_ip = CURRENT_MCP_IP.get() or getattr(flask_app, "current_mcp_ip", "unknown")
        status = "success"
        error_msg = None
        result = None

        with flask_app.app_context():
            try:
                result = func(*args, **kwargs)
                if isinstance(result, dict):
                    if result.get("status") == "requires_confirmation":
                        status = "requires_confirmation"
                    elif result.get("status") == "error" or result.get("success") is False:
                        status = "error"
                        error_msg = result.get("message") or result.get("error")
            except PermissionError as pe:
                from models import db
                try:
                    db.session.rollback()
                except Exception:
                    pass
                status = "blocked_403"
                error_msg = str(pe)
                result = {
                    "status": "error",
                    "error_code": 403,
                    "message": f"⛔ ACCÈS REFUSÉ : {str(pe)}",
                }
            except Exception as ex:
                from models import db
                try:
                    db.session.rollback()
                except Exception:
                    pass
                status = "error"
                error_msg = str(ex)
                result = {
                    "status": "error",
                    "error_code": 500,
                    "message": f"❌ Erreur lors de l'exécution de l'outil '{func.__name__}' : {str(ex)}",
                }
            finally:
                exec_time_ms = int((time.time() - start_time) * 1000)
                try:
                    from models import McpAuditLog, db
                    user_id = getattr(user, "id", None)
                    token_id = getattr(user, "current_token_id", None)
                    args_json = None
                    if kwargs or args:
                        try:
                            args_payload = {"args": args, "kwargs": kwargs} if args else kwargs
                            args_json = json.dumps(args_payload, ensure_ascii=False, default=str)[:2000]
                        except Exception:
                            args_json = str(kwargs or args)[:2000]

                    audit_entry = McpAuditLog(
                        user_id=user_id,
                        token_id=token_id,
                        tool_name=func.__name__,
                        arguments_json=args_json,
                        status=status,
                        error_message=error_msg[:1000] if error_msg else None,
                        ip_address=client_ip,
                        execution_time_ms=exec_time_ms,
                    )
                    db.session.add(audit_entry)
                    db.session.commit()
                except Exception as audit_err:
                    from mcp_server.config import logger
                    logger.error(f"❌ Erreur enregistrement audit MCP: {audit_err}")
                    try:
                        db.session.rollback()
                    except Exception:
                        pass

            return result
    return wrapper
