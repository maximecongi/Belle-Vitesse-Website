"""
Gestion des fichiers et médias rattachés aux incidents (photos, documents justificatifs).
"""

import logging
import os
import uuid
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename

from utils.image_utils import optimize_and_save_image

logger = logging.getLogger(__name__)


def _save_uploaded_files(file_list, subfolder="photos"):
    """
    Sauvegarde une liste de fichiers uploadés dans output/incidents/<subfolder>/ et retourne leurs chemins relatifs.
    """
    if not file_list:
        return []

    output_base = Path(
        os.getenv("OUTPUT_FOLDER", Path(current_app.root_path) / "output")
    )
    dest_dir = output_base / "incidents" / subfolder
    dest_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    for f in file_list:
        if not f or not getattr(f, "filename", None):
            continue
        original_name = secure_filename(f.filename)
        if not original_name:
            continue

        unique_prefix = uuid.uuid4().hex[:8]
        stem = Path(original_name).stem
        ext = Path(original_name).suffix or ".jpg"
        if subfolder == "photos" and ext.lower() in (".heic", ".heif"):
            ext = ".jpg"
        safe_name = f"{unique_prefix}_{stem}{ext}"
        target_path = dest_dir / safe_name

        try:
            if subfolder == "photos":
                optimize_and_save_image(f, target_path)
            else:
                f.save(target_path)
            # Enregistre le chemin relatif par rapport à output_base
            rel_path = os.path.relpath(target_path, output_base)
            saved_paths.append(rel_path)
        except Exception as err:
            logger.error(
                f"Erreur lors de la sauvegarde du fichier {original_name} : {err}"
            )

    return saved_paths

