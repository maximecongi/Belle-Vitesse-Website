#!/usr/bin/env python3
"""
purge_empty_kdrive_folders.py
Supprime tous les dossiers vides dans kDrive (récursivement).
Usage : python purge_empty_kdrive_folders.py [--dry-run]
"""

import sys
import time
import logging
import requests
from pathlib import Path
import os
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
    r = requests.get(url, headers=HEADERS, params=params)
    r.raise_for_status()
    data = r.json().get("data", [])
    # kDrive peut paginer via cursor
    items = data if isinstance(data, list) else data.get("files", [])
    return items


def delete_folder(file_id, name):
    if DRY_RUN:
        log.info(f"[DRY-RUN] Supprimerait dossier : {name!r} (id={file_id})")
        return
    url = f"{BASE_URL}/files/{file_id}"
    r = requests.delete(url, headers=HEADERS)
    if r.status_code in (200, 204):
        log.info(f"✓ Supprimé : {name!r} (id={file_id})")
    else:
        log.warning(
            f"✗ Échec suppression {name!r} (id={file_id}) → {r.status_code} {r.text}")


# ── Logique principale ────────────────────────────────────────────────────────

def process_directory(dir_id, path=""):
    """
    Parcourt récursivement un dossier.
    Retourne True si le dossier est vide après traitement (peut être supprimé par le parent).
    """
    try:
        children = list_children(dir_id)
    except requests.HTTPError as e:
        log.error(f"Impossible de lister {path} (id={dir_id}) : {e}")
        return False

    dirs = [f for f in children if f.get("type") == "dir"]

    # Recurse d'abord dans les sous-dossiers
    for d in dirs:
        child_path = f"{path}/{d['name']}"
        child_empty = process_directory(d["id"], child_path)
        if child_empty:
            delete_folder(d["id"], child_path)
            time.sleep(0.1)  # throttle léger

    # Re-lister pour voir si des sous-dossiers ont été supprimés
    # (on recompte : si plus rien → ce dossier est vide)
    try:
        remaining = list_children(dir_id)
    except requests.HTTPError:
        return False

    return len(remaining) == 0


def main():
    log.info(
        f"{'[DRY-RUN] ' if DRY_RUN else ''}Démarrage purge dossiers vides — drive {DRIVE_ID}")

    if ROOT_DIR_ID is None:
        # Lister la racine : on récupère les dossiers de premier niveau
        url = f"{BASE_URL}/files"
        r = requests.get(url, headers=HEADERS, params={"limit": 1000})
        r.raise_for_status()
        top_level = r.json().get("data", [])
        dirs = [f for f in top_level if f.get("type") == "dir"]
        for d in dirs:
            empty = process_directory(d["id"], d["name"])
            if empty:
                delete_folder(d["id"], d["name"])
    else:
        process_directory(ROOT_DIR_ID, str(ROOT_DIR_ID))

    log.info("Terminé.")


if __name__ == "__main__":
    main()
