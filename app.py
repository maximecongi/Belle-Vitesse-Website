import os
from dotenv import load_dotenv

load_dotenv()

# En développement local sur macOS, utiliser PyMySQL comme pilote MySQLdb
# pour contourner l'erreur de chargement de mysql_native_password présente sur MySQL 9+
if os.getenv("FLASK_ENV") != "production":
    try:
        import pymysql

        pymysql.install_as_MySQLdb()
    except ImportError:
        pass

from pathlib import Path

from flask import Flask, request
from flask_migrate import Migrate

from config import config
from extensions import cache, compress, csrf, limiter, server_session
from models import db
from routes import init_error_handlers, init_routes
from services.admin.sql_logger import init_sql_logger
from utils.database import (
    get_all_static,
    get_grips_categories,
    get_heads,
    get_vehicles,
    init_cache,
)
from utils.keepalive import init_tcp_keepalive
from utils.jinja_filters import init_jinja_filters
from utils.i18n import init_i18n
from utils.context_processors import init_context_processors

# Configuration


def create_app():
    """Usine de création de l'application Flask (Application Factory)."""
    env = os.getenv("FLASK_ENV", "development")
    app_config = config.get(env, config["default"])

    app = Flask(
        __name__,
        static_folder=os.getenv("STATIC_FOLDER"),
        static_url_path=os.getenv("STATIC_URL_PATH"),
    )
    app.config.from_object(app_config)
    app.config["FLASK_ENV"] = env
    app.url_map.strict_slashes = False

    # Validation de la configuration critique
    if not app.config.get("SECRET_KEY"):
        if env == "production":
            raise RuntimeError("❌ SECRET_KEY doit être définie en production !")
        app.config["SECRET_KEY"] = "dev-only-insecure-key-change-in-production"
        app.logger.warning(
            "⚠️ SECRET_KEY non définie — clé par défaut utilisée (dev uniquement)"
        )

    if env == "production":
        hmac_key = os.getenv("HASH_SECRET_KEY") or app.config.get("SECRET_KEY")
        if not hmac_key or hmac_key in (
            "dev-only-insecure-key-change-in-production",
            "fallback_secret_for_dev_only",
            "fallback-secret-for-dev-only-change-in-prod",
        ):
            raise RuntimeError(
                "❌ HASH_SECRET_KEY (ou SECRET_KEY robuste) doit être définie en production !"
            )

    # Correction de Proxy pour SSL derrière Traefik (nécessaire pour url_for HTTPS et détection d'IP)
    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Tunnel SSH (uniquement en développement pour accéder à la DB distante)
    if env == "development":
        from utils.ssh_helper import get_ssh_tunnel

        tunnel, local_port = get_ssh_tunnel()

        if tunnel:
            mysql_user = os.getenv("MYSQL_USER", "root")
            mysql_pass = os.getenv("MYSQL_PASSWORD", "")
            mysql_db = os.getenv("MYSQL_DATABASE", "bellevitesse")
            app.config["SQLALCHEMY_DATABASE_URI"] = (
                f"mysql+mysqldb://{mysql_user}:{mysql_pass}"
                f"@127.0.0.1:{local_port}/{mysql_db}"
            )
    # S'assurer que les dossiers nécessaires existent sur le serveur
    for folder in ["OUTPUT_FOLDER", "BACKUPS_FOLDER", "LOGS_FOLDER"]:
        if folder in app.config:
            try:
                Path(app.config[folder]).mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

    # Initialisation des extensions
    cache.init_app(app)
    compress.init_app(app)
    limiter.init_app(app)
    csrf.init_app(app)

    # Initialisation de Flask-Session (côté serveur avec Redis)
    session_type = app.config.get("SESSION_TYPE")
    if session_type == "redis":
        from redis import Redis

        session_redis = app.config.get("SESSION_REDIS")
        if session_redis is None:
            redis_host = app.config.get(
                "REDIS_HOST", "bv_redis" if env == "production" else "localhost"
            )
            redis_port = int(app.config.get("REDIS_PORT", 6379))
            redis_db = int(app.config.get("REDIS_DB_SESSION", 2))
            redis_password = os.getenv("REDIS_PASSWORD", None)
            try:
                session_redis = Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    password=redis_password,
                    socket_connect_timeout=2.0,
                    socket_timeout=3.0,
                )
                session_redis.ping()
                app.config["SESSION_REDIS"] = session_redis
                server_session.init_app(app)
                app.logger.info(
                    "✅ Flask-Session initialisé avec Redis (db=%s sur %s:%s)",
                    redis_db,
                    redis_host,
                    redis_port,
                )
            except Exception as err:
                app.logger.warning(
                    "⚠️ Redis non joignable pour Flask-Session (%s:%s/db%s: %s). "
                    "Repli automatique sur sessions cookies signées.",
                    redis_host,
                    redis_port,
                    redis_db,
                    err,
                )
        else:
            server_session.init_app(app)
    elif session_type and session_type != "null":
        server_session.init_app(app)

    init_cache(cache)
    db.init_app(app)
    Migrate(app, db, render_as_batch=True)

    # Journalisation des requêtes SQL
    init_sql_logger(app, db)

    # Initialisation des routes et des gestionnaires d'erreurs
    init_routes(app)
    init_error_handlers(app)

    # TCP Keepalive sur les connexions DB
    init_tcp_keepalive(app)

    # Filtres Jinja2 personnalisés
    init_jinja_filters(app)

    # i18n : Gestion de la langue et de la traduction
    init_i18n(app)

    # Processeurs de Contexte (Variables Globales pour les Templates)
    init_context_processors(app)

    # En production, vérifier et régénérer les bundles CSS si absents ou obsolètes
    if env == "production":
        try:
            from scripts.build_bundles import ensure_bundles_fresh

            ensure_bundles_fresh(app.static_folder)
        except Exception as e:
            app.logger.warning(
                f"⚠️ Impossible de vérifier la fraîcheur des bundles CSS : {e}"
            )

    @app.route("/health")
    def health_check():
        """Route de vérification de l'état de l'application (health check)."""
        try:
            from sqlalchemy import text

            db.session.execute(text("SELECT 1"))
            return {"status": "healthy", "database": "up"}, 200
        except Exception as e:
            app.logger.error(f"❌ Healthcheck failed: {e}")
            return {"status": "unhealthy", "error": str(e)}, 500

    @app.after_request
    def add_security_headers(response):
        """Ajoute des en-têtes de sécurité standard sur l'ensemble des réponses HTTP."""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"

        if os.getenv("FLASK_ENV") == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Content Security Policy (CSP) robust
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com https://cdn.jsdelivr.net https://code.jquery.com https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://unpkg.com; "
            "img-src 'self' data: blob: https: http:; "
            "font-src 'self' data: https://fonts.gstatic.com; "
            "connect-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com; "
            "frame-src 'self'; "
            "object-src 'none';"
        )
        response.headers["Content-Security-Policy"] = csp

        # Gestion de la politique de cache HTTP pour les assets statiques
        if request.path.startswith("/static/"):
            if os.getenv("FLASK_ENV") == "production":
                # Si l'asset dispose d'un paramètre de version ?v=, il peut être mis en cache de façon immuable.
                # Sinon, forcer la revalidation avec max-age court pour éviter le blocage des clients.
                if "v" in request.args:
                    response.headers["Cache-Control"] = (
                        "public, max-age=31536000, immutable"
                    )
                else:
                    response.headers["Cache-Control"] = (
                        "public, max-age=3600, must-revalidate"
                    )
            else:
                response.headers["Cache-Control"] = (
                    "no-cache, no-store, must-revalidate"
                )

        return response

    @app.teardown_request
    def teardown_request_cleanup(exception=None):
        """Assure le rollback systématique des transactions SQLAlchemy en cas d'erreur non interceptée."""
        if exception:
            try:
                db.session.rollback()
            except Exception:
                pass

    # Initialisation de la DB et migrations de schéma
    if os.getenv("RUN_MIGRATIONS") == "true":
        try:
            from flask_migrate import upgrade as _upgrade

            with app.app_context():
                _upgrade()
                app.logger.info(
                    "✅ Database schema migrated successfully via Flask-Migrate."
                )
        except Exception as e:
            app.logger.error(f"❌ Failed to run database migrations: {e}")
    elif os.getenv("FLASK_ENV") != "production":
        try:
            with app.app_context():
                db.create_all()
                app.logger.info(
                    "✅ Development database tables created successfully (db.create_all)."
                )
        except Exception as e:
            app.logger.error(f"❌ Failed to initialize dev database: {e}")

    return app


_app_instance = None


def __getattr__(name):
    """Accesseur paresseux (PEP 562) pour l'instance `app` évitant les instanciations prématurées à l'import."""
    if name == "app":
        global _app_instance
        if _app_instance is None:
            _app_instance = create_app()
        return _app_instance
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def warm_cache(target_app=None):
    """Pré-charge (warmup) le cache avec les données Airtable pour améliorer les performances."""
    a = target_app
    if a is None:
        global _app_instance
        if _app_instance is None:
            _app_instance = create_app()
        a = _app_instance
    try:
        with a.app_context():
            get_vehicles()
            get_heads()
            get_grips_categories()
            get_all_static()
            a.logger.info("🔥 Cache pré-chargé avec succès")
    except Exception as e:
        a.logger.error(f"❌ Erreur lors du pré-chargement du cache : {e}")


if __name__ == "__main__":
    current_flask_app = create_app()
    current_flask_app.run(debug=True, use_reloader=True, port=5001)
