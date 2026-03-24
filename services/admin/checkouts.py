import logging
from datetime import date

from flask import current_app

from models import CheckoutVehicle, db
from services.admin.inspections import (
    apply_inspection_data,
    delete_inspection_unified,
    get_inspection_detail_unified,
    get_unified_form_context,
    list_inspections_unified,
    upload_inspection_photos_shared,
)
from services.admin.utils import handle_admin_service_error

logger = logging.getLogger(__name__)


def list_checkouts():
    """Récupère tous les départs par la logique unifiée."""
    return list_inspections_unified("checkout")


def get_checkout_detail(record_id):
    """Récupère un départ spécifique par la logique unifiée."""
    return get_inspection_detail_unified("checkout", record_id)


def get_checkout_form_context():
    """Récupère le contexte du formulaire pour un départ."""
    return get_unified_form_context(mode="checkout")


@handle_admin_service_error
def create_checkout(form, files=None):
    """Crée un nouvel enregistrement de départ dans la base de données."""
    pid = form.get("project_id")
    uid = form.get("controller_id")
    try:
        controller_id = int(uid) if uid and uid != "None" else None
    except (ValueError, TypeError):
        current_app.logger.warning(f"⚠️ Identifiant contrôleur invalide : {uid}")
        controller_id = None

    record = CheckoutVehicle(
        status="in_progress",
        inspection_date=date.today(),
        project_id=int(pid) if pid and pid != "None" else None,
        controller_id=controller_id,
        vehicle_id=form.get("vehicle_id") if form.get("vehicle_id") != "None" else None,
    )

    apply_inspection_data(record, form, is_checkout=True)
    db.session.add(record)
    db.session.commit()

    if files:
        upload_inspection_photos_shared("checkout", record, files)

    return True


@handle_admin_service_error
def update_checkout(record_id, form, files=None):
    """Met à jour un départ existant."""
    record = db.session.get(CheckoutVehicle, record_id)
    if not record:
        return False

    apply_inspection_data(record, form, is_checkout=True)
    db.session.commit()

    if files:
        upload_inspection_photos_shared("checkout", record, files)

    return True


@handle_admin_service_error
def delete_checkout(record_id):
    """Supprime un départ par la logique unifiée."""
    return delete_inspection_unified("checkout", record_id)
