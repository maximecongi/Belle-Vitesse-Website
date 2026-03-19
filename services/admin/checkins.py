import logging
from datetime import date
from flask import current_app
from models import db, CheckinVehicle, CheckoutVehicle
from services.admin.inspections import (
    list_inspections_unified,
    get_inspection_detail_unified,
    get_unified_form_context,
    apply_inspection_data,
    delete_inspection_unified,
    upload_inspection_photos_shared
)
from services.admin.utils import handle_admin_service_error

logger = logging.getLogger(__name__)


def list_checkins():
    """Fetch all checkin records using unified logic."""
    return list_inspections_unified("checkin")


def get_checkin_detail(record_id):
    """Fetch a single checkin record using unified logic."""
    return get_inspection_detail_unified("checkin", record_id)


def get_checkin_form_context():
    """Get form context for checkin."""
    return get_unified_form_context(mode="checkin")


@handle_admin_service_error
def create_checkin(form, files=None):
    """Create a new checkin record in the database."""
    pid = form.get("project_id")
    uid = form.get("controller_id")
    try:
        controller_id = int(uid) if uid and uid != "None" else None
    except (ValueError, TypeError):
        current_app.logger.warning(f"⚠️ Invalid controller_id detected: {uid}")
        controller_id = None

    record = CheckinVehicle(
        status="in_progress",
        inspection_date=date.today(),
        project_id=int(pid) if pid and pid != "None" else None,
        controller_id=controller_id,
        vehicle_id=form.get("vehicle_id") if form.get("vehicle_id") != "None" else None,
    )

    apply_inspection_data(record, form, is_checkout=False)

    # Safety: ensure latest checkout is signed
    if record.vehicle_id:
        latest_checkout = CheckoutVehicle.query.filter_by(
            vehicle_id=record.vehicle_id).order_by(CheckoutVehicle.id.desc()).first()
        if not latest_checkout or latest_checkout.status not in ["signed", "validated"]:
            raise ValueError("Le départ de ce véhicule n'a pas été validé par une signature.")

    db.session.add(record)
    db.session.commit()

    if files:
        upload_inspection_photos_shared("checkin", record, files)

    return True


@handle_admin_service_error
def update_checkin(record_id, form, files=None):
    """Update an existing checkin record."""
    record = db.session.get(CheckinVehicle, record_id)
    if not record:
        return False

    apply_inspection_data(record, form, is_checkout=False)
    db.session.commit()

    if files:
        upload_inspection_photos_shared("checkin", record, files)

    return True


@handle_admin_service_error
def delete_checkin(record_id):
    """Delete a checkin record using unified logic."""
    return delete_inspection_unified("checkin", record_id)
