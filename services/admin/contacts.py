import logging
from models import db, Contact, Production
from services.admin.utils import (
    generic_list_records,
    generic_get_record_for_edit,
    generic_delete_record,
    handle_admin_service_error
)

logger = logging.getLogger(__name__)


def list_contacts():
    """Fetch all contacts formatted for listing."""
    fields_map = {
        "prenom": "prenom",
        "nom": "nom",
        "telephone": "telephone",
        "mail": "mail",
        "metier": "metier",
        "production_name": lambda r: r.production_rel.nom if r.production_rel else "Freelance",
    }
    return generic_list_records(Contact, fields_map, order_by_attr=Contact.nom)


@handle_admin_service_error
def create_contact(form):
    """Create a new contact record."""
    pid = form.get("production_id")
    contact = Contact(
        prenom=form.get("prenom", ""),
        nom=form.get("nom", ""),
        telephone=form.get("telephone", ""),
        mail=form.get("mail", ""),
        production_id=int(pid) if pid and pid != "None" else None,
        metier=form.get("metier", ""),
    )
    db.session.add(contact)
    db.session.commit()
    return True


@handle_admin_service_error
def update_contact(record_id, form):
    """Update an existing contact record."""
    contact = db.session.get(Contact, record_id)
    if not contact:
        return False

    pid = form.get("production_id")
    contact.prenom = form.get("prenom", "")
    contact.nom = form.get("nom", "")
    contact.telephone = form.get("telephone", "")
    contact.mail = form.get("mail", "")
    contact.production_id = int(pid) if pid and pid != "None" else None
    contact.metier = form.get("metier", "")

    db.session.commit()
    return True


def get_contact_for_edit(record_id):
    """Fetch contact data for editing."""
    fields = ["prenom", "nom", "telephone", "mail", "production_id", "metier"]
    return generic_get_record_for_edit(Contact, record_id, fields)


def delete_contact(record_id):
    """Delete a contact record."""
    return generic_delete_record(Contact, record_id)


def get_productions_for_select():
    """Return all productions for the contact form select."""
    return Production.query.order_by(Production.nom).all()
