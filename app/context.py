from datetime import datetime, timezone
from services.airtable_service import (
    get_vehicles,
    get_heads,
    get_grips_categories,
    get_static_by_lang,
)

def register_context(app):
    @app.context_processor
    def inject_globals():
        return {
            "vehicles": get_vehicles(),
            "heads": get_heads(),
            "grips_categories": get_grips_categories(),
            "static": get_static_by_lang("en"),
            "now": datetime.now(timezone.utc)
        }
    
    # Custom filters
    @app.template_filter('slugify')
    def slugify_filter(s):
        return s.lower().replace(" ", "_")
