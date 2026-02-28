import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from flask import Flask, request, session, redirect, url_for

from extensions import cache, limiter, csrf
from routes import init_routes, init_error_handlers
from utils.airtable import (
    init_cache,
    get_vehicles,
    get_all_static,
    get_heads,
    get_grips_categories,
)
from utils.database import init_checkout_db, init_checkin_db
from models import db


_ssh_tunnel = None


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

    # Database config (MySQL via SQLAlchemy)
    global _ssh_tunnel

    use_ssh = os.getenv("USE_SSH_TUNNEL", "false").lower() == "true"
    is_prod = os.getenv("FLASK_ENV") == "production"

    mysql_host = os.getenv("MYSQL_HOST", "localhost")
    mysql_port = 3306

    if use_ssh and not is_prod:
        from sshtunnel import SSHTunnelForwarder
        try:
            if _ssh_tunnel is None or not _ssh_tunnel.is_active:
                _ssh_tunnel = SSHTunnelForwarder(
                    (os.getenv("SSH_HOST"), 22),
                    ssh_username=os.getenv("SSH_USER"),
                    ssh_password=os.getenv("SSH_PASSWORD"),
                    remote_bind_address=(mysql_host, 3306)
                )
                _ssh_tunnel.start()
                app.logger.info(
                    f"✅ SSH Tunnel started on port {_ssh_tunnel.local_bind_port}")

            mysql_host = "127.0.0.1"
            mysql_port = _ssh_tunnel.local_bind_port
        except Exception as e:
            app.logger.error(f"❌ Failed to start SSH Tunnel: {e}")

    mysql_user = os.getenv("MYSQL_USER", "root")
    mysql_pass = os.getenv("MYSQL_PASSWORD", "")
    mysql_db = os.getenv("MYSQL_DATABASE", "bellevitesse")

    default_uri = f"mysql+mysqlconnector://{mysql_user}:{mysql_pass}@{mysql_host}:{mysql_port}/{mysql_db}"
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "SQLALCHEMY_DATABASE_URI", default_uri)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Session Config
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12)
    if os.getenv("FLASK_ENV") == "production":
        app.config["PRIVATE_FOLDER"] = Path("/app/private")
    else:
        app.config["PRIVATE_FOLDER"] = Path(
            "/Users/maximecongi/kDrive/Common documents/BELLE VITESSE/2_WEBSITE/2_WEBSITE")
    app.config["PRIVATE_FOLDER"].mkdir(parents=True, exist_ok=True)

    # Initialize extensions
    cache.init_app(app)
    limiter.init_app(app)
    csrf.init_app(app)
    init_cache(cache)
    db.init_app(app)

    # Initialize routes & error handlers
    init_routes(app)
    init_error_handlers(app)

    # Custom Jinja2 Filters
    app.jinja_env.filters["slugify"] = lambda s: s.lower().replace(" ", "_")

    # ── i18n: language switching route ────────────────────────
    @app.route("/set_lang/<lang>")
    def set_lang(lang):
        if lang in ('en', 'fr'):
            session['lang'] = lang
        return redirect(request.referrer or url_for('home'))

    # ── i18n: translation helpers ────────────────────────────
    def t(fields, key):
        """Translate a dynamic-content field (suffixed columns).
        Fallback: key_fr → key_en → key (original column)."""
        lang = session.get('lang', 'en')
        return (fields.get(f'{key}_{lang}')
                or fields.get(f'{key}_en')
                or fields.get(key, ''))

    def ts(key):
        """Translate a static UI string (row-per-language table).
        Fallback: fr value → en value → raw key."""
        lang = session.get('lang', 'en')
        static_all = get_all_static()
        return (static_all.get(lang, {}).get(key)
                or static_all.get('en', {}).get(key, key))

    # Context Processors (Globals)
    @app.context_processor
    def inject_globals():
        is_admin = request.path.startswith('/admin')
        lang = session.get('lang', 'en')

        # Base globals
        ctx = {
            "now": datetime.now(timezone.utc),
            "is_admin": is_admin,
            "lang": lang,
            "t": t,
            "ts": ts,
        }

        if is_admin:
            # Admin specific globals
            ctx["current_user"] = {
                "firstname": session.get('admin_user_firstname'),
                "lastname": session.get('admin_user_lastname'),
                "role": session.get('admin_user_role', 'User'),
                "role_lower": session.get('admin_user_role', 'User').lower()
            }
            # Vehicles are still needed for some admin displays
            ctx["vehicles"] = get_vehicles()
        else:
            # Public site globals (MySQL lookups)
            ctx.update({
                "vehicles": get_vehicles(),
                "heads": get_heads(),
                "grips_categories": get_grips_categories(),
            })

        return ctx

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
            db.create_all()
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
            get_all_static()
            app.logger.info("🔥 Cache warmé avec succès")
    except Exception as e:
        app.logger.error(f"❌ Erreur warm cache : {e}")


if os.getenv("FLASK_ENV") == "production":
    warm_cache()

if __name__ == "__main__":
    app.run(debug=True, use_reloader=True, port=5001)
