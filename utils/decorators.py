from functools import wraps

from flask import current_app, flash, redirect, request, session, url_for


def require_roles(*allowed_roles):
    """
    Decorator to restrict access to specific roles.
    Assumes `session.get('admin_user_role')` stores the user's role.

    Usage:
    @require_roles('administrator', 'manager')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Ensure user is authenticated
            if not session.get("admin_authenticated"):
                return redirect(url_for("admin_login", next=request.url))

            # Session repair fallback
            if not session.get("admin_user_id") and session.get("admin_user_firstname"):
                pass

            # 2. Check Role
            user_role = session.get("admin_user_role", "User").lower()
            allowed = [r.lower() for r in allowed_roles]

            if user_role not in allowed:
                current_app.logger.warning(
                    f"⚠️ Unauthorized access attempt: User role '{user_role}' "
                    f"attempted to access {request.url}. Allowed: {allowed}"
                )
                flash(
                    "Vous n'avez pas les permissions nécessaires pour accéder à cette page.", "error")
                return redirect(url_for("admin_dashboard"))

            return f(*args, **kwargs)
        return decorated_function
    return decorator
