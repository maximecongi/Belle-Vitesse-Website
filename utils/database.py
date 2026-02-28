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
        if _ssh_tunnel is None or not _ssh_tunnel.is_active:
            _ssh_tunnel = SSHTunnelForwarder(
                (SSH_HOST, 22),
                ssh_username=SSH_USER,
                ssh_password=SSH_PASSWORD,
                remote_bind_address=(MYSQL_HOST, 3306),
            )
            _ssh_tunnel.start()

        return mysql.connector.connect(
            host="127.0.0.1",
            port=_ssh_tunnel.local_bind_port,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
        )
    else:
        return mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
        )


def init_cache(app_cache: Cache):
    """Initialize the cache instance for both database and airtable services."""
    global cache
    cache = app_cache
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
            fields = (
                json.loads(row["fields"])
                if isinstance(row["fields"], str)
                else row["fields"]
            )
            records.append(
                {
                    "id": row["id"],
                    "createdTime": str(row["createdTime"])
                    if row["createdTime"]
                    else None,
                    "fields": fields,
                }
            )

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
            fields = (
                json.loads(row["fields"])
                if isinstance(row["fields"], str)
                else row["fields"]
            )
            if fields.get(field_name) == field_value:
                return {
                    "id": row["id"],
                    "createdTime": str(row["createdTime"])
                    if row["createdTime"]
                    else None,
                    "fields": fields,
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
    return get_cached(
        "vehicles", lambda: _fetch_all_from_table("vehicles", order_by="order")
    )


def get_heads():
    """Get all heads sorted by order."""
    return get_cached("heads", lambda: _fetch_all_from_table("heads", order_by="order"))


def get_grips_categories():
    """Get all grip categories sorted by order."""
    return get_cached(
        "grips_categories",
        lambda: _fetch_all_from_table("grips_categories", order_by="order"),
    )


def get_grips_categories_by_slug(slug):
    """Get a grip category by its slug."""
    return get_cached(
        f"grips_categories_{slug}",
        lambda: _fetch_by_field("grips_categories", "slug", slug),
    )


def get_grips_products_for_category(category_id):
    """Get all products for a specific grip category."""

    def fetcher():
        all_products = _fetch_all_from_table("grip_products")
        return [
            p for p in all_products if category_id in p["fields"].get("category", [])
        ]

    return get_cached(f"grips_products_{category_id}", fetcher)


def get_vehicle_by_slug(slug):
    """Get a vehicle by its slug."""
    return get_cached(
        f"vehicle_{slug}", lambda: _fetch_by_field("vehicles", "slug", slug)
    )


def get_head_by_slug(slug):
    """Get a head by its slug."""
    return get_cached(f"head_{slug}", lambda: _fetch_by_field("heads", "slug", slug))


def get_static_by_lang(lang="en"):
    """Get static content for a specific language."""
    return get_cached(
        f"static_{lang}", lambda: _fetch_by_field("static", "language", lang)
    )


def get_all_static():
    """Get all static content rows, keyed by language code.

    Returns: {"en": {fields}, "fr": {fields}, ...}
    """
    def fetcher():
        rows = _fetch_all_from_table("static")
        return {
            r["fields"].get("language", "en"): r["fields"]
            for r in rows
        }
    return get_cached("static_all", fetcher)


def get_configs_for_vehicle(vehicle_id):
    """Get all configs for a specific vehicle."""

    def fetcher():
        all_configs = _fetch_all_from_table("configs")
        return [c for c in all_configs if vehicle_id in c["fields"].get("vehicle", [])]

    return get_cached(f"configs_vehicle_{vehicle_id}", fetcher)


# ============================================================
# Checkout Verification (MySQL)
# ============================================================


def _get_existing_columns(cursor, table_name):
    """Return the set of column names that exist on a table."""
    cursor.execute(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
        (table_name,),
    )
    return {row["COLUMN_NAME"] for row in cursor.fetchall()}


def init_checkout_db():
    """
    Initialize checkout tables and apply any pending schema migrations.

    Safe to call on every app startup:
    - Creates tables if they don't exist yet.
    - Adds missing columns to existing tables (additive only — never drops columns).

    Current migrations tracked here:
      signed_documents:
        - pdf_file_hash VARCHAR(64)  → SHA-256 of the raw PDF binary (Option B verification)
    """
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # ── signed_documents ──────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signed_documents (
                inspection_id  VARCHAR(255) PRIMARY KEY,
                hash           VARCHAR(255) NOT NULL,
                pdf_file_hash  VARCHAR(64)  NULL,
                data_snapshot  JSON         NOT NULL,
                signature      MEDIUMTEXT,
                pdf_url        TEXT,
                signed_at      DATETIME,
                created_at     TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migration: add pdf_file_hash to tables that were created before this column existed
        existing = _get_existing_columns(cursor, "signed_documents")
        if "pdf_file_hash" not in existing:
            cursor.execute(
                "ALTER TABLE signed_documents ADD COLUMN pdf_file_hash VARCHAR(64) NULL"
            )
            print("✅ Migration applied: signed_documents.pdf_file_hash added.")

        # ── checkout_tokens ───────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkout_tokens (
                token          VARCHAR(36)  PRIMARY KEY,
                record_id      VARCHAR(255) NOT NULL,
                inspection_id  VARCHAR(255) NOT NULL,
                signature      MEDIUMTEXT,
                created_at     DATETIME     NOT NULL,
                expires_at     DATETIME GENERATED ALWAYS AS
                               (created_at + INTERVAL 24 HOUR) VIRTUAL
            )
        """)

        connection.commit()
        print("✅ Checkout DB initialized.")

    except mysql.connector.Error as err:
        print(f"❌ Error initializing checkout DB: {err}")
    finally:
        cursor.close()
        connection.close()


def store_signed_document(
    inspection_id,
    file_hash,
    data_snapshot,
    signature,
    pdf_url,
    signed_at,
    pdf_file_hash=None,  # SHA-256 of the raw PDF binary — None for legacy documents
):
    """
    Store a signed document snapshot in MySQL.

    pdf_file_hash is optional to maintain backward compatibility with call sites
    that were created before Option B was introduced. Legacy rows will have NULL
    in that column and will skip PDF file verification gracefully.
    """
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        if isinstance(data_snapshot, dict):
            data_snapshot = json.dumps(data_snapshot, ensure_ascii=False)

        sql = """
            INSERT INTO signed_documents
                (inspection_id, hash, pdf_file_hash, data_snapshot, signature, pdf_url, signed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                hash          = VALUES(hash),
                pdf_file_hash = VALUES(pdf_file_hash),
                data_snapshot = VALUES(data_snapshot),
                signature     = VALUES(signature),
                pdf_url       = VALUES(pdf_url),
                signed_at     = VALUES(signed_at)
        """
        cursor.execute(
            sql,
            (
                inspection_id,
                file_hash,
                pdf_file_hash,
                data_snapshot,
                signature,
                pdf_url,
                signed_at,
            ),
        )
        connection.commit()
        return True
    except mysql.connector.Error as err:
        print(f"❌ Error storing signed document: {err}")
        return False
    finally:
        cursor.close()
        connection.close()


def get_checkout_signed_document(inspection_id):
    """
    Retrieve a signed document by inspection ID from MySQL.

    Returns the full row as a dict, including pdf_file_hash (may be None
    for documents signed before the Option B migration).
    """
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT * FROM signed_documents WHERE inspection_id = %s",
            (inspection_id,),
        )
        record = cursor.fetchone()

        if record:
            if isinstance(record["data_snapshot"], str):
                record["data_snapshot"] = json.loads(record["data_snapshot"])
            return record
        return None
    except mysql.connector.Error as err:
        print(f"❌ Error fetching signed document: {err}")
        return None
    finally:
        cursor.close()
        connection.close()


def store_checkout_token(token, record_id, inspection_id, created_at):
    """Store a checkout session token."""
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        sql = """
            INSERT INTO checkout_tokens (token, record_id, inspection_id, created_at)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(sql, (token, record_id, inspection_id, created_at))
        connection.commit()
    except mysql.connector.Error as err:
        print(f"❌ Error storing token: {err}")
    finally:
        cursor.close()
        connection.close()


def get_checkout_token(token):
    """Retrieve a token for checking validity."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT * FROM checkout_tokens WHERE token = %s", (token,))
        return cursor.fetchone()
    except mysql.connector.Error as err:
        print(f"❌ Error fetching token: {err}")
        return None
    finally:
        cursor.close()
        connection.close()


def update_checkout_token_signature(token, signature):
    """Update signature for a token."""
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "UPDATE checkout_tokens SET signature = %s WHERE token = %s",
            (signature, token),
        )
        connection.commit()
    except mysql.connector.Error as err:
        print(f"❌ Error updating token signature: {err}")
    finally:
        cursor.close()
        connection.close()


def delete_checkout_token(token):
    """Delete a token after use."""
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "DELETE FROM checkout_tokens WHERE token = %s", (token,))
        connection.commit()
    except mysql.connector.Error as err:
        print(f"❌ Error deleting token: {err}")
    finally:
        cursor.close()
        connection.close()

# ============================================================
# Checkin Verification (MySQL)
# ============================================================


def init_checkin_db():
    """
    Initialize checkin tables and apply any pending schema migrations.
    """
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # ── checkin_signed_documents ──────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkin_signed_documents (
                inspection_id  VARCHAR(255) PRIMARY KEY,
                hash           VARCHAR(255) NOT NULL,
                pdf_file_hash  VARCHAR(64)  NULL,
                data_snapshot  JSON         NOT NULL,
                signature      MEDIUMTEXT,
                pdf_url        TEXT,
                signed_at      DATETIME,
                created_at     TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
            )
        """)

        existing = _get_existing_columns(cursor, "checkin_signed_documents")
        if "pdf_file_hash" not in existing:
            cursor.execute(
                "ALTER TABLE checkin_signed_documents ADD COLUMN pdf_file_hash VARCHAR(64) NULL"
            )
            print("✅ Migration applied: checkin_signed_documents.pdf_file_hash added.")

        # ── checkin_tokens ───────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkin_tokens (
                token          VARCHAR(36)  PRIMARY KEY,
                record_id      VARCHAR(255) NOT NULL,
                inspection_id  VARCHAR(255) NOT NULL,
                signature      MEDIUMTEXT,
                created_at     DATETIME     NOT NULL,
                expires_at     DATETIME GENERATED ALWAYS AS
                               (created_at + INTERVAL 24 HOUR) VIRTUAL
            )
        """)

        connection.commit()
        print("✅ Checkin DB initialized.")

    except mysql.connector.Error as err:
        print(f"❌ Error initializing checkin DB: {err}")
    finally:
        cursor.close()
        connection.close()


def store_checkin_signed_document(
    inspection_id,
    file_hash,
    data_snapshot,
    signature,
    pdf_url,
    signed_at,
    pdf_file_hash=None,
):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        if isinstance(data_snapshot, dict):
            data_snapshot = json.dumps(data_snapshot, ensure_ascii=False)

        sql = """
            INSERT INTO checkin_signed_documents
                (inspection_id, hash, pdf_file_hash, data_snapshot, signature, pdf_url, signed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                hash          = VALUES(hash),
                pdf_file_hash = VALUES(pdf_file_hash),
                data_snapshot = VALUES(data_snapshot),
                signature     = VALUES(signature),
                pdf_url       = VALUES(pdf_url),
                signed_at     = VALUES(signed_at)
        """
        cursor.execute(
            sql,
            (
                inspection_id,
                file_hash,
                pdf_file_hash,
                data_snapshot,
                signature,
                pdf_url,
                signed_at,
            ),
        )
        connection.commit()
        return True
    except mysql.connector.Error as err:
        print(f"❌ Error storing checkin signed document: {err}")
        return False
    finally:
        cursor.close()
        connection.close()


def get_checkin_signed_document(inspection_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT * FROM checkin_signed_documents WHERE inspection_id = %s",
            (inspection_id,),
        )
        record = cursor.fetchone()

        if record:
            if isinstance(record["data_snapshot"], str):
                record["data_snapshot"] = json.loads(record["data_snapshot"])
            return record
        return None
    except mysql.connector.Error as err:
        print(f"❌ Error fetching checkin signed document: {err}")
        return None
    finally:
        cursor.close()
        connection.close()


def store_checkin_token(token, record_id, inspection_id, created_at):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        sql = """
            INSERT INTO checkin_tokens (token, record_id, inspection_id, created_at)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(sql, (token, record_id, inspection_id, created_at))
        connection.commit()
    except mysql.connector.Error as err:
        print(f"❌ Error storing checkin token: {err}")
    finally:
        cursor.close()
        connection.close()


def get_checkin_token(token):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT * FROM checkin_tokens WHERE token = %s", (token,))
        return cursor.fetchone()
    except mysql.connector.Error as err:
        print(f"❌ Error fetching checkin token: {err}")
        return None
    finally:
        cursor.close()
        connection.close()


def update_checkin_token_signature(token, signature):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "UPDATE checkin_tokens SET signature = %s WHERE token = %s",
            (signature, token),
        )
        connection.commit()
    except mysql.connector.Error as err:
        print(f"❌ Error updating checkin token signature: {err}")
    finally:
        cursor.close()
        connection.close()


def delete_checkin_token(token):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("DELETE FROM checkin_tokens WHERE token = %s", (token,))
        connection.commit()
    except mysql.connector.Error as err:
        print(f"❌ Error deleting checkin token: {err}")
    finally:
        cursor.close()
        connection.close()
