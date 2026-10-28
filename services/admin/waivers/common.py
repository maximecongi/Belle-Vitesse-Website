"""
services/admin/waivers/common.py — Fonctions utilitaires partagées, formatage et gestion des tokens/URLs.
"""
import hashlib
import logging
import os
import uuid
from datetime import datetime

from models import (
    CglWaiver,
    SafetyRulesWaiver,
    PilotWaiver,
    Waiver,
    WaiverSignedDocument,
    WaiverToken,
    db,
)
from models.db import _utcnow
from services.admin.utils import handle_admin_service_error
from utils.entity_resolvers import (
    resolve_cgl,
    resolve_safety_rules_waiver,
    resolve_pilot_waiver,
    resolve_waiver,
)

logger = logging.getLogger(__name__)


def format_waiver_shooting_dates(shooting_dates_str, default_sep=" au "):
    """
    Simplifie une chaîne de dates de tournage pour n'afficher que la date de début et la date de fin.
    """
    if not shooting_dates_str or str(shooting_dates_str).strip() in ("", "—", "-"):
        return "—"

    val = str(shooting_dates_str).strip()

    if "," in val:
        parts = [p.strip() for p in val.split(",") if p.strip()]
        if not parts:
            return "—"
        if len(parts) == 1:
            return parts[0]
        if parts[0] == parts[-1]:
            return parts[0]
        return f"{parts[0]}{default_sep}{parts[-1]}"

    if " au " in val:
        parts = [p.strip() for p in val.split(" au ") if p.strip()]
        if len(parts) == 2:
            if parts[0] == parts[1]:
                return parts[0]
            return f"{parts[0]}{default_sep}{parts[1]}"

    for arrow_sep in (" → ", " -> "):
        if arrow_sep in val:
            parts = [p.strip() for p in val.split(arrow_sep) if p.strip()]
            if len(parts) == 2:
                if parts[0] == parts[1]:
                    return parts[0]
                return f"{parts[0]}{default_sep}{parts[1]}"

    return val


def _format_project_shooting_dates(p, default_sep=" au "):
    """
    Formate les dates de tournage du projet (début et fin).
    """
    if not p:
        return "—"
    if getattr(p, "date_mode", None) == "punctual" and p.shoot_dates:
        try:
            sorted_dates = sorted([datetime.strptime(d, "%Y-%m-%d").date() for d in p.shoot_dates if d])
            if sorted_dates:
                d_start = sorted_dates[0]
                d_end = sorted_dates[-1]
                if d_start == d_end:
                    return d_start.strftime("%d/%m/%Y")
                return f"{d_start.strftime('%d/%m/%Y')}{default_sep}{d_end.strftime('%d/%m/%Y')}"
        except Exception:
            pass
    if p.shoot_start_date and p.shoot_end_date:
        if p.shoot_start_date == p.shoot_end_date:
            return p.shoot_start_date.strftime("%d/%m/%Y")
        return f"{p.shoot_start_date.strftime('%d/%m/%Y')}{default_sep}{p.shoot_end_date.strftime('%d/%m/%Y')}"
    elif p.shoot_start_date:
        return p.shoot_start_date.strftime("%d/%m/%Y")
    elif p.shoot_end_date:
        return p.shoot_end_date.strftime("%d/%m/%Y")
    return "—"


def _get_waiver_config(mode: str):
    """
    Retourne la configuration selon le type de contrat (cgl, safety_rules ou pilot_waiver).
    """
    if mode == "safety_rules":
        return {
            "model": SafetyRulesWaiver,
            "route_base": "safety-rules",
            "attachment_fields": [],
        }
    elif mode == "pilot_waiver":
        return {
            "model": PilotWaiver,
            "route_base": "pilot-attestation",
            "attachment_fields": [],
        }
    return {
        "model": CglWaiver,
        "route_base": "cgl",
        "attachment_fields": ["production_insurance_path"],
    }


