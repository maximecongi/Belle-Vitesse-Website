import os
from flask import Flask
from dotenv import load_dotenv
from flask_caching import Cache
from app.config import Config

cache = Cache()

def create_app():
    # Load environment variables
    load_dotenv()

    app = Flask(
        __name__,
        static_folder="../static",
        static_url_path=Config.STATIC_URL_PATH,
        template_folder="../templates"
    )

    # Load configuration
    app.config.from_object(Config)

    # Initialize extensions
    cache.init_app(app)

    # Initialize services
    from services.airtable_service import init_airtable_service, warm_cache
    init_airtable_service(app.config, cache)

    # Register routes and context
    from app.routes import register_routes
    from app.context import register_context
    
    register_routes(app)
    register_context(app)

    # Warm cache if in production
    if app.config.get("FLASK_ENV") == "production":
        with app.app_context():
            warm_cache(app)

    return app
