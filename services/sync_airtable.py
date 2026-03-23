"""
Airtable Sync Service

Core logic for syncing Airtable data to MySQL and downloading images.
"""

import json
import os
import shutil
from pathlib import Path

import requests
from pyairtable import Api
from sshtunnel import SSHTunnelForwarder
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

IMAGE_STORE_PATH = "static/images/airtable"
STATIC_URL_PREFIX = "/static/images/airtable"

TABLES = ["vehicles", "heads", "grips_categories",
          "grip_products", "configs", "static"]

THUMBNAIL_SIZES = ["small", "large", "full"]


# ── MySQL helpers ────────────────────────────────────────────

def get_sqlalchemy_engine(host, user, password, database, port=3306):
    """Create and return a SQLAlchemy engine."""
    try:
        url = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}"
        engine = create_engine(url)
        return engine
    except Exception as e:
        print(f"Error creating SQLAlchemy engine: {e}")
        raise


def create_table_if_not_exists(connection, table_name):
    """Create table with flexible JSON structure if it doesn't exist."""
    connection.execute(text(f"""
        CREATE TABLE IF NOT EXISTS `{table_name}` (
            id VARCHAR(255) PRIMARY KEY,
            createdTime DATETIME,
            fields JSON,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """))


# ── Image download helpers ───────────────────────────────────

def download_file(url, save_path):
    """Download a file from URL to the specified path."""
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        Path(save_path).parent.mkdir(parents=True, exist_ok=True)

        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return True
    except Exception as e:
        print(f"  Error downloading {url}: {e}")
        return False


def process_attachment(attachment, table_name, record_id):
    """
    Process a single attachment: download main image and thumbnails.
    Returns modified attachment with local URLs.
    """
    filename = attachment.get("filename", "image.jpg")
    original_url = attachment.get("url")

    base_path = os.path.join(IMAGE_STORE_PATH, table_name, record_id)
    base_url = f"{STATIC_URL_PREFIX}/{table_name}/{record_id}"

    processed = attachment.copy()

    if original_url:
        main_save_path = os.path.join(base_path, filename)
        if download_file(original_url, main_save_path):
            processed["url"] = f"{base_url}/{filename}"
            print(f"  Downloaded: {filename}")
        else:
            print(f"  Failed to download main image: {filename}")

    thumbnails = attachment.get("thumbnails", {})
    if thumbnails:
        processed_thumbnails = {}

        for size in THUMBNAIL_SIZES:
            thumb_data = thumbnails.get(size, {})
            thumb_url = thumb_data.get("url")

            if thumb_url:
                thumb_save_path = os.path.join(
                    base_path, "thumbnails", size, filename)
                thumb_local_url = f"{base_url}/thumbnails/{size}/{filename}"

                if download_file(thumb_url, thumb_save_path):
                    processed_thumbnails[size] = {
                        "url": thumb_local_url,
                        "width": thumb_data.get("width"),
                        "height": thumb_data.get("height")
                    }
                    print(f"    Thumbnail ({size}): {filename}")
                else:
                    processed_thumbnails[size] = thumb_data

        processed["thumbnails"] = processed_thumbnails

    return processed


def process_attachments_in_fields(fields, table_name, record_id):
    """
    Iterate through all fields and process any attachment arrays.
    Returns modified fields with local URLs.
    """
    processed_fields = {}

    for key, value in fields.items():
        if isinstance(value, list) and len(value) > 0:
            first_item = value[0]
            if isinstance(first_item, dict) and "url" in first_item and "filename" in first_item:
                print(f"  Processing attachment field: {key}")
                processed_attachments = []
                for attachment in value:
                    processed = process_attachment(
                        attachment, table_name, record_id)
                    processed_attachments.append(processed)
                processed_fields[key] = processed_attachments
            else:
                processed_fields[key] = value
        else:
            processed_fields[key] = value

    return processed_fields


# ── Sync logic ───────────────────────────────────────────────

def _is_attachment_field(value):
    """Check if a field value is an Airtable attachment array."""
    return (isinstance(value, list) and len(value) > 0
            and isinstance(value[0], dict)
            and "url" in value[0] and "filename" in value[0])


def _preserve_existing_attachments(connection, table_name, record_id, new_fields):
    """
    Merge new fields with existing attachment fields from DB.
    """
    query = text(f"SELECT fields FROM `{table_name}` WHERE id = :record_id")
    result = connection.execute(query, {"record_id": record_id})
    row = result.fetchone()

    if not row:
        return {k: v for k, v in new_fields.items()
                if not _is_attachment_field(v)}

    existing_fields = row[0]
    if isinstance(existing_fields, str):
        existing_fields = json.loads(existing_fields)

    merged = {}
    for key, value in new_fields.items():
        if _is_attachment_field(value) and key in existing_fields:
            merged[key] = existing_fields[key]
        else:
            merged[key] = value

    return merged


