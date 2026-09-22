"""
Service partagé de signature et de jetons pour les Retours et Départs (flux technicien) ainsi que les décharges.
"""

import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from flask import current_app, render_template

from models import (
    CheckinSignedDocument,
    CheckinToken,
    CheckinVehicle,
    CheckoutSignedDocument,
    CheckoutToken,
    # Inspections
    CheckoutVehicle,
    # Waivers
    PilotWaiver,
    PilotWaiverSignedDocument,
    PilotWaiverToken,
    ProductionWaiver,
    ProductionWaiverSignedDocument,
    ProductionWaiverToken,
    AppSetting,
    db,
)
from utils.database import get_vehicles
from utils.document_utils import (
    compute_hmac_seal,
    compute_pdf_hash,
    generate_qr_code,
    render_pdf_from_template,
)
from utils.mailer import send_waiver_signed_email
from utils.storage import (
    ensure_dir,
    get_checkin_path,
    get_checkout_path,
    get_pilot_waiver_path,
    get_production_waiver_path,
)

logger = logging.getLogger(__name__)

# ── Configuration des Flux ──────────────────────────────────────

FLOW_CONFIG = {
    "checkout": {
        "model": CheckoutVehicle,
        "token_model": CheckoutToken,
        "signed_model": CheckoutSignedDocument,
        "prefix": "BVCO",
        "url_path": "checkout",
        "storage_func": get_checkout_path,
        "stylesheets": ["css/styles.css", "css/checkout.css"],
        "template": "pdf/checkout.html"
    },
    "checkin": {
        "model": CheckinVehicle,
        "token_model": CheckinToken,
        "signed_model": CheckinSignedDocument,
        "prefix": "BVCI",
        "url_path": "checkin",
        "storage_func": get_checkin_path,
        "stylesheets": ["css/styles.css", "css/checkin.css"],
        "template": "pdf/checkin.html"
    },
    "pilot": {
        "model": PilotWaiver,
        "token_model": PilotWaiverToken,
        "signed_model": PilotWaiverSignedDocument,
        "prefix": "WAIVER",
        "url_path": "pilot-waiver",
        "storage_func": get_pilot_waiver_path,
        "stylesheets": [],  # Utilise des styles en ligne ou globaux pour les décharges
        "template": "pdf/pilot_waiver.html"
    },
    "production": {
        "model": ProductionWaiver,
        "token_model": ProductionWaiverToken,
        "signed_model": ProductionWaiverSignedDocument,
        "prefix": "WAIVER_PROD",
        "url_path": "production-waiver",
        "storage_func": get_production_waiver_path,
        "stylesheets": [],  # Utilise des styles en ligne ou globaux pour les décharges
        "template": "pdf/production_waiver.html"
    }
}

# ── Gestion des Jetons ───────────────────────────────────────────


def validate_inspection_token(token_str, mode):
    config = FLOW_CONFIG[mode]
    token_model = config["token_model"]

    entry = db.session.get(token_model, token_str)
    if not entry:
        return None, 404

    created_at = entry.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) - created_at > timedelta(hours=24):
        db.session.delete(entry)
        db.session.commit()
        return None, 410

    if entry.signature:
        return None, 400

    return entry, None


def generate_inspection_token(record_id, mode):
    config = FLOW_CONFIG[mode]
    model = config["model"]
    token_model = config["token_model"]

    record = db.session.get(model, record_id)
    if not record:
        return None

    # Importation dynamique pour éviter les dépendances circulaires
    from services.admin.inspections import _format_base_inspection_admin

    vehicles = get_vehicles()
    vehicle_map = {v["id"]: v.get("fields", {}) for v in vehicles}
    data = _format_base_inspection_admin(record, vehicle_map)

    token = str(uuid.uuid4())
    new_token = token_model(
        token=token,
        record_id=str(record_id),
        inspection_id=data["inspection_id"],
        created_at=datetime.utcnow()
    )
    db.session.add(new_token)

    record.status = "pending"
    db.session.commit()

    base_url = os.getenv("BASE_URL", "https://bellevitesse.com")
    return {
        "inspection_id": data["inspection_id"],
        "token": token,
        "sign_url": f"{base_url}/{config['url_path']}/sign/{token}",
    }


