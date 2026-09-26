from flask import flash, redirect, request, url_for
from flask_wtf.csrf import CSRFError

from .api import api_bp, init_api_routes
from .auth import auth_bp, init_auth_routes
from .booking import booking_bp, init_booking_routes
from .calendar import calendar_bp, init_calendar_routes
from .catalog import catalog_bp, init_catalog_routes
from .checkins import checkins_bp, init_checkins_routes
from .checkouts import checkouts_bp, init_checkouts_routes
from .checkpoints import checkpoints_bp, init_checkpoints_routes
from .contacts import contacts_bp, init_contacts_routes
from .dashboard import dashboard_bp, init_dashboard_routes
from .files import files_bp, init_files_routes
from .fleet import fleet_bp, init_fleet_routes
from .incidents import incidents_bp, init_incidents_routes
from .mcp_tokens import mcp_tokens_bp
from .newsletter import newsletter_bp, init_newsletter_routes
from .pricing import pricing_bp, init_pricing_routes
from .productions import productions_bp, init_productions_routes
from .projects import projects_bp, init_projects_routes
from .settings import settings_bp
from .tools import tools_bp, init_tools_routes
from .users import users_bp, init_users_routes
from .waivers import waivers_bp, init_waivers_routes

ADMIN_BLUEPRINTS = [
    auth_bp,
    files_bp,
    dashboard_bp,
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
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json
        if is_ajax:
            return {"status": "error", "message": "Votre session a expiré. Veuillez vous reconnecter."}, 400
        flash("Votre session a expiré. Veuillez vous reconnecter.", "error")
        return redirect(url_for('admin_auth.admin_login'))

