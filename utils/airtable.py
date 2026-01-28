from flask_caching import Cache
from pyairtable import Table
import os
from dotenv import load_dotenv

load_dotenv("/home/Maxcongi/bellevitesse/.env")    

cache: Cache = None

# ⚡ Récupérer les variables
AIRTABLE_SECRET_TOKEN = os.getenv("AIRTABLE_SECRET_TOKEN")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")

# ⚡ Vérifier qu’elles existent
if not AIRTABLE_SECRET_TOKEN or not AIRTABLE_BASE_ID:
    raise RuntimeError(
        "AIRTABLE_SECRET_TOKEN et AIRTABLE_BASE_ID doivent être définis dans le .env"
    )

# ⚡ Créer les tables après avoir confirmé que les variables existent
TABLE_STATIC = Table(AIRTABLE_SECRET_TOKEN, AIRTABLE_BASE_ID, "static")
TABLE_VEHICLES = Table(AIRTABLE_SECRET_TOKEN, AIRTABLE_BASE_ID, "vehicles")
TABLE_HEADS = Table(AIRTABLE_SECRET_TOKEN, AIRTABLE_BASE_ID, "heads")
TABLE_GRIPS_CATEGORIES = Table(AIRTABLE_SECRET_TOKEN, AIRTABLE_BASE_ID, "grips_categories")
TABLE_GRIP_PRODUCTS = Table(AIRTABLE_SECRET_TOKEN, AIRTABLE_BASE_ID, "grip_products")
TABLE_CONFIGS = Table(AIRTABLE_SECRET_TOKEN, AIRTABLE_BASE_ID, "configs")



def init_cache(app_cache: Cache):
    global cache
    cache = app_cache


def get_cached(key, fetcher, timeout=3600):
    value = cache.get(key)
    if value is None:
        value = fetcher()
        cache.set(key, value, timeout=timeout)
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
