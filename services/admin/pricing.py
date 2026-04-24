"""
Service layer for the Pricing admin page.
Handles equipment rates and salary rates CRUD operations.
"""

from collections import OrderedDict

from models import EquipmentRate, SalaryRate, db


# ── Catégories d'équipement avec labels d'affichage ──────────

EQUIPMENT_CATEGORIES = OrderedDict([
    ("vehicle", "Tracking Vehicles"),
    ("head", "Remote Heads"),
    ("gimbal", "Gimbals"),
    ("mount", "Mounts & Support"),
])

LOGISTICS_CATEGORIES = OrderedDict([
    ("logistics", "Delivery / Travel / Return"),
])

SALARY_GROUPS_ORDER = [
    "Pilote",
    "Remote Head / Gimbal Technician",
    "Grip",
]

# Champs éditables par type
EQUIPMENT_EDITABLE_FIELDS = {"item_name", "quantity", "daily_rate", "notes"}
SALARY_EDITABLE_FIELDS = {
    "position", "annexe", "base_hourly",
    "invoice_10h", "invoice_8h", "inter_10h", "inter_8h", "notes",
}


# ── Équipement ───────────────────────────────────────────────

def list_equipment_rates():
    """Retourne les EquipmentRate groupés par catégorie (hors logistics)."""
    rates = (EquipmentRate.query
             .filter(EquipmentRate.category != "logistics")
             .order_by(EquipmentRate.category, EquipmentRate.display_order)
             .all())

    grouped = OrderedDict()
    for cat_key, cat_label in EQUIPMENT_CATEGORIES.items():
        grouped[cat_key] = {
            "label": cat_label,
            "items": [],
        }

    for rate in rates:
        if rate.category in grouped:
            grouped[rate.category]["items"].append(rate.to_dict())

    return grouped


def list_logistics_rates():
    """Retourne les EquipmentRate de catégorie 'logistics'."""
    rates = (EquipmentRate.query
             .filter_by(category="logistics")
             .order_by(EquipmentRate.display_order)
             .all())

    return {
        "logistics": {
            "label": "Delivery / Travel / Return",
            "items": [r.to_dict() for r in rates],
        }
    }


def update_equipment_rate(rate_id, field, value):
    """Met à jour un champ spécifique d'un EquipmentRate."""
    if field not in EQUIPMENT_EDITABLE_FIELDS:
        raise ValueError(f"Champ non autorisé : {field}")

    rate = EquipmentRate.query.get(rate_id)
    if not rate:
        raise ValueError(f"Tarif équipement #{rate_id} introuvable")

    # Coercition de type
    if field == "daily_rate":
        value = float(value) if value not in (None, "") else 0
    elif field == "quantity":
        value = int(value) if value not in (None, "") else 1
    elif field in ("item_name",):
        value = str(value).strip()
        if not value:
            raise ValueError("Le nom ne peut pas être vide")

    setattr(rate, field, value)
    db.session.commit()
    return rate.to_dict()


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
