from functools import wraps

from flask import current_app, flash, redirect, request, session, url_for


def normalize_role(role_name):
    """Normalise les libellés de rôles (français et anglais) en minuscules standard."""
    if not role_name:
        return "technicien"
    r = str(role_name).strip().lower()
    if r in ("super administrator", "super administrateur"):
        return "super administrateur"
    if r in ("administrator", "administrateur"):
        return "administrateur"
    if r in ("user", "technicien"):
        return "technicien"
    return r


ADMIN_ROLES = ("administrateur", "super administrateur")


def is_admin_role(role_name):
    """Vrai si le rôle (FR ou EN, casse libre) est administrateur ou super administrateur."""
    return normalize_role(role_name) in ADMIN_ROLES


def session_is_admin():
    """Vrai si l'utilisateur connecté en session a un rôle administrateur."""
    return is_admin_role(session.get("admin_user_role"))


def is_super_admin_role(role_name):
    """Vrai uniquement pour le super administrateur (FR ou EN, casse libre)."""
    return normalize_role(role_name) == "super administrateur"


def session_is_super_admin():
    """Vrai si l'utilisateur connecté en session est super administrateur."""
    return is_super_admin_role(session.get("admin_user_role"))


def require_roles(*allowed_roles):
    """
    Décorateur pour restreindre l'accès à des rôles spécifiques.
    Suppose que `session.get('admin_user_role')` contient le rôle de l'utilisateur.

    Usage :
    @require_roles('administrateur', 'manager')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. S'assurer que l'utilisateur est authentifié
            if not session.get("admin_authenticated"):
                return redirect(url_for("admin_auth.admin_login", next=request.url))

            # Repli en cas de session incomplète
            if not session.get("admin_user_id") and session.get("admin_user_firstname"):
                pass

            # 2. Vérification d'intégrité de l'utilisateur en base (hors testing pour compatibilité tests unitaires)
            user_id = session.get("admin_user_id")
            if user_id and not current_app.config.get("TESTING"):
                from models import User, db
                user = db.session.get(User, user_id)
                if not user:
                    session.clear()
                    flash("Votre compte a été supprimé ou n'existe plus.", "error")
                    return redirect(url_for("admin_auth.admin_login"))

                # Synchronisation dynamique du rôle (sauf si simulation de rôle active en dev)
                if not session.get("admin_dev_role_simulated"):
                    db_role = normalize_role(user.role)
                    current_role = normalize_role(session.get("admin_user_role"))
                    if db_role != current_role:
                        session["admin_user_role"] = user.role

            # 3. Vérifier le rôle
            user_role = normalize_role(session.get("admin_user_role", "Technicien"))

            # Super Administrateur a accès à tout
            if user_role == "super administrateur":
                return f(*args, **kwargs)

            allowed = [normalize_role(r) for r in allowed_roles]

            if user_role not in allowed:
                current_app.logger.warning(
                    f"⚠️ Tentative d'accès non autorisée : Le rôle '{user_role}' "
                    f"a tenté d'accéder à {request.url}. Autorisés : {allowed}"
                )
                flash(
                    "Vous n'avez pas les permissions nécessaires pour accéder à cette page.", "error")
                return redirect(url_for("admin_dashboard.admin_dashboard"))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_preview_access(f):
    """
    Autorise l'accès direct en dev/testing sans login pour faciliter l'ajustement CSS/live-reload des PDF.
    En production, les routes de prévisualisation PDF sont strictement indisponibles (erreur 404).
    """
    import os
    from flask import abort

    @wraps(f)
    def decorated(*args, **kwargs):
        # Sécurité : strictement indisponible en production (erreur 404)
        if os.getenv("FLASK_ENV") == "production" or current_app.config.get("FLASK_ENV") == "production":
            abort(404)
        return f(*args, **kwargs)
    return decorated

