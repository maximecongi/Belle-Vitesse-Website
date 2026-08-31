"""
Service layer for the Pricing admin page.
Reads daily_rate directly from vehicles, heads, grip_products tables.
Handles salary_rates and logistics_rates CRUD operations.
"""

import logging

from models import AppSetting, GripProduct, Head, LogisticsRate, SalaryPosition, SalaryRate, Vehicle, db

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
    """Met à jour le facteur et recalcule TOUTES les lignes Facture à partir de Publicité."""
    new_factor = round(float(new_factor), 4)
    if new_factor <= 0:
        raise ValueError("Le facteur doit être positif")

    AppSetting.set(INVOICE_FACTOR_KEY, new_factor)

    # Recalcul global de toutes les lignes Facture
    facture_rates = SalaryRate.query.filter_by(annexe="Facture").all()
    for f_rate in facture_rates:
        publicite_rate = SalaryRate.query.filter_by(
            position_id=f_rate.position_id,
            annexe="Publicité"
        ).first()
        if publicite_rate:
            f_rate.base_hourly = round(float(publicite_rate.base_hourly or 0) * new_factor, 2)
            _calculate_salary_columns(f_rate)

    db.session.commit()
    logger.info(
        f"Coefficient de facturation mis à jour à {new_factor}. Les tarifs Facture ont été recalculés.")
    return new_factor


def _calculate_salary_columns(rate, factor=None):
    """Calcule toutes les colonnes à partir de base_hourly."""
    if factor is None:
        factor = get_invoice_factor()
    
    base = float(rate.base_hourly or 0)
    
    # Calculs Intermittents
    if rate.annexe == "Annexe 1 renfort":
        rate.inter_8h = round(base * 10.25, 2)
        rate.inter_10h = round(base * 13.25, 2)
    elif rate.annexe == "USPA":
        rate.inter_8h = round(base * 8, 2)
        rate.inter_10h = round(base * 10, 2)
    elif rate.annexe == "USPA renfort":
        rate.inter_8h = round(base * 8, 2)
        rate.inter_10h = round(base * 10.5, 2)
    else:
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
        record = db.session.get(model, item_id)
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

    record = db.session.get(model, record_id)
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

def _make_renfort_rate_dict(rate):
    """Génère le dictionnaire d'un tarif Annexe 1 renfort à partir d'un SalaryRate."""
    d = rate.to_dict() if hasattr(rate, 'to_dict') else dict(rate)
    d["id"] = f"renfort_{d['id']}"
    d["annexe"] = "Annexe 1 renfort"
    
    # Calculs Intermittents spécifiques (8h = 10.25x, 10h = 13.25x)
    base = float(d["base_hourly"] or 0)
    d["inter_8h"] = round(base * 10.25, 2)
    d["inter_10h"] = round(base * 13.25, 2)
    d["inter_hs"] = round(base * 3, 2)
    
    # Calculs Facture
    factor = get_invoice_factor()
    d["invoice_8h"] = round(d["inter_8h"] * factor, 2)
    d["invoice_10h"] = round(d["inter_10h"] * factor, 2)
    d["invoice_hs"] = round(d["inter_hs"] * factor, 2)
    
    return d


def list_salary_rates():
    """Retourne tous les salaires triés (liste plate pour l'API)."""
    try:
        rates = SalaryRate.query.join(SalaryPosition).order_by(
            SalaryPosition.display_order, SalaryRate.id).all()
        results = []
        for r in rates:
            results.append(r.to_dict())
            if r.annexe == "Annexe 1":
                results.append(_make_renfort_rate_dict(r))
        return results
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
        rates = SalaryRate.query.join(SalaryPosition).order_by(
            SalaryPosition.display_order, SalaryRate.id).all()

        grouped = OrderedDict()
        for r in rates:
            gname = r.group_name or "Sans groupe"
            if gname not in grouped:
                grouped[gname] = []
            grouped[gname].append(r.to_dict())
            if r.annexe == "Annexe 1":
                grouped[gname].append(_make_renfort_rate_dict(r))

        return grouped
    except Exception as e:
        logger.error(f"Erreur chargement salary_rates groupés: {e}")
        return OrderedDict()


