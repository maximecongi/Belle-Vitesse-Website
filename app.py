import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from flask import Flask, request, session, url_for, g, abort

from extensions import cache, compress, limiter, csrf
from routes import init_routes, init_error_handlers
from utils.database import (
    init_cache,
    get_vehicles,
    get_all_static,
    get_heads,
    get_grips_categories,
)
from utils.database import init_checkout_db, init_checkin_db
from models import db, User
from services.admin.status_mapping import (
    get_inspection_key,
    get_checkpoint_key,
    get_checkpoint_status,
    INSPECTION_STATUS_MAP,
    CHECKPOINT_STATUS_MAP
)
from services.sql_logger import init_sql_logger

SUPPORTED_LANGS = ('en', 'fr')
DEFAULT_LANG = 'en'

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

    # Redis Cache Config
    if os.getenv("FLASK_ENV") == "production":
        app.config["CACHE_TYPE"] = "RedisCache"
        app.config["CACHE_REDIS_HOST"] = os.getenv("REDIS_HOST", "bv_redis")
        app.config["CACHE_REDIS_PORT"] = int(os.getenv("REDIS_PORT", 6379))
        app.config["CACHE_REDIS_DB"] = int(
            os.getenv("REDIS_DB_FLASK_CACHING", 0))
        app.config["CACHE_REDIS_URL"] = os.getenv(
            "REDIS_URL", f"redis://{app.config['CACHE_REDIS_HOST']}:{app.config['CACHE_REDIS_PORT']}/{app.config['CACHE_REDIS_DB']}")
    else:
        app.config["CACHE_TYPE"] = "SimpleCache"
    app.config["CACHE_DEFAULT_TIMEOUT"] = 86400  # 24h
    app.config["CACHE_KEY_PREFIX"] = "bv_cache_"
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
    app.config["SQLALCHEMY_POOL_RECYCLE"] = 280
    app.config["SQLALCHEMY_POOL_PRE_PING"] = True
    app.config["SQLALCHEMY_POOL_SIZE"] = 5
    app.config["SQLALCHEMY_MAX_OVERFLOW"] = 10
    app.config["SQLALCHEMY_POOL_TIMEOUT"] = 10

    # Session Config
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12)
    if os.getenv("FLASK_ENV") == "production":
        app.config["OUTPUT_FOLDER"] = Path("/app/output")
        app.config["BACKUPS_FOLDER"] = Path("/app/backups")
        app.config["LOGS_FOLDER"] = Path("/app/logs")
    else:
        app.config["OUTPUT_FOLDER"] = Path(
            "/Users/maximecongi/kDrive/Common documents/BELLE VITESSE/2_WEBSITE/2_WEBSITE/output")
        app.config["BACKUPS_FOLDER"] = Path(
            "/Users/maximecongi/kDrive/Common documents/BELLE VITESSE/2_WEBSITE/2_WEBSITE/backups")
        app.config["LOGS_FOLDER"] = Path(
            "/Users/maximecongi/kDrive/Common documents/BELLE VITESSE/2_WEBSITE/2_WEBSITE/logs")

    app.config["OUTPUT_FOLDER"].mkdir(parents=True, exist_ok=True)
    app.config["BACKUPS_FOLDER"].mkdir(parents=True, exist_ok=True)
    app.config["LOGS_FOLDER"].mkdir(parents=True, exist_ok=True)

    # Limiter Config
    if os.getenv("FLASK_ENV") == "production":
        app.config["RATELIMIT_STORAGE_URI"] = os.getenv(
            "REDIS_URL", f"redis://{app.config['CACHE_REDIS_HOST']}:{app.config['CACHE_REDIS_PORT']}/{app.config['CACHE_REDIS_DB']}")
    else:
        app.config["RATELIMIT_STORAGE_URI"] = "memory://"

    # Initialize extensions
    cache.init_app(app)
    compress.init_app(app)
    limiter.init_app(app)
    csrf.init_app(app)
    init_cache(cache)
    db.init_app(app)

    # Initialize SQL Logger
    init_sql_logger(app, db)

    # Initialize routes & error handlers
    init_routes(app)
    init_error_handlers(app)

    # Custom Jinja2 Filters
    import json
    import ast
    app.jinja_env.filters["slugify"] = lambda s: s.lower().replace(" ", "_")

    def _from_json(s):
        if not isinstance(s, str):
            return s
        # Try JSON first, then Python literal syntax (tuples, etc.)
        try:
            return json.loads(s)
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            result = ast.literal_eval(s)
            # Convert tuples to lists for consistency
            if isinstance(result, list):
                return [list(item) if isinstance(item, tuple) else item for item in result]
            return result
        except (ValueError, SyntaxError):
            return []

    app.jinja_env.filters["from_json"] = _from_json

    # ── i18n: URL-based language handling ─────────────────────

    @app.url_value_preprocessor
    def pull_lang(endpoint, values):
        """Extract lang from URL, store in g.lang, save to session."""
        if values and 'lang' in values:
            lang = values.pop('lang')
            if lang in SUPPORTED_LANGS:
                g.lang = lang
                session['lang'] = lang
            else:
                abort(404)
        else:
            g.lang = session.get('lang', DEFAULT_LANG)

    @app.url_defaults
    def inject_lang(endpoint, values):
        """Automatically inject lang into url_for() for routes that need it."""
        if 'lang' in values or not app.url_map.is_endpoint_expecting(endpoint, 'lang'):
            return
        values['lang'] = g.get('lang', session.get('lang', DEFAULT_LANG))

    # ── i18n: translation helpers ────────────────────────────

    def t(fields, key):
        """Translate a dynamic-content field (suffixed columns).
        Fallback: key_fr → key_en → key (original column)."""
        lang = g.get('lang', DEFAULT_LANG)
        return (fields.get(f'{key}_{lang}')
                or fields.get(f'{key}_en')
                or fields.get(key, ''))

    def ts(key):
        """Translate a static UI string (row-per-language table).
        Fallback: current lang → en → raw key."""
        lang = g.get('lang', DEFAULT_LANG)
        static_all = get_all_static()
        return (static_all.get(lang, {}).get(key)
                or static_all.get('en', {}).get(key, key))

    def alt_url(target_lang):
        """Generate the URL for the current page in a different language."""
        if request.endpoint and request.view_args is not None:
            try:
                args = dict(request.view_args)
                args['lang'] = target_lang
                return url_for(request.endpoint, **args)
            except Exception:
                pass
        return url_for('home', lang=target_lang)

    # Context Processors (Globals)
    @app.context_processor
    def inject_globals():
        # Skip heavy DB calls for error pages to prevent cascading failures
        if getattr(g, '_rendering_error', False):
            return {
                "now": datetime.now(timezone.utc),
                "is_admin": request.path.startswith('/admin'),
                "lang": g.get('lang', DEFAULT_LANG),
                "t": t, "ts": ts, "alt_url": alt_url,
            }

        is_admin = request.path.startswith('/admin')
        lang = g.get('lang', DEFAULT_LANG)

        # Base globals
        ctx = {
            "now": datetime.now(timezone.utc),
            "is_admin": is_admin,
            "lang": lang,
            "t": t,
            "ts": ts,
            "alt_url": alt_url,
            "company_name": "Belle Vitesse SAS",
            "company_representative": "Simon Maignan",
            "company_siret": "981 514 040 00014",
            "company_address": "33 rue Maurice Gunsbourg, 94200 Ivry-sur-Seine, France",
            "company_phone": "+33 6 65 51 40 40",
            "company_email": "contact@bellevitesse.com",
            # Status Mapping Utilities
            "get_inspection_key": get_inspection_key,
            "get_checkpoint_key": get_checkpoint_key,
            "get_checkpoint_status": get_checkpoint_status,
            "INSPECTION_STATUS_MAP": INSPECTION_STATUS_MAP,
            "CHECKPOINT_STATUS_MAP": CHECKPOINT_STATUS_MAP,
        }

        def _load_db_context(is_admin):
            if is_admin:
                user_id = session.get('admin_user_id')
                user = None
                if user_id:
                    cache_key = f"user:{user_id}"
                    user = cache.get(cache_key)

                    if not user:
                        user = db.session.get(User, user_id)
                        if user:
                            cache.set(cache_key, user, timeout=300)

                return {
                    "current_user": user if user else {
                        "id": session.get('admin_user_id', 0),
                        "firstname": session.get('admin_user_firstname', ''),
                        "lastname": session.get('admin_user_lastname', ''),
                        "role": session.get('admin_user_role', 'User'),
                        "role_lower": session.get('admin_user_role', 'User').lower(),
                        "mail": "",
                        "job": "",
                        "phone": ""
                    },
                    "vehicles": get_vehicles(),
                }
            else:
                return {
                    "vehicles": get_vehicles(),
                    "heads": get_heads(),
                    "grips_categories": get_grips_categories(),
                }

        for attempt in range(2):
            try:
                ctx.update(_load_db_context(is_admin))
                break
            except Exception as e:
                if attempt == 0:
                    app.logger.warning(
                        f"⚠️ Context processor DB error (retrying): {e}")
                    continue
                app.logger.error(
                    f"❌ Context processor DB error (giving up): {e}")
                if is_admin:
                    ctx["current_user"] = {
                        "firstname": "", "lastname": "", "role": "User", "role_lower": "user"}
                    ctx["vehicles"] = []
                else:
                    ctx.update({"vehicles": [], "heads": [],
                               "grips_categories": []})

        return ctx

    @app.after_request
    def add_security_headers(response):
        """Add security headers, specifically for admin routes."""
        if request.path.startswith('/admin/'):
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
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

    # ── Scheduler : re-warm du cache toutes les 23h50 ──────────
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=warm_cache,
        trigger="interval",
        hours=23,
        minutes=50,
        id="cache_warmup",
        replace_existing=True,
    )
    scheduler.start()
    app.logger.info("⏰ Scheduler cache démarré")
    # ───────────────────────────────────────────────────────────


if __name__ == "__main__":
    app.run(debug=True, use_reloader=True, port=5001)
