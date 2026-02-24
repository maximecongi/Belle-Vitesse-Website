import json
import logging
import os
from pathlib import Path
from collections import defaultdict
from datetime import date

from flask import current_app, url_for
from werkzeug.utils import secure_filename

from models import db, CheckoutVehicle, CheckinVehicle, Production, Project, User
from utils.airtable import get_vehicles
from utils.formatting import format_date_fr

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
    Includes odometer photos, interior/exterior photos, and the signed PDF.
    """
    private_folder = current_app.config.get("PRIVATE_FOLDER")
    if not private_folder:
        return

    # 1. Photos
    photo_fields = [record.photo_compteur,
                    record.photos_interieur, record.photos_exterieur]
    for field in photo_fields:
        if not field:
            continue
        try:
            # Field can be a JSON array or a single filename
            paths = json.loads(field) if isinstance(
                field, str) and field.startswith('[') else [field]
            for p in paths:
                # Sanitize p (it might be a full dict if not careful, but usually it's a string)
                if not isinstance(p, str):
                    continue
                full_path = Path(private_folder) / "uploads" / p
                if full_path.exists():
                    try:
                        os.remove(full_path)
                        logger.info(f"🗑️ Photo supprimée : {full_path}")
                    except Exception as e:
                        logger.error(
                            f"❌ Échec de la suppression de la photo {full_path}: {e}")
        except Exception as e:
            logger.warning(
                f"⚠️ Erreur lors du parsing des photos pour suppression: {e}")

    # 2. Signed PDF
    if record.pdf_scelle:
        # pdf_scelle is usually a URL: http://.../checkout/document/filename.pdf
        filename = record.pdf_scelle.split("/")[-1]
        if "?" in filename:
            filename = filename.split("?")[0]

        # Determine subfolder based on record type
        subfolder = "checkout_pdfs" if isinstance(
            record, CheckoutVehicle) else "checkin_pdfs"
        pdf_path = Path(private_folder) / subfolder / filename
        if pdf_path.exists():
            try:
                os.remove(pdf_path)
                logger.info(f"🗑️ PDF supprimé : {pdf_path}")
            except Exception as e:
                logger.error(
                    f"❌ Échec de la suppression du PDF {pdf_path}: {e}")


def _is_ready(form):
    """
    Calculate if the vehicle is ready based on inspection fields.
    Returns True if all critical fields are 'OK' or 'Non pertinent'.
    """
    checks = [
        "tires", "spare_tire", "brakes", "lights", "oil", "coolant",
        "engine_start", "wipers", "horn", "safety_triangle", "fire_extinguisher"
    ]
    for key in checks:
        val = form.get(key)
        if val not in ["OK", "Non pertinent"]:
            return False
    return True


