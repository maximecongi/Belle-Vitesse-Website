import logging
from models import db, Production
from services.admin.utils import (
    generic_list_records,
    generic_get_record_for_edit,
    generic_delete_record,
    handle_admin_service_error
)

logger = logging.getLogger(__name__)


def list_productions():
    """Fetch all production records formatted for listing."""
    fields_map = {
        "name": "name",
        "address": "address",
        "email": "mail",
        "phone": "phone",
    }
    return generic_list_records(Production, fields_map, order_by_attr=Production.name)


@handle_admin_service_error
def create_production(form):
    """Create a new production record."""
    prod = Production(
        name=form.get("name", ""),
        address=form.get("address", ""),
        mail=form.get("email", ""),
        phone=form.get("phone", "")
    )
    db.session.add(prod)
    db.session.commit()
    return True


@handle_admin_service_error
def update_production(record_id, form):
    """Update an existing production record."""
    prod = db.session.get(Production, record_id)
    if not prod:
        return False

    prod.name = form.get("name", "")
    prod.address = form.get("address", "")
    prod.mail = form.get("email", "")
    prod.phone = form.get("phone", "")

    db.session.commit()
    return True


def get_production_for_edit(record_id):
    """Fetch production data for editing."""
    fields = ["name", "address", "mail", "phone"]
    data = generic_get_record_for_edit(Production, record_id, fields)
    if not data:
        return None
    
    # Map model names to form names
    return {
        "name": data["name"],
        "address": data.get("address", ""),
        "email": data.get("mail", ""),
        "phone": data.get("phone", ""),
    }


def delete_production(record_id):
    """Delete a production record."""
    return generic_delete_record(Production, record_id)
