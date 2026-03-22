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
    """Fetch all checkout records using unified logic."""
    return list_inspections_unified("checkout")


def get_checkout_detail(record_id):
    """Fetch a single checkout record using unified logic."""
    return get_inspection_detail_unified("checkout", record_id)


def get_checkout_form_context():
    """Get form context for checkout."""
    return get_unified_form_context(mode="checkout")


@handle_admin_service_error
def create_checkout(form, files=None):
    """Create a new checkout record in the database."""
    pid = form.get("project_id")
    uid = form.get("controller_id")
    try:
        controller_id = int(uid) if uid and uid != "None" else None
    except (ValueError, TypeError):
        current_app.logger.warning(f"⚠️ Invalid controller_id detected: {uid}")
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
    """Update an existing checkout record."""
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
    """Delete a checkout record using unified logic."""
    return delete_inspection_unified("checkout", record_id)
