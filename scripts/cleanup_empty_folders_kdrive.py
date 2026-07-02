#!/usr/bin/env python3
"""
purge_empty_kdrive_folders.py
Supprime tous les dossiers vides dans kDrive (récursivement).
Usage : python purge_empty_kdrive_folders.py [--dry-run]
"""

import logging
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# ── Config ────────────────────────────────────────────────────────────────────
DRIVE_ID = os.getenv("N8N_DRIVE_ID")
API_TOKEN = os.getenv("N8N_API_TOKEN")
ROOT_DIR_ID = os.getenv("N8N_ROOT_DIR_ID")
DRY_RUN = "--dry-run" in sys.argv

BASE_URL = f"https://api.infomaniak.com/2/drive/{DRIVE_ID}"
HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── API helpers ───────────────────────────────────────────────────────────────


def list_children(directory_id):
    """Retourne la liste des enfants directs d'un dossier."""
    url = f"{BASE_URL}/files/{directory_id}/files"
    params = {"limit": 1000}
    try:
        r = requests.get(url, headers=HEADERS, params=params)
        r.raise_for_status()
        data = r.json().get("data", [])
        # kDrive peut paginer via cursor
        items = data if isinstance(data, list) else data.get("files", [])
        return items
    except Exception as e:
        log.error(f"Erreur list_children(id={directory_id}): {e}")
        return []


def get_folder_name(file_id):
    """Récupère le nom d'un dossier via son ID."""
    url = f"{BASE_URL}/files/{file_id}"
    try:
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        return r.json().get("data", {}).get("name", str(file_id))
    except Exception:
        return str(file_id)


def delete_folder(file_id, name):
    if DRY_RUN:
        log.info(f"[DRY-RUN] Supprimerait dossier : {name!r} (id={file_id})")
        return
    url = f"{BASE_URL}/files/{file_id}"
    try:
        r = requests.delete(url, headers=HEADERS)
        if r.status_code in (200, 204):
            log.info(f"✓ Supprimé : {name!r} (id={file_id})")
        else:
            log.warning(
                f"✗ Échec suppression {name!r} (id={file_id}) → {r.status_code} {r.text}")
    except Exception as e:
        log.error(f"Erreur delete_folder({name}): {e}")


# ── Logique principale ────────────────────────────────────────────────────────

def process_directory(dir_id, path=""):
    """
    Parcourt récursivement un dossier.
    Retourne True si le dossier est vide après traitement (peut être supprimé par le parent).
    """
    children = list_children(dir_id)

    dirs = [f for f in children if f.get("type") == "dir"]

    # Recurse d'abord dans les sous-dossiers
    for d in dirs:
        child_path = f"{path}/{d['name']}" if path else d['name']
        child_empty = process_directory(d["id"], child_path)
        if child_empty and "SÉCURITÉ" in child_path.upper() and "SÉCURITÉ" not in d["name"].upper():
            delete_folder(d["id"], child_path)
            time.sleep(0.1)  # throttle léger

    # Re-lister pour voir si des sous-dossiers ont été supprimés
    # (on recompte : si plus rien → ce dossier est vide)
    remaining = list_children(dir_id)

    return len(remaining) == 0


def main():
    if not DRIVE_ID or not API_TOKEN:
        log.error(
            "ERREUR : N8N_DRIVE_ID ou N8N_API_TOKEN manquant dans le .env")
        sys.exit(1)

    log.info(
        f"{'[DRY-RUN] ' if DRY_RUN else ''}Démarrage purge dossiers vides — drive {DRIVE_ID}")

    if not ROOT_DIR_ID:
        # Lister la racine : on récupère les dossiers de premier niveau
        url = f"{BASE_URL}/files"
        try:
            r = requests.get(url, headers=HEADERS, params={"limit": 1000})
            r.raise_for_status()
            top_level = r.json().get("data", [])
            dirs = [f for f in top_level if f.get("type") == "dir"]
            for d in dirs:
                empty = process_directory(d["id"], d["name"])
                if empty and "SÉCURITÉ" in d["name"].upper():
                    delete_folder(d["id"], d["name"])
        except Exception as e:
            log.error(f"Erreur lors du listing racine : {e}")
    else:
        root_name = get_folder_name(ROOT_DIR_ID)
        process_directory(ROOT_DIR_ID, root_name)

    log.info("Terminé.")


def log_cron_status(job_name, status, error=None):
    import json
    from datetime import datetime, timezone
    from pathlib import Path

    possible_paths = [
        Path("/srv/bellevitesse/logs"),
        Path("/app/logs"),
        Path(__file__).parent.parent.parent / "logs",
        Path(__file__).parent.parent / "logs",
    ]
    logs_dir = None
    for p in possible_paths:
        if p.exists() and p.is_dir():
            logs_dir = p
            break

    if not logs_dir:
        logs_dir = Path(__file__).parent.parent / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

    status_file = logs_dir / "cron_status.json"

    data = {}
    if status_file.exists():
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    data[job_name] = {
        "last_run": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "error": error
    }

    try:
        temp_file = status_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        temp_file.replace(status_file)
    except Exception as e:
        print(f"Failed to write cron status for {job_name}: {e}")


if __name__ == "__main__":
    import traceback
    log_cron_status("cleanup_empty_folders_kdrive", "running")
    try:
        main()
        log_cron_status("cleanup_empty_folders_kdrive", "success")
    except Exception as e:
        tb = traceback.format_exc()
        log_cron_status("cleanup_empty_folders_kdrive", "failed", error=tb)
        raise e
