import functools
import json
import logging
import os
from pathlib import Path

from flask import current_app

from models import CheckoutVehicle, db
from utils.checkpoints import get_checkpoints_for_vehicle

logger = logging.getLogger(__name__)


def handle_admin_service_error(func):
    """Décorateur pour centraliser la gestion des erreurs dans les services admin (rollback et log)."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erreur dans {func.__name__} : {e}")
            raise e
    return wrapper


def _parse_photos_json(text):
    """Analyse une chaîne JSON de chemins de photos et retourne une liste de dictionnaires (URL, label)."""
    if not text:
        return []
    try:
        paths = json.loads(text)
        return [{"url": f"/files/{p}", "label": p.split("/")[-1]} for p in paths]
    except Exception:
        return [{"url": f"/files/{text}", "label": "File"}]


def _delete_inspection_files(record):
    """
    Supprime tous les fichiers physiques associés à un enregistrement de départ ou de retour.
    Inclut les photos intérieures/extérieures et le PDF signé.
    """

    output_base = current_app.config.get(
        "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))

    # 1. Photos (Hierarchical: output/YEAR/MONTH/.../PHOTOS/ID)
    if record.project and record.inspection_number:
        import shutil

        from utils.storage import get_checkin_photos_path, get_checkout_photos_path

        if isinstance(record, CheckoutVehicle):
            hierarchical_photo_dir = get_checkout_photos_path(
                record.project, record.inspection_number)
        else:
            hierarchical_photo_dir = get_checkin_photos_path(
                record.project, record.inspection_number)

        if hierarchical_photo_dir.exists():
            try:
                shutil.rmtree(hierarchical_photo_dir)
                logger.info(
                    f"🗑️ Dossier PHOTOS supprimé : {hierarchical_photo_dir}")
            except Exception as e:
                logger.error(
                    f"❌ Échec de la suppression du dossier PHOTOS {hierarchical_photo_dir}: {e}")

    # 2. Signed PDF
    if record.signed_pdf_path:
        # signed_pdf_path is usually a URL or relative path: http://.../checkout/document/filepath
        path_part = record.signed_pdf_path.split(
            "/document/")[-1].split("?")[0]
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
    Calcule si le véhicule est 'prêt' basé sur les points de contrôle.
    Retourne True si tous les points critiques sont 'OK' ou 'Non pertinent'.
    Pour les départs (checkout), exige également une batterie à 100%.
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


# ── Aides CRUD Génériques ──────────────────────────────────────────


def generic_list_records(model, fields_map, order_by_attr=None):
    """
    Récupérateur générique qui retourne une liste d'enregistrements formattés.

    Args:
        model: Classe du modèle SQLAlchemy.
        fields_map: Dict mappant les clés frontend aux attributs du modèle ou callables.
        order_by_attr: Attribut optionnel pour le tri.
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
    Récupérateur générique pour les données d'édition de formulaire.

    Args:
        model: Classe du modèle SQLAlchemy.
        record_id: ID de l'enregistrement.
        fields_list: Liste des attributs du modèle à inclure.
    """
    record = db.session.get(model, record_id)
    if not record:
        return None

    return {field: getattr(record, field) or "" for field in fields_list}


@handle_admin_service_error
def generic_delete_record(model, record_id):
    """
    Suppression d'enregistrement générique.
    """
    record = db.session.get(model, record_id)
    if record:
        db.session.delete(record)
        db.session.commit()
    return True
