import base64
import os
import re
from pathlib import Path
from typing import Optional
from flask import current_app


def _get_output_folder() -> Path:
    """Résout le chemin absolu du dossier output (config Flask ou variable d'environnement)."""
    try:
        if current_app and current_app.config.get("OUTPUT_FOLDER"):
            return Path(current_app.config["OUTPUT_FOLDER"])
    except RuntimeError:
        pass
    return Path(
        os.getenv(
            "OUTPUT_FOLDER",
            Path(current_app.root_path) / "output" if current_app else Path(__file__).resolve().parent.parent / "output"
        )
    )


def get_signatures_base_dir() -> Path:
    """Retourne le répertoire de base pour le stockage des signatures (output/signatures/)."""
    output_base = _get_output_folder()
    sig_dir = output_base / "signatures"
    sig_dir.mkdir(parents=True, exist_ok=True)
    return sig_dir


def sanitize_filename_part(text: str) -> str:
    """Nettoie une chaîne pour une utilisation sûre dans un nom de fichier."""
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", str(text).strip())


def validate_stored_signature_file(rel_path: str) -> str:
    """
    Vérifie qu'un chemin relatif de signature existant pointe vers un fichier PNG
    réellement présent dans le sous-dossier sécurisé output/signatures/, sans risque
    de traversée de répertoire (path traversal).
    """
    if not rel_path or not isinstance(rel_path, str):
        raise ValueError("Chemin de signature invalide.")

    clean_rel = rel_path.strip().lstrip("/")
    if not (clean_rel.startswith("signatures/") and clean_rel.endswith(".png")):
        raise ValueError("Chemin de signature non conforme.")

    output_base = _get_output_folder().resolve()
    target = (output_base / clean_rel).resolve()

    if not str(target).startswith(str((output_base / "signatures").resolve())):
        raise ValueError("Tentative de traversée de répertoire interdite.")

    if not target.is_file():
        raise ValueError(f"Fichier de signature introuvable sur le disque : {clean_rel}")

    return clean_rel


def save_signature_image(base64_data: str, entity_type: str, record_id: str, suffix: str = "") -> str:
    """
    Décode une signature Base64 (data:image/png;base64,...), l'enregistre en fichier PNG
    dans output/signatures/<entity_type>/ et retourne son chemin relatif.

    :param base64_data: Chaîne Base64 complète ou brute (PNG obligatoire)
    :param entity_type: Type d'entité ('waivers', 'incidents', 'checkouts', 'checkins')
    :param record_id: Identifiant métier (ex: BVPW-123, INC-2026-001)
    :param suffix: Suffixe optionnel (ex: '_bv', '_prod')
    :return: Chemin relatif sous output (ex: 'signatures/waivers/BVPW-123.png')
    """
    if not base64_data or not str(base64_data).strip():
        raise ValueError("Données de signature vides ou invalides.")

    raw_str = str(base64_data).strip()

    # Extraction du Base64 pur
    if "," in raw_str:
        raw_str = raw_str.split(",", 1)[1]

    try:
        binary_data = base64.b64decode(raw_str)
    except Exception as err:
        raise ValueError(f"Échec du décodage Base64 de la signature : {err}")

    # Contrôle strict de la taille (max 500 Ko)
    if len(binary_data) > 500 * 1024:
        raise ValueError(f"Signature trop volumineuse ({len(binary_data)} octets, max 500 Ko).")

    # Contrôle strict des octets magiques PNG
    PNG_MAGIC_BYTES = b"\x89PNG\r\n\x1a\n"
    if not binary_data.startswith(PNG_MAGIC_BYTES):
        raise ValueError("Format de signature invalide : le fichier doit être une image PNG valide.")

    # Validation de l'intégrité de l'image via Pillow
    try:
        from io import BytesIO
        from PIL import Image
        with Image.open(BytesIO(binary_data)) as img:
            img.verify()
    except Exception as img_err:
        raise ValueError(f"Fichier image PNG corrompu ou invalide : {img_err}")

    clean_entity = sanitize_filename_part(entity_type)
    clean_id = sanitize_filename_part(record_id)
    clean_suffix = sanitize_filename_part(suffix) if suffix else ""

    target_dir = get_signatures_base_dir() / clean_entity
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{clean_id}{clean_suffix}.png"
    target_file = target_dir / filename

    target_file.write_bytes(binary_data)

    output_base = _get_output_folder()
    return str(target_file.relative_to(output_base))


def load_signature_data_uri(signature_path: Optional[str]) -> Optional[str]:
    """
    Lit le fichier PNG de la signature sur le disque et retourne une Data URI utilisable
    directement dans les templates HTML et WeasyPrint (data:image/png;base64,...).
    """
    if not signature_path or not str(signature_path).strip():
        return None

    clean_path = str(signature_path).strip().lstrip("/")

    # Fresh start : si jamais une chaîne data:image/ est passée directement
    if clean_path.startswith("data:image/"):
        return clean_path

    output_base = _get_output_folder()
    full_path = output_base / clean_path

    if not full_path.exists() or not full_path.is_file():
        return None

    try:
        raw_bytes = full_path.read_bytes()
        encoded = base64.b64encode(raw_bytes).decode("utf-8")
        return f"data:image/png;base64,{encoded}"
    except Exception:
        return None


def delete_signature_file(signature_path: Optional[str]) -> bool:
    """Supprime le fichier physique de signature sur disque."""
    if not signature_path or not str(signature_path).strip():
        return False

    clean_path = str(signature_path).strip().lstrip("/")
    output_base = Path(
        os.getenv(
            "OUTPUT_FOLDER",
            Path(current_app.root_path) / "output" if current_app else Path(__file__).resolve().parent.parent / "output"
        )
    )
    full_path = output_base / clean_path

    try:
        if full_path.exists() and full_path.is_file():
            full_path.unlink()
            return True
    except Exception:
        pass
    return False
