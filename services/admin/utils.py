import json
import logging
import os
from pathlib import Path

from flask import current_app

from models import CheckoutVehicle
from utils.checkpoints import get_checkpoints_for_vehicle

logger = logging.getLogger(__name__)


def _parse_photos_json(text):
    if not text:
        return []
    try:
        paths = json.loads(text)
        return [{"url": f"/files/{p}", "label": p.split("/")[-1]} for p in paths]
    except Exception:
        return [{"url": f"/files/{text}", "label": "File"}]


def _delete_inspection_files(record):
    """
    Delete all physical files associated with a checkout or checkin record.
    Includes interior/exterior photos, and the signed PDF.
    """
    private_folder = current_app.config.get("PRIVATE_FOLDER")
    if not private_folder:
        return

    # 1. Photos
    photo_fields = [record.photos_interieur, record.photos_exterieur]

    deleted_dirs = set()

    for field in photo_fields:
        if not field:
            continue
        try:
            # Field can be a JSON array or a single filename
            paths = json.loads(field) if isinstance(
                field, str) and field.startswith('[') else [field]
            for p in paths:
                if not isinstance(p, str):
                    continue
                full_path = Path(private_folder) / "uploads" / p
                if full_path.exists():
                    try:
                        parent_dir = full_path.parent
                        os.remove(full_path)
                        logger.info(f"🗑️ Photo supprimée : {full_path}")
                        deleted_dirs.add(parent_dir)
                    except Exception as e:
                        logger.error(
                            f"❌ Échec de la suppression de la photo {full_path}: {e}")
        except Exception as e:
            logger.warning(
                f"⚠️ Erreur lors du parsing des photos pour suppression: {e}")

    # 1.1 Cleanup empty photo directories
    for d in deleted_dirs:
        try:
            if d.exists() and not any(d.iterdir()):
                d.rmdir()
                logger.info(f"🗑️ Dossier vide supprimé : {d}")
        except Exception:
            pass

    output_base = current_app.config.get(
        "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))

    # 2. Signed PDF
    if record.pdf_scelle:
        # pdf_scelle is usually a URL: http://.../checkout/document/filename.pdf
        # or http://.../checkout/document/YEAR/MONTH/.../filename.pdf
        path_part = record.pdf_scelle.split("/document/")[-1].split("?")[0]

        # Check new hierarchical structure
        pdf_path_new = Path(output_base) / path_part
        if pdf_path_new.exists():
            try:
                os.remove(pdf_path_new)
                logger.info(f"🗑️ PDF (Nouveau) supprimé : {pdf_path_new}")
            except Exception as e:
                logger.error(
                    f"❌ Échec de la suppression du PDF (Nouveau) {pdf_path_new}: {e}")
        else:
            # Fallback to legacy flat structure
            subfolder = "checkout_pdfs" if isinstance(
                record, CheckoutVehicle) else "checkin_pdfs"
            pdf_path_legacy = Path(private_folder) / subfolder / path_part
            if pdf_path_legacy.exists():
                try:
                    os.remove(pdf_path_legacy)
                    logger.info(
                        f"🗑️ PDF (Legacy) supprimé : {pdf_path_legacy}")
                except Exception as e:
                    logger.error(
                        f"❌ Échec de la suppression du PDF (Legacy) {pdf_path_legacy}: {e}")


def _is_ready(form, vehicle_id=None):
    """
    Calculate if the vehicle is ready based on inspection fields.
    Returns True if all critical fields are 'OK' or 'Non pertinent'.
    """
    # Get specific checkpoints for this vehicle
    checkpoints = get_checkpoints_for_vehicle(vehicle_id)

    # Only check 'status' type fields
    # Only check 'status' type fields
    status_keys = [cp['key']
                   for cp in checkpoints if cp.get('type') == 'status']

    for key in status_keys:
        val = form.get(key)
        # If it's not present (hidden/not pertinent), we treat it as OK
        # This will be supplemented by the service layer setting it to "Non pertinent"
        if val is not None and val not in ["OK", "Non pertinent"]:
            return False
    return True
