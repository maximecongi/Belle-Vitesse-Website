import os
from datetime import datetime, timezone
from flask import Flask

from extensions import cache
from routes import init_routes, init_error_handlers
from utils.database import (
    init_cache,
    get_vehicles,
    get_static_by_lang,
    get_heads,
    get_grips_categories,
)

def create_app():
    app = Flask(
        __name__,
        static_folder=os.getenv("STATIC_FOLDER"),
        static_url_path=os.getenv("STATIC_URL_PATH"),
    )
    
    # App Config
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "bv_super_secret_key_2026")
    app.config["CACHE_TYPE"] = "SimpleCache"
    app.config["CACHE_DEFAULT_TIMEOUT"] = 3600
    app.config["CACHE_KEY_PREFIX"] = "myapp_"
    
    # Initialize extensions
    cache.init_app(app)
    init_cache(cache)
    
    # Initialize routes & error handlers
    init_routes(app)
    init_error_handlers(app)
    
    # Custom Jinja2 Filters
    app.jinja_env.filters['slugify'] = lambda s: s.lower().replace(" ", "_")
    
    # Context Processors (Globals)
    @app.context_processor
    def inject_globals():
        return {
            "vehicles": get_vehicles(),
            "heads": get_heads(),
            "grips_categories": get_grips_categories(),
            "static": get_static_by_lang("en"),
            "now": datetime.now(timezone.utc)
        }
        
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
