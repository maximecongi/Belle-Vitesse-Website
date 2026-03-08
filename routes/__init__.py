import os

from flask import g, render_template
from werkzeug.exceptions import HTTPException

from routes.admin import init_admin_routes
from routes.web import init_web_routes
from routes.checkout import init_checkout_routes
from routes.checkin import init_checkin_routes
from routes.users import init_users_routes


def init_routes(app):
    """Register all route modules."""
    init_admin_routes(app)
    init_web_routes(app)
    init_checkout_routes(app)
    init_checkin_routes(app)
    init_users_routes(app)


def init_error_handlers(app):
    if os.getenv("FLASK_ENV") == "production":

        @app.errorhandler(HTTPException)
        def handle_http_exception(e):
            return render_template(
                "error.html",
                error_title=f"{e.code} - {e.name}",
                error_message=e.description,
            ), e.code

        @app.errorhandler(Exception)
        def handle_exception(e):
            app.logger.error(f"❌ Unhandled exception: {e}", exc_info=True)
            g._rendering_error = True
            return render_template(
                "error.html",
                error_title="500 - Internal Server Error",
                error_message="An unexpected error occurred.",
            ), 500
