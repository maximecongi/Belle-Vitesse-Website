import logging

from models import Production, db
from services.admin.utils import (
    BusinessIntegrityError,
    generic_delete_record,
    generic_get_record_for_edit,
    generic_list_records,
    handle_admin_service_error,
)
from services.common.kdrive import dispatch_rename_production

logger = logging.getLogger(__name__)


def list_productions():
    """Récupère tous les enregistrements de production formattés pour l'affichage."""
    fields_map = {
        "name": "name",
        "address": "address",
        "email": "mail",
        "phone": "phone",
    }
    return generic_list_records(Production, fields_map, order_by_attr=Production.name)


@handle_admin_service_error
def create_production(form):
    """Crée un nouvel enregistrement de production."""
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
    """Met à jour un enregistrement de production existant et renomme les dossiers kDrive si le nom a changé."""
    prod = db.session.get(Production, record_id)
    if not prod:
        return False

    old_name = (prod.name or "").strip()
    new_name = form.get("name", "").strip()

    prod.name = new_name
    prod.address = form.get("address", "")
    prod.mail = form.get("email", "")
    prod.phone = form.get("phone", "")

    db.session.commit()

    renamed_kdrive = False
    if old_name and new_name and old_name != new_name:
        try:
            logger.info(f"🏷️ Déclenchement du renommage kDrive pour la production '{old_name}' -> '{new_name}'")
            dispatch_rename_production(old_name, new_name)
            renamed_kdrive = True
        except Exception as e:
            logger.error(f"❌ Erreur lors du déclenchement du renommage kDrive pour '{old_name}' -> '{new_name}': {e}")

    return {"success": True, "renamed_kdrive": renamed_kdrive}


def get_production_for_edit(record_id):
    """Récupère les données d'une production pour l'édition."""
    fields = ["name", "address", "mail", "phone"]
    data = generic_get_record_for_edit(Production, record_id, fields)
    if not data:
        return None
    
    # Mappe les noms des modèles vers les noms des formulaires
    return {
        "name": data["name"],
        "address": data.get("address", ""),
        "email": data.get("mail", ""),
        "phone": data.get("phone", ""),
    }


def delete_production(record_id):
    """
    Supprime un enregistrement de production après vérification de l'intégrité référentielle.
    Empêche la suppression si des projets ou des contacts y sont rattachés.
    """
    prod = db.session.get(Production, record_id)
    if not prod:
        return True

    from models import Contact, Project

    # 1. Vérifier si des projets sont associés à cette société de production
    linked_projects = Project.query.filter_by(production_id=record_id).all()
    if linked_projects:
        active_projects = [p for p in linked_projects if p.deleted_at is None]
        projects_to_show = active_projects if active_projects else linked_projects
        count = len(projects_to_show)
        sample_names = ", ".join(f"« {p.name} »" for p in projects_to_show[:3])
        if count > 3:
            sample_names += f" et {count - 3} autre(s)"

        raise BusinessIntegrityError(
            f"Impossible de supprimer la société de production « {prod.name} » : "
            f"elle est actuellement associée à {count} projet(s) ({sample_names}). "
            "Veuillez d'abord réassigner ou archiver ces projets."
        )

    # 2. Vérifier si des contacts sont associés à cette production
    linked_contacts = Contact.query.filter_by(production_id=record_id).all()
    if linked_contacts:
        count = len(linked_contacts)
        sample_names = ", ".join(f"{c.first_name} {c.last_name}".strip() for c in linked_contacts[:3])
        if count > 3:
            sample_names += f" et {count - 3} autre(s)"

        raise BusinessIntegrityError(
            f"Impossible de supprimer la société de production « {prod.name} » : "
            f"{count} contact(s) y sont rattaché(s) ({sample_names}). "
            "Veuillez réassigner ou supprimer ces contacts avant de continuer."
        )

    return generic_delete_record(Production, record_id)
