import os
from dotenv import load_dotenv

from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, g, request, session, url_for

from config import config
from extensions import cache, compress, csrf, limiter
from models import User, db
from routes import init_error_handlers, init_routes
from services.admin.sql_logger import init_sql_logger
from services.admin.status_mapping import (
    CHECKPOINT_STATUS_MAP,
    INSPECTION_STATUS_MAP,
    format_checkpoint_status,
    format_inspection_status,
    get_checkpoint_key,
    get_inspection_key,
)
from utils.database import (
    get_all_static,
    get_grips_categories,
    get_heads,
    get_vehicles,
    init_cache,
)

SUPPORTED_LANGS = ('en', 'fr')
DEFAULT_LANG = 'en'

load_dotenv()

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

    # Correction de Proxy pour SSL derrière Traefik (nécessaire pour url_for HTTPS)
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # Tunnel SSH (uniquement en développement pour accéder à la DB distante)
    if env != "production":
        from utils.ssh_helper import get_ssh_tunnel
        tunnel, local_port = get_ssh_tunnel()

        if tunnel:
            mysql_user = os.getenv("MYSQL_USER", "root")
            mysql_pass = os.getenv("MYSQL_PASSWORD", "")
            mysql_db = os.getenv("MYSQL_DATABASE", "bellevitesse")
            app.config["SQLALCHEMY_DATABASE_URI"] = (
                f"mysql+mysqlconnector://{mysql_user}:{mysql_pass}"
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

    # Journalisation des requêtes SQL
    init_sql_logger(app, db)

    # Initialisation des routes et des gestionnaires d'erreurs
    init_routes(app)
    init_error_handlers(app)

    # Filtres Jinja2 personnalisés
    import ast
    import json
    app.jinja_env.filters["slugify"] = lambda s: s.lower().replace(" ", "_")

    def _from_json(s):
        """Désérialise une chaîne JSON ou une syntaxe littérale Python en objet."""
        if not isinstance(s, str):
            return s
        # Tente le JSON d'abord, puis la syntaxe littérale Python (tuples, etc.)
        try:
            return json.loads(s)
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            result = ast.literal_eval(s)
            # Convertit les tuples en listes pour la cohérence
            if isinstance(result, list):
                return [list(item) if isinstance(item, tuple) else item for item in result]
            return result
        except (ValueError, SyntaxError):
            return []

    app.jinja_env.filters["from_json"] = _from_json

    # ── i18n : Gestion de la langue via l'URL ─────────────────

    @app.url_value_preprocessor
    def pull_lang(endpoint, values):
        """Extrait la langue de l'URL, la stocke dans g.lang et en session."""
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
        """Injecte automatiquement la langue dans url_for() pour les routes concernées."""
        if 'lang' in values or not app.url_map.is_endpoint_expecting(endpoint, 'lang'):
            return
        values['lang'] = g.get('lang', session.get('lang', DEFAULT_LANG))

    # ── i18n : Aides à la traduction ──────────────────────────

    def t(fields, key):
        """Traduit un champ de contenu dynamique (colonnes suffixées).
        Priorité : clé_fr → clé_en → clé (colonne originale)."""
        lang = g.get('lang', DEFAULT_LANG)
        return (fields.get(f'{key}_{lang}')
                or fields.get(f'{key}_en')
                or fields.get(key, ''))

    def ts(key):
        """Traduit une chaîne UI statique (table de traduction par ligne).
        Priorité : langue courante → en → clé brute."""
        lang = g.get('lang', DEFAULT_LANG)
        static_all = get_all_static()
        return (static_all.get(lang, {}).get(key)
                or static_all.get('en', {}).get(key, key))

    def alt_url(target_lang):
        """Génère l'URL de la page courante dans une autre langue."""
        if request.endpoint and request.view_args is not None:
            try:
                args = dict(request.view_args)
                args['lang'] = target_lang
                return url_for(request.endpoint, **args)
            except Exception:
                pass
        return url_for('home', lang=target_lang)

    # Processeurs de Contexte (Variables Globales pour les Templates)
    @app.context_processor
    def inject_globals():
        # Évite les appels DB lourds pour les pages d'erreur afin de prévenir les pannes en cascade
        if getattr(g, '_rendering_error', False):
            return {
                "now": datetime.now(timezone.utc),
                "is_admin": request.path.startswith('/admin'),
                "lang": g.get('lang', DEFAULT_LANG),
                "t": t, "ts": ts, "alt_url": alt_url,
            }

        is_admin = request.path.startswith('/admin')
        lang = g.get('lang', DEFAULT_LANG)

        # Variables globales de base
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
            # Utilitaires de mapping de statuts
            "get_inspection_key": get_inspection_key,
            "get_checkpoint_key": get_checkpoint_key,
            "format_inspection_status": format_inspection_status,
            "format_checkpoint_status": format_checkpoint_status,
            "INSPECTION_STATUS_MAP": INSPECTION_STATUS_MAP,
            "CHECKPOINT_STATUS_MAP": CHECKPOINT_STATUS_MAP,
        }

        def _load_db_context(is_admin):
            """Charge les données dynamiques depuis la base de données pour le contexte."""
            if is_admin:
                user_id = session.get('admin_user_id')
                user_dict = None
                if user_id:
                    cache_key = f"user:{user_id}"
                    user_dict = cache.get(cache_key)

                    if not user_dict:
                        user_obj = db.session.get(User, user_id)
                        if user_obj:
                            # Stocke un dict, pas un objet ORM (évite DetachedInstanceError avec Redis)
                            user_dict = {
                                "id": user_obj.id,
                                "firstname": user_obj.firstname,
                                "lastname": user_obj.lastname,
                                "role": user_obj.role,
                                "role_lower": user_obj.role.lower() if user_obj.role else "user",
                                "mail": user_obj.mail or "",
                                "job": getattr(user_obj, 'job', '') or "",
                                "phone": getattr(user_obj, 'phone', '') or "",
                            }
                            cache.set(cache_key, user_dict, timeout=300)

                return {
                    "current_user": user_dict if user_dict else {
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

        # Tentative de chargement avec retry en cas d'erreur DB
        for attempt in range(2):
            try:
                ctx.update(_load_db_context(is_admin))
                break
            except Exception as e:
                if attempt == 0:
                    app.logger.warning(
                        f"⚠️ Erreur DB dans le context processor (nouvelle tentative) : {e}")
                    continue
                app.logger.error(
                    f"❌ Erreur DB dans le context processor (abandon) : {e}")
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
        """Ajoute des en-têtes de sécurité, particulièrement pour les routes admin."""
        if request.path.startswith('/admin/'):
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
            response.headers['X-Content-Type-Options'] = 'nosniff'

        if os.getenv("FLASK_ENV") == "production":
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        return response

    # Initialisation de la DB et migrations de schéma
    def _init_database_schema():
        """Initialise le schéma de la base de données et applique les migrations manuelles."""
        with app.app_context():
            db.create_all()

            # Migrations manuelles pour les tables existantes (colonnes manquantes)
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            tables_to_check = [
                'checkout_signed_documents',
                'checkin_signed_documents',
                'pilot_waiver_signed_documents',
                'production_waiver_signed_documents'
            ]

            for table in tables_to_check:
                if inspector.has_table(table):
                    columns = [c['name'] for c in inspector.get_columns(table)]
                    if 'pdf_file_hash' not in columns:
                        try:
                            db.session.execute(
                                text(f"ALTER TABLE {table} ADD COLUMN pdf_file_hash VARCHAR(64) NULL"))
                            db.session.commit()
                            app.logger.info(
                                f"✅ Migration : {table}.pdf_file_hash ajoutée.")
                        except Exception as e:
                            db.session.rollback()
                            app.logger.warning(
                                f"⚠️ Échec de la migration pour {table} : {e}")

    try:
        _init_database_schema()
        app.logger.info("✅ Schéma de base de données initialisé.")
    except Exception as e:
        app.logger.error(f"❌ Erreur d'initialisation DB : {e}")

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


if os.getenv("FLASK_ENV") == "production":
    import threading
    # Exécute le warmup dans un thread séparé au démarrage
    threading.Thread(target=warm_cache, daemon=True).start()

    # ── Scheduler ──────────────────────────────────────────────
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler()

    # Re-warm du cache toutes les 23h50
    scheduler.add_job(
        func=warm_cache,
        trigger="interval",
        hours=23,
        minutes=50,
        id="cache_warmup",
        replace_existing=True,
    )

    # Heartbeat DB : garde les connexions du pool vivantes (évite les 90s timeout)
    def db_heartbeat():
        try:
            with app.app_context():
                from sqlalchemy import text
                db.session.execute(text("SELECT 1"))
                db.session.remove()
        except Exception as e:
            app.logger.warning(f"⚠️ Heartbeat DB échoué : {e}")

    scheduler.add_job(
        func=db_heartbeat,
        trigger="interval",
        minutes=5,
        id="db_heartbeat",
        replace_existing=True,
    )

    scheduler.start()
    app.logger.info("⏰ Scheduler démarré (cache + heartbeat DB)")
    # ───────────────────────────────────────────────────────────


if __name__ == "__main__":
    app.run(debug=True, use_reloader=True, port=5001)