def sync_table(table_name, api, base_id, connection, download_images=True):
    """Sync a single table from Airtable to MySQL."""
    print(f"\n{'='*50}")
    print(f"Syncing table: {table_name}")
    print(f"{'='*50}")

    create_table_if_not_exists(connection, table_name)

    table = api.table(base_id, table_name)
    records = table.all()

    print(f"Found {len(records)} records")

    for record in records:
        record_id = record["id"]
        created_time = record["createdTime"]
        fields = record["fields"]

        print(f"\nProcessing record: {record_id}")

        if download_images:
            processed_fields = process_attachments_in_fields(
                fields, table_name, record_id)
        else:
            processed_fields = _preserve_existing_attachments(
                connection, table_name, record_id, fields)

        created_time_clean = created_time.split(
            '.')[0].replace("T", " ").replace("Z", "")

        fields_json = json.dumps(processed_fields, ensure_ascii=False)

        upsert_query = text(f"""
            INSERT INTO `{table_name}` (`id`, `createdTime`, `fields`)
            VALUES (:id, :createdTime, :fields)
            ON DUPLICATE KEY UPDATE
                `createdTime` = VALUES(`createdTime`),
                `fields` = VALUES(`fields`)
        """)

        try:
            connection.execute(
                upsert_query, 
                {"id": record_id, "createdTime": created_time_clean, "fields": fields_json}
            )
        except Exception as e:
            print(
                f"  FAILED to upsert record {record_id} in table {table_name}: {e}")
            raise e

    print(f"\nCompleted syncing {table_name}: {len(records)} records")
    return [r["id"] for r in records]


def cleanup_records(connection, table_name, active_ids):
    """Delete records from MySQL that are no longer in Airtable."""
    if not active_ids:
        print(f"  Cleaning up: deleting ALL records from {table_name}")
        connection.execute(text(f"DELETE FROM `{table_name}`"))
        return

    query = text(f"DELETE FROM `{table_name}` WHERE id NOT IN (:active_ids)")
    connection.execute(query, {"active_ids": active_ids})
    
    # In SQLAlchemy Core, we can get affected rows from the result
    # but for simplicity in this script, we'll just log that cleanup ran
    print(f"  Cleaning up stale records from {table_name}")


def cleanup_images(table_name, active_ids):
    """Delete local image folders for records that are no longer in Airtable."""
    table_dir = os.path.join(IMAGE_STORE_PATH, table_name)
    if not os.path.exists(table_dir):
        return

    for record_id in os.listdir(table_dir):
        if record_id not in active_ids:
            record_dir = os.path.join(table_dir, record_id)
            if os.path.isdir(record_dir):
                print(
                    f"  Cleaning up: deleting images for stale record {record_id}")
                shutil.rmtree(record_dir)


# ── Public API ───────────────────────────────────────────────

def clean_images_folder():
    """Clear all contents from the images folder."""
    if os.path.exists(IMAGE_STORE_PATH):
        print(f"🧹 Cleaning {IMAGE_STORE_PATH}...")
        for item in os.listdir(IMAGE_STORE_PATH):
            item_path = os.path.join(IMAGE_STORE_PATH, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)
    else:
        os.makedirs(IMAGE_STORE_PATH, exist_ok=True)


def run_sync(config, sync_db=True, sync_images=True):
    """
    Main sync entry point.

    Args:
        config: dict with keys: airtable_token, airtable_base_id,
                mysql_host, mysql_user, mysql_password, mysql_database,
                use_ssh_tunnel, ssh_host, ssh_user, ssh_password
        sync_db: whether to sync database records
        sync_images: whether to download images
    """
    api = Api(config["airtable_token"])

    if sync_images:
        clean_images_folder()

    def _do_sync(connection):
        for table_name in TABLES:
            if sync_db:
                sync_table(table_name, api, config["airtable_base_id"],
                           connection, download_images=sync_images)
            elif sync_images:
                table = api.table(config["airtable_base_id"], table_name)
                records = table.all()
                print(f"\n{'='*50}")
                print(f"Downloading images for: {table_name}")
                print(f"{'='*50}")
                for record in records:
                    print(f"\nProcessing record: {record['id']}")
                    process_attachments_in_fields(
                        record["fields"], table_name, record["id"])

    if config.get("use_ssh_tunnel"):
        print("Using SSH tunnel...")
        with SSHTunnelForwarder(
            (config["ssh_host"], 22),
            ssh_username=config["ssh_user"],
            ssh_password=config["ssh_password"],
            remote_bind_address=(config["mysql_host"], 3306),
            local_bind_address=('127.0.0.1', 0)
        ) as tunnel:
            print(f"SSH tunnel established on local port {tunnel.local_bind_port}")
            engine = get_sqlalchemy_engine(
                "127.0.0.1", config["mysql_user"], config["mysql_password"],
                config["mysql_database"], port=tunnel.local_bind_port
            )
            with engine.begin() as connection:
                try:
                    _do_sync(connection)
                except Exception as e:
                    print(f"\nError during sync: {e}")
                    raise
    else:
        engine = get_sqlalchemy_engine(
            config["mysql_host"], config["mysql_user"], config["mysql_password"],
            config["mysql_database"]
        )
        with engine.begin() as connection:
            try:
                _do_sync(connection)
            except Exception as e:
                print(f"\nError during sync: {e}")
                raise
