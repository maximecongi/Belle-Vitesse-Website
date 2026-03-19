import json
import logging
import os
from pathlib import Path

from flask import current_app

from models import db, CheckoutVehicle
from utils.checkpoints import get_checkpoints_for_vehicle

import functools

logger = logging.getLogger(__name__)


def handle_admin_service_error(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Error in {func.__name__}: {e}")
            raise e
    return wrapper


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

    output_base = current_app.config.get(
        "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))

    # 1. Photos (Hierarchical: output/YEAR/MONTH/.../PHOTOS/ID)
    if record.project and record.numero_inspection:
        from utils.storage import get_checkout_photos_path, get_checkin_photos_path
        import shutil

        if isinstance(record, CheckoutVehicle):
            hierarchical_photo_dir = get_checkout_photos_path(
                record.project, record.numero_inspection)
        else:
            hierarchical_photo_dir = get_checkin_photos_path(
                record.project, record.numero_inspection)

        if hierarchical_photo_dir.exists():
            try:
                shutil.rmtree(hierarchical_photo_dir)
                logger.info(
                    f"🗑️ Dossier PHOTOS supprimé : {hierarchical_photo_dir}")
            except Exception as e:
                logger.error(
                    f"❌ Échec de la suppression du dossier PHOTOS {hierarchical_photo_dir}: {e}")

    # 2. Signed PDF
    if record.pdf_scelle:
        # pdf_scelle is usually a URL: http://.../checkout/document/filepath
        path_part = record.pdf_scelle.split("/document/")[-1].split("?")[0]
        pdf_path = Path(output_base) / path_part
        if pdf_path.exists():
            try:
                os.remove(pdf_path)
                logger.info(f"🗑️ PDF supprimé : {pdf_path}")
            except Exception as e:
                logger.error(
                    f"❌ Échec de la suppression du PDF {pdf_path}: {e}")


def _is_ready(form, vehicle_id=None, is_checkout=False):
    """
    Calculate if the vehicle is ready based on inspection fields.
    Returns True if all critical fields are 'OK' or 'Non pertinent'.
    For checkouts, also requires a 100% battery charge.
    """
    # 1. Battery check for checkout
    if is_checkout:
        battery_val = form.get("battery_level") or form.get("battery")
        try:
            if battery_val and float(battery_val) < 100:
                return False
        except (ValueError, TypeError):
            pass

    # 2. Status checkpoints check
    checkpoints = get_checkpoints_for_vehicle(vehicle_id)

    # Only check 'status' type fields
    status_keys = [cp['key']
                   for cp in checkpoints if cp.get('type') == 'status']

    for key in status_keys:
        val = form.get(key)
        # If it's not present (hidden/not pertinent), we treat it as OK
        if val is not None and val not in ["ok", "non_applicable"]:
            return False
    return True


# ── Generic CRUD Helpers ──────────────────────────────────────────


def generic_list_records(model, fields_map, order_by_attr=None):
    """
    Generic fetcher that returns a list of records formatted with the 'Fields Pattern'.

    Args:
        model: SQLAlchemy model class.
        fields_map: Dict mapping frontend keys to model attributes or callables.
        order_by_attr: Optional attribute to order by.
    """
    query = model.query
    if order_by_attr:
        query = query.order_by(order_by_attr)

    records = query.all()
    result = []

    for r in records:
        formatted = {"id": r.id}
        for key, attr in fields_map.items():
            if callable(attr):
                formatted[key] = attr(r)
            else:
                formatted[key] = getattr(r, attr) or "—"
        result.append(formatted)

    return result


def format_contact_for_list(c): return {
    "id": c.id,
    "name": f"{c.first_name} {c.last_name}",
    "production": c.production_rel.name if c.production_rel else "Indépendant",
    "job": c.job_title or "—",
    "phone": c.phone or "—",
    "mail": c.mail or "—"
}


def format_production_for_list(p): return {
    "id": p.id,
    "name": p.name,
    "address": p.address or "—",
    "contacts_count": len(p.contacts),
    "projects_count": len(p.projects)
}


def generic_get_record_for_edit(model, record_id, fields_list):
    """
    Generic fetcher for form editing data.

    Args:
        model: SQLAlchemy model class.
        record_id: ID of the record.
        fields_list: List of model attributes to include.
    """
    record = db.session.get(model, record_id)
    if not record:
        return None

    return {field: getattr(record, field) or "" for field in fields_list}


@handle_admin_service_error
def generic_delete_record(model, record_id):
    """
    Generic record deletion.
    """
    record = db.session.get(model, record_id)
    if record:
        db.session.delete(record)
        db.session.commit()
    return True
