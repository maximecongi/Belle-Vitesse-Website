from routes.api.auth import api_auth_bp
from routes.api.checkouts import api_checkouts_bp
from routes.api.checkins import api_checkins_bp
from routes.api.projects import api_projects_bp
from routes.api.productions import api_productions_bp
from routes.api.contacts import api_contacts_bp
from routes.api.dashboard import api_dashboard_bp
from routes.api.waivers import api_waivers_bp
from routes.api.arclight import api_arclight_bp
from extensions import csrf


def init_api_v1_routes(app):
    """Register all API v1 blueprints and exempt them from CSRF (JWT auth)."""
    blueprints = [
        api_auth_bp,
        api_checkouts_bp,
        api_checkins_bp,
        api_projects_bp,
        api_productions_bp,
        api_contacts_bp,
        api_dashboard_bp,
        api_waivers_bp,
        api_arclight_bp,
    ]
    for bp in blueprints:
        csrf.exempt(bp)
        app.register_blueprint(bp, url_prefix="/api/v1")


    from routes.api.meta import api_meta_bp
    app.register_blueprint(api_meta_bp, url_prefix="/api/v1")
