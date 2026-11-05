"""
Routes publiques pour la consultation des règles de sécurité des véhicules.
Accessible sans authentification par QR Code physique apposé sur les véhicules.
"""

import logging
from flask import Blueprint, abort, render_template

from models import AppSetting
from models.catalog import Vehicle
from services.admin.safety_rules_config import (
    _find_default_rules,
    get_all_vehicle_safety_rules_catalog,
    get_general_safety_rules,
)
from utils.database import get_vehicles
from utils.image_utils import extract_vehicle_image

logger = logging.getLogger(__name__)

public_safety_rules_bp = Blueprint("public_safety_rules", __name__, url_prefix="/safety-rules")


def _resolve_vehicle_data(vehicle_id: str):
    """
    Résout les informations d'un véhicule à partir de son identifiant ID, unique_id ou slug.
    Recherche d'abord en base SQL locale puis dans le catalogue complet.
    """
    clean_id = (vehicle_id or "").strip()
    if not clean_id:
        return None

    clean_lower = clean_id.lower()
    clean_upper = clean_id.upper()

    # 1. Recherche dans la base de données SQL locale
    try:
        db_veh = Vehicle.query.get(clean_id)
        if not db_veh:
            all_db = Vehicle.query.all()
            for v in all_db:
                f = v.fields or {}
                if (
                    str(v.id) == clean_id
                    or (f.get("slug") and f.get("slug").lower() == clean_lower)
                    or (f.get("unique_id") and f.get("unique_id").upper() == clean_upper)
                    or (f.get("name") and f.get("name").lower() == clean_lower)
                    or (f.get("Nom") and f.get("Nom").lower() == clean_lower)
                ):
                    db_veh = v
                    break

        if db_veh:
            fields = db_veh.fields or {}
            vname = fields.get("name") or fields.get("Nom") or f"Véhicule {db_veh.id}"
            vslug = fields.get("slug") or ""
            if not vslug and vname:
                vslug = vname.lower().strip().replace(" ", "-")
            return {
                "id": str(db_veh.id),
                "name": vname,
                "slug": vslug,
                "unique_id": fields.get("unique_id") or (vslug.upper() if vslug else str(db_veh.id)[:8].upper()),
                "brand": fields.get("brand") or "",
                "model": fields.get("model") or "",
                "image_url": extract_vehicle_image(fields),
                "max_speed": fields.get("max_speed"),
                "passengers": fields.get("passengers"),
                "battery_life": fields.get("battery_life"),
                "daily_rate": float(db_veh.daily_rate) if getattr(db_veh, "daily_rate", None) is not None else fields.get("daily_rate"),
                "description": fields.get("description") or "",
                "fields": fields,
            }
    except Exception as e:
        logger.warning(f"Erreur requête SQL véhicule pour règles de sécurité : {e}")

    # 2. Recherche dans le catalogue global
    try:
        catalog_vehicles = get_vehicles() or []
        clean_lower = clean_id.lower()
        for v in catalog_vehicles:
            vid = str(v.get("id") or "").strip()
            vfields = v.get("fields") or {}
            vslug = (vfields.get("slug") or "").lower()
            vuid = (vfields.get("unique_id") or "").upper()
            vname = (vfields.get("name") or vfields.get("Nom") or "").lower()

            if (
                vid == clean_id
                or vslug == clean_lower
                or vuid == clean_id.upper()
                or vname == clean_lower
            ):
                final_slug = vfields.get("slug") or ""
                disp_name = vfields.get("name") or vfields.get("Nom") or f"Véhicule {vid}"
                if not final_slug and disp_name:
                    final_slug = disp_name.lower().strip().replace(" ", "-")
                return {
                    "id": vid,
                    "name": disp_name,
                    "slug": final_slug,
                    "unique_id": vfields.get("unique_id") or (final_slug.upper() if final_slug else vid[:8].upper()),
                    "brand": vfields.get("brand") or "",
                    "model": vfields.get("model") or "",
                    "image_url": extract_vehicle_image(vfields),
                    "max_speed": vfields.get("max_speed"),
                    "passengers": vfields.get("passengers"),
                    "battery_life": vfields.get("battery_life"),
                    "daily_rate": vfields.get("daily_rate"),
                    "description": vfields.get("description") or "",
                    "fields": vfields,
                }
    except Exception as e:
        logger.warning(f"Erreur recherche catalogue véhicule pour règles de sécurité : {e}")

    return None


@public_safety_rules_bp.route("/v/<vehicle_id>", methods=["GET"], endpoint="view_vehicle_safety_rules")
@public_safety_rules_bp.route("/vehicle/<vehicle_id>", methods=["GET"], endpoint="view_vehicle_safety_rules_alt")
def view_vehicle_safety_rules(vehicle_id: str):
    """
    Page publique responsive présentant les consignes de sécurité spécifiques
    d'un véhicule et le protocole général de sécurité Belle Vitesse.
    """
    vehicle_info = _resolve_vehicle_data(vehicle_id)
    if not vehicle_info:
        abort(404, description="Véhicule introuvable.")

    # 1. Règles spécifiques et équipements du véhicule
    rules_catalog = get_all_vehicle_safety_rules_catalog()
    vid = vehicle_info["id"]
    vslug = vehicle_info.get("slug", "").lower()
    vname = vehicle_info.get("name", "").lower()

    entry = rules_catalog.get(vid)
    if not entry and vslug:
        entry = rules_catalog.get(vslug)
    if not entry:
        for c_id, c_data in rules_catalog.items():
            if (
                c_id.lower() == vname
                or c_data.get("name", "").lower() == vname
                or (c_id.lower() in vname and len(c_id) >= 4)
            ):
                entry = c_data
                break

    if entry:
        rules_fr = entry.get("rules_fr") or []
        rules_en = entry.get("rules_en") or []
        equipment_fr = entry.get("equipment_fr") or []
        equipment_en = entry.get("equipment_en") or []
    else:
        def_fr, def_en, _, _ = _find_default_rules(vehicle_info["name"])
        rules_fr = def_fr
        rules_en = def_en
        equipment_fr = []
        equipment_en = []

    # 2. Règles générales universelles de sécurité BV
    general_rules = get_general_safety_rules()

    # 3. Coordonnées d'urgence et contact Belle Vitesse
    company_phone = AppSetting.get("company_phone", "+33 1 84 25 00 00")
    company_email = AppSetting.get("company_email", "contact@bellevitesse.com")

    return render_template(
        "public/vehicle_safety_rules.html",
        vehicle=vehicle_info,
        rules_fr=rules_fr,
        rules_en=rules_en,
        equipment_fr=equipment_fr,
        equipment_en=equipment_en,
        general_rules=general_rules,
        company_phone=company_phone,
        company_email=company_email,
    )
