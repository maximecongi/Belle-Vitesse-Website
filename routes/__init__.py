import os

from flask import flash, g, redirect, render_template, request, url_for
from werkzeug.exceptions import HTTPException

from routes.admin import init_admin_routes
from routes.api import init_api_v1_routes
from routes.public.checkin import init_checkin_routes
from routes.public.checkout import init_checkout_routes
from routes.public.waivers import init_waiver_routes
from routes.public.web import init_web_routes


def init_routes(app):
    """Register all route modules."""
    init_admin_routes(app)
    init_web_routes(app)
    init_checkout_routes(app)
    init_checkin_routes(app)
    init_waiver_routes(app)
    init_api_v1_routes(app)


def init_error_handlers(app):
    if os.getenv("FLASK_ENV") == "production":

        @app.errorhandler(HTTPException)
        def handle_http_exception(e):
            # Routes admin : redirige vers login au lieu d'afficher une page publique
            if request.path.startswith('/admin'):
                if e.code in (401, 403):
                    flash("Session expirée. Veuillez vous reconnecter.", "error")
                    return redirect(url_for('admin_login'))
                app.logger.warning(
                    f"⚠️ Erreur HTTP {e.code} sur {request.path}: {e.description}")
            return render_template(
                "public/error.html",
                error_title=f"{e.code} - {e.name}",
                error_message=e.description,
            ), e.code

        @app.errorhandler(Exception)
        def handle_exception(e):
            app.logger.error(f"❌ Unhandled exception: {e}", exc_info=True)
            # Routes admin : redirige vers login pour éviter la page blanche
            if request.path.startswith('/admin'):
                flash("Une erreur est survenue. Veuillez vous reconnecter.", "error")
                return redirect(url_for('admin_login'))
            g._rendering_error = True
            return render_template(
                "public/error.html",
                error_title="500 - Internal Server Error",
                error_message="An unexpected error occurred.",
            ), 500
