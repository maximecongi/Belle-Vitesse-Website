from flask import flash, redirect, request, url_for
from flask_wtf.csrf import CSRFError

from .api import api_bp
from .auth import auth_bp, init_auth_routes
from .booking import booking_bp
from .calendar import calendar_bp
from .catalog import catalog_bp
from .checkins import checkins_bp
from .checkouts import checkouts_bp
from .checkpoints import checkpoints_bp
from .contacts import contacts_bp
from .dashboard import dashboard_bp
from .files import files_bp
from .fleet import fleet_bp
from .incidents import incidents_bp
from .indicators import indicators_bp
from .mcp_tokens import mcp_tokens_bp
from .newsletter import newsletter_bp
from .preview import preview_bp
from .pricing import pricing_bp
from .productions import productions_bp
from .projects import projects_bp, init_projects_routes
from .settings import settings_bp
from .tools import tools_bp
from .users import users_bp
from .waivers import waivers_bp

ADMIN_BLUEPRINTS = [
    auth_bp,
    files_bp,
    dashboard_bp,
    indicators_bp,
    fleet_bp,
    checkpoints_bp,
    checkouts_bp,
    checkins_bp,
    incidents_bp,
    projects_bp,
    booking_bp,
    productions_bp,
    contacts_bp,
    newsletter_bp,
    api_bp,
    waivers_bp,
    tools_bp,
    users_bp,
    pricing_bp,
    calendar_bp,
    catalog_bp,
    settings_bp,
    mcp_tokens_bp,
    preview_bp,
]


def admin_url_alias_handler(error, endpoint, values):
    """
    Gestionnaire d'erreurs de construction d'URL Flask (url_build_error_handlers).
    Permet la résolution automatique et transparente des endpoints historiques sans nom de blueprint
    (ex: url_for('admin_projects.admin_projects_list') ou url_for('admin_auth.admin_login')) vers leur blueprint respectif.
    """
    from flask import current_app, url_for

    alias_cache = getattr(current_app, "_admin_endpoint_alias_cache", None)
    if alias_cache is None:
        alias_cache = {}
        for registered_ep in current_app.view_functions:
            if "." in registered_ep:
                _, ep_name = registered_ep.split(".", 1)
                if ep_name not in alias_cache:
                    alias_cache[ep_name] = registered_ep
        current_app._admin_endpoint_alias_cache = alias_cache

    target_ep = alias_cache.get(endpoint)
    if target_ep and target_ep != endpoint:
        return url_for(target_ep, **values)

    return None


def init_admin_routes(app):
    """Enregistre l'ensemble des Blueprints d'administration et configure l'aliasing d'URL."""
    # Installation du résolveur d'alias d'endpoint
    if admin_url_alias_handler not in app.url_build_error_handlers:
        app.url_build_error_handlers.append(admin_url_alias_handler)

    # Enregistrement des Blueprints
    for bp in ADMIN_BLUEPRINTS:
        if bp.name not in app.blueprints:
            app.register_blueprint(bp)

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        app.logger.warning(f"⚠️ CSRF Error: {e.description}")
        is_ajax = (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or request.accept_mimetypes.accept_json
        )
        if is_ajax:
            return {
                "status": "error",
                "message": "Votre session a expiré. Veuillez vous reconnecter.",
            }, 400
        flash("Votre session a expiré. Veuillez vous reconnecter.", "error")
        return redirect(url_for("admin_auth.admin_login"))