def abandon_inspection_signature(token_str, mode):
    config = FLOW_CONFIG[mode]
    token_model = config["token_model"]
    model = config["model"]

    entry = db.session.get(token_model, token_str)
    if not entry or entry.signature:
        return False

    try:
        record = db.session.get(model, int(entry.record_id))
        if record:
            record.status = "in_progress"
            db.session.commit()
        logger.info(f"🔙 Signature abandonnée pour {entry.inspection_id}")
    except Exception as e:
        logger.error(f"❌ Échec de l'abandon de la signature : {e}")
    return True


def resume_inspection_signature(token_str, mode):
    config = FLOW_CONFIG[mode]
    token_model = config["token_model"]
    model = config["model"]

    entry = db.session.get(token_model, token_str)
    if not entry or entry.signature:
        return False

    try:
        record = db.session.get(model, int(entry.record_id))
        if record:
            record.status = "pending"
            db.session.commit()
    except Exception as e:
        logger.error(f"❌ Échec de la reprise de la signature : {e}")
    return True


# ── Moteur de Traitement des Signatures ──────────────────────────

def finalize_signed_document(mode, record_id, signature_data, signed_ip, extra_data=None):
    """
    Moteur unifié pour finaliser n'importe quel document signé (Inspection ou Décharge).
    Génère le PDF, enregistre l'archive et déclenche les webhooks/emails.
    """
    config = FLOW_CONFIG.get(mode)
    if not config:
        raise ValueError(f"Invalid mode: {mode}")

    model = config["model"]
    signed_model = config["signed_model"]

    record = db.session.get(model, record_id)
    if not record:
        raise ValueError(f"Record {record_id} not found for mode {mode}")

    signed_at = datetime.now(timezone.utc)
    base_url = os.getenv("BASE_URL") or os.getenv(
        "APP_BASE_URL", "https://bellevitesse.com")
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"

    try:
        # 1. Mise à jour de l'état
        if hasattr(record, "status"):
            record.status = "signed"
        if hasattr(record, "signed_at"):
            record.signed_at = signed_at.replace(tzinfo=None)
        if hasattr(record, "signer_ip"):
            record.signer_ip = signed_ip

        # 2. Construction du Snapshot des données et Scellé (Hash)
        document_id = getattr(
            record, "inspection_number", getattr(record, "waiver_id", None))
        snapshot, seal_args = _build_flow_data(mode, record, extra_data)

        current_hash = compute_hmac_seal(
            config["prefix"], document_id, *seal_args, signature_data, signed_at.isoformat())

        # 3. QR code et génération du PDF
        verification_url = f"{base_url}/{config['url_path']}/verify/{document_id}"
        qr_code_img = generate_qr_code(verification_url)

        # Préparation du contexte de rendu
        render_ctx = {
            "signature": signature_data,
            "qr": qr_code_img,
            "hash": current_hash,
            "document_hash": current_hash,  # utilisé pour les décharges
            "verification_url": verification_url,
            "signed_at_str": signed_at.strftime("%d/%m/%Y %H:%M"),
            "signed_ip": signed_ip,
            # Données de l'entreprise tirées de la DB
            "company_name": AppSetting.get("company_name", "Belle Vitesse SAS"),
            "company_representative": AppSetting.get("company_representative", "Simon Maignan"),
            "company_siret": AppSetting.get("company_siret", "981 514 040 00014"),
            "company_vat": AppSetting.get("company_vat", "FR32981514040"),
            "company_address": AppSetting.get("company_address", "33 rue Maurice Gunsbourg, 94200 Ivry-sur-Seine, France"),
            "company_phone": AppSetting.get("company_phone", "+33 6 65 51 40 40"),
            "company_email": AppSetting.get("company_email", "contact@bellevitesse.com"),
            "bank_iban": AppSetting.get("bank_iban", ""),
            "bank_bic": AppSetting.get("bank_bic", ""),
        }
        # Ajout des données spécifiques au flux
        if mode in ["checkout", "checkin"]:
            render_ctx["data"] = snapshot
        else:
            render_ctx["waiver"] = record

        project_obj = getattr(record, "project", None)
        pdf_dir = ensure_dir(config["storage_func"](project_obj))
        filename = f"{document_id}_{secrets.token_hex(8)}.pdf"
        file_path = os.path.join(pdf_dir, filename)

        html_content = render_template(config["template"], **render_ctx)
        pdf_bytes = render_pdf_from_template(
            html_content, base_url, config["stylesheets"], filename=filename)

        # 4. Stockage physique
        output_base = current_app.config.get(
            "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))
        rel_pdf_path = os.path.relpath(file_path, output_base)

        with open(file_path, "wb") as f:
            f.write(pdf_bytes)

        pdf_public_url = f"{base_url}/{config['url_path']}/document/{rel_pdf_path}"
        pdf_file_hash = compute_pdf_hash(pdf_bytes)

        # 5. Persistance en base de données
        if hasattr(record, "signed_pdf_path"):
            record.signed_pdf_path = rel_pdf_path

        if hasattr(record, "hash"):
            record.hash = current_hash

        # Création de l'enregistrement d'archive
        # Détermine le nom de la PK pour le modèle de document signé
        pk_name = "inspection_id" if mode in [
            "checkout", "checkin"] else "waiver_id"
        signed_doc = signed_model(
            **{pk_name: document_id},
            hash=current_hash,
            pdf_file_hash=pdf_file_hash,
            data_snapshot={
                **snapshot,
                "signer_ip": signed_ip,
                "_seal_signed_at": signed_at.isoformat(),
            },
            signature=signature_data,
            pdf_url=pdf_public_url,
            signed_at=signed_at.replace(tzinfo=None)
        )
        db.session.add(signed_doc)
        db.session.commit()

        # 6. Post-traitement (kDrive et Emails)
        _dispatch_kdrive_document_bundle(
            mode, record, rel_pdf_path, base_url, current_hash, snapshot)

        if mode in ["pilot", "production"]:
            _send_waiver_confirmation_email(mode, record, file_path)

        return {
            "document_id": document_id,
            "pdf_url": pdf_public_url,
            "hash": current_hash,
        }

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ La transaction a échoué pendant la signature {mode} : {e}")
        raise


def _build_flow_data(mode, record, extra_data):
    """Construit l'instantané (snapshot) et les arguments du scellé spécifiques au type de flux."""
    if mode in ["checkout", "checkin"]:
        from services.admin.inspections import _format_base_inspection_admin
        vehicles = get_vehicles()
        vehicle_map = {v["id"]: v.get("fields", {}) for v in vehicles}
        data = _format_base_inspection_admin(record, vehicle_map)
        seal_args = [data["vehicle_id"]]
        return data, seal_args

    elif mode == "pilot":
        full_name = f"{record.pilot_first_name} {record.pilot_last_name}"
        seal_args = [full_name, record.pilot_license_number or ""]
        # Snapshot pour les décharges
        snapshot = {
            "_seal_pilot_name": full_name,
            "_seal_license": record.pilot_license_number or "",
            "project": record.project_name or (record.project.name if record.project else "—"),
            "production": record.production_name or (record.project.production.name if record.project and record.project.production else "—"),
        }
        return snapshot, seal_args

    elif mode == "production":
        seal_args = [record.production_name or "",
                     record.production_representative or ""]
        snapshot = {
            "_seal_production_name": record.production_name or "",
            "_seal_representative": record.production_representative or "",
            "project": record.project_name or (record.project.name if record.project else "—"),
            "production": record.production_name or (record.project.production.name if record.project and record.project.production else "—"),
        }
        return snapshot, seal_args

    return {}, []


def process_waiver_signature(mode, record_id):
    """Aide historique pour les décharges où les données sont déjà sur l'enregistrement."""
    config = FLOW_CONFIG.get(mode)
    record = db.session.get(config["model"], record_id)
    return finalize_signed_document(
        mode, record_id, record.signature_data, record.signer_ip)


# Alias de compatibilité descendante pour les inspections
def process_inspection_signature(token_str, mode, signature_data, signed_ip):
    config = FLOW_CONFIG[mode]
    token_model = config["token_model"]
    entry = db.session.get(token_model, token_str)
    if not entry:
        raise ValueError("Token invalide ou introuvable.")

    res = finalize_signed_document(
        mode, int(entry.record_id), signature_data, signed_ip)
    db.session.delete(entry)
    db.session.commit()
    return res


# ── Synchronisation kDrive ──────────────────────────────────────────

def _dispatch_kdrive_document_bundle(mode, record, rel_pdf_path, base_url, current_hash, snapshot):
    """
    Déclenche la synchronisation kDrive native pour tout document signé (bundle PDF + pièces jointes).
    """
    config = FLOW_CONFIG.get(mode)
    project_obj = getattr(record, "project", None)

    # 1. Synchronisation native kDrive (dispatch asynchrone post-commit)
    if project_obj and getattr(project_obj, "id", None):
        try:
            from services.common.kdrive import dispatch_upload_bundle
            entity_id = getattr(record, "inspection_number", getattr(record, "waiver_id", None))
            entity_type_map = {
                "checkout": "checkout",
                "checkin": "checkin",
                "pilot": "pilot_waiver",
                "production": "production_waiver",
            }
            kdrive_entity_type = entity_type_map.get(mode, mode)

            file_specs = [
                {"role": "pdf", "path": rel_pdf_path, "filename": os.path.basename(rel_pdf_path)}
            ]

            if mode in ["checkout", "checkin"]:
                import json
                interior_raw = getattr(record, "interior_photos", None)
                exterior_raw = getattr(record, "exterior_photos", None)
                try:
                    for p in (json.loads(interior_raw) if interior_raw else []):
                        if p:
                            file_specs.append({"role": "photo", "path": p})
                except Exception:
                    pass
                try:
                    for p in (json.loads(exterior_raw) if exterior_raw else []):
                        if p:
                            file_specs.append({"role": "photo", "path": p})
                except Exception:
                    pass
            elif mode == "pilot":
                if getattr(record, "pilot_license_path", None):
                    file_specs.append({"role": "license", "path": record.pilot_license_path})
                if getattr(record, "pilot_insurance_path", None):
                    file_specs.append({"role": "insurance", "path": record.pilot_insurance_path})
                if getattr(record, "pilot_identity_path", None):
                    file_specs.append({"role": "identity", "path": record.pilot_identity_path})
            elif mode == "production":
                if getattr(record, "production_insurance_path", None):
                    file_specs.append({"role": "insurance", "path": record.production_insurance_path})

            if entity_id:
                dispatch_upload_bundle(
                    project_id=project_obj.id,
                    entity_type=kdrive_entity_type,
                    entity_id=entity_id,
                    file_specs=file_specs,
                )
        except Exception as k_err:
            logger.error(f"❌ Erreur dispatch kDrive ({mode}) : {k_err}")


def _send_waiver_confirmation_email(mode, waiver, pdf_path):
    """Envoie une confirmation par e-mail avec le PDF en pièce jointe."""
    try:
        recipient_email = None
        recipient_name = None

        if mode == "pilot":
            if waiver.project and waiver.project.pilot_contact:
                recipient_email = waiver.project.pilot_contact.mail
            recipient_name = f"{waiver.pilot_first_name} {waiver.pilot_last_name}"
        else:
            if waiver.project and waiver.project.production_contact:
                recipient_email = waiver.project.production_contact.mail
            recipient_name = waiver.production_representative

        if recipient_email:
            send_waiver_signed_email(
                recipient_email,
                recipient_name,
                waiver.project_name or (
                    waiver.project.name if waiver.project else "—"),
                pdf_path
            )
    except Exception as e:
        logger.error(f"❌ Erreur e-mail ({mode} {waiver.id}) : {e}")
