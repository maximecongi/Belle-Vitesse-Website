import os
from pathlib import Path
from datetime import datetime, timezone
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
    format_checkpoint_status,
    format_inspection_status,
    INSPECTION_STATUS_MAP,
    CHECKPOINT_STATUS_MAP
)
from services.admin.sql_logger import init_sql_logger

from config import config

SUPPORTED_LANGS = ('en', 'fr')
DEFAULT_LANG = 'en'

_ssh_tunnel = None


def create_app():
    env = os.getenv("FLASK_ENV", "development")
    app_config = config.get(env, config['default'])
    
    app = Flask(
        __name__,
        static_folder=os.getenv("STATIC_FOLDER"),
        static_url_path=os.getenv("STATIC_URL_PATH"),
    )
    app.config.from_object(app_config)

    # Proxy Fix for SSL behind Traefik
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # SSH Tunnel (Development only)
    global _ssh_tunnel
    if env != "production":
        from utils.ssh_helper import start_ssh_tunnel
        tunnel, local_port = start_ssh_tunnel(app.config, app.logger, existing_tunnel=_ssh_tunnel)
        
        if tunnel:
            _ssh_tunnel = tunnel
            mysql_user = app.config.get("MYSQL_USER", "root")
            mysql_pass = app.config.get("MYSQL_PASS", "")
            mysql_db = app.config.get("MYSQL_DB", "bellevitesse")
            app.config["SQLALCHEMY_DATABASE_URI"] = f"mysql+mysqlconnector://{mysql_user}:{mysql_pass}@127.0.0.1:{local_port}/{mysql_db}"

    # Ensure folders exist
    for folder in ["OUTPUT_FOLDER", "BACKUPS_FOLDER", "LOGS_FOLDER", "ARCLIGHT_UPLOAD_DIR"]:
        if folder in app.config:
            Path(app.config[folder]).mkdir(parents=True, exist_ok=True)

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
            "format_inspection_status": format_inspection_status,
            "format_checkpoint_status": format_checkpoint_status,
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
    import threading
    threading.Thread(target=warm_cache, daemon=True).start()

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
