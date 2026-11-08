"""
Routes publiques des fiches techniques véhicules (consultation mobile + impression / PDF).
Accessible sans authentification, en lien croisé avec les règles de sécurité (QR Code).
Aucun tarif n'est exposé sur ces fiches.
"""

import base64
import logging
import os
from datetime import datetime
from io import BytesIO

from flask import (
    Blueprint,
    abort,
    current_app,
    make_response,
    render_template,
    request,
    url_for,
)

from models import AppSetting
from routes.public.safety_rules import _resolve_vehicle_data
from utils.database import get_configs_for_vehicle
from utils.request_utils import resolve_base_url
from utils.specs import build_specs_bilingual

logger = logging.getLogger(__name__)

public_vehicle_sheet_bp = Blueprint(
    "public_vehicle_sheet", __name__, url_prefix="/vehicle-sheet"
)

# Ordre d'affichage et libellés bilingues des familles de configurations
CONFIG_TYPE_ORDER = ["Operator", "Gimbal", "Crane"]
CONFIG_TYPE_LABELS = {
    "Operator": {"fr": "Opérateur", "en": "Operator"},
    "Gimbal": {"fr": "Stabilisateur", "en": "Gimbal"},
    "Crane": {"fr": "Grue", "en": "Crane"},
}


def _first_image_url(attachments, size="large"):
    """Retourne l'URL d'une miniature Airtable (large par défaut), ou l'URL brute."""
    if not attachments or not isinstance(attachments, list):
        return None
    first = attachments[0] or {}
    thumbs = first.get("thumbnails") or {}
    return (thumbs.get(size) or {}).get("url") or first.get("url")


def _group_configs(vehicle_id: str):
    """Regroupe les configurations du véhicule par famille, triées par ordre métier."""
    try:
        configs = get_configs_for_vehicle(vehicle_id) or []
    except Exception as e:
        logger.warning(f"Configurations indisponibles pour {vehicle_id} : {e}")
        configs = []

    groups = {}
    for cfg in configs:
        f = cfg.get("fields") or {}
        type_name = f.get("type") or "Other"
        name_en = f.get("name_en") or f.get("name") or ""
        groups.setdefault(type_name, []).append({
            "id": cfg.get("id"),
            "name_fr": f.get("name_fr") or name_en,
            "name_en": name_en,
            "image_url": _first_image_url(f.get("image")),
            "order": f.get("order") or 0,
        })

    def type_rank(t):
        return CONFIG_TYPE_ORDER.index(t) if t in CONFIG_TYPE_ORDER else len(CONFIG_TYPE_ORDER)

    result = []
    for type_name in sorted(groups.keys(), key=lambda t: (type_rank(t), t)):
        labels = CONFIG_TYPE_LABELS.get(type_name, {"fr": type_name, "en": type_name})
        result.append({
            "type": type_name,
            "label_fr": labels["fr"],
            "label_en": labels["en"],
            "items": sorted(groups[type_name], key=lambda c: c["order"]),
        })
    return result


def _setup_icon_url(setup_name: str):
    """
    Icône SVG du site public pour un setup caméra (même convention que le filtre
    Jinja `slugify` : minuscules, espaces → underscore). None si absente.
    """
    slug = (setup_name or "").strip().lower().replace(" ", "_")
    if not slug:
        return None
    rel = f"imgs/icons/{slug}.svg"
    if not os.path.exists(os.path.join(current_app.static_folder, rel)):
        return None
    return url_for("static", filename=rel)


def _public_slug(vehicle_info: dict, fallback: str) -> str:
    return vehicle_info.get("slug") or vehicle_info.get("id") or fallback


def _build_qr_base64(url: str) -> str:
    """QR Code PNG encodé base64 pointant vers la fiche publique (version imprimée)."""
    try:
        import qrcode

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=1,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as e:
        logger.warning(f"Génération QR fiche véhicule impossible : {e}")
        return ""


