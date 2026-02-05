"""
Database access layer for MySQL.
Replaces direct Airtable API calls with MySQL queries.
Maintains the same interface as the original airtable.py.
"""

import os
import json
import mysql.connector
from flask_caching import Cache
from dotenv import load_dotenv
from sshtunnel import SSHTunnelForwarder

# Load environment variables
load_dotenv()

# MySQL Configuration
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE")

# SSH Configuration (for local development)
SSH_HOST = os.getenv("SSH_HOST", "ssh.pythonanywhere.com")
SSH_USER = os.getenv("SSH_USER")
SSH_PASSWORD = os.getenv("SSH_PASSWORD")
USE_SSH_TUNNEL = os.getenv("USE_SSH_TUNNEL", "false").lower() == "true"

cache: Cache = None

# Global tunnel and connection for SSH mode
_ssh_tunnel = None
_ssh_connection = None


def get_db_connection():
    """Create and return a MySQL connection (with optional SSH tunnel)."""
    global _ssh_tunnel, _ssh_connection
    
    if USE_SSH_TUNNEL:
        # For SSH tunnel mode, reuse connection if available
        if _ssh_tunnel is None or not _ssh_tunnel.is_active:
            _ssh_tunnel = SSHTunnelForwarder(
                (SSH_HOST, 22),
                ssh_username=SSH_USER,
                ssh_password=SSH_PASSWORD,
                remote_bind_address=(MYSQL_HOST, 3306)
            )
            _ssh_tunnel.start()
        
        return mysql.connector.connect(
            host="127.0.0.1",
            port=_ssh_tunnel.local_bind_port,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE
        )
    else:
        # Direct connection (for PythonAnywhere)
        return mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE
        )


def init_cache(app_cache: Cache):
    """Initialize the cache instance for both database and airtable services."""
    global cache
    cache = app_cache
    # Also initialize airtable's cache since we proxy functions to it
    import utils.airtable as airtable_service
    airtable_service.init_cache(app_cache)


def get_cached(key, fetcher, timeout=3600):
    """Get a value from cache or fetch it."""
    if cache is None:
        return fetcher()
    value = cache.get(key)
    if value is None:
        value = fetcher()
        cache.set(key, value, timeout=timeout)
    return value


def _fetch_all_from_table(table_name, order_by=None):
    """Fetch all records from a table and format like Airtable response."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        query = f"SELECT id, createdTime, fields FROM `{table_name}`"
        cursor.execute(query)
        rows = cursor.fetchall()
        
        records = []
        for row in rows:
            fields = json.loads(row["fields"]) if isinstance(row["fields"], str) else row["fields"]
            records.append({
                "id": row["id"],
                "createdTime": str(row["createdTime"]) if row["createdTime"] else None,
                "fields": fields
            })
        
        # Sort by order field if specified
        if order_by:
            records.sort(key=lambda r: r["fields"].get(order_by, 999))
        
        return records
    finally:
        cursor.close()
        connection.close()


def _fetch_by_field(table_name, field_name, field_value):
    """Fetch a single record by field value."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        query = f"SELECT id, createdTime, fields FROM `{table_name}`"
        cursor.execute(query)
        rows = cursor.fetchall()
        
        for row in rows:
            fields = json.loads(row["fields"]) if isinstance(row["fields"], str) else row["fields"]
            if fields.get(field_name) == field_value:
                return {
                    "id": row["id"],
                    "createdTime": str(row["createdTime"]) if row["createdTime"] else None,
                    "fields": fields
                }
        return None
    finally:
        cursor.close()
        connection.close()


# ============================================================
# Public API (same interface as original airtable.py)
# ============================================================

def get_vehicles():
    """Get all vehicles sorted by order."""
    return get_cached("vehicles", lambda: _fetch_all_from_table("vehicles", order_by="order"))


def get_heads():
    """Get all heads sorted by order."""
    return get_cached("heads", lambda: _fetch_all_from_table("heads", order_by="order"))


def get_grips_categories():
    """Get all grip categories sorted by order."""
    return get_cached("grips_categories", lambda: _fetch_all_from_table("grips_categories", order_by="order"))


def get_grips_categories_by_slug(slug):
    """Get a grip category by its slug."""
    return get_cached(
        f"grips_categories_{slug}",
        lambda: _fetch_by_field("grips_categories", "slug", slug)
    )


def get_grips_products_for_category(category_id):
    """Get all products for a specific grip category."""
    def fetcher():
        all_products = _fetch_all_from_table("grip_products")
        return [
            p for p in all_products
            if category_id in p["fields"].get("category", [])
        ]
    return get_cached(f"grips_products_{category_id}", fetcher)


def get_vehicle_by_slug(slug):
    """Get a vehicle by its slug."""
    return get_cached(
        f"vehicle_{slug}",
        lambda: _fetch_by_field("vehicles", "slug", slug)
    )


def get_head_by_slug(slug):
    """Get a head by its slug."""
    return get_cached(
        f"head_{slug}",
        lambda: _fetch_by_field("heads", "slug", slug)
    )


def get_static_by_lang(lang="en"):
    """Get static content for a specific language."""
    return get_cached(
        f"static_{lang}",
        lambda: _fetch_by_field("static", "language", lang)
    )


def get_configs_for_vehicle(vehicle_id):
    """Get all configs for a specific vehicle."""
    def fetcher():
        all_configs = _fetch_all_from_table("configs")
        return [
            c for c in all_configs
            if vehicle_id in c["fields"].get("vehicle", [])
        ]
    
    return get_cached(f"configs_vehicle_{vehicle_id}", fetcher)


# Proxy Newsletter functions to Airtable service for real-time management
from utils.airtable import add_newsletter_subscriber, remove_newsletter_subscriber
