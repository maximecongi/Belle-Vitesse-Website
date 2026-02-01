from pyairtable import Table
import os

_cache = None

# Tables will be initialized in init_airtable
TABLE_STATIC = None
TABLE_VEHICLES = None
TABLE_HEADS = None
TABLE_GRIPS_CATEGORIES = None
TABLE_GRIP_PRODUCTS = None
TABLE_CONFIGS = None

def init_airtable_service(app_config, cache):
    global _cache, TABLE_STATIC, TABLE_VEHICLES, TABLE_HEADS, TABLE_GRIPS_CATEGORIES, TABLE_GRIP_PRODUCTS, TABLE_CONFIGS
    _cache = cache
    
    token = app_config['AIRTABLE_SECRET_TOKEN']
    base_id = app_config['AIRTABLE_BASE_ID']
    
    if not token or not base_id:
        raise RuntimeError("AIRTABLE_SECRET_TOKEN and AIRTABLE_BASE_ID must be set")
        
    TABLE_STATIC = Table(token, base_id, "static")
    TABLE_VEHICLES = Table(token, base_id, "vehicles")
    TABLE_HEADS = Table(token, base_id, "heads")
    TABLE_GRIPS_CATEGORIES = Table(token, base_id, "grips_categories")
    TABLE_GRIP_PRODUCTS = Table(token, base_id, "grip_products")
    TABLE_CONFIGS = Table(token, base_id, "configs")

def get_cached(key, fetcher, timeout=3600):
    if _cache is None:
        return fetcher()
    value = _cache.get(key)
    if value is None:
        value = fetcher()
        _cache.set(key, value, timeout=timeout)
    return value

def get_static_by_lang(lang="en"):
    return get_cached(
        f"static_{lang}",
        lambda: TABLE_STATIC.first(formula=f"{{language}}='{lang}'")
    )

def get_vehicles():
    return get_cached("vehicles", lambda: TABLE_VEHICLES.all(sort=["order"]))

def get_heads():
    return get_cached("heads", lambda: TABLE_HEADS.all(sort=["order"]))

def get_grips_categories():
    return get_cached("grips_categories", lambda: TABLE_GRIPS_CATEGORIES.all(sort=["order"]))

def get_grips_categories_by_slug(slug):
    return get_cached(
        f"grips_categories_{slug}",
        lambda: TABLE_GRIPS_CATEGORIES.first(formula=f"{{slug}}='{slug}'")
    )

def get_grips_products_for_category(category_id):
    return get_cached(
        f"grips_products_{category_id}",
        lambda: [
            c for c in TABLE_GRIP_PRODUCTS.all(sort=["order"])
            if category_id in c["fields"].get("category", [])
        ]
    )

def get_vehicle_by_slug(slug):
    return get_cached(
        f"vehicle_{slug}",
        lambda: TABLE_VEHICLES.first(formula=f"{{slug}}='{slug}'")
    )

def get_head_by_slug(slug):
    return get_cached(
        f"head_{slug}",
        lambda: TABLE_HEADS.first(formula=f"{{slug}}='{slug}'")
    )

def get_configs_for_vehicle(vehicle_id):
    return get_cached(
        f"configs_vehicle_{vehicle_id}",
        lambda: [
            c for c in TABLE_CONFIGS.all()
            if vehicle_id in c["fields"].get("vehicle", [])
        ]
    )

def warm_cache(app):
    try:
        get_vehicles()
        get_heads()
        get_grips_categories()
        get_static_by_lang("en")
        app.logger.info("🔥 Cache warmé avec succès")
    except Exception as e:
        app.logger.error(f"❌ Erreur warm cache : {e}")
