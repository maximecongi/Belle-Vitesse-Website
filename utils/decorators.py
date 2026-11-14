import re
from functools import wraps

from flask import current_app, flash, jsonify, redirect, request, session, url_for


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
    if r in ("associé", "associe", "partner"):
        return ASSOCIATE_ROLE
    return r


ADMIN_ROLES = ("administrateur", "super administrateur")

# ─────────────────────────────────────────────────────────────────────────────
# RÔLE « ASSOCIÉ » : périmètre de lecture d'un administrateur, sans aucune écriture
# ─────────────────────────────────────────────────────────────────────────────
ASSOCIATE_ROLE = "associé"
READ_ONLY_ROLES = frozenset({ASSOCIATE_ROLE})

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# Endpoints non-GET tolérés en lecture seule : authentification, simple calcul / export sans
# écriture en base, et préférences personnelles (favoris, clés MCP plafonnées en lecture).
READ_ONLY_ALLOWED_WRITE_ENDPOINTS = frozenset({
    "admin_auth.admin_login",
    "admin_auth.admin_logout",
    "admin_auth.admin_dev_switch_role",
    "admin_projects.admin_api_check_conflicts",
    "admin_tools.admin_meeting_report_pdf",
    "admin_api.admin_api_pins_create",
    "admin_api.admin_api_pins_rename",
    "admin_api.admin_api_pins_delete",
    "admin_api.admin_api_pins_reorder",
    "admin_mcp_tokens.generate_token",
    "admin_mcp_tokens.revoke_token",
    "admin_mcp_tokens.delete_token",
})

# Pages GET qui n'existent que pour écrire (formulaires de création / édition) ou qui déclenchent
# une écriture malgré le verbe GET (ex. régénération du catalogue PDF).
_READ_ONLY_BLOCKED_GET = re.compile(
    r"(^|_)(new|create|edit|duplicate|send|compose|update)(_|$)"
)
# Exceptions : pages de consultation dont l'endpoint porte un suffixe d'édition.
READ_ONLY_ALLOWED_GET_ENDPOINTS = frozenset({
    "admin_settings.admin_settings_edit",
})


def is_read_only_role(role_name):
    """Vrai si le rôle n'a qu'un accès en lecture (Associé)."""
    return normalize_role(role_name) in READ_ONLY_ROLES


def session_is_read_only():
    """Vrai si l'utilisateur connecté en session a un rôle en lecture seule."""
    return is_read_only_role(session.get("admin_user_role"))


def effective_role_for_access(role_name):
    """Rôle de référence pour les contrôles d'accès en lecture : un Associé lit comme un Administrateur."""
    role = normalize_role(role_name)
    return "administrateur" if role in READ_ONLY_ROLES else role


def is_read_only_request_blocked(endpoint=None, method=None):
    """Indique si la requête courante est une écriture interdite à un rôle en lecture seule."""
    endpoint = endpoint if endpoint is not None else (request.endpoint or "")
    method = (method or request.method or "GET").upper()
    if method not in SAFE_METHODS:
        return endpoint not in READ_ONLY_ALLOWED_WRITE_ENDPOINTS
    if endpoint in READ_ONLY_ALLOWED_GET_ENDPOINTS:
        return False
    short_name = endpoint.split(".", 1)[-1]
    return bool(_READ_ONLY_BLOCKED_GET.search(short_name))


def _wants_json():
    return (
        request.is_json
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.accept_mimetypes.best == "application/json"
        or request.path.startswith("/admin/api/")
    )


def read_only_denied_response():
    """Réponse standard lorsqu'un Associé tente une action d'écriture."""
    message = "Accès en lecture seule : votre rôle Associé ne permet pas de modifier les données."
    current_app.logger.warning(
        f"🔒 Écriture refusée (lecture seule) : {request.method} {request.path} "
        f"par l'utilisateur #{session.get('admin_user_id')}"
    )
    if _wants_json():
        return jsonify({"status": "error", "success": False, "error": message, "message": message}), 403
    flash(message, "warning")
    referrer = request.referrer or ""
    if referrer.startswith(request.host_url) and referrer.rstrip("/") != request.url.rstrip("/"):
        return redirect(referrer)
    return redirect(url_for("admin_dashboard.admin_dashboard"))


def enforce_read_only_guard():
    """
    Garde globale (before_request) : bloque toute écriture d'un rôle en lecture seule sur l'ERP,
    quel que soit le décorateur de la route. Défense en profondeur avec `require_roles`.
    """
    if not request.path.startswith("/admin"):
        return None
    if not session.get("admin_authenticated") or not session_is_read_only():
        return None
    if is_read_only_request_blocked():
        return read_only_denied_response()
    return None


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

            # Associé : accès en lecture aux pages de l'administrateur, aucune écriture
            if user_role in READ_ONLY_ROLES:
                if is_read_only_request_blocked():
                    return read_only_denied_response()
                user_role = "administrateur"

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

