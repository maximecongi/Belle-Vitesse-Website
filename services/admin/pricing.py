"""
Service layer for the Pricing admin page.
Reads daily_rate directly from vehicles, heads, grip_products tables.
Handles salary_rates and logistics_rates CRUD operations.
"""

import logging

from models import AppSetting, GripProduct, Head, LogisticsRate, SalaryRate, Vehicle, db

logger = logging.getLogger(__name__)

# Champs éditables
SALARY_EDITABLE_FIELDS = {
    "group_name", "position", "annexe", "base_hourly", "notes"
}

LOGISTICS_EDITABLE_FIELDS = {"item_name", "daily_rate", "notes"}

# Clé de stockage et valeur par défaut du facteur de conversion
INVOICE_FACTOR_KEY = "invoice_factor"
INVOICE_FACTOR_DEFAULT = 1.65


def get_invoice_factor():
    """Récupère le facteur de conversion intermittent → facture depuis la DB."""
    raw = AppSetting.get(INVOICE_FACTOR_KEY, INVOICE_FACTOR_DEFAULT)
    try:
        return round(float(raw), 4)
    except (ValueError, TypeError):
        return INVOICE_FACTOR_DEFAULT


def update_invoice_factor(new_factor):
    """Met à jour le facteur et recalcule TOUTES les lignes invoice existantes."""
    new_factor = round(float(new_factor), 4)
    if new_factor <= 0:
        raise ValueError("Le facteur doit être positif")

    AppSetting.set(INVOICE_FACTOR_KEY, new_factor)

    # Recalcul global de toutes les lignes salaires
    rates = SalaryRate.query.all()
    for rate in rates:
        _calculate_salary_columns(rate, new_factor)
    db.session.commit()
    logger.info(
        "Coefficient de facturation mis à jour. Les tarifs ont été recalculés.")
    return new_factor


def _calculate_salary_columns(rate, factor=None):
    """Calcule toutes les colonnes à partir de base_hourly."""
    if factor is None:
        factor = get_invoice_factor()
    
    base = float(rate.base_hourly or 0)
    
    # Calculs Intermittents
    rate.inter_8h = round(base * 8, 2)
    rate.inter_10h = round(base * 12, 2)
    rate.inter_hs = round(base * 3, 2)
    
    # Calculs Facture
    rate.invoice_8h = round(float(rate.inter_8h) * factor, 2)
    rate.invoice_10h = round(float(rate.inter_10h) * factor, 2)
    rate.invoice_hs = round(float(rate.inter_hs) * factor, 2)
    
    return rate


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
        "display_order": getattr(record, 'display_order', 0) or 0,
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
            items.sort(key=lambda x: (x["display_order"], x["name"]))
            result[key]["items"] = items
        except Exception as e:
            logger.error(f"Erreur chargement {key} pour tarification: {e}")

    return result


def reorder_equipment(table_name, item_ids):
    """Réordonne les items d'une catégorie d'équipement."""
    table_map = {"vehicles": Vehicle, "heads": Head, "grip_products": GripProduct}
    model = table_map.get(table_name)
    if not model:
        raise ValueError(f"Table inconnue : {table_name}")
    for i, item_id in enumerate(item_ids):
        record = model.query.get(item_id)
        if record:
            record.display_order = i
    db.session.commit()
    return True


def update_equipment_daily_rate(table_name, record_id, value):
    """Met à jour le daily_rate d'un item dans sa table source."""
    table_map = {"vehicles": Vehicle,
                 "heads": Head, "grip_products": GripProduct}
    model = table_map.get(table_name)
    if not model:
        raise ValueError(f"Table inconnue : {table_name}")

    record = model.query.get(record_id)
    if not record:
        raise ValueError(
            f"Enregistrement {record_id} introuvable dans {table_name}")

    record.daily_rate = _safe_float(value) if value not in (
        None, "", "0") else float(value) if value == "0" else None
    db.session.commit()
    return _item_from_record(record)


# ══════════════════════════════════════════════════════════════
# SALAIRES
# ══════════════════════════════════════════════════════════════

def list_salary_rates():
    """Retourne tous les salaires triés (liste plate pour l'API)."""
    try:
        rates = SalaryRate.query.order_by(
            SalaryRate.display_order, SalaryRate.id).all()
        return [r.to_dict() for r in rates]
    except Exception as e:
        logger.error(f"Erreur chargement salary_rates: {e}")
        return []


