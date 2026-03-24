import logging

from models import Contact, Production, db
from services.admin.utils import (
    generic_delete_record,
    generic_get_record_for_edit,
    generic_list_records,
    handle_admin_service_error,
)

logger = logging.getLogger(__name__)


def list_contacts():
    """Récupère tous les contacts formattés pour l'affichage en liste."""
    fields_map = {
        "first_name": "first_name",
        "last_name": "last_name",
        "phone": "phone",
        "mail": "mail",
        "job_title": "job_title",
        "production_name": lambda r: r.production_rel.name if r.production_rel else "Freelance",
    }
    return generic_list_records(Contact, fields_map, order_by_attr=Contact.last_name)


@handle_admin_service_error
def create_contact(form):
    """Crée un nouvel enregistrement de contact."""
    pid = form.get("production_id")
    contact = Contact(
        first_name=form.get("first_name", ""),
        last_name=form.get("last_name", ""),
        phone=form.get("phone", ""),
        mail=form.get("mail", ""),
        production_id=int(pid) if pid and pid != "None" else None,
        job_title=form.get("job_title", ""),
    )
    db.session.add(contact)
    db.session.commit()
    return True


@handle_admin_service_error
def update_contact(record_id, form):
    """Met à jour un enregistrement de contact existant."""
    contact = db.session.get(Contact, record_id)
    if not contact:
        return False

    pid = form.get("production_id")
    contact.first_name = form.get("first_name", "")
    contact.last_name = form.get("last_name", "")
    contact.phone = form.get("phone", "")
    contact.mail = form.get("mail", "")
    contact.production_id = int(pid) if pid and pid != "None" else None
    contact.job_title = form.get("job_title", "")

    db.session.commit()
    return True


def get_contact_for_edit(record_id):
    """Récupère les données d'un contact pour l'édition."""
    fields = ["first_name", "last_name", "phone", "mail", "production_id", "job_title"]
    return generic_get_record_for_edit(Contact, record_id, fields)


def delete_contact(record_id):
    """Supprime un enregistrement de contact."""
    return generic_delete_record(Contact, record_id)


def get_productions_for_select():
    """Retourne toutes les productions pour le sélecteur du formulaire contact."""
    return Production.query.order_by(Production.name).all()
