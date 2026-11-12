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
    RiskAssessmentWaiver,
    Waiver,
    WaiverSignedDocument,
    WaiverToken,
    db,
)
from models.db import _utcnow
from services.admin.utils import handle_admin_service_error
from utils.document_utils import generate_pdf_access_token
from utils.entity_resolvers import (
    resolve_cgl,
    resolve_safety_rules_waiver,
    resolve_pilot_waiver,
    resolve_waiver,
)

logger = logging.getLogger(__name__)


def format_waiver_shooting_dates(shooting_dates_str, default_sep=" au "):
    """
    Simplifie une chaîne de dates de tournage pour n'afficher que la date de début et la date de fin,
    au format numérique standard JJ/MM/AAAA (ex: 01/01/2026).
    """
    if not shooting_dates_str or str(shooting_dates_str).strip() in ("", "—", "-"):
        return "—"

    from utils.formatting import format_date_numeric

    val = str(shooting_dates_str).strip()
    if val.startswith("Du ") or val.startswith("du "):
        val = val[3:].strip()
    elif val.startswith("Le ") or val.startswith("le "):
        val = val[3:].strip()

    parts = []
    if "," in val:
        parts = [p.strip() for p in val.split(",") if p.strip()]
    elif " au " in val:
        parts = [p.strip() for p in val.split(" au ") if p.strip()]
    else:
        for arrow_sep in (" → ", " -> "):
            if arrow_sep in val:
                parts = [p.strip() for p in val.split(arrow_sep) if p.strip()]
                break

    if parts:
        d_start = format_date_numeric(parts[0])
        d_end = format_date_numeric(parts[-1])
        if d_start == d_end or not d_end or d_end == "—":
            return d_start
        return f"{d_start}{default_sep}{d_end}"

    return format_date_numeric(val)


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
    Retourne la configuration selon le type de contrat (cgl, safety_rules, pilot_waiver ou risk_assessment).
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
    elif mode == "risk_assessment":
        return {
            "model": RiskAssessmentWaiver,
            "route_base": "risk-assessment",
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

    from utils.document_utils import signer_copy_path

    files_to_delete = [
        waiver.signed_pdf_path,
        signer_copy_path(waiver.signed_pdf_path),  # copie signataire générée à côté de l'archive
    ] + [getattr(waiver, f, None) for f in config["attachment_fields"]]

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

    if mode in ("safety_rules", "pilot_waiver", "risk_assessment"):
        signer_fields = [
            "signer_first_name", "signer_last_name", "signer_email", "signer_phone",
            "signer_company", "signer_role", "signer_role_custom",
            "bv_signature_data", "bv_signed_at", "bv_signer_name"
        ]
        for f in signer_fields:
            if hasattr(waiver, f):
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


def _contact_full_name(contact):
    if not contact:
        return ""
    return f"{contact.first_name or ''} {contact.last_name or ''}".strip()


def resolve_waiver_recipient(waiver):
    """
    Destinataire (e-mail, nom) de l'invitation et des relances d'un document.

    Le signataire enregistré sur le document fait foi ; à défaut, on se rabat sur la fiche
    contact rattachée, puis sur le contact du projet correspondant au rôle (production pour
    les CGL, pilote pour l'Annexe 3...).
    """
    p = waiver.project
    mode = waiver.waiver_type

    if mode == "cgl":
        fallback = waiver.signer_contact or (p.production_contact if p else None)
        stored_name = (waiver.production_representative or "").strip()
    else:
        fallback = waiver.signer_contact
        if fallback is None and p:
            if mode == "pilot_waiver" or waiver.signer_role == "pilot":
                fallback = p.pilot_contact
            elif waiver.signer_role == "production":
                fallback = p.production_contact
        stored_name = waiver.signer_name if waiver.signer_name != "—" else ""

    mail = (waiver.signer_email or "").strip()
    if mail:
        return mail, stored_name or _contact_full_name(fallback)

    if fallback is not None and (fallback.mail or "").strip():
        return fallback.mail.strip(), _contact_full_name(fallback)
    return None, stored_name


@handle_admin_service_error
def get_or_create_waiver_signing_url(waiver_id: str, waiver_type: str = "cgl", base_url: str = None) -> tuple:
    """
    Génère ou récupère l'URL complète de signature active pour CGL, BVSR ou Attestation Pilote.
    """

    if waiver_type == "safety_rules":
        waiver = resolve_safety_rules_waiver(waiver_id)
    elif waiver_type == "pilot_waiver":
        waiver = resolve_pilot_waiver(waiver_id)
    elif waiver_type == "risk_assessment":
        from utils.entity_resolvers import resolve_risk_assessment_waiver
        waiver = resolve_risk_assessment_waiver(waiver_id)
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
    elif mode == "risk_assessment":
        route_prefix = "risk-assessment"
    else:
        route_prefix = "cgl"
    signing_url = f"{root_url}/sign/{route_prefix}/{active_token.token}"
    return True, signing_url


def get_secured_waiver_pdf_url(path, doc_type):
    """
    Génère une URL sécurisée avec jeton HMAC temporaire pour un document PDF scellé.
    doc_type: 'cgl', 'safety-rules' / 'safety_rules' ou 'pilot-attestation' / 'pilot_waiver'.
    """
    if not path:
        return None
    if doc_type in ("pilot_waiver", "pilot-attestation", "pilot-waiver", "pilot"):
        route_prefix = "pilot-attestation"
    elif doc_type in ("risk_assessment", "risk-assessment", "risk"):
        route_prefix = "risk-assessment"
    elif doc_type in ("cgl", "production-waiver"):
        route_prefix = "cgl"
    else:
        route_prefix = "safety-rules"
    clean_path = path.split("?")[0].split(f"/{route_prefix}/document/")[-1].lstrip("/")
    token = generate_pdf_access_token(clean_path)
    return f"/{route_prefix}/document/{clean_path}?t={token}"