def list_salary_rates_grouped():
    """Retourne les salaires groupés par group_name (OrderedDict).
    Les groupes sont triés par le display_order min de leurs membres.
    Les rates sont triés par display_order au sein de chaque groupe.
    """
    from collections import OrderedDict
    try:
        rates = SalaryRate.query.order_by(
            SalaryRate.display_order, SalaryRate.id).all()

        grouped = OrderedDict()
        for r in rates:
            gname = r.group_name or "Sans groupe"
            if gname not in grouped:
                grouped[gname] = []
            grouped[gname].append(r.to_dict())

        return grouped
    except Exception as e:
        logger.error(f"Erreur chargement salary_rates groupés: {e}")
        return OrderedDict()


def list_salary_groups():
    """Retourne la liste des groupes uniques existants pour l'autocomplétion."""
    groups = db.session.query(SalaryRate.group_name).distinct().all()
    return sorted([g[0] for g in groups if g[0]])


def add_salary_rate(group_name=""):
    """Ajoute une nouvelle ligne de salaire dans un groupe donné."""
    # display_order = max de ce groupe + 1
    max_order = db.session.query(db.func.max(
        SalaryRate.display_order)).scalar() or 0
    new_rate = SalaryRate(
        group_name=group_name or "",
        position="",
        annexe="",
        base_hourly=0,
        display_order=max_order + 1,
    )
    _calculate_salary_columns(new_rate)
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


def reorder_salary_rates(groups_order):
    """Réordonne toutes les lignes de salaire.
    groups_order = {"GroupeA": [id1, id2], "GroupeB": [id3, id4], ...}
    Met à jour group_name et display_order pour chaque ligne.
    """
    order_counter = 0
    for group_name, rate_ids in groups_order.items():
        for rate_id in rate_ids:
            rate = SalaryRate.query.get(int(rate_id))
            if rate:
                rate.group_name = group_name
                rate.display_order = order_counter
                order_counter += 1
    db.session.commit()
    logger.info(f"Réordonnement salaires: {order_counter} lignes mises à jour")
    return True


def rename_salary_group(old_name, new_name):
    """Renomme toutes les lignes d'un groupe."""
    new_name = new_name.strip()
    if not new_name:
        raise ValueError("Le nom du groupe ne peut pas être vide")
    rates = SalaryRate.query.filter_by(group_name=old_name).all()
    if not rates:
        raise ValueError(f"Groupe '{old_name}' introuvable")
    for rate in rates:
        rate.group_name = new_name
    db.session.commit()
    logger.info(f"Groupe renommé: '{old_name}' → '{new_name}' ({len(rates)} lignes)")
    return new_name


def delete_salary_group(group_name):
    """Supprime toutes les lignes d'un groupe."""
    rates = SalaryRate.query.filter_by(group_name=group_name).all()
    if not rates:
        raise ValueError(f"Groupe '{group_name}' introuvable")
    count = len(rates)
    for rate in rates:
        db.session.delete(rate)
    db.session.commit()
    logger.info(f"Groupe '{group_name}' supprimé ({count} lignes)")
    return count


def update_salary_rate(rate_id, field, value):
    """Met à jour un champ spécifique d'un SalaryRate.
    Si base_hourly est modifié, recalcule TOUTES les colonnes.
    """
    if field not in SALARY_EDITABLE_FIELDS:
        raise ValueError(f"Champ non autorisé : {field}")

    rate = SalaryRate.query.get(rate_id)
    if not rate:
        raise ValueError(f"Salaire #{rate_id} introuvable")

    if field == "base_hourly":
        value = round(_safe_float(value), 2)
    else:
        value = str(value).strip() if value else ""

    setattr(rate, field, value)

    # Si c'est la base qui a changé, on recalcule tout
    if field == "base_hourly":
        _calculate_salary_columns(rate)

    db.session.commit()
    return rate.to_dict()


# ══════════════════════════════════════════════════════════════
# LOGISTIQUE
# ══════════════════════════════════════════════════════════════

def list_logistics_rates():
    """Retourne tous les tarifs logistiques triés."""
    try:
        rates = LogisticsRate.query.order_by(
            LogisticsRate.display_order, LogisticsRate.id).all()
        return [r.to_dict() for r in rates]
    except Exception as e:
        logger.error(f"Erreur chargement logistics_rates: {e}")
        return []


def add_logistics_rate():
    """Ajoute une nouvelle ligne logistique."""
    max_order = db.session.query(db.func.max(
        LogisticsRate.display_order)).scalar() or 0
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
        value = round(_safe_float(value), 2)
    else:
        value = str(value).strip() if value else ""

    setattr(rate, field, value)
    db.session.commit()
    return rate.to_dict()


def reorder_logistics_rates(item_ids):
    """Réordonne les tarifs logistiques."""
    for i, rate_id in enumerate(item_ids):
        rate = LogisticsRate.query.get(int(rate_id))
        if rate:
            rate.display_order = i
    db.session.commit()
    return True
