"""
Service partagé de signature et de jetons pour les Retours et Départs (flux technicien) ainsi que les décharges.
"""

import logging
import os
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone

from flask import current_app, render_template
from sqlalchemy.exc import IntegrityError

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
    # Incidents
    Incident,
    IncidentToken,
    IncidentSignedDocument,
    AppSetting,
    db,
)
from models.db import _utcnow
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
    get_incident_path,
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
        "template": "pdf/checkout.html",
        "pk_name": "inspection_id",
    },
    "checkin": {
        "model": CheckinVehicle,
        "token_model": CheckinToken,
        "signed_model": CheckinSignedDocument,
        "prefix": "BVCI",
        "url_path": "checkin",
        "storage_func": get_checkin_path,
        "stylesheets": ["css/styles.css", "css/checkin.css"],
        "template": "pdf/checkin.html",
        "pk_name": "inspection_id",
    },
    "pilot": {
        "model": PilotWaiver,
        "token_model": PilotWaiverToken,
        "signed_model": PilotWaiverSignedDocument,
        "prefix": "WAIVER",
        "url_path": "pilot-waiver",
        "storage_func": get_pilot_waiver_path,
        "stylesheets": [],  # Utilise des styles en ligne ou globaux pour les décharges
        "template": "pdf/pilot_waiver.html",
        "pk_name": "waiver_id",
    },
    "production": {
        "model": ProductionWaiver,
        "token_model": ProductionWaiverToken,
        "signed_model": ProductionWaiverSignedDocument,
        "prefix": "WAIVER_PROD",
        "url_path": "production-waiver",
        "storage_func": get_production_waiver_path,
        "stylesheets": [],  # Utilise des styles en ligne ou globaux pour les décharges
        "template": "pdf/production_waiver.html",
        "pk_name": "waiver_id",
    },
    "incident": {
        "model": Incident,
        "token_model": IncidentToken,
        "signed_model": IncidentSignedDocument,
        "prefix": "INCIDENT",
        "url_path": "incidents",
        "storage_func": lambda project_or_rec: get_incident_path(
            project_or_rec if hasattr(project_or_rec, "departure_date") or hasattr(project_or_rec, "name")
            else getattr(project_or_rec, "project", None)
        ),
        "stylesheets": ["css/styles.css", "css/checkout.css", "css/incident_pdf.css"],
        "template": "pdf/incident_report.html",
        "pk_name": "incident_number",
    },
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
        created_at=_utcnow()
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
            "company_address": AppSetting.get("company_address", "39 rue Maurice Gunsbourg, 94200 Ivry-sur-Seine, France"),
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
        logger.error(
            f"❌ La transaction a échoué pendant la signature {mode} : {e}")
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
            from services.common.kdrive import (
                dispatch_upload_bundle,
                extract_bundle_file_specs,
                resolve_entity_info,
            )

            entity_type, entity_id, project_id = resolve_entity_info(
                record, mode)
            if entity_id and project_id:
                file_specs = extract_bundle_file_specs(
                    record, entity_type=entity_type, rel_pdf_path=rel_pdf_path
                )
                dispatch_upload_bundle(
                    project_id=project_id,
                    entity_type=entity_type,
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

        prod_name = None
        if waiver.project and waiver.project.production:
            prod_name = waiver.project.production.name
        elif getattr(waiver, "production_name", None):
            prod_name = waiver.production_name

        if recipient_email:
            send_waiver_signed_email(
                recipient_email,
                recipient_name,
                waiver.project_name or (
                    waiver.project.name if waiver.project else "—"),
                pdf_path,
                production_name=prod_name,
                waiver_type=mode,
            )
    except Exception as e:
        logger.error(f"❌ Erreur e-mail ({mode} {waiver.id}) : {e}")


def seal_incident_contradictory_document(incident, incident_data, base_url=None):
    """
    Moteur unifié de scellement électronique et d'archivage contradictoire pour un incident :
    1. Calcule le sceau HMAC-SHA256 d'intégrité contradictoire.
    2. Génère le QR code de vérification pointant vers /incidents/verify/<incident_number>.
    3. Rend et compresse le PDF scellé intégrant les 2 signatures et le cartouche de conformité.
    4. Enregistre le PDF dans output/.../1_SÉCURITÉ/5_INCIDENTS/.
    5. Met à jour l'incident (hash, pdf_file_hash, signature_status='signed', status 'en_expertise' si signale).
    6. Persiste ou met à jour l'archive légale immuable IncidentSignedDocument.
    7. Déclenche l'upload kDrive asynchrone (bundle PDF + photos + documents).
    """
    if not base_url:
        try:
            from flask import request
            if request:
                base_url = request.host_url.rstrip("/")
        except Exception:
            base_url = current_app.config.get(
                "APP_BASE_URL", "https://bellevitesse.com").rstrip("/")

    verification_url = f"{base_url}/incidents/verify/{incident.incident_number}"
    qr_code_img = generate_qr_code(verification_url)

    # Calcul du sceau HMAC contradictoire
    bv_signed_iso = incident.bv_signed_at.isoformat() if incident.bv_signed_at else ""
    prod_signed_iso = incident.prod_signed_at.isoformat() if incident.prod_signed_at else ""
    current_hash = compute_hmac_seal(
        "INCIDENT",
        incident.incident_number,
        incident.bv_signer_name or "",
        incident.bv_signature_data or "",
        bv_signed_iso,
        incident.prod_signer_name or "",
        incident.prod_signature_data or "",
        prod_signed_iso,
    )

    company_address = "39 rue Maurice Gunsbourg, 94200 Ivry-sur-Seine"
    company_name = "Belle Vitesse SAS"
    try:
        from utils.context_processors import DEFAULT_SETTINGS
        company_address = AppSetting.get(
            "company_address", DEFAULT_SETTINGS["company_address"])
        company_name = AppSetting.get(
            "company_name", DEFAULT_SETTINGS["company_name"])
    except Exception:
        pass

    filename = f"Belle_Vitesse_INCIDENT_{incident.incident_number}_{secrets.token_hex(4)}.pdf"
    project_obj = incident.project if hasattr(incident, "project") else None
    pdf_dir = ensure_dir(get_incident_path(project_obj))
    file_path = os.path.join(pdf_dir, filename)

    today_str = date.today().strftime("%d/%m/%Y")

    render_ctx = {
        "company_name": company_name,
        "company_address": company_address,
        "incident": incident_data,
        "today": today_str,
        "is_sealed": True,
        "hash": current_hash,
        "qr": qr_code_img,
        "verification_url": verification_url,
        "signed_at_str": (incident.prod_signed_at or _utcnow()).strftime("%d/%m/%Y %H:%M"),
    }

    html = render_template("pdf/incident_report.html", **render_ctx)
    pdf_bytes = render_pdf_from_template(
        html_content=html,
        base_url=current_app.root_path,
        stylesheets=["css/styles.css",
                     "css/checkout.css", "css/incident_pdf.css"],
        filename=filename,
    )

    output_base = current_app.config.get(
        "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))
    rel_pdf_path = os.path.relpath(file_path, output_base)

    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    pdf_file_hash = compute_pdf_hash(pdf_bytes)

    incident.signed_pdf_path = rel_pdf_path
    incident.hash = current_hash
    incident.pdf_file_hash = pdf_file_hash
    incident.signature_status = "signed"

    # Transition automatique vers "en_expertise" si "signale"
    if incident.status == "signale":
        incident.status = "en_expertise"
        logger.info(
            f"⚡ Statut de l'incident {incident.incident_number} passé automatiquement à 'en_expertise' suite au scellement contradictoire.")

    # Enregistrement ou mise à jour de l'archive légale
    try:
        signed_doc = IncidentSignedDocument.query.filter_by(
            incident_number=incident.incident_number).first()
        if not signed_doc:
            signed_doc = IncidentSignedDocument(
                incident_number=incident.incident_number,
                incident_id=incident.id,
                hash=current_hash,
                pdf_file_hash=pdf_file_hash,
                data_snapshot=incident.to_dict(),
                signature=incident.prod_signature_data or incident.bv_signature_data,
                pdf_url=f"/incidents/document/{rel_pdf_path}",
                signed_at=(incident.prod_signed_at or _utcnow()
                           ).replace(tzinfo=None)
            )
            db.session.add(signed_doc)
        else:
            signed_doc.incident_id = incident.id
            signed_doc.hash = current_hash
            signed_doc.pdf_file_hash = pdf_file_hash
            signed_doc.data_snapshot = incident.to_dict()
            signed_doc.signature = incident.prod_signature_data or incident.bv_signature_data
            signed_doc.pdf_url = f"/incidents/document/{rel_pdf_path}"
            signed_doc.signed_at = (
                incident.prod_signed_at or _utcnow()).replace(tzinfo=None)

        db.session.commit()
    except IntegrityError as commit_err:
        logger.warning(
            f"⚠️ Archive légale déjà présente pour {incident.incident_number} ({commit_err}), mise à jour de l'existant...")
        db.session.rollback()
        existing_doc = IncidentSignedDocument.query.filter_by(
            incident_number=incident.incident_number).first()
        if existing_doc:
            existing_doc.incident_id = incident.id
            existing_doc.hash = current_hash
            existing_doc.pdf_file_hash = pdf_file_hash
            existing_doc.data_snapshot = incident.to_dict()
            existing_doc.signature = incident.prod_signature_data or incident.bv_signature_data
            existing_doc.pdf_url = f"/incidents/document/{rel_pdf_path}"
            existing_doc.signed_at = (
                incident.prod_signed_at or _utcnow()).replace(tzinfo=None)
            db.session.commit()
        else:
            raise commit_err

    # Synchronisation kDrive native (bundle PDF + photos + documents)
    _dispatch_kdrive_document_bundle(
        "incident", incident, rel_pdf_path, base_url, current_hash, incident.to_dict()
    )

    return {
        "document_id": incident.incident_number,
        "pdf_url": f"/incidents/document/{rel_pdf_path}",
        "hash": current_hash,
        "file_path": file_path,
    }
