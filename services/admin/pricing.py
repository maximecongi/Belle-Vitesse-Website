"""
Service layer for the Pricing admin page.
Reads daily_rate directly from vehicles, heads, grip_products tables.
Handles salary_rates CRUD operations.
"""

from collections import OrderedDict

from models import GripProduct, Head, SalaryRate, Vehicle, db


# ── Ordre d'affichage des groupes salaires ───────────────────

SALARY_GROUPS_ORDER = [
    "Pilote",
    "Remote Head / Gimbal Technician",
    "Grip",
]

SALARY_EDITABLE_FIELDS = {
    "position", "annexe", "base_hourly",
    "invoice_10h", "invoice_8h", "inter_10h", "inter_8h", "notes",
}


# ── Helpers ──────────────────────────────────────────────────

def _item_from_record(record):
    """Convertit un record Airtable-synced en dict pour le template."""
    fields = record.fields or {}
    return {
        "id": record.id,
        "name": fields.get("name", "Sans nom"),
        "daily_rate": float(record.daily_rate) if record.daily_rate else 0,
        "order": fields.get("order", 999),
    }


# ── Équipement ───────────────────────────────────────────────

def list_equipment_rates():
    """
    Retourne les tarifs jour groupés par catégorie :
    Tracking Vehicles / Remote Heads / Grip Products
    """
    vehicles = Vehicle.query.all()
    heads = Head.query.all()
    grips = GripProduct.query.all()

    def to_sorted_list(records):
        items = [_item_from_record(r) for r in records]
        items.sort(key=lambda x: x["order"])
        return items

    return OrderedDict([
        ("vehicles", {
            "label": "Tracking Vehicles",
            "table": "vehicles",
            "items": to_sorted_list(vehicles),
        }),
        ("heads", {
            "label": "Remote Heads",
            "table": "heads",
            "items": to_sorted_list(heads),
        }),
        ("grip_products", {
            "label": "Grip & Accessoires",
            "table": "grip_products",
            "items": to_sorted_list(grips),
        }),
    ])


# Map table name → model class
_TABLE_MODELS = {
    "vehicles": Vehicle,
    "heads": Head,
    "grip_products": GripProduct,
}


def update_equipment_daily_rate(table_name, record_id, value):
    """Met à jour le daily_rate d'un item dans sa table source."""
    model = _TABLE_MODELS.get(table_name)
    if not model:
        raise ValueError(f"Table inconnue : {table_name}")

    record = model.query.get(record_id)
    if not record:
        raise ValueError(f"Enregistrement {record_id} introuvable dans {table_name}")

    try:
        record.daily_rate = float(value) if value not in (None, "") else None
    except (ValueError, TypeError):
        raise ValueError(f"Valeur invalide : {value}")

    db.session.commit()
    return _item_from_record(record)


# ── Salaires ─────────────────────────────────────────────────

def list_salary_rates():
    """Retourne les SalaryRate groupés par group_name."""
    rates = (SalaryRate.query
             .order_by(SalaryRate.group_name, SalaryRate.display_order)
             .all())

    grouped = OrderedDict()
    for group in SALARY_GROUPS_ORDER:
        grouped[group] = []

    for rate in rates:
        if rate.group_name not in grouped:
            grouped[rate.group_name] = []
        grouped[rate.group_name].append(rate.to_dict())

    return grouped


def update_salary_rate(rate_id, field, value):
    """Met à jour un champ spécifique d'un SalaryRate."""
    if field not in SALARY_EDITABLE_FIELDS:
        raise ValueError(f"Champ non autorisé : {field}")

    rate = SalaryRate.query.get(rate_id)
    if not rate:
        raise ValueError(f"Tarif salaire #{rate_id} introuvable")

    # Coercition de type
    numeric_fields = {"base_hourly", "invoice_10h", "invoice_8h", "inter_10h", "inter_8h"}
    if field in numeric_fields:
        value = float(value) if value not in (None, "") else None
    elif field == "position":
        value = str(value).strip()
        if not value:
            raise ValueError("La position ne peut pas être vide")
    else:
        value = str(value).strip() if value else ""

    setattr(rate, field, value)
    db.session.commit()
    return rate.to_dict()
