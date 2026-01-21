#!/usr/bin/env python3
"""
Airtable to MySQL Sync Script

Syncs Airtable tables to MySQL database and downloads images with thumbnails.
Preserves Airtable API attachment structure with local URLs.
"""

import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv
from pyairtable import Api
import shutil
import mysql.connector
from mysql.connector import Error
from sshtunnel import SSHTunnelForwarder

from utils.cache_clearer import clear_cache

# Load environment variables
load_dotenv()

# Configuration
AIRTABLE_SECRET_TOKEN = os.getenv("AIRTABLE_SECRET_TOKEN")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")

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

IMAGE_STORE_PATH = "static/images/airtable"
STATIC_URL_PREFIX = "/static/images/airtable"

# Tables to sync
TABLES = ["vehicles", "heads", "supports", "configs"]

# Thumbnail sizes to download
THUMBNAIL_SIZES = ["small", "large", "full"]


def get_mysql_connection():
    """Create and return a MySQL connection."""
    try:
        connection = mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE
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
    attachment_id = attachment.get("id", "unknown")
    filename = attachment.get("filename", "image.jpg")
    original_url = attachment.get("url")
    
    # Base path for this attachment
    base_path = os.path.join(IMAGE_STORE_PATH, table_name, record_id)
    base_url = f"{STATIC_URL_PREFIX}/{table_name}/{record_id}"
    
    # Create a copy of the attachment to modify
    processed = attachment.copy()
    
    # Download main image
    if original_url:
        main_save_path = os.path.join(base_path, filename)
        if download_file(original_url, main_save_path):
            processed["url"] = f"{base_url}/{filename}"
            print(f"  Downloaded: {filename}")
        else:
            print(f"  Failed to download main image: {filename}")
    
    # Process thumbnails
    thumbnails = attachment.get("thumbnails", {})
    if thumbnails:
        processed_thumbnails = {}
        
        for size in THUMBNAIL_SIZES:
            thumb_data = thumbnails.get(size, {})
            thumb_url = thumb_data.get("url")
            
            if thumb_url:
                # Create thumbnail path
                thumb_save_path = os.path.join(base_path, "thumbnails", size, filename)
                thumb_local_url = f"{base_url}/thumbnails/{size}/{filename}"
                
                if download_file(thumb_url, thumb_save_path):
                    processed_thumbnails[size] = {
                        "url": thumb_local_url,
                        "width": thumb_data.get("width"),
                        "height": thumb_data.get("height")
                    }
                    print(f"    Thumbnail ({size}): {filename}")
                else:
                    # Keep original structure but note failure
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
        # Check if this field is an attachment array
        if isinstance(value, list) and len(value) > 0:
            first_item = value[0]
            if isinstance(first_item, dict) and "url" in first_item and "filename" in first_item:
                # This is an attachment field
                print(f"  Processing attachment field: {key}")
                processed_attachments = []
                for attachment in value:
                    processed = process_attachment(attachment, table_name, record_id)
                    processed_attachments.append(processed)
                processed_fields[key] = processed_attachments
            else:
                processed_fields[key] = value
        else:
            processed_fields[key] = value
    
    return processed_fields


def sync_table(table_name, api, cursor):
    """Sync a single table from Airtable to MySQL."""
    print(f"\n{'='*50}")
    print(f"Syncing table: {table_name}")
    print(f"{'='*50}")
    
    # Ensure table exists
    create_table_if_not_exists(cursor, table_name)
    
    # Get table from Airtable
    table = api.table(AIRTABLE_BASE_ID, table_name)
    records = table.all()
    
    print(f"Found {len(records)} records")
    
    for record in records:
        record_id = record["id"]
        created_time = record["createdTime"]
        fields = record["fields"]
        
        print(f"\nProcessing record: {record_id}")
        
        # Process attachments in fields
        processed_fields = process_attachments_in_fields(fields, table_name, record_id)
        
        # Convert to JSON for storage
        fields_json = json.dumps(processed_fields, ensure_ascii=False)
        
        # Upsert into MySQL
        upsert_query = f"""
            INSERT INTO `{table_name}` (id, createdTime, fields)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                createdTime = VALUES(createdTime),
                fields = VALUES(fields)
        """
        
        cursor.execute(upsert_query, (record_id, created_time, fields_json))
    
    print(f"\nCompleted syncing {table_name}: {len(records)} records")
    
    # Return list of synced IDs for cleanup
    return [r["id"] for r in records]


