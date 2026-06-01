"""
Couche d'accès à la base de données pour MySQL.
Remplace les appels directs à l'API Airtable par des requêtes MySQL.
Maintient la même interface que le fichier original airtable.py.
"""

import logging
from flask_caching import Cache
from models import (
    Vehicle,
    Head,
    GripCategory,
    GripProduct,
    Config,
    Static
)

# Correspondance des noms de tables avec les modèles
TABLE_MODELS = {
    "vehicles": Vehicle,
    "heads": Head,
    "grips_categories": GripCategory,
    "grip_products": GripProduct,
    "configs": Config,
    "static": Static,
}

cache: Cache = None


def init_cache(app_cache: Cache):
    """Initialise l'instance de cache pour les services de base de données et Airtable."""
    global cache
    cache = app_cache
    import utils.airtable as airtable_service

    airtable_service.init_cache(app_cache)


def get_cached(key, fetcher, timeout=3600):
    """Récupère une valeur du cache ou l'extrait via le 'fetcher'."""
    if cache is None:
        return fetcher()
    value = cache.get(key)
    if value is None:
        value = fetcher()
        cache.set(key, value, timeout=timeout)
    return value


def _fetch_all_from_table(table_name, order_by=None):
    """Récupère tous les enregistrements d'une table via l'ORM."""
    try:
        model = TABLE_MODELS.get(table_name)
        if not model:
            logging.error(f"No model found for table: {table_name}")
            return []

        records = []
        for row in model.query.all():
            records.append({
                "id": row.id,
                "createdTime": str(row.createdTime) if row.createdTime else None,
                "fields": row.fields
            })

        if order_by:
            records.sort(key=lambda r: r["fields"].get(order_by, 999))

        return records
    except Exception as e:
        logging.error(f"Error fetching from {table_name}: {e}")
        return []


def _fetch_by_field(table_name, field_name, field_value):
    """Récupère un seul enregistrement par valeur de champ via un scan ORM (les champs sont en JSON)."""
    try:
        model = TABLE_MODELS.get(table_name)
        if not model:
            return None

        # Scan all (since columns are hidden in JSON 'fields')
        for row in model.query.all():
            if row.fields.get(field_name) == field_value:
                return {
                    "id": row.id,
                    "createdTime": str(row.createdTime) if row.createdTime else None,
                    "fields": row.fields
                }
        return None
    except Exception as e:
        logging.error(f"Error fetching by field from {table_name}: {e}")
        return None


# ============================================================
# API Publique (même interface que l'original airtable.py)
# ============================================================


def get_vehicles():
    """Récupère tous les véhicules triés par ordre."""
    return get_cached(
        "vehicles", lambda: _fetch_all_from_table("vehicles", order_by="order")
    )


def get_heads():
    """Récupère toutes les têtes triées par ordre."""
    return get_cached("heads", lambda: _fetch_all_from_table("heads", order_by="order"))


def get_grips_categories():
    """Récupère toutes les catégories de grip triées par ordre."""
    return get_cached(
        "grips_categories",
        lambda: _fetch_all_from_table("grips_categories", order_by="order"),
    )


def get_grips_categories_by_slug(slug):
    """Récupère une catégorie de grip par son slug."""
    return get_cached(
        f"grips_categories_{slug}",
        lambda: _fetch_by_field("grips_categories", "slug", slug),
    )


def get_grips_products_for_category(category_id):
    """Récupère tous les produits pour une catégorie de grip spécifique."""

    def fetcher():
        all_products = _fetch_all_from_table("grip_products")
        return [
            p for p in all_products if category_id in p["fields"].get("category", [])
        ]

    return get_cached(f"grips_products_{category_id}", fetcher)


def get_vehicle_by_slug(slug):
    """Récupère un véhicule par son slug."""
    return get_cached(
        f"vehicle_{slug}", lambda: _fetch_by_field("vehicles", "slug", slug)
    )


def get_head_by_slug(slug):
    """Récupère une tête par son slug."""
    return get_cached(f"head_{slug}", lambda: _fetch_by_field("heads", "slug", slug))
def get_all_static():
    """Récupère toutes les lignes de contenu statique, indexées par code langue.

    Retourne : {"en": {fields}, "fr": {fields}, ...}
    """
    def fetcher():
        rows = _fetch_all_from_table("static")
        return {
            r["fields"].get("language", "en"): r["fields"]
            for r in rows
        }
    return get_cached("static_all", fetcher)


def get_configs_for_vehicle(vehicle_id):
    """Récupère toutes les configurations pour un véhicule spécifique."""

    def fetcher():
        all_configs = _fetch_all_from_table("configs")
        return [c for c in all_configs if vehicle_id in c["fields"].get("vehicle", [])]

    return get_cached(f"configs_vehicle_{vehicle_id}", fetcher)


# End of generic data utilities
