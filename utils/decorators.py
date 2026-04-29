from functools import wraps

from flask import current_app, flash, redirect, request, session, url_for


def format_date_fr(date_str: str) -> str:
    """Convertit une chaîne de date au format français (ex: 16 février 2026)."""
    if not date_str or date_str == "—":
        return "—"
    try:
        from utils.formatting import format_date_fr as _format
        return _format(date_str)
    except Exception:
        return date_str


def require_roles(*allowed_roles):
    """
    Décorateur pour restreindre l'accès à des rôles spécifiques.
    Suppose que `session.get('admin_user_role')` contient le rôle de l'utilisateur.

    Usage :
    @require_roles('administrator', 'manager')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. S'assurer que l'utilisateur est authentifié
            if not session.get("admin_authenticated"):
                return redirect(url_for("admin_login", next=request.url))

            # Repli en cas de session incomplète
            if not session.get("admin_user_id") and session.get("admin_user_firstname"):
                pass

            # 2. Vérifier le rôle
            user_role = session.get("admin_user_role", "User").lower()

            # Super Administrator a accès à tout
            if user_role == "super administrator":
                return f(*args, **kwargs)

            allowed = [r.lower() for r in allowed_roles]

            if user_role not in allowed:
                current_app.logger.warning(
                    f"⚠️ Tentative d'accès non autorisée : Le rôle '{user_role}' "
                    f"a tenté d'accéder à {request.url}. Autorisés : {allowed}"
                )
                flash(
                    "Vous n'avez pas les permissions nécessaires pour accéder à cette page.", "error")
                return redirect(url_for("admin_dashboard"))

            return f(*args, **kwargs)
        return decorated_function
    return decorator
