from .auth import init_auth_routes
from .files import init_files_routes
from .dashboard import init_dashboard_routes
from .checkouts import init_checkouts_routes
from .checkins import init_checkins_routes
from .projects import init_projects_routes
from .productions import init_productions_routes
from .contacts import init_contacts_routes
from .newsletter import init_newsletter_routes
from .api import init_api_routes
from .waivers import init_waivers_routes
from flask_wtf.csrf import CSRFError
from flask import redirect, url_for


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

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        app.logger.warning(f"⚠️ CSRF Error: {e.description}")
        return redirect(url_for('admin_dashboard'))
