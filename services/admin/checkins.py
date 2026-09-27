import logging
from datetime import date

from flask import current_app

from models import CheckinVehicle, CheckoutVehicle, db
from services.admin.inspections import (
    apply_inspection_data,
    delete_inspection_unified,
    get_inspection_detail_unified,
    get_unified_form_context,
    list_inspections_unified,
    upload_inspection_photos_shared,
)
from services.admin.utils import handle_admin_service_error
from utils.entity_resolvers import resolve_inspection, resolve_project

logger = logging.getLogger(__name__)


def list_checkins():
    """Récupère tous les enregistrements de retour par la logique unifiée."""
    return list_inspections_unified("checkin")


def get_checkin_detail(record_id):
    """Récupère un retour spécifique par la logique unifiée."""
    return get_inspection_detail_unified("checkin", record_id)


def get_checkin_form_context():
    """Récupère le contexte du formulaire pour un retour."""
    return get_unified_form_context(mode="checkin")


@handle_admin_service_error
def create_checkin(form, files=None):
    """Crée un nouvel enregistrement de retour dans la base de données."""
    pid = form.get("project_id")
    uid = form.get("controller_id")
    try:
        controller_id = int(uid) if uid and uid != "None" else None
    except (ValueError, TypeError):
        current_app.logger.warning(f"⚠️ Identifiant contrôleur invalide : {uid}")
        controller_id = None

    proj = resolve_project(pid) if pid and pid != "None" else None
    vehicle_id = form.get("vehicle_id") if form.get("vehicle_id") != "None" else None

    # Sécurité : interdire la création d'un retour si un retour existe déjà pour ce véhicule sur ce projet
    if vehicle_id and proj:
        existing_checkin = CheckinVehicle.query.filter(
            CheckinVehicle.vehicle_id == vehicle_id,
            CheckinVehicle.project_id == proj.id,
            CheckinVehicle.deleted_at.is_(None)
        ).order_by(CheckinVehicle.id.desc()).first()

        if existing_checkin:
            code = existing_checkin.inspection_number or f"BVCI-#{existing_checkin.id}"
            raise ValueError(f"un retour est déjà en cours ({code})")

    record = CheckinVehicle(
        status="in_progress",
        inspection_date=date.today(),
        project_id=proj.id if proj else None,
        controller_id=controller_id,
        vehicle_id=vehicle_id,
    )

    apply_inspection_data(record, form, is_checkout=False)

    # Sécurité : s'assurer que le dernier départ (checkout) est bien signé
    if record.vehicle_id:
        query = CheckoutVehicle.query.filter(
            CheckoutVehicle.vehicle_id == record.vehicle_id,
            CheckoutVehicle.deleted_at.is_(None)
        )
        if record.project_id:
            latest_checkout = query.filter(
                CheckoutVehicle.project_id == record.project_id
            ).order_by(CheckoutVehicle.id.desc()).first() or query.order_by(CheckoutVehicle.id.desc()).first()
        else:
            latest_checkout = query.order_by(CheckoutVehicle.id.desc()).first()

        signed_statuses = {"signed", "validated", "completed", "approved", "ok", "signé", "validé"}
        is_signed = bool(latest_checkout and str(latest_checkout.status or "").strip().lower() in signed_statuses)
        if not is_signed:
            force_checkin = str(form.get("force_checkin", "")).strip().lower() in ["true", "1", "on"]
            if not force_checkin:
                raise ValueError("Le départ de ce véhicule n'a pas été validé par une signature. Veuillez cocher la case de confirmation pour enregistrer ce retour exceptionnel.")

            logger.warning(f"⚠️ Création d'un retour exceptionnel sans départ validé pour véhicule {record.vehicle_id} (projet {record.project_id})")
            mention = "⚠️ [Retour exceptionnel sans départ préalable validé]"
            if record.notes:
                if mention not in record.notes:
                    record.notes = f"{mention}\n{record.notes}"
            else:
                record.notes = mention

    db.session.add(record)
    db.session.commit()

    if files:
        upload_inspection_photos_shared("checkin", record, files)

    return True


@handle_admin_service_error
def update_checkin(record_id, form, files=None):
    """Met à jour un retour existant."""
    record = resolve_inspection("checkin", record_id)
    if not record or record.deleted_at is not None:
        return False

    apply_inspection_data(record, form, is_checkout=False)
    db.session.commit()

    if files:
        upload_inspection_photos_shared("checkin", record, files)

    return True


@handle_admin_service_error
def delete_checkin(record_id):
    """Supprime un retour par la logique unifiée."""
    return delete_inspection_unified("checkin", record_id)
