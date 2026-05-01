"""
Service de Synchronisation Airtable

Logique principale pour synchroniser les données Airtable vers MySQL et télécharger les images.
"""

import json
import os
import shutil
from pathlib import Path

import requests
from pyairtable import Api
from sqlalchemy import create_engine, text

IMAGE_STORE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "images", "airtable")
STATIC_URL_PREFIX = "/static/images/airtable"

TABLES = ["vehicles", "heads", "grips_categories",
          "grip_products", "configs", "static"]

THUMBNAIL_SIZES = ["small", "large", "full"]


# ── Aide MySQL ───────────────────────────────────────────────

def get_sqlalchemy_engine(host, user, password, database, port=3306):
    """Crée et retourne un moteur SQLAlchemy."""
    try:
        url = f"mysql+mysqldb://{user}:{password}@{host}:{port}/{database}"
        engine = create_engine(url)
        return engine
    except Exception as e:
        print(f"Erreur lors de la création du moteur SQLAlchemy : {e}")
        raise


def create_table_if_not_exists(connection, table_name):
    """Crée la table avec une structure JSON flexible si elle n'existe pas."""
    connection.execute(text(f"""
        CREATE TABLE IF NOT EXISTS `{table_name}` (
            id VARCHAR(255) PRIMARY KEY,
            createdTime DATETIME,
            fields JSON,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """))


# ── Aides au téléchargement d'images ─────────────────────────

def download_file(url, save_path):
    """Télécharge un fichier depuis une URL vers le chemin spécifié."""
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        Path(save_path).parent.mkdir(parents=True, exist_ok=True)

        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return True
    except Exception as e:
        print(f"  Erreur lors du téléchargement de {url} : {e}")
        return False


def process_attachment(attachment, table_name, record_id):
    """
    Traite une seule pièce jointe : télécharge l'image principale et les miniatures.
    Retourne la pièce jointe modifiée avec les URLs locales.
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
            print(f"  Téléchargé : {filename}")
        else:
            print(f"  Échec du téléchargement de l'image principale : {filename}")

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
                    print(f"    Miniature ({size}) : {filename}")
                else:
                    processed_thumbnails[size] = thumb_data

        processed["thumbnails"] = processed_thumbnails

    return processed


def process_attachments_in_fields(fields, table_name, record_id):
    """
    Parcourt tous les champs et traite les tableaux de pièces jointes.
    Retourne les champs modifiés avec les URLs locales.
    """
    processed_fields = {}

    for key, value in fields.items():
        if isinstance(value, list) and len(value) > 0:
            first_item = value[0]
            if isinstance(first_item, dict) and "url" in first_item and "filename" in first_item:
                print(f"  Traitement du champ de pièce jointe : {key}")
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


# ── Logique de Synchronisation ───────────────────────────────

def _is_attachment_field(value):
    """Vérifie si une valeur de champ est un tableau de pièces jointes Airtable."""
    return (isinstance(value, list) and len(value) > 0
            and isinstance(value[0], dict)
            and "url" in value[0] and "filename" in value[0])


def _preserve_existing_attachments(connection, table_name, record_id, new_fields):
    """
    Fusionne les nouveaux champs avec les champs de pièces jointes existants de la base.
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
    """Synchronise une seule table depuis Airtable vers MySQL."""
    print(f"\n{'='*50}")
    print(f"Synchronisation de la table : {table_name}")
    print(f"{'='*50}")

    create_table_if_not_exists(connection, table_name)

    table = api.table(base_id, table_name)
    records = table.all()

    print(f"{len(records)} enregistrements trouvés")

    for record in records:
        record_id = record["id"]
        created_time = record["createdTime"]
        fields = record["fields"]

        print(f"\nTraitement de l'enregistrement : {record_id}")

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
                f"  ÉCHEC de l'insertion de l'enregistrement {record_id} dans la table {table_name} : {e}")
            raise e

    print(f"\nSynchronisation terminée pour {table_name} : {len(records)} enregistrements")
    return [r["id"] for r in records]


def cleanup_records(connection, table_name, active_ids):
    """Supprime les enregistrements de MySQL qui ne sont plus présents dans Airtable."""
    if not active_ids:
        print(f"  Nettoyage : suppression de TOUS les enregistrements de {table_name}")
        connection.execute(text(f"DELETE FROM `{table_name}`"))
        return

    query = text(f"DELETE FROM `{table_name}` WHERE id NOT IN (:active_ids)")
    connection.execute(query, {"active_ids": active_ids})
    
    # Dans SQLAlchemy Core, nous pouvons obtenir les lignes affectées via le résultat
    # mais pour simplifier dans ce script, nous logguons juste que le nettoyage a eu lieu
    print(f"  Nettoyage des enregistrements obsolètes de {table_name}")


def cleanup_images(table_name, active_ids):
    """Supprime les dossiers d'images locaux pour les enregistrements qui ne sont plus dans Airtable."""
    table_dir = os.path.join(IMAGE_STORE_PATH, table_name)
    if not os.path.exists(table_dir):
        return

    for record_id in os.listdir(table_dir):
        if record_id not in active_ids:
            record_dir = os.path.join(table_dir, record_id)
            if os.path.isdir(record_dir):
                print(
                    f"  Nettoyage : suppression des images pour l'enregistrement obsolète {record_id}")
                shutil.rmtree(record_dir)


# ── Public API ───────────────────────────────────────────────

def clean_images_folder():
    """Vide tout le contenu du dossier des images."""
    if os.path.exists(IMAGE_STORE_PATH):
        print(f"🧹 Nettoyage de {IMAGE_STORE_PATH}...")
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
    Point d'entrée principal de la synchronisation.

    Args:
        config: dict avec les clés : airtable_token, airtable_base_id,
                mysql_host, mysql_user, mysql_password, mysql_database,
                use_ssh_tunnel, etc.
        sync_db : si True, synchronise les enregistrements de la base de données
        sync_images : si True, télécharge les images
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

    # Centralized connection handling
    use_ssh = config.get("use_ssh_tunnel") or os.getenv("FLASK_ENV") != "production"
    
    if use_ssh:
        from utils.ssh_helper import get_ssh_tunnel
        print("Ensuring SSH tunnel via centralized helper...")
        tunnel, local_port = get_ssh_tunnel()
        
        if tunnel:
            print(f"SSH tunnel active on local port {local_port}")
            engine = get_sqlalchemy_engine(
                "127.0.0.1", config["mysql_user"], config["mysql_password"],
                config["mysql_database"], port=local_port
            )
        else:
            # Fallback for dev if tunnel is not available (e.g. local mysql)
            print("SSH tunnel not available, attempting direct connection...")
            engine = get_sqlalchemy_engine(
                config["mysql_host"], config["mysql_user"], config["mysql_password"],
                config["mysql_database"]
            )
    else:
        engine = get_sqlalchemy_engine(
            config["mysql_host"], config["mysql_user"], config["mysql_password"],
            config["mysql_database"]
        )

    with engine.begin() as connection:
        try:
            _do_sync(connection)
        except Exception as e:
            print(f"\nErreur pendant la synchronisation : {e}")
            raise