def _cleanup_waiver_assets(mode: str, waiver: Waiver):
    """
    Supprime les fichiers physiques (PDF signés, pièces jointes) et les enregistrements liés.
    """
    from flask import current_app
    config = _get_waiver_config(mode)

    files_to_delete = [waiver.signed_pdf_path] + [
        getattr(waiver, f, None) for f in config["attachment_fields"]
    ]

    output_base = current_app.config.get(
        "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output")
    )

    for file_path in files_to_delete:
        if file_path:
            full_path = os.path.join(output_base, file_path)
            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                    logger.info(f"🗑️ Fichier supprimé : {full_path}")
                except Exception as e:
                    logger.error(f"❌ Erreur suppression fichier {full_path} : {e}")

    signed_doc = WaiverSignedDocument.query.filter_by(waiver_id=waiver.waiver_id).order_by(WaiverSignedDocument.version.desc()).first()
    if signed_doc:
        from services.common.signatures import log_signature_event
        admin_user = "system"
        try:
            from flask import session
            admin_user = (
                session.get("admin_user_mail")
                or session.get("user")
                or session.get("admin_user_firstname")
                or "system"
            )
        except Exception:
            pass

        log_signature_event(
            waiver.waiver_id,
            mode,
            "archive_deleted",
            {
                "deleted_hash": signed_doc.hash,
                "deleted_pdf_hash": signed_doc.pdf_file_hash or "",
                "admin_user": admin_user,
                "reason": "waiver_reset_or_deletion",
            }
        )

    # Suppression de l'archive légale et des jetons
    WaiverSignedDocument.query.filter_by(waiver_id=waiver.waiver_id).delete()
    WaiverToken.query.filter_by(waiver_id=waiver.waiver_id).delete()


def _reset_waiver_fields(mode: str, waiver: Waiver):
    """
    Réinitialise tous les champs d'état, de signature et de snapshot.
    """
    waiver.status = "to_generate"
    waiver.generated_at = None
    waiver.sent_at = None
    waiver.signed_at = None
    waiver.signature_data = None
    waiver.signed_pdf_path = None
    waiver.signer_ip = None
    waiver.webhook_triggered_at = None

    for f in ["project_name", "vehicles", "shooting_dates"]:
        setattr(waiver, f, None)

    if mode in ("safety_rules", "pilot_waiver"):
        signer_fields = [
            "signer_first_name", "signer_last_name", "signer_email", "signer_phone",
            "signer_company", "bv_signature_data", "bv_signed_at", "bv_signer_name"
        ]
        for f in signer_fields:
            setattr(waiver, f, None)
    else:
        cgl_fields = [
            "production_name", "production_representative", "production_address",
            "production_siret", "production_vat", "production_insurance_company",
            "production_insurance_policy", "production_insurance_validity",
            "location_of_use", "production_insurance_path"
        ]
        for f in cgl_fields:
            setattr(waiver, f, None)


@handle_admin_service_error
def get_or_create_waiver_signing_url(waiver_id: str, waiver_type: str = "cgl", base_url: str = None) -> tuple:
    """
    Génère ou récupère l'URL complète de signature active pour CGL, BVSR ou Attestation Pilote.
    """
    from flask import current_app, has_request_context, request

    if waiver_type == "safety_rules":
        waiver = resolve_safety_rules_waiver(waiver_id)
    elif waiver_type == "pilot_waiver":
        waiver = resolve_pilot_waiver(waiver_id)
    else:
        waiver = resolve_cgl(waiver_id) or resolve_waiver(waiver_id)

    if not waiver:
        return False, "Document non trouvé."

    if waiver.status == "signed":
        return False, "Ce document est déjà signé."

    mode = waiver.waiver_type

    if waiver.status == "to_generate":
        from .core import generate_waiver
        gen_ok, gen_msg = generate_waiver(waiver.waiver_id, waiver_type=mode)
        if not gen_ok:
            return False, gen_msg

    now = _utcnow()
    active_token = WaiverToken.query.filter(
        WaiverToken.waiver_id == waiver.waiver_id,
        WaiverToken.expires_at > now
    ).order_by(WaiverToken.created_at.desc()).first()

    if not active_token:
        new_token = str(uuid.uuid4())
        active_token = WaiverToken(token=new_token, waiver_id=waiver.waiver_id)
        db.session.add(active_token)
        db.session.commit()

        from services.common.signatures import log_signature_event
        admin_user = "system"
        try:
            from flask import session
            admin_user = (
                session.get("admin_user_mail")
                or session.get("user")
                or session.get("admin_user_firstname")
                or "system"
            )
        except Exception:
            pass

        log_signature_event(
            waiver.waiver_id,
            mode,
            "link_generated",
            {
                "token_preview": f"{new_token[:8]}..." if new_token else "",
                "token_sha256": hashlib.sha256(new_token.encode("utf-8")).hexdigest() if new_token else "",
                "admin_user": admin_user,
            }
        )

    from utils.request_utils import resolve_base_url
    root_url = resolve_base_url(base_url)

    if mode == "safety_rules":
        route_prefix = "safety-rules"
    elif mode == "pilot_waiver":
        route_prefix = "pilot-attestation"
    else:
        route_prefix = "cgl"
    signing_url = f"{root_url}/sign/{route_prefix}/{active_token.token}"
    return True, signing_url
