import logging

from models import Production, db
from services.admin.utils import (
    generic_delete_record,
    generic_get_record_for_edit,
    generic_list_records,
    handle_admin_service_error,
)

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
    """Met à jour un enregistrement de production existant."""
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
    """Supprime un enregistrement de production."""
    return generic_delete_record(Production, record_id)
