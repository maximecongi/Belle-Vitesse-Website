"""
Gestion des signatures électroniques (BV / Production), des jetons d'invitation et du scellement contradictoire.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from models import db
from models.incident import IncidentToken
from services.admin.incidents.crud import get_incident_detail
from services.admin.utils import handle_admin_service_error
from utils.entity_resolvers import resolve_incident
from utils.request_utils import resolve_base_url
from utils.signature_storage import save_signature_image

logger = logging.getLogger(__name__)


@handle_admin_service_error
def sign_incident_bv(incident_id, signer_name, signer_role, signature_data, ip_address=None):
    """
    Enregistre le visa et la signature manuscrite de Belle Vitesse pour un incident.
    """
    inc = resolve_incident(incident_id)
    if not inc or inc.deleted_at is not None:
        raise ValueError(f"Incident #{incident_id} introuvable.")

    if inc.is_fully_signed and inc.signed_pdf_path:
        return {
            "success": True,
            "message": "Le visa Belle Vitesse a déjà été enregistré et le constat est scellé.",
            "incident_number": inc.incident_number,
            "signature_status": inc.signature_status,
            "is_fully_signed": True,
            "signed_pdf_path": inc.signed_pdf_path,
            "pdf_url": f"/incidents/document/{inc.signed_pdf_path}",
            "file_path": None,
        }

    if not signer_name or not str(signer_name).strip():
        raise ValueError("Le nom du signataire Belle Vitesse est requis.")
    if not signature_data or not str(signature_data).strip():
        raise ValueError("Le tracé de signature est requis.")

    inc.bv_signer_name = str(signer_name).strip()
    inc.bv_signer_role = str(signer_role).strip(
    ) if signer_role else "Responsable Technique Belle Vitesse"
    sig_rel_path = save_signature_image(
        signature_data,
        entity_type="incidents",
        record_id=inc.incident_number,
        suffix="_bv"
    )
    inc.bv_signature_data = sig_rel_path
    inc.bv_signed_at = datetime.now(timezone.utc)
    inc.bv_signer_ip = ip_address or "127.0.0.1"

    # Scellement contradictoire UNIQUEMENT si la Production a déjà signé
    if inc.is_signed_prod:
        res = finalize_incident_document(inc)
        message = "Visa Belle Vitesse enregistré et constat scellé contradictoirement avec succès."
    else:
        inc.signature_status = "signed_bv"
        db.session.commit()
        res = {}
        message = "Visa Belle Vitesse enregistré avec succès (en attente de la signature Production pour scellement)."

    return {
        "success": True,
        "message": message,
        "incident_number": inc.incident_number,
        "signature_status": inc.signature_status,
        "is_fully_signed": inc.is_fully_signed,
        "signed_pdf_path": inc.signed_pdf_path,
        "pdf_url": res.get("pdf_url"),
        "file_path": res.get("file_path"),
    }


@handle_admin_service_error
def sign_incident_prod(incident_id, signer_name, signer_role, signature_data, ip_address=None, token_str=None):
    """
    Enregistre le visa et la signature manuscrite de la Production (sur place ou via token).
    Déclenche le scellement contradictoire final UNIQUEMENT si Belle Vitesse a déjà signé.
    """
    inc = resolve_incident(incident_id)
    if not inc or inc.deleted_at is not None:
        raise ValueError(f"Incident #{incident_id} introuvable.")

    if inc.is_fully_signed and inc.signed_pdf_path:
        return {
            "success": True,
            "message": "La signature Production a déjà été enregistrée et le constat est scellé.",
            "incident_number": inc.incident_number,
            "signature_status": inc.signature_status,
            "is_fully_signed": True,
            "signed_pdf_path": inc.signed_pdf_path,
            "pdf_url": f"/incidents/document/{inc.signed_pdf_path}",
            "file_path": None,
        }

    if not signer_name or not str(signer_name).strip():
        raise ValueError("Le nom du représentant de la Production est requis.")
    if not signature_data or not str(signature_data).strip():
        raise ValueError("Le tracé de signature est requis.")

    inc.prod_signer_name = str(signer_name).strip()
    inc.prod_signer_role = str(signer_role).strip(
    ) if signer_role else "Représentant Production"
    sig_rel_path = save_signature_image(
        signature_data,
        entity_type="incidents",
        record_id=inc.incident_number,
        suffix="_prod"
    )
    inc.prod_signature_data = sig_rel_path
    inc.prod_signed_at = datetime.now(timezone.utc)
    inc.prod_signer_ip = ip_address or "127.0.0.1"

    if token_str:
        tok = db.session.get(IncidentToken, token_str)
        if tok:
            tok.signature = sig_rel_path

    # Scellement contradictoire UNIQUEMENT si Belle Vitesse a déjà signé
    if inc.is_signed_bv:
        res = finalize_incident_document(inc)
        message = "Signature Production enregistrée et constat scellé contradictoirement avec succès."
    else:
        inc.signature_status = "signed_prod"
        db.session.commit()
        res = {}
        message = "Signature Production enregistrée avec succès (en attente du visa Belle Vitesse pour scellement)."

    return {
        "success": True,
        "message": message,
        "incident_number": inc.incident_number,
        "signature_status": inc.signature_status,
        "is_fully_signed": inc.is_fully_signed,
        "signed_pdf_path": inc.signed_pdf_path,
        "pdf_url": res.get("pdf_url"),
        "file_path": res.get("file_path"),
    }


@handle_admin_service_error
def generate_incident_token(incident_id, recipient_email=None):
    """
    Génère un jeton sécurisé temporaire (48h) pour la signature distante par la Production.
    """
    inc = resolve_incident(incident_id)
    if not inc or inc.deleted_at is not None:
        raise ValueError(f"Incident #{incident_id} introuvable.")

    token_str = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(hours=48)

    token_entry = IncidentToken(
        token=token_str,
        incident_id=inc.id,
        recipient_email=recipient_email.strip() if recipient_email else None,
        created_at=datetime.now(timezone.utc),
        expires_at=expires_at,
    )
    db.session.add(token_entry)

    if inc.signature_status != "signed":
        inc.signature_status = "pending_prod"

    db.session.commit()

    base_url = resolve_base_url()
    signing_url = f"{base_url}/incidents/sign/{token_str}"

    # Expédition de l'invitation par email si une adresse est renseignée
    email_sent = False
    if recipient_email:
        try:
            from utils.mailer import send_incident_signature_request_email
            send_incident_signature_request_email(
                inc, recipient_email.strip(), signing_url)
            email_sent = True
        except Exception as mail_err:
            logger.warning(
                f"⚠️ Échec d'envoi de l'invitation email pour l'incident {inc.incident_number}: {mail_err}")

    return {
        "success": True,
        "token": token_str,
        "signing_url": signing_url,
        "recipient_email": recipient_email,
        "email_sent": email_sent,
        "expires_at": expires_at.isoformat(),
    }


def validate_incident_token(token_str):
    """
    Valide un jeton de signature publique pour incident.
    Retourne (token_entry, incident) ou (None, code_erreur).
    """
    token_entry = db.session.get(IncidentToken, token_str)
    if not token_entry:
        return None, 404

    now_utc = datetime.now(timezone.utc)
    exp = token_entry.expires_at
    if exp:
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < now_utc:
            return None, 410  # Expiré

    incident = token_entry.incident
    if not incident or incident.deleted_at is not None:
        return None, 404

    return (token_entry, incident), 200


def finalize_incident_document(incident, base_url=None):
    """
    Finalise et scelle un constat d'incident contradictoirement signé :
    Délègue l'ensemble du cycle de scellement électronique, d'archivage légal
    et de synchronisation kDrive au moteur unifié de signatures.py.
    """
    from services.common.signatures import seal_incident_contradictory_document

    incident_data = get_incident_detail(incident.id)
    return seal_incident_contradictory_document(incident, incident_data, base_url=base_url)