def _build_sheet_context(vehicle_id: str) -> dict:
    vehicle_info = _resolve_vehicle_data(vehicle_id)
    if not vehicle_info:
        abort(404, description="Véhicule introuvable.")

    fields = vehicle_info.get("fields") or {}
    slug = _public_slug(vehicle_info, vehicle_id)

    hero_image = (
        _first_image_url(fields.get("thumbnail"), "full")
        or vehicle_info.get("image_url")
    )

    description_en = (fields.get("description_en") or fields.get("description") or "").strip()
    description_fr = (fields.get("description_fr") or description_en).strip()
    tagline_en = (fields.get("powerquote_en") or fields.get("powerquote") or "").strip()
    tagline_fr = (fields.get("powerquote_fr") or tagline_en).strip()

    raw_setups = fields.get("setups") or []
    if isinstance(raw_setups, str):
        raw_setups = [s.strip() for s in raw_setups.split(",") if s.strip()]
    setups = [{"name": s, "icon_url": _setup_icon_url(s)} for s in raw_setups]

    return {
        "vehicle": vehicle_info,
        "hero_image": hero_image,
        "tagline_fr": tagline_fr,
        "tagline_en": tagline_en,
        "description_fr_paragraphs": [p.strip() for p in description_fr.split("\n") if p.strip()],
        "description_en_paragraphs": [p.strip() for p in description_en.split("\n") if p.strip()],
        # Marque / modèle déjà affichés dans le hero
        "specs": [s for s in build_specs_bilingual(fields) if s["key"] not in ("Brand", "Model")],
        "setups": setups,
        "config_groups": _group_configs(vehicle_info["id"]),
        "sheet_url": resolve_base_url().rstrip("/") + url_for(
            "public_vehicle_sheet.view_vehicle_sheet", vehicle_id=slug
        ),
        "pdf_url": url_for("public_vehicle_sheet.vehicle_sheet_pdf", vehicle_id=slug),
        "safety_url": url_for(
            "public_safety_rules.view_vehicle_safety_rules", vehicle_id=slug
        ),
        "company_phone": AppSetting.get("company_phone"),
        "company_email": AppSetting.get("company_email", "contact@bellevitesse.com"),
        "company_name": AppSetting.get("company_name") or "Belle Vitesse SAS",
        # Date d'édition affichée dans l'en-tête officiel (comme les autres documents ERP)
        "doc_date_str": datetime.now().strftime("%d/%m/%Y"),
    }


@public_vehicle_sheet_bp.route(
    "/v/<vehicle_id>", methods=["GET"], endpoint="view_vehicle_sheet"
)
def view_vehicle_sheet(vehicle_id: str):
    """Fiche technique publique responsive (mobile-first), bilingue FR/EN et imprimable."""
    ctx = _build_sheet_context(vehicle_id)
    ctx["contact_url_fr"] = url_for("public_web.contact", lang="fr")
    ctx["contact_url_en"] = url_for("public_web.contact", lang="en")
    return render_template("public/vehicle_sheet.html", **ctx)


@public_vehicle_sheet_bp.route(
    "/v/<vehicle_id>/pdf", methods=["GET"], endpoint="vehicle_sheet_pdf"
)
def vehicle_sheet_pdf(vehicle_id: str):
    """Fiche technique A4 générée côté serveur (WeasyPrint), dans la langue demandée."""
    from utils.document_utils import render_pdf_from_template

    lang = (request.args.get("lang") or "fr").lower()
    if lang not in ("fr", "en"):
        lang = "fr"

    ctx = _build_sheet_context(vehicle_id)
    ctx["lang"] = lang
    ctx["fr"] = lang == "fr"
    ctx["qr_base64"] = _build_qr_base64(ctx["sheet_url"])

    vehicle = ctx["vehicle"]
    rendered_html = render_template("pdf/vehicle_sheet.html", **ctx)

    label = "Fiche-Technique" if lang == "fr" else "Technical-Sheet"
    clean_slug = vehicle.get("slug") or vehicle["name"].replace(" ", "_")
    filename = f"{label}-{clean_slug}-{lang.upper()}.pdf"

    try:
        pdf_bytes = render_pdf_from_template(
            html_content=rendered_html,
            base_url=request.url_root,
            # La feuille dédiée est liée dans le template (cascade « auteur »,
            # comme les autres documents ERP) ; base-pdf.css est injectée par défaut.
            stylesheets=[],
            compress=True,
            filename=filename,
            include_base_pdf=True,
        )
    except Exception as e:
        logger.error(
            f"❌ Erreur génération PDF fiche véhicule {vehicle_id} : {e}", exc_info=True
        )
        abort(500, description="Erreur lors de la génération du PDF.")

    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    disposition = "attachment" if request.args.get("download") == "1" else "inline"
    response.headers["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    return response
