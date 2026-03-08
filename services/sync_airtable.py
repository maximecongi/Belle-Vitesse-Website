"""
Airtable Sync Service

Core logic for syncing Airtable data to MySQL and downloading images.
"""

import os
import json
import shutil
import requests
from pathlib import Path
from pyairtable import Api
import mysql.connector
from mysql.connector import Error
from sshtunnel import SSHTunnelForwarder

IMAGE_STORE_PATH = "static/images/airtable"
STATIC_URL_PREFIX = "/static/images/airtable"

TABLES = ["vehicles", "heads", "grips_categories",
          "grip_products", "configs", "static"]

THUMBNAIL_SIZES = ["small", "large", "full"]


# ── MySQL helpers ────────────────────────────────────────────

def get_mysql_connection(host, user, password, database, port=3306):
    """Create and return a MySQL connection."""
    try:
        connection = mysql.connector.connect(
            host=host, user=user, password=password,
            database=database, port=port,
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        raise


def create_table_if_not_exists(cursor, table_name):
    """Create table with flexible JSON structure if it doesn't exist."""
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS `{table_name}` (
            id VARCHAR(255) PRIMARY KEY,
            createdTime DATETIME,
            fields JSON,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)


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

def sync_table(table_name, api, base_id, cursor, download_images=True):
    """Sync a single table from Airtable to MySQL."""
    print(f"\n{'='*50}")
    print(f"Syncing table: {table_name}")
    print(f"{'='*50}")

    create_table_if_not_exists(cursor, table_name)

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
            processed_fields = fields

        created_time_clean = created_time.split(
            '.')[0].replace("T", " ").replace("Z", "")

        fields_json = json.dumps(processed_fields, ensure_ascii=False)

        upsert_query = f"""
            INSERT INTO `{table_name}` (`id`, `createdTime`, `fields`)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                `createdTime` = VALUES(`createdTime`),
                `fields` = VALUES(`fields`)
        """

        try:
            cursor.execute(
                upsert_query, (record_id, created_time_clean, fields_json))
        except Error as e:
            print(
                f"  FAILED to upsert record {record_id} in table {table_name}: {e}")
            raise e

    print(f"\nCompleted syncing {table_name}: {len(records)} records")
    return [r["id"] for r in records]


def cleanup_records(cursor, table_name, active_ids):
    """Delete records from MySQL that are no longer in Airtable."""
    if not active_ids:
        print(f"  Cleaning up: deleting ALL records from {table_name}")
        cursor.execute(f"DELETE FROM `{table_name}`")
        return

    format_strings = ','.join(['%s'] * len(active_ids))
    query = f"DELETE FROM `{table_name}` WHERE id NOT IN ({format_strings})"
    cursor.execute(query, tuple(active_ids))
    deleted_count = cursor.rowcount
    if deleted_count > 0:
        print(
            f"  Cleaning up: deleted {deleted_count} stale records from {table_name}")


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

    def _do_sync(cursor):
        for table_name in TABLES:
            if sync_db:
                sync_table(table_name, api, config["airtable_base_id"],
                           cursor, download_images=sync_images)
            elif sync_images:
                # Images only: still need to read records from Airtable
                # to know what images to download
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
            print(
                f"SSH tunnel established on local port {tunnel.local_bind_port}")
            connection = mysql.connector.connect(
                host="127.0.0.1",
                port=tunnel.local_bind_port,
                user=config["mysql_user"],
                password=config["mysql_password"],
                database=config["mysql_database"],
            )
            cursor = connection.cursor()
            try:
                _do_sync(cursor)
                connection.commit()
            except Exception as e:
                connection.rollback()
                print(f"\nError during sync: {e}")
                raise
            finally:
                cursor.close()
                connection.close()
    else:
        connection = mysql.connector.connect(
            host=config["mysql_host"],
            user=config["mysql_user"],
            password=config["mysql_password"],
            database=config["mysql_database"],
        )
        cursor = connection.cursor()
        try:
            _do_sync(cursor)
            connection.commit()
        except Exception as e:
            connection.rollback()
            print(f"\nError during sync: {e}")
            raise
        finally:
            cursor.close()
            connection.close()