def cleanup_records(cursor, table_name, active_ids):
    """Delete records from MySQL that are no longer in Airtable."""
    if not active_ids:
        # If no records, delete everything
        print(f"  Cleaning up: deleting ALL records from {table_name}")
        cursor.execute(f"DELETE FROM `{table_name}`")
        return

    # Delete records that are NOT in active_ids
    format_strings = ','.join(['%s'] * len(active_ids))
    query = f"DELETE FROM `{table_name}` WHERE id NOT IN ({format_strings})"
    cursor.execute(query, tuple(active_ids))
    deleted_count = cursor.rowcount
    if deleted_count > 0:
        print(f"  Cleaning up: deleted {deleted_count} stale records from {table_name}")


def cleanup_images(table_name, active_ids):
    """Delete local image folders for records that are no longer in Airtable."""
    table_dir = os.path.join(IMAGE_STORE_PATH, table_name)
    if not os.path.exists(table_dir):
        return

    # Iterate over directories in table_dir
    for record_id in os.listdir(table_dir):
        if record_id not in active_ids:
            record_dir = os.path.join(table_dir, record_id)
            if os.path.isdir(record_dir):
                print(f"  Cleaning up: deleting images for stale record {record_id}")
                shutil.rmtree(record_dir)


def main():
    """Main sync function."""
    print("=" * 60)
    print("Starting Airtable to MySQL Sync")
    print("=" * 60)
    
    # Validate configuration
    if not AIRTABLE_SECRET_TOKEN or not AIRTABLE_BASE_ID:
        raise RuntimeError("AIRTABLE_SECRET_TOKEN and AIRTABLE_BASE_ID must be set")
    
    if not MYSQL_USER or not MYSQL_PASSWORD or not MYSQL_DATABASE:
        raise RuntimeError("MySQL credentials must be set in .env")
    
    # Initialize Airtable API
    api = Api(AIRTABLE_SECRET_TOKEN)
    
    # Connect to MySQL (with optional SSH tunnel)
    if USE_SSH_TUNNEL:
        print("Using SSH tunnel...")
        if not SSH_USER or not SSH_PASSWORD:
            raise RuntimeError("SSH_USER and SSH_PASSWORD must be set when USE_SSH_TUNNEL is true")
        
        with SSHTunnelForwarder(
            (SSH_HOST, 22),
            ssh_username=SSH_USER,
            ssh_password=SSH_PASSWORD,
            remote_bind_address=(MYSQL_HOST, 3306)
        ) as tunnel:
            print(f"SSH tunnel established on local port {tunnel.local_bind_port}")
            
            connection = mysql.connector.connect(
                host="127.0.0.1",
                port=tunnel.local_bind_port,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DATABASE
            )
            cursor = connection.cursor()
            
            try:
                for table_name in TABLES:
                    sync_table(table_name, api, cursor)
                
                connection.commit()
                print("\n" + "=" * 60)
                print("Sync completed successfully!")
                print("=" * 60)
                
            except Exception as e:
                connection.rollback()
                print(f"\nError during sync: {e}")
                raise
            finally:
                cursor.close()
                connection.close()
    else:
        # Direct connection (for running on PythonAnywhere)
        connection = mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE
        )
        cursor = connection.cursor()
        
        try:
            for table_name in TABLES:
                sync_table(table_name, api, cursor)
            
            connection.commit()
            print("\n" + "=" * 60)
            print("Sync completed successfully!")
            print("=" * 60)
            
        except Exception as e:
            connection.rollback()
            print(f"\nError during sync: {e}")
            raise
        finally:
            cursor.close()
            connection.close()
            clear_cache()


if __name__ == "__main__":
    main()
