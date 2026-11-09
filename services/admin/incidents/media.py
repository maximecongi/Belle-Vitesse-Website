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


def _output_base():
    return Path(os.getenv("OUTPUT_FOLDER", Path(current_app.root_path) / "output"))


def _save_uploaded_files(file_list, subfolder="photos", root="incidents"):
    """
    Sauvegarde une liste de fichiers uploadés dans output/<root>/<subfolder>/ et retourne leurs chemins relatifs.
    Les photos sont optimisées (redimensionnement / compression) ; `root` permet le partage avec d'autres
    entités (ex : « reports » pour les rapports d'équipe).
    """
    if not file_list:
        return []

    output_base = _output_base()
    dest_dir = output_base / root / subfolder
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



def _delete_stored_file(rel_path, allowed_prefix):
    """
    Supprime physiquement un fichier stocké sous OUTPUT_FOLDER.
    Refuse tout chemin hors du préfixe autorisé (protection contre la traversée de répertoires).
    """
    if not rel_path:
        return False
    output_base = _output_base().resolve()
    target = (output_base / rel_path).resolve()
    allowed_root = (output_base / allowed_prefix).resolve()
    if allowed_root not in target.parents:
        logger.warning(f"⚠️ Suppression refusée hors de {allowed_prefix} : {rel_path}")
        return False
    try:
        if target.exists():
            target.unlink()
        return True
    except OSError as err:
        logger.error(f"Erreur lors de la suppression du fichier {rel_path} : {err}")
        return False
