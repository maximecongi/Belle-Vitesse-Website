"""
Production service layer — business logic for production management.
"""

from utils.checkout import TABLE_PRODUCTIONS


def list_productions():
    records = TABLE_PRODUCTIONS.all(sort=["Nom"])
    productions = []
    for r in records:
        fields = r.get("fields", {})
        productions.append({
            "id": r["id"],
            "name": fields.get("Nom", "—"),
            "address": fields.get("Adresse", "—"),
            "email": fields.get("Mail", "—"),
            "phone": fields.get("Téléphone", "—"),
        })
    return productions


def build_production_fields(form):
    return {
        "Nom": form.get("name"),
        "Adresse": form.get("address"),
        "Mail": form.get("email"),
        "Téléphone": form.get("phone"),
    }


def create_production(form):
    fields = build_production_fields(form)
    TABLE_PRODUCTIONS.create(fields)
    return True


def update_production(record_id, form):
    fields = build_production_fields(form)
    TABLE_PRODUCTIONS.update(record_id, fields)
    return True


def get_production_for_edit(record_id):
    record = TABLE_PRODUCTIONS.get(record_id)
    if not record:
        return None

    fields = record.get("fields", {})
    return {
        "name": fields.get("Nom", ""),
        "address": fields.get("Adresse", ""),
        "email": fields.get("Mail", ""),
        "phone": fields.get("Téléphone", ""),
    }


def delete_production(record_id):
    TABLE_PRODUCTIONS.delete(record_id)
