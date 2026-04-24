"""
Service layer for the Pricing admin page.
Reads daily_rate directly from vehicles, heads, grip_products tables.
Handles salary_rates and logistics_rates CRUD operations.
"""

from models import GripProduct, Head, LogisticsRate, SalaryRate, Vehicle, db


# Champs éditables
SALARY_EDITABLE_FIELDS = {
    "group_name", "position", "annexe", "base_hourly",
    "invoice_10h", "invoice_8h", "inter_10h", "inter_8h", "notes",
}

LOGISTICS_EDITABLE_FIELDS = {"item_name", "daily_rate", "notes"}


# ── Helpers ──────────────────────────────────────────────────

def _item_from_record(record):
    """Convertit un record Airtable-synced en dict."""
    fields = record.fields or {}
    return {
        "id": record.id,
        "name": fields.get("name") or fields.get("Label") or "Sans nom",
        "daily_rate": float(record.daily_rate) if record.daily_rate else 0,
        "order": fields.get("order", 999),
    }


# ── Équipement ───────────────────────────────────────────────

def list_equipment_rates():
    """Affiche TOUS les équipements, par ordre de tri Airtable."""
    try:
        vehicles = Vehicle.query.all()
        heads = Head.query.all()
        grips = GripProduct.query.all()

        def to_sorted_list(records):
            items = [_item_from_record(r) for r in records]
            items.sort(key=lambda x: x["order"])
            return items

        return {
            "vehicles": {"label": "Tracking Vehicles", "table": "vehicles", "items": to_sorted_list(vehicles)},
            "heads": {"label": "Remote Heads", "table": "heads", "items": to_sorted_list(heads)},
            "grip_products": {"label": "Grip & Accessoires", "table": "grip_products", "items": to_sorted_list(grips)},
        }
    except Exception as e:
        print(f"DEBUG: Error in list_equipment_rates: {e}")
        return {}


def update_equipment_daily_rate(table_name, record_id, value):
    _TABLE_MODELS = {"vehicles": Vehicle, "heads": Head, "grip_products": GripProduct}
    model = _TABLE_MODELS.get(table_name)
    record = model.query.get(record_id)
    if record:
        try:
            record.daily_rate = float(value) if value not in (None, "") else None
            db.session.commit()
            return _item_from_record(record)
        except: pass
    return None


# ── Salaires ─────────────────────────────────────────────────

def list_salary_rates():
    """Affiche tous les salaires dans un seul tableau simple."""
    rates = SalaryRate.query.order_by(SalaryRate.display_order, SalaryRate.id).all()
    return [r.to_dict() for r in rates]


def add_salary_rate():
    """Ajoute une ligne de salaire vide."""
    max_order = db.session.query(db.func.max(SalaryRate.display_order)).scalar() or 0
    new_rate = SalaryRate(
        group_name="PILOTE",
        position="Nouvelle position",
        display_order=max_order + 1
    )
    db.session.add(new_rate)
    db.session.commit()
    return new_rate.to_dict()


def delete_salary_rate(rate_id):
    rate = SalaryRate.query.get(rate_id)
    if rate:
        db.session.delete(rate)
        db.session.commit()
        return True
    return False


def update_salary_rate(rate_id, field, value):
    if field not in SALARY_EDITABLE_FIELDS: return None
    rate = SalaryRate.query.get(rate_id)
    if not rate: return None

    numeric_fields = {"base_hourly", "invoice_10h", "invoice_8h", "inter_10h", "inter_8h"}
    if field in numeric_fields:
        try: value = float(value) if value not in (None, "") else None
        except: value = None
    else:
        value = str(value).strip() if value else ""

    setattr(rate, field, value)
    db.session.commit()
    return rate.to_dict()


# ── Logistique ───────────────────────────────────────────────

def list_logistics_rates():
    rates = LogisticsRate.query.order_by(LogisticsRate.display_order, LogisticsRate.id).all()
    return [r.to_dict() for r in rates]


def add_logistics_rate():
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
    rate = LogisticsRate.query.get(rate_id)
    if rate:
        db.session.delete(rate)
        db.session.commit()
        return True
    return False


def update_logistics_rate(rate_id, field, value):
    if field not in LOGISTICS_EDITABLE_FIELDS: return None
    rate = LogisticsRate.query.get(rate_id)
    if not rate: return None

    if field == "daily_rate":
        try: value = float(value) if value not in (None, "") else 0
        except: value = 0
    else:
        value = str(value).strip() if value else ""

    setattr(rate, field, value)
    db.session.commit()
    return rate.to_dict()
