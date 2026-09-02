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

from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, request
from flask_migrate import Migrate

from config import config
from extensions import cache, compress, csrf, limiter
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
from utils.i18n import init_i18n, SUPPORTED_LANGS, DEFAULT_LANG
from utils.context_processors import init_context_processors

# Configuration


def create_app():
    """Usine de création de l'application Flask (Application Factory)."""
    env = os.getenv("FLASK_ENV", "development")
    app_config = config.get(env, config['default'])

    app = Flask(
        __name__,
        static_folder=os.getenv("STATIC_FOLDER"),
        static_url_path=os.getenv("STATIC_URL_PATH"),
    )
    app.config.from_object(app_config)
    app.config['FLASK_ENV'] = env

    # Validation de la configuration critique
    if not app.config.get("SECRET_KEY"):
        if env == "production":
            raise RuntimeError("❌ SECRET_KEY doit être définie en production !")
        app.config["SECRET_KEY"] = "dev-only-insecure-key-change-in-production"
        app.logger.warning("⚠️ SECRET_KEY non définie — clé par défaut utilisée (dev uniquement)")

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
    for folder in ["OUTPUT_FOLDER", "BACKUPS_FOLDER", "LOGS_FOLDER", "ARCLIGHT_UPLOAD_DIR"]:
        if folder in app.config:
            Path(app.config[folder]).mkdir(parents=True, exist_ok=True)

    # Initialisation des extensions
    cache.init_app(app)
    compress.init_app(app)
    limiter.init_app(app)
    csrf.init_app(app)
    init_cache(cache)
    db.init_app(app)
    Migrate(app, db)

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
        """Ajoute des en-têtes de sécurité, particulièrement pour les routes admin."""
        if request.path.startswith('/admin/'):
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
            response.headers['X-Content-Type-Options'] = 'nosniff'

        if os.getenv("FLASK_ENV") == "production":
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        # Content Security Policy (CSP) robust
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com https://cdn.jsdelivr.net https://code.jquery.com https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://unpkg.com; "
            "img-src 'self' data: https: http:; "
            "font-src 'self' data: https://fonts.gstatic.com; "
            "connect-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com; "
            "frame-src 'self'; "
            "object-src 'none';"
        )
        response.headers['Content-Security-Policy'] = csp

        # Gestion de la politique de cache HTTP pour les assets statiques
        if request.path.startswith('/static/'):
            if os.getenv("FLASK_ENV") == "production":
                response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
            else:
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'

        return response

    # Initialisation de la DB et migrations de schéma
    if os.getenv("RUN_MIGRATIONS") == "true":
        try:
            from flask_migrate import upgrade as _upgrade
            with app.app_context():
                _upgrade()
                app.logger.info("✅ Database schema migrated successfully via Flask-Migrate.")
        except Exception as e:
            app.logger.error(f"❌ Failed to run database migrations: {e}")
    elif os.getenv("FLASK_ENV") != "production":
        try:
            with app.app_context():
                db.create_all()
                app.logger.info("✅ Development database tables created successfully (db.create_all).")
        except Exception as e:
            app.logger.error(f"❌ Failed to initialize dev database: {e}")

    return app


app = create_app()


def warm_cache():
    """Pré-charge (warmup) le cache avec les données Airtable pour améliorer les performances."""
    try:
        with app.app_context():
            get_vehicles()
            get_heads()
            get_grips_categories()
            get_all_static()
            app.logger.info("🔥 Cache pré-chargé avec succès")
    except Exception as e:
        app.logger.error(f"❌ Erreur lors du pré-chargement du cache : {e}")





if __name__ == "__main__":
    app.run(debug=True, use_reloader=True, port=5001)