def list_salary_groups():
    """Retourne la liste des groupes uniques existants pour l'autocomplétion."""
    groups = db.session.query(SalaryPosition.group_name).distinct().all()
    return sorted([g[0] for g in groups if g[0]])


def add_salary_rate(group_name="", annexe="Annexe 1"):
    """Ajoute une nouvelle position (avec toutes ses annexes) dans un groupe donné."""
    # display_order = max global + 1
    max_order = db.session.query(db.func.max(
        SalaryPosition.display_order)).scalar() or 0
    
    import random
    temp_position = f"Nouvelle position ({random.randint(1000, 9999)})"
    
    pos_obj = SalaryPosition(
        group_name=group_name or "",
        position=temp_position,
        notes="",
        display_order=max_order + 1
    )
    db.session.add(pos_obj)
    db.session.flush()
    
    # Créer les 7 annexes pour cette nouvelle position
    annexes = ["Annexe 1", "Annexe 3", "USPA", "USPA renfort", "Court-métrage", "Publicité", "Facture"]
    new_rates = []
    
    for ann in annexes:
        rate = SalaryRate(
            position_id=pos_obj.id,
            annexe=ann,
            base_hourly=0
        )
        _calculate_salary_columns(rate)
        db.session.add(rate)
        new_rates.append(rate)
        
    db.session.commit()
    
    # Retourner le dictionnaire de la ligne correspondant à l'annexe demandée
    target_rate = next((r for r in new_rates if r.annexe == annexe), new_rates[0])
    res_dict = target_rate.to_dict()
    res_dict["all_rates"] = [r.to_dict() for r in new_rates]
    return res_dict


def delete_salary_rate(rate_id):
    """Supprime une position (et toutes ses déclinaisons d'annexes)."""
    if str(rate_id).startswith("renfort_"):
        rate_id = int(str(rate_id).replace("renfort_", ""))
    rate = db.session.get(SalaryRate, rate_id)
    if not rate:
        raise ValueError(f"Salaire #{rate_id} introuvable")

    if rate.position_ref:
        db.session.delete(rate.position_ref)

    db.session.commit()
    return True


def reorder_salary_rates(groups_order):
    """Réordonne toutes les lignes de salaire.
    Synchronise display_order pour toutes les annexes de chaque position.
    """
    order_counter = 0
    for group_name, rate_ids in groups_order.items():
        for rate_id in rate_ids:
            clean_id = rate_id
            if str(clean_id).startswith("renfort_"):
                clean_id = str(clean_id).replace("renfort_", "")
            rate = db.session.get(SalaryRate, int(clean_id))
            if rate and rate.position_ref:
                rate.position_ref.group_name = group_name
                rate.position_ref.display_order = order_counter
                order_counter += 1
    db.session.commit()
    logger.info(f"Réordonnement salaires: {order_counter} positions synchronisées")
    return True


def rename_salary_group(old_name, new_name):
    """Renomme toutes les lignes d'un groupe."""
    new_name = new_name.strip()
    if not new_name:
        raise ValueError("Le nom du groupe ne peut pas être vide")
    positions = SalaryPosition.query.filter_by(group_name=old_name).all()
    if not positions:
        raise ValueError(f"Groupe '{old_name}' introuvable")
    for pos in positions:
        pos.group_name = new_name
    db.session.commit()
    logger.info(f"Groupe renommé: '{old_name}' → '{new_name}' ({len(positions)} positions)")
    return new_name


def delete_salary_group(group_name):
    """Supprime toutes les lignes d'un groupe."""
    positions = SalaryPosition.query.filter_by(group_name=group_name).all()
    if not positions:
        raise ValueError(f"Groupe '{group_name}' introuvable")
    count = len(positions)
    for pos in positions:
        db.session.delete(pos)
    db.session.commit()
    logger.info(f"Groupe '{group_name}' supprimé ({count} positions)")
    return count



