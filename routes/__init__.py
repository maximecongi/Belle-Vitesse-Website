import os

from flask import current_app, flash, g, redirect, render_template, request, url_for
from werkzeug.exceptions import HTTPException

from routes.admin import init_admin_routes
from routes.api import init_api_v1_routes
from routes.public.calendar_feed import cal_feed_bp
from routes.public.incidents import public_incidents_bp
from routes.public.inspections import public_inspections_bp
from routes.public.waivers import public_waivers_bp
from routes.public.web import public_web_bp


def public_url_alias_handler(error, endpoint, values):
    """Fallback transparent pour résoudre les endpoints publics non préfixés

    dans url_for (ex: 'home' -> 'public_web.home',
    'checkout_verify' -> 'public_inspections.checkout_verify').
    """
    if "." in endpoint:
        return None
    prefixes = (
        "public_web.",
        "public_inspections.",
        "public_waivers.",
        "public_incidents.",
    )
    for prefix in prefixes:
        candidate = f"{prefix}{endpoint}"
        if candidate in current_app.view_functions:
            return url_for(candidate, **values)
    return None


def init_routes(app):
    """Enregistre tous les Blueprints de l'application (admin, public, API)."""
    # Enregistrement des Blueprints d'administration
    init_admin_routes(app)

    # Enregistrement des Blueprints publics
    app.register_blueprint(public_web_bp)
    app.register_blueprint(public_inspections_bp)
    app.register_blueprint(public_waivers_bp)
    app.register_blueprint(public_incidents_bp)

    # Flux calendrier ICS public (exempt CSRF — accédé par les apps calendrier)
    from extensions import csrf
    csrf.exempt(cal_feed_bp)
    app.register_blueprint(cal_feed_bp)

    # Enregistrement des Blueprints API REST v1
    init_api_v1_routes(app)

    # Handler de fallback pour les URL publiques non préfixées dans les templates et le code legacy
    if public_url_alias_handler not in app.url_build_error_handlers:
        app.url_build_error_handlers.append(public_url_alias_handler)


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
                    return redirect(url_for('admin_auth.admin_login'))
                elif e.code == 403:
                    if is_ajax:
                        return {"status": "error", "message": "Accès refusé. Vous n'avez pas les autorisations nécessaires."}, 403
                    flash("Accès refusé : vous n'avez pas les autorisations nécessaires.", "error")
                    return redirect(url_for('admin_dashboard.admin_dashboard'))
                app.logger.warning(
                    f"⚠️ Erreur HTTP {e.code} sur {request.path}: {e.description}")

            is_admin = request.path.startswith('/admin')
            return render_template(
                "public/error.html",
                error_title=f"{e.code} - {e.name}",
                error_message=e.description,
                return_url=url_for('admin_dashboard.admin_dashboard') if is_admin else url_for('home'),
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
                return_url=url_for('admin_dashboard.admin_dashboard') if is_admin else url_for('home'),
                return_label="Retourner au tableau de bord" if is_admin else "Return to Home",
            ), 500
