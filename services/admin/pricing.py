"""
Service layer for the Pricing admin page.
Reads daily_rate directly from vehicles, heads, grip_products tables.
Handles salary_rates and logistics_rates CRUD operations.
"""

import logging

from models import GripProduct, Head, LogisticsRate, SalaryRate, Vehicle, db

logger = logging.getLogger(__name__)

# Champs éditables
SALARY_EDITABLE_FIELDS = {
    "group_name", "position", "annexe", "base_hourly",
    "inter_10h", "inter_8h", "notes",
}

LOGISTICS_EDITABLE_FIELDS = {"item_name", "daily_rate", "notes"}

# Facteur de conversion intermittent → facture
INVOICE_FACTOR = 1.65


# ── Helpers ──────────────────────────────────────────────────

def _safe_float(val):
    """Convertit en float de manière sécurisée."""
    if val is None:
        return 0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0


def _item_from_record(record):
    """Convertit un record Airtable-synced en dict pour le template."""
    fields = record.fields or {}
    rate = 0
    try:
        rate = _safe_float(record.daily_rate)
    except AttributeError:
        # La colonne daily_rate n'existe pas encore
        pass
    return {
        "id": record.id,
        "name": fields.get("name") or fields.get("Label") or "Sans nom",
        "daily_rate": rate,
        "order": fields.get("order", 999),
    }


# ══════════════════════════════════════════════════════════════
# ÉQUIPEMENT — lecture depuis vehicles, heads, grip_products
# ══════════════════════════════════════════════════════════════

def list_equipment_rates():
    """Retourne les équipements groupés. Isolé des erreurs SQL."""
    result = {
        "vehicles": {"label": "Tracking Vehicles", "table": "vehicles", "items": []},
        "heads": {"label": "Remote Heads", "table": "heads", "items": []},
        "grip_products": {"label": "Grip & Accessoires", "table": "grip_products", "items": []},
    }

    # Chaque table est chargée indépendamment pour éviter qu'un crash
    # sur une table ne bloque les autres
    for key, model in [("vehicles", Vehicle), ("heads", Head), ("grip_products", GripProduct)]:
        try:
            records = model.query.all()
            items = [_item_from_record(r) for r in records]
            items.sort(key=lambda x: x["order"])
            result[key]["items"] = items
        except Exception as e:
            logger.error(f"Erreur chargement {key} pour tarification: {e}")
            # On laisse items=[] pour cette catégorie

    return result


def update_equipment_daily_rate(table_name, record_id, value):
    """Met à jour le daily_rate d'un item dans sa table source."""
    table_map = {"vehicles": Vehicle, "heads": Head, "grip_products": GripProduct}
    model = table_map.get(table_name)
    if not model:
        raise ValueError(f"Table inconnue : {table_name}")

    record = model.query.get(record_id)
    if not record:
        raise ValueError(f"Enregistrement {record_id} introuvable dans {table_name}")

    record.daily_rate = _safe_float(value) if value not in (None, "", "0") else float(value) if value == "0" else None
    db.session.commit()
    return _item_from_record(record)


# ══════════════════════════════════════════════════════════════
# SALAIRES
# ══════════════════════════════════════════════════════════════

def list_salary_rates():
    """Retourne tous les salaires triés."""
    try:
        rates = SalaryRate.query.order_by(SalaryRate.display_order, SalaryRate.id).all()
        return [r.to_dict() for r in rates]
    except Exception as e:
        logger.error(f"Erreur chargement salary_rates: {e}")
        return []


def list_salary_groups():
    """Retourne la liste des groupes uniques existants pour l'autocomplétion."""
    groups = db.session.query(SalaryRate.group_name).distinct().all()
    return sorted([g[0] for g in groups if g[0]])


def add_salary_rate():
    """Ajoute une nouvelle ligne de salaire."""
    max_order = db.session.query(db.func.max(SalaryRate.display_order)).scalar() or 0
    new_rate = SalaryRate(
        group_name="",
        position="",
        annexe="",
        display_order=max_order + 1,
    )
    db.session.add(new_rate)
    db.session.commit()
    return new_rate.to_dict()


def delete_salary_rate(rate_id):
    """Supprime une ligne de salaire."""
    rate = SalaryRate.query.get(rate_id)
    if not rate:
        raise ValueError(f"Salaire #{rate_id} introuvable")
    db.session.delete(rate)
    db.session.commit()
    return True


def update_salary_rate(rate_id, field, value):
    """Met à jour un champ spécifique d'un SalaryRate.
    Si le champ est inter_10h ou inter_8h, recalcule automatiquement
    le champ invoice correspondant (× INVOICE_FACTOR).
    """
    if field not in SALARY_EDITABLE_FIELDS:
        raise ValueError(f"Champ non autorisé : {field}")

    rate = SalaryRate.query.get(rate_id)
    if not rate:
        raise ValueError(f"Salaire #{rate_id} introuvable")

    numeric_fields = {"base_hourly", "inter_10h", "inter_8h"}
    if field in numeric_fields:
        value = _safe_float(value) if value not in (None, "") else None
    else:
        value = str(value).strip() if value else ""

    setattr(rate, field, value)

    # Auto-calcul des colonnes Invoice à partir des colonnes Inter
    if field == "inter_10h":
        rate.invoice_10h = round(value * INVOICE_FACTOR, 2) if value else None
    elif field == "inter_8h":
        rate.invoice_8h = round(value * INVOICE_FACTOR, 2) if value else None

    db.session.commit()
    return rate.to_dict()


# ══════════════════════════════════════════════════════════════
# LOGISTIQUE
# ══════════════════════════════════════════════════════════════

def list_logistics_rates():
    """Retourne tous les tarifs logistiques triés."""
    try:
        rates = LogisticsRate.query.order_by(LogisticsRate.display_order, LogisticsRate.id).all()
        return [r.to_dict() for r in rates]
    except Exception as e:
        logger.error(f"Erreur chargement logistics_rates: {e}")
        return []


def add_logistics_rate():
    """Ajoute une nouvelle ligne logistique."""
    max_order = db.session.query(db.func.max(LogisticsRate.display_order)).scalar() or 0
    new_rate = LogisticsRate(
        item_name="",
        daily_rate=0,
        display_order=max_order + 1,
    )
    db.session.add(new_rate)
    db.session.commit()
    return new_rate.to_dict()


def delete_logistics_rate(rate_id):
    """Supprime une ligne logistique."""
    rate = LogisticsRate.query.get(rate_id)
    if not rate:
        raise ValueError(f"Logistique #{rate_id} introuvable")
    db.session.delete(rate)
    db.session.commit()
    return True


def update_logistics_rate(rate_id, field, value):
    """Met à jour un champ spécifique d'un LogisticsRate."""
    if field not in LOGISTICS_EDITABLE_FIELDS:
        raise ValueError(f"Champ non autorisé : {field}")

    rate = LogisticsRate.query.get(rate_id)
    if not rate:
        raise ValueError(f"Logistique #{rate_id} introuvable")

    if field == "daily_rate":
        value = _safe_float(value)
    else:
        value = str(value).strip() if value else ""

    setattr(rate, field, value)
    db.session.commit()
    return rate.to_dict()