def update_salary_rate(rate_id, field, value):
    """Met à jour un champ spécifique d'un SalaryRate.
    Si base_hourly est modifié, recalcule TOUTES les colonnes.
    """
    if field not in SALARY_EDITABLE_FIELDS:
        raise ValueError(f"Champ non autorisé : {field}")

    if str(rate_id).startswith("renfort_"):
        rate_id = int(str(rate_id).replace("renfort_", ""))
    rate = db.session.get(SalaryRate, rate_id)
    if not rate:
        raise ValueError(f"Salaire #{rate_id} introuvable")

    if field == "base_hourly":
        value = round(_safe_float(value), 2)
    else:
        value = str(value).strip() if value else ""

    affected_rates = []

    if field in ("position", "group_name", "notes"):
        setattr(rate, field, value)
        if rate.position_ref:
            affected_rates.extend(rate.position_ref.rates)
    elif field == "base_hourly":
        if rate.annexe == "Facture":
            raise ValueError("Le taux horaire de base de la facture est calculé et ne peut pas être modifié directement.")
        rate.base_hourly = value
        _calculate_salary_columns(rate)
        if rate not in affected_rates:
            affected_rates.append(rate)
    else:
        setattr(rate, field, value)
        if rate not in affected_rates:
            affected_rates.append(rate)

    # Appliquer les modifications temporaires pour les requêtes suivantes
    db.session.flush()

    if rate.position_ref:
        # Trouver la ligne Publicité correspondante
        publicite_rate = next((r for r in rate.position_ref.rates if r.annexe == "Publicité"), None)
        if publicite_rate:
            facture_rate = next((r for r in rate.position_ref.rates if r.annexe == "Facture"), None)
            
            factor = get_invoice_factor()
            expected_facture_base = round(float(publicite_rate.base_hourly or 0) * factor, 2)

            if not facture_rate:
                facture_rate = SalaryRate(
                    position_id=rate.position_ref.id,
                    annexe="Facture",
                    base_hourly=expected_facture_base
                )
                _calculate_salary_columns(facture_rate)
                db.session.add(facture_rate)
                if facture_rate not in affected_rates:
                    affected_rates.append(facture_rate)
            elif field == "base_hourly" and rate.annexe == "Publicité":
                facture_rate.base_hourly = expected_facture_base
                _calculate_salary_columns(facture_rate)
                if facture_rate not in affected_rates:
                    affected_rates.append(facture_rate)

    db.session.commit()
    
    return {
        "rate": rate.to_dict(),
        "updated_rates": [r.to_dict() for r in affected_rates]
    }


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
    rate = db.session.get(LogisticsRate, rate_id)
    if not rate:
        raise ValueError(f"Logistique #{rate_id} introuvable")
    db.session.delete(rate)
    db.session.commit()
    return True


def update_logistics_rate(rate_id, field, value):
    """Met à jour un champ spécifique d'un LogisticsRate."""
    if field not in LOGISTICS_EDITABLE_FIELDS:
        raise ValueError(f"Champ non autorisé : {field}")

    rate = db.session.get(LogisticsRate, rate_id)
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
        rate = db.session.get(LogisticsRate, int(rate_id))
        if rate:
            rate.display_order = i
    db.session.commit()
    return True


def generate_salaries_pdf(annexe):
    """Génère le binaire PDF de la grille des salaires pour une annexe donnée."""
    from collections import OrderedDict
    from datetime import datetime
    from flask import render_template, current_app
    from utils.document_utils import render_pdf_from_template
    
    # 1. Récupérer tous les salaires groupés
    all_grouped = list_salary_rates_grouped()
    
    # 2. Filtrer par l'annexe demandée
    grouped_filtered = OrderedDict()
    for gname, rates in all_grouped.items():
        filtered_rates = [r for r in rates if r.get("annexe") == annexe]
        if filtered_rates:
            grouped_filtered[gname] = filtered_rates
            
    # 3. Paramètres de l'entreprise
    settings = {
        "company_name": AppSetting.get("company_name", "Belle Vitesse SAS"),
        "company_address": AppSetting.get("company_address", ""),
        "company_siret": AppSetting.get("company_siret", ""),
        "company_phone": AppSetting.get("company_phone", ""),
        "company_email": AppSetting.get("company_email", ""),
    }
    
    # 4. Préparer les données pour le template
    data = {
        "annexe": annexe,
        "grouped_salaries": grouped_filtered,
        "invoice_factor": get_invoice_factor(),
        "settings": settings,
        "now": datetime.now(),
    }
    
    # 5. Rendre le HTML
    html = render_template("pdf/salaries.html", **data)
    
    # 6. Générer le PDF
    pdf_bytes = render_pdf_from_template(html, base_url=current_app.root_path)
    return pdf_bytes

