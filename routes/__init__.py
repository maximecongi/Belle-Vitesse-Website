import os

from flask import flash, g, redirect, render_template, request, url_for
from werkzeug.exceptions import HTTPException

from routes.admin import init_admin_routes
from routes.api import init_api_v1_routes
from routes.public.checkin import init_checkin_routes
from routes.public.checkout import init_checkout_routes
from routes.public.incidents import init_incident_public_routes
from routes.public.waivers import init_waiver_routes
from routes.public.calendar_feed import cal_feed_bp
from routes.public.web import init_web_routes


def init_routes(app):
    """Register all route modules."""
    init_admin_routes(app)
    init_web_routes(app)
    init_checkout_routes(app)
    init_checkin_routes(app)
    init_waiver_routes(app)
    init_incident_public_routes(app)
    init_api_v1_routes(app)

    # Flux calendrier ICS public (exempt CSRF — accédé par les apps calendrier)
    from extensions import csrf
    csrf.exempt(cal_feed_bp)
    app.register_blueprint(cal_feed_bp)


def init_error_handlers(app):
    if os.getenv("FLASK_ENV") == "production":

        @app.errorhandler(HTTPException)
        def handle_http_exception(e):
            if request.path.startswith('/admin'):
                is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json
                if e.code == 401:
                    if is_ajax:
                        return {"status": "error", "message": "Session expirée. Veuillez vous reconnecter."}, 401
                    flash("Session expirée. Veuillez vous reconnecter.", "error")
                    return redirect(url_for('admin_login'))
                elif e.code == 403:
                    if is_ajax:
                        return {"status": "error", "message": "Accès refusé. Vous n'avez pas les autorisations nécessaires."}, 403
                    flash("Accès refusé : vous n'avez pas les autorisations nécessaires.", "error")
                    return redirect(url_for('admin_dashboard'))
                app.logger.warning(
                    f"⚠️ Erreur HTTP {e.code} sur {request.path}: {e.description}")

            is_admin = request.path.startswith('/admin')
            return render_template(
                "public/error.html",
                error_title=f"{e.code} - {e.name}",
                error_message=e.description,
                return_url=url_for('admin_dashboard') if is_admin else url_for('home'),
                return_label="Retourner au tableau de bord" if is_admin else "Return to Home",
            ), e.code

        @app.errorhandler(Exception)
        def handle_exception(e):
            app.logger.error(f"❌ Unhandled exception: {e}", exc_info=True)
            g._rendering_error = True

            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json
            if is_ajax:
                return {"status": "error", "message": "Une erreur serveur interne est survenue."}, 500

            is_admin = request.path.startswith('/admin')
            return render_template(
                "public/error.html",
                error_title="500 - Erreur Serveur Interne" if is_admin else "500 - Internal Server Error",
                error_message=(
                    "Une erreur inattendue est survenue dans le panneau d'administration. L'incident a été consigné dans les journaux."
                    if is_admin else
                    "An unexpected error occurred."
                ),
                return_url=url_for('admin_dashboard') if is_admin else url_for('home'),
                return_label="Retourner au tableau de bord" if is_admin else "Return to Home",
            ), 500
