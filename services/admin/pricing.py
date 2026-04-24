"""
Service layer for the Pricing admin page.
Reads daily_rate directly from vehicles, heads, grip_products tables.
Handles salary_rates and logistics_rates CRUD operations.
"""

from collections import OrderedDict

from models import GripProduct, Head, LogisticsRate, SalaryRate, Vehicle, db


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

LOGISTICS_EDITABLE_FIELDS = {"item_name", "daily_rate", "notes"}


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


def add_salary_rate(group_name):
    """Ajoute une nouvelle ligne vide dans un groupe de salaires."""
    if group_name not in SALARY_GROUPS_ORDER:
        group_name = SALARY_GROUPS_ORDER[0]

    # Trouver l'ordre max
    max_order = db.session.query(db.func.max(SalaryRate.display_order)).filter_by(group_name=group_name).scalar() or 0

    new_rate = SalaryRate(
        group_name=group_name,
        position="Nouvelle position",
        display_order=max_order + 1
    )
    db.session.add(new_rate)
    db.session.commit()
    return new_rate.to_dict()


def delete_salary_rate(rate_id):
    """Supprime une ligne de salaire."""
    rate = SalaryRate.query.get(rate_id)
    if rate:
        db.session.delete(rate)
        db.session.commit()
        return True
    return False


def update_salary_rate(rate_id, field, value):
    """Met à jour un champ spécifique d'un SalaryRate."""
    if field not in SALARY_EDITABLE_FIELDS:
        raise ValueError(f"Champ non autorisé : {field}")

    rate = SalaryRate.query.get(rate_id)
    if not rate:
        raise ValueError(f"Tarif salaire #{rate_id} introuvable")

    numeric_fields = {"base_hourly", "invoice_10h", "invoice_8h", "inter_10h", "inter_8h"}
    if field in numeric_fields:
        try:
            value = float(value) if value not in (None, "") else None
        except ValueError:
            value = None
    elif field == "position":
        value = str(value).strip()
        if not value:
            raise ValueError("La position ne peut pas être vide")
    else:
        value = str(value).strip() if value else ""

    setattr(rate, field, value)
    db.session.commit()
    return rate.to_dict()


# ── Logistique ───────────────────────────────────────────────

def list_logistics_rates():
    """Retourne tous les tarifs logistiques."""
    rates = (LogisticsRate.query
             .order_by(LogisticsRate.display_order)
             .all())
    return [r.to_dict() for r in rates]


def add_logistics_rate():
    """Ajoute une nouvelle ligne logistique vide."""
    max_order = db.session.query(db.func.max(LogisticsRate.display_order)).scalar() or 0
    new_rate = LogisticsRate(
        item_name="Nouvel élément logistique",
        daily_rate=0,
        display_order=max_order + 1
    )
    db.session.add(new_rate)
    db.session.commit()
    return new_rate.to_dict()


def delete_logistics_rate(rate_id):
    """Supprime une ligne logistique."""
    rate = LogisticsRate.query.get(rate_id)
    if rate:
        db.session.delete(rate)
        db.session.commit()
        return True
    return False


def update_logistics_rate(rate_id, field, value):
    """Met à jour un champ spécifique d'un LogisticsRate."""
    if field not in LOGISTICS_EDITABLE_FIELDS:
        raise ValueError(f"Champ non autorisé : {field}")

    rate = LogisticsRate.query.get(rate_id)
    if not rate:
        raise ValueError(f"Tarif logistique #{rate_id} introuvable")

    if field == "daily_rate":
        try:
            value = float(value) if value not in (None, "") else 0
        except ValueError:
            value = 0
    else:
        value = str(value).strip() if value else ""

    setattr(rate, field, value)
    db.session.commit()
    return rate.to_dict()
