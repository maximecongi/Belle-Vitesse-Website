import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from flask import Flask, request

from extensions import cache, limiter, csrf
from routes import init_routes, init_error_handlers
from utils.airtable import (
    init_cache,
    get_vehicles,
    get_static_by_lang,
    get_heads,
    get_grips_categories,
)
from utils.database import init_checkout_db, init_checkin_db


def create_app():
    app = Flask(
        __name__,
        static_folder=os.getenv("STATIC_FOLDER"),
        static_url_path=os.getenv("STATIC_URL_PATH"),
    )

    # Proxy Fix for SSL behind Traefik
    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # App Config
    app.config["SECRET_KEY"] = os.getenv(
        "SECRET_KEY", "bv_super_secret_key_2026")
    app.config["CACHE_TYPE"] = "SimpleCache"
    app.config["CACHE_DEFAULT_TIMEOUT"] = 3600
    app.config["CACHE_KEY_PREFIX"] = "myapp_"
    app.config["PREFERRED_URL_SCHEME"] = "https"

    # Session Config
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12)
    if os.getenv("FLASK_ENV") == "production":
        app.config["PRIVATE_FOLDER"] = Path("/app/private")
    else:
        app.config["PRIVATE_FOLDER"] = Path(
            "Users/maximecongi/kDrive/Common documents/BELLE VITESSE/2_WEBSITE/2_PROTOTYPE")
    app.config["PRIVATE_FOLDER"].mkdir(parents=True, exist_ok=True)

    # Initialize extensions
    cache.init_app(app)
    limiter.init_app(app)
    csrf.init_app(app)
    init_cache(cache)

    # Initialize routes & error handlers
    init_routes(app)
    init_error_handlers(app)

    # Custom Jinja2 Filters
    app.jinja_env.filters["slugify"] = lambda s: s.lower().replace(" ", "_")

    # Context Processors (Globals)
    @app.context_processor
    def inject_globals():
        return {
            "vehicles": get_vehicles(),
            "heads": get_heads(),
            "grips_categories": get_grips_categories(),
            "static": get_static_by_lang("en"),
            "now": datetime.now(timezone.utc),
        }

    @app.after_request
    def add_security_headers(response):
        """Add security headers, specifically for admin routes."""
        if request.path.startswith('/admin/'):
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-Content-Type-Options'] = 'nosniff'

        if os.getenv("FLASK_ENV") == "production":
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        return response

    # Initialize DB
    try:
        with app.app_context():
            init_checkout_db()
            init_checkin_db()
            app.logger.info("✅ Databases initialized.")
    except Exception as e:
        app.logger.error(f"❌ DB Init error: {e}")

    return app


app = create_app()


def warm_cache():
    try:
        with app.app_context():
            get_vehicles()
            get_heads()
            get_grips_categories()
            get_static_by_lang("en")
            app.logger.info("🔥 Cache warmé avec succès")
    except Exception as e:
        app.logger.error(f"❌ Erreur warm cache : {e}")


if os.getenv("FLASK_ENV") == "production":
    warm_cache()

if __name__ == "__main__":
    app.run(debug=True, use_reloader=True, port=5001)
