from flask import flash, redirect, url_for
from flask_wtf.csrf import CSRFError

from .api import init_api_routes
from .catalog import init_catalog_routes
from .auth import init_auth_routes
from .calendar import init_calendar_routes
from .checkins import init_checkins_routes
from .checkouts import init_checkouts_routes
from .contacts import init_contacts_routes
from .dashboard import init_dashboard_routes
from .files import init_files_routes
from .newsletter import init_newsletter_routes
from .productions import init_productions_routes
from .projects import init_projects_routes
from .pre_quotes import init_pre_quotes_routes
from .pricing import init_pricing_routes
from .settings import settings_bp
from .tools import init_tools_routes
from .users import init_users_routes
from .waivers import init_waivers_routes


def init_admin_routes(app):
    init_auth_routes(app)
    init_files_routes(app)
    init_dashboard_routes(app)
    init_checkouts_routes(app)
    init_checkins_routes(app)
    init_projects_routes(app)
    init_productions_routes(app)
    init_contacts_routes(app)
    init_newsletter_routes(app)
    init_api_routes(app)
    init_waivers_routes(app)
    init_tools_routes(app)
    init_users_routes(app)
    init_pricing_routes(app)
    init_calendar_routes(app)
    init_pre_quotes_routes(app)
    init_catalog_routes(app)
    app.register_blueprint(settings_bp)

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        app.logger.warning(f"⚠️ CSRF Error: {e.description}")
        flash("Votre session a expiré. Veuillez vous reconnecter.", "error")
        return redirect(url_for('admin_login'))
