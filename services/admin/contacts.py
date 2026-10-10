import logging

from models import Contact, Production, db
from services.admin.utils import (
    BusinessIntegrityError,
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
        "email": "mail",
        "job_title": "job_title",
        "job": "job_title",
        "production_id": lambda r: r.production_id,
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
        mail=form.get("mail", "") or form.get("email", ""),
        production_id=int(pid) if pid and pid != "None" else None,
        job_title=form.get("job_title", "") or form.get("job", ""),
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
    contact.mail = form.get("mail", "") or form.get("email", "")
    contact.production_id = int(pid) if pid and pid != "None" else None
    contact.job_title = form.get("job_title", "") or form.get("job", "")

    db.session.commit()
    return True


def get_contact_for_edit(record_id):
    """Récupère les données d'un contact pour l'édition."""
    fields = ["first_name", "last_name", "phone", "mail", "production_id", "job_title"]
    data = generic_get_record_for_edit(Contact, record_id, fields)
    if data and data.get("production_id") in ("", "—", "None"):
        data["production_id"] = None
    return data


def delete_contact(record_id):
    """
    Supprime un enregistrement de contact après vérification de son rattachement aux projets.
    Empêche la suppression si le contact est actuellement référencé sur des projets actifs.
    """
    contact = db.session.get(Contact, record_id)
    if not contact:
        return True

    from models import Project
    from sqlalchemy import or_

    full_name = f"{contact.first_name} {contact.last_name}".strip() or f"Contact #{record_id}"

    # Vérifier l'assignation sur les projets (pilote, production, dop, 1er ac, chef machino)
    linked_projects = Project.query.filter(
        or_(
            Project.pilot_contact_id == record_id,
            Project.production_contact_id == record_id,
            Project.dop_contact_id == record_id,
            Project.first_ac_contact_id == record_id,
            Project.key_grip_contact_id == record_id,
        )
    ).all()

    if linked_projects:
        active_projects = [p for p in linked_projects if p.deleted_at is None]
        projects_to_show = active_projects if active_projects else linked_projects
        count = len(projects_to_show)
        sample_names = ", ".join(f"« {p.name} »" for p in projects_to_show[:3])
        if count > 3:
            sample_names += f" et {count - 3} autre(s)"

        raise BusinessIntegrityError(
            f"Impossible de supprimer le contact « {full_name} » : "
            f"il est actuellement désigné comme intervenant clé sur {count} projet(s) ({sample_names}). "
            "Veuillez réassigner ces postes sur les projets concernés avant de supprimer ce contact."
        )

    return generic_delete_record(Contact, record_id)


def get_productions_for_select():
    """Retourne toutes les productions pour le sélecteur du formulaire contact."""
    return Production.query.order_by(Production.name).all()
