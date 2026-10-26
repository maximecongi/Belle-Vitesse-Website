"""
Service partagé de signature et de jetons pour les Retours et Départs (flux technicien) ainsi que les décharges.
"""

import hashlib
import json
import logging
import os
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode

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
    # Waivers & CGL
    CglWaiver,
    SafetyRulesWaiver,
    WaiverToken,
    WaiverSignedDocument,
    # Incidents
    Incident,
    IncidentToken,
    IncidentSignedDocument,
    AppSetting,
    db,
)
from models.db import _utcnow
from models.signature_event import SignatureEvent
from utils.database import get_vehicles
from utils.document_utils import (
    CGL_VERSION,
    compute_canonical_seal,
    verify_canonical_seal,
    compute_file_sha256,
    compute_hmac_seal,
    compute_pdf_hash,
    generate_qr_code,
    generate_document_verification_token,
    render_pdf_from_template,
)
from utils.mailer import send_waiver_signed_email
from utils.signature_storage import (
    save_signature_image,
    load_signature_data_uri,
    delete_signature_file,
)


def log_signature_event(document_id: str, mode: str, event_type: str, details: dict = None, ip: str = None, user_agent: str = None, raise_on_failure: bool = False):
    """
    Enregistre un événement d'audit immuable dans la table signature_events avec chaînage SHA-256.
    Utilise un point de sauvegarde (savepoint) pour isoler l'insertion et éviter
    d'invalider la session globale SQLAlchemy si la table est manquante ou indisponible.
    """
    try:
        with db.session.begin_nested():
            # Chaînage cryptographique des événements pour ce document
            last_event = (
                SignatureEvent.query.filter_by(document_id=str(document_id))
                .order_by(SignatureEvent.id.desc())
                .first()
            )
            prev_hash = last_event.event_hash if (last_event and last_event.event_hash) else ""
            now_dt = _utcnow().replace(tzinfo=None, microsecond=0)
            details_payload = details or {}
            details_json = json.dumps(details_payload, sort_keys=True, ensure_ascii=False)
            ip_str = ip[:45] if ip else ""
            ua_str = user_agent[:255] if user_agent else ""
            raw_chain = f"{document_id}|{mode}|{event_type}|{ip_str}|{ua_str}|{details_json}|{prev_hash}|{now_dt.isoformat()}"
            curr_hash = hashlib.sha256(raw_chain.encode("utf-8")).hexdigest()

            event_record = SignatureEvent(
                document_id=str(document_id),
                mode=str(mode),
                event_type=str(event_type),
                ip=ip[:45] if ip else None,
                user_agent=user_agent[:255] if user_agent else None,
                details=details_payload,
                previous_event_hash=prev_hash or None,
                event_hash=curr_hash,
                created_at=now_dt
            )
            db.session.add(event_record)
            db.session.flush()
        return event_record
    except Exception as e:
        logger.error(f"⚠️ Échec de l'enregistrement de signature_event ({event_type} pour {document_id}): {e}")
        if raise_on_failure:
            raise
        return None


def verify_signature_events_chain(document_id: str, require_events: bool = False) -> dict:
    """
    Vérifie l'intégrité cryptographique complète de la chaîne d'audit signature_events pour un document.
    Retourne un dict {"valid": bool, "count": int, "error": str or None}.
    """
    events = (
        SignatureEvent.query.filter_by(document_id=str(document_id))
        .order_by(SignatureEvent.id.asc())
        .all()
    )
    if not events:
        if require_events:
            return {
                "valid": False,
                "count": 0,
                "error": "Aucun événement d'audit enregistré pour ce document scellé.",
            }
        return {"valid": True, "count": 0, "error": None}

    expected_prev = ""
    for ev in events:
        actual_prev = ev.previous_event_hash or ""
        if actual_prev != expected_prev:
            return {
                "valid": False,
                "count": len(events),
                "error": f"Rupture de chaînage à l'événement #{ev.id} ({ev.event_type})",
            }
        details_json = json.dumps(ev.details or {}, sort_keys=True, ensure_ascii=False)
        ip_str = ev.ip or ""
        ua_str = ev.user_agent or ""
        dt_str = ev.created_at.replace(tzinfo=None, microsecond=0).isoformat() if ev.created_at else ""
        raw_chain = f"{ev.document_id}|{ev.mode}|{ev.event_type}|{ip_str}|{ua_str}|{details_json}|{actual_prev}|{dt_str}"
        recalculated_hash = hashlib.sha256(raw_chain.encode("utf-8")).hexdigest()
        if recalculated_hash != ev.event_hash:
            return {
                "valid": False,
                "count": len(events),
                "error": f"Empreinte falsifiée à l'événement #{ev.id} ({ev.event_type})",
            }
        expected_prev = ev.event_hash

    return {"valid": True, "count": len(events), "error": None}

from utils.storage import (
    ensure_dir,
    get_cgl_path,
    get_safety_rules_path,
    get_checkin_path,
    get_checkout_path,
    get_incident_path,
)
from services.admin.safety_rules_config import (
    get_safety_rules_for_vehicles,
    DEFAULT_HELMETS_INVENTORY,
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
    "cgl": {
        "model": CglWaiver,
        "token_model": WaiverToken,
        "signed_model": WaiverSignedDocument,
        "prefix": "BVRA",
        "url_path": "cgl",
        "storage_func": get_cgl_path,
        "stylesheets": ["css/styles.css", "css/admin/cgl-pdf.css"],
        "template": "pdf/cgl.html",
        "pk_name": "waiver_id",
    },
    "safety_rules": {
        "model": SafetyRulesWaiver,
        "token_model": WaiverToken,
        "signed_model": WaiverSignedDocument,
        "prefix": "BVSR",
        "url_path": "safety-rules",
        "storage_func": get_safety_rules_path,
        "stylesheets": ["css/styles.css", "css/admin/safety-rules-pdf.css"],
        "template": "pdf/safety_rules.html",
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
    config = FLOW_CONFIG.get(mode)
    if not config:
        return None, 404

    token_model = config["token_model"]
    entry = db.session.get(token_model, token_str)
    if not entry:
        return None, 404

    if hasattr(entry, "is_expired") and entry.is_expired():
        return None, 410

    if entry.signature:
        return None, 409

    return entry, None


def generate_inspection_token(record_id, mode):
    config = FLOW_CONFIG.get(mode)
    if not config:
        return None
    model = config["model"]
    token_model = config["token_model"]
    signed_model = config.get("signed_model")

    record = db.session.get(model, record_id)
    if not record or getattr(record, "deleted_at", None) is not None:
        return None

    if getattr(record, "status", None) in ["signed", "completed"]:
        raise ValueError(f"Cet enregistrement {mode} #{record_id} a déjà été signé et validé.")

    doc_id = getattr(record, "inspection_number", getattr(record, "waiver_id", f"{mode}_{record_id}"))
    if signed_model and db.session.get(signed_model, doc_id):
        raise ValueError(f"Une archive scellée immuable existe déjà pour cette inspection ({doc_id}).")

    if mode == "checkout":
        from services.admin.utils import compute_inspection_readiness
        is_ready, failures = compute_inspection_readiness(
            record,
            vehicle_id=record.vehicle_id,
            is_checkout=True,
            battery_val=record.battery_level,
        )
        if not is_ready:
            fail_str = f" ({', '.join(failures)})" if failures else ""
            raise ValueError(f"Impossible de générer le jeton de signature : le véhicule n'est pas prêt{fail_str}.")

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

    if record.status not in ["signed", "completed"]:
        record.status = "pending"
    db.session.commit()

    base_url = (
        current_app.config.get("APP_BASE_URL")
        or current_app.config.get("BASE_URL")
        or os.getenv("APP_BASE_URL")
        or os.getenv("BASE_URL", "https://bellevitesse.com")
    ) if current_app else os.getenv("BASE_URL", "https://bellevitesse.com")
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"

    return {
        "inspection_id": data["inspection_id"],
        "token": token,
        "sign_url": f"{base_url.rstrip('/')}/{config['url_path']}/sign/{token}",
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
        # Ne jamais rétrograder en 'in_progress' si le document est déjà scellé ou signé
        if record and record.status not in ["signed", "completed"]:
            record.status = "in_progress"
            db.session.commit()
        logger.info(f"🔙 Signature abandonnée pour {entry.inspection_id}")
    except Exception as e:
        db.session.rollback()
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
        if record and record.status not in ["signed", "completed"]:
            record.status = "pending"
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Échec de la reprise de la signature : {e}")
    return True


# ── Moteur de Traitement des Signatures ──────────────────────────

def finalize_signed_document(mode, record_id, signature_data, signed_ip, extra_data=None, user_agent=None, token_entry=None):
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
    base_url = (
        current_app.config.get("APP_BASE_URL")
        or current_app.config.get("BASE_URL")
        or os.getenv("APP_BASE_URL")
        or os.getenv("BASE_URL", "https://bellevitesse.com")
    ) if current_app else os.getenv("BASE_URL", "https://bellevitesse.com")
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"

    try:
        # 1. Mise à jour de l'état (sans écraser la date ou l'IP originale du client si déjà présent)
        if hasattr(record, "status"):
            record.status = "signed"
        if hasattr(record, "signed_at"):
            if not record.signed_at:
                record.signed_at = signed_at.replace(tzinfo=None)
        if hasattr(record, "signer_ip"):
            if not record.signer_ip:
                record.signer_ip = signed_ip

        # 2. Déport de la signature binaire sur disque en fichier PNG
        document_id = getattr(
            record, "inspection_number", getattr(record, "waiver_id", f"{mode}_{record.id}"))
        entity_type = "waivers" if mode in ["cgl", "safety_rules"] else (
            "checkouts" if mode == "checkout" else "checkins"
        )
        output_base = current_app.config.get(
            "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))

        # Point 3: Contrôle d'immuabilité en mémoire AVANT toute écriture de PNG sur disque
        if hasattr(signed_model, "version"):
            existing_doc = signed_model.query.filter_by(waiver_id=document_id).order_by(signed_model.version.desc()).first()
        elif hasattr(signed_model, "inspection_id"):
            existing_doc = signed_model.query.filter_by(inspection_id=document_id).first()
        else:
            existing_doc = db.session.get(signed_model, document_id)

        is_bv_countersign = False
        if existing_doc:
            is_bv_countersign = (
                mode == "safety_rules"
                and getattr(record, "bv_signature_data", None)
                and getattr(existing_doc, "version", 1) == 1
                and not (existing_doc.data_snapshot or {}).get("bv_signature_sha256")
            )
            if not is_bv_countersign:
                raise ValueError(
                    f"Ce document #{document_id} ({mode}) a déjà été signé et scellé de manière immuable. "
                    "L'écrasement de la signature d'origine est interdit."
                )

        if str(signature_data).startswith("signatures/") and str(signature_data).endswith(".png"):
            from utils.signature_storage import validate_stored_signature_file
            sig_file_rel_path = validate_stored_signature_file(signature_data)
        else:
            sig_file_rel_path = save_signature_image(
                signature_data, entity_type=entity_type, record_id=document_id)
        if hasattr(record, "signature_data"):
            record.signature_data = sig_file_rel_path

        sig_full_path = os.path.join(output_base, sig_file_rel_path)
        sig_file_sha256 = compute_file_sha256(sig_full_path)

        # Déport et hachage du PNG de contre-signature BV si présent
        bv_sig_file_sha256 = ""
        if mode == "safety_rules" and getattr(record, "bv_signature_data", None):
            bv_raw = record.bv_signature_data
            if str(bv_raw).startswith("data:image"):
                bv_file_rel = save_signature_image(
                    bv_raw, entity_type="waivers", record_id=f"{document_id}_bv")
                record.bv_signature_data = bv_file_rel
            elif str(bv_raw).startswith("signatures/") and str(bv_raw).endswith(".png"):
                from utils.signature_storage import validate_stored_signature_file
                bv_file_rel = validate_stored_signature_file(bv_raw)
            else:
                bv_file_rel = bv_raw
            full_bv_path = os.path.join(output_base, bv_file_rel.lstrip("/"))
            bv_sig_file_sha256 = compute_file_sha256(full_bv_path)

        db.session.flush()

        # Construction du Snapshot des données et Scellé Canonique (Hash)
        if existing_doc and mode == "safety_rules" and existing_doc.data_snapshot:
            # Point 9: Réutiliser l'instantané figé du client pour ne pas altérer les miniatures Airtable ni les détails
            frozen_client_snapshot = dict(existing_doc.data_snapshot.get("snapshot") or {})
            frozen_client_snapshot["bv_signature"] = record.bv_signature_data or ""
            frozen_client_snapshot["bv_signed_at"] = record.bv_signed_at.isoformat() if record.bv_signed_at else ""
            frozen_client_snapshot["bv_signer_name"] = record.bv_signer_name or ""
            if bv_sig_file_sha256:
                frozen_client_snapshot["bv_signature_sha256"] = bv_sig_file_sha256
            snapshot = frozen_client_snapshot
        else:
            snapshot, seal_args = _build_flow_data(mode, record, extra_data)
            if bv_sig_file_sha256:
                snapshot["bv_signature_sha256"] = bv_sig_file_sha256

        client_signed_at_dt = getattr(record, "signed_at", None) or signed_at.replace(tzinfo=None)
        canonical_payload = {
            "version": "2.0",
            "_seal_kid": "v1",
            "mode": mode,
            "document_id": str(document_id),
            "signed_at": client_signed_at_dt.isoformat(),
            "signer_ip": getattr(record, "signer_ip", None) or signed_ip,
            "signature_sha256": sig_file_sha256,
            "snapshot": snapshot,
        }
        archive_version = 2 if is_bv_countersign else 1
        if is_bv_countersign and existing_doc:
            # Le lien vers l'archive précédente fait partie du contenu signé.
            canonical_payload["parent_hash"] = existing_doc.hash
        if bv_sig_file_sha256:
            canonical_payload["bv_signature_sha256"] = bv_sig_file_sha256

        current_hash = compute_canonical_seal(canonical_payload)

        # 3. QR code et génération du PDF
        verification_token = generate_document_verification_token(
            mode, str(document_id), archive_version, current_hash
        )
        verification_query = urlencode({"version": archive_version, "t": verification_token})
        verification_url = (
            f"{base_url}/{config['url_path']}/verify/{document_id}?{verification_query}"
        )
        qr_code_img = generate_qr_code(verification_url)

        # Résolution de la Data URI pour les moteurs de rendu (WeasyPrint)
        sig_data_uri = load_signature_data_uri(
            sig_file_rel_path) or signature_data

        # Préparation du contexte de rendu
        render_ctx = {
            "signature": sig_data_uri,
            "qr": qr_code_img,
            "hash": current_hash,
            "document_hash": current_hash,  # utilisé pour les décharges et CGL
            "verification_url": verification_url,
            "signed_at_str": signed_at.strftime("%d/%m/%Y %H:%M"),
            "signed_ip": signed_ip,
            # Données de l'entreprise tirées de la DB
            "company_name": AppSetting.get("company_name", "Belle Vitesse SAS"),
            "company_representative": AppSetting.get("company_representative", ""),
            "company_siret": AppSetting.get("company_siret", ""),
            "company_vat": AppSetting.get("company_vat", ""),
            "company_address": AppSetting.get("company_address", ""),
            "company_phone": AppSetting.get("company_phone", ""),
            "company_email": AppSetting.get("company_email", ""),
            "company_capital": AppSetting.get("company_capital", "1 000 €"),
            "company_rcs": AppSetting.get("company_rcs", ""),
            "bank_iban": AppSetting.get("bank_iban", ""),
            "bank_bic": AppSetting.get("bank_bic", ""),
        }
        # Ajout des données spécifiques au flux
        if mode in ["checkout", "checkin"]:
            render_ctx["data"] = snapshot
        elif mode == "cgl":
            render_ctx["cgl"] = record
            render_ctx["waiver"] = record
        elif mode == "safety_rules":
            render_ctx["safety_rules"] = record
            render_ctx["waiver"] = record
            render_ctx["vehicle_rules"] = get_safety_rules_for_vehicles(record.vehicles_details)
            render_ctx["helmets"] = record.helmets_inventory or DEFAULT_HELMETS_INVENTORY
            render_ctx["safety_technicians"] = record.safety_technicians or ""
            render_ctx["bv_signature"] = record.bv_signature_data_uri
        else:
            render_ctx["waiver"] = record

        project_obj = getattr(record, "project", None)
        pdf_dir = ensure_dir(config["storage_func"](project_obj))
        filename = f"{document_id}_{secrets.token_hex(8)}.pdf"
        file_path = os.path.join(pdf_dir, filename)

        html_content = render_template(config["template"], **render_ctx)

        # 4. Stockage physique
        rel_pdf_path = os.path.relpath(file_path, output_base)
        pdf_public_url = f"{base_url}/{config['url_path']}/document/{rel_pdf_path}"

        # 5. Persistance en base de données
        if hasattr(record, "signed_pdf_path"):
            record.signed_pdf_path = rel_pdf_path

        if hasattr(record, "hash"):
            record.hash = current_hash

        # Création ou persistance de l'enregistrement d'archive (avec support du versionnement pour BVSR)
        pk_name = "inspection_id" if mode in ["checkout", "checkin"] else "waiver_id"
        if hasattr(signed_model, "version"):
            existing_doc = signed_model.query.filter_by(waiver_id=document_id).order_by(signed_model.version.desc()).first()
        elif hasattr(signed_model, "inspection_id"):
            existing_doc = signed_model.query.filter_by(inspection_id=document_id).first()
        else:
            existing_doc = db.session.get(signed_model, document_id)

        if is_bv_countersign and existing_doc:
            # Contre-signature versionnée : créer une nouvelle ligne distincte (Version 2)
            # sans écraser ni altérer la version 1 d'origine du client
            signed_doc = signed_model(
                waiver_id=document_id,
                version=archive_version,
                parent_hash=existing_doc.hash,
                hash=current_hash,
                pdf_file_hash="",
                data_snapshot=canonical_payload,
                signature=sig_file_rel_path,
                pdf_url=pdf_public_url,
                signed_at=signed_at.replace(tzinfo=None)
            )
            db.session.add(signed_doc)
            log_signature_event(document_id, mode, "archive_countersigned", {
                "parent_hash": existing_doc.hash,
                "new_hash": current_hash,
                "bv_signature_sha256": bv_sig_file_sha256,
                "version": 2,
            }, ip=signed_ip, user_agent=user_agent, raise_on_failure=True)
        elif existing_doc:
            raise ValueError(
                f"Ce document #{document_id} ({mode}) a déjà été signé et scellé de manière immuable. "
                "L'écrasement de l'archive d'origine est interdit."
            )
        else:
            signed_doc = signed_model(
                **{pk_name: document_id},
                hash=current_hash,
                pdf_file_hash="",
                data_snapshot=canonical_payload,
                signature=sig_file_rel_path,
                pdf_url=pdf_public_url,
                signed_at=signed_at.replace(tzinfo=None)
            )
            if hasattr(signed_doc, "version"):
                signed_doc.version = archive_version
            db.session.add(signed_doc)
            log_signature_event(document_id, mode, "document_signed", {
                "hash": current_hash,
                "signature_sha256": sig_file_sha256,
                "version": 1,
            }, ip=signed_ip, user_agent=user_agent, raise_on_failure=True)

        if token_entry:
            token_entry.signature = current_hash

        try:
            db.session.commit()
        except IntegrityError as commit_err:
            db.session.rollback()
            raise ValueError(f"Erreur d'intégrité : une archive scellée existe déjà pour {document_id} ({commit_err}).")

        # 6. Compilation PDF asynchrone via RQ & Post-traitements (kDrive, Emails)
        try:
            from services.common.pdf_tasks import dispatch_pdf_generation
            dispatch_pdf_generation(
                html_content=html_content,
                output_file_path=file_path,
                base_url=base_url,
                stylesheets=config["stylesheets"],
                compress=True,
                filename=filename,
                entity_type="waiver" if mode in ["cgl", "safety_rules"] else "inspection",
                entity_id=document_id,
                post_action="waiver_post_actions" if mode in ["cgl", "safety_rules"] else "inspection_post_actions",
                extra_context={
                    "mode": mode,
                    "rel_pdf_path": rel_pdf_path,
                    "current_hash": current_hash,
                    "snapshot": snapshot,
                },
            )
        except Exception as queue_err:
            logger.warning(
                f"⚠️ Document {document_id} scellé avec succès en base, mais la mise en file du PDF a échoué : {queue_err}. "
                "La preuve DB est préservée et le document reste en attente de compilation PDF."
            )

        return {
            "document_id": document_id,
            "pdf_url": pdf_public_url,
            "verification_url": verification_url,
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
        vehicle_id = str(getattr(record, "vehicle_id", "") or data.get("vehicle_id", "") or "")
        data["vehicle_id"] = vehicle_id
        seal_args = [vehicle_id]
        snapshot = dict(data)
        snapshot["mode"] = mode
        snapshot["_seal_vehicle_id"] = vehicle_id
        return snapshot, seal_args

    elif mode == "safety_rules":
        signer_name = record.signer_name if hasattr(record, "signer_name") else "Intervenant"
        role_label = record.signer_role_label if hasattr(record, "signer_role_label") else "Intervenant"
        sign_data = getattr(record, "sign_data", None) or {}
        seal_args = [signer_name, role_label]
        snapshot = {
            "mode": "safety_rules",
            "waiver_id": record.waiver_id,
            "project_name": record.project_name or (record.project.name if record.project else "—"),
            "production_name": record.display_production_name if hasattr(record, "display_production_name") else "—",
            "project": record.project_name or (record.project.name if record.project else "—"),
            "production": record.display_production_name if hasattr(record, "display_production_name") else "—",
            "signer_name": signer_name,
            "signer_role": role_label,
            "signer_email": getattr(record, "signer_email", "") or "",
            "signer_phone": getattr(record, "signer_phone", "") or "",
            "signer_company": getattr(record, "signer_company", "") or "",
            "vehicles_details": getattr(record, "vehicles_details", None) or [],
            "helmets_inventory": getattr(record, "helmets_inventory", None) or DEFAULT_HELMETS_INVENTORY,
            "safety_technicians": getattr(record, "safety_technicians", "") or "",
            "ack_rules": sign_data.get("ack_rules", True),
            "ack_authority": sign_data.get("ack_authority", True),
            "bv_signature": record.bv_signature_data or "",
            "bv_signed_at": record.bv_signed_at.isoformat() if record.bv_signed_at else "",
            "bv_signer_name": record.bv_signer_name or "",
            "_seal_signer_name": signer_name,
            "_seal_signer_role": role_label,
        }
        return snapshot, seal_args

    elif mode == "cgl":
        sign_data = record.sign_data or {}
        seal_args = [record.production_name or "",
                     record.production_representative or ""]
        snapshot = {
            "mode": "cgl",
            "waiver_id": record.waiver_id,
            "project_name": record.project_name or (record.project.name if record.project else "—"),
            "production_name": record.production_name or (record.project.production.name if record.project and record.project.production else "—"),
            "project": record.project_name or (record.project.name if record.project else "—"),
            "production": record.production_name or (record.project.production.name if record.project and record.project.production else "—"),
            "representative_name": record.production_representative or "",
            "representative_role": record.signer_role_custom or sign_data.get("representative_role", ""),
            "has_signing_authority": sign_data.get("has_signing_authority", True),
            "authority_declaration_text": sign_data.get("authority_declaration_text", ""),
            "accepted_terms": sign_data.get("accepted_terms", True),
            "accepted_at": sign_data.get("accepted_at", ""),
            "terms_fingerprint": sign_data.get("terms_fingerprint", ""),
            "cgl_version": sign_data.get("cgl_version", CGL_VERSION),
            "signer_email": record.signer_email or "",
            "signer_phone": record.signer_phone or "",
            "siret": record.production_siret or "",
            "address": record.production_address or "",
            "vat_number": record.production_vat or "",
            "legal_form": sign_data.get("legal_form", ""),
            "legal_country": sign_data.get("legal_country", ""),
            "insurance_company": record.production_insurance_company or "",
            "insurance_policy": record.production_insurance_policy or "",
            "insurance_file_sha256": sign_data.get("insurance_file_sha256", ""),
            "location_of_use": record.location_of_use or "",
            "vehicles": getattr(record, "vehicles_details", None) or [],
            "shooting_dates": record.shooting_dates or "",
            "order_ref": getattr(record, "display_order_ref", None) or getattr(record, "order_ref", None) or sign_data.get("order_ref", "") or "",
            "signature_city": sign_data.get("signature_city", "") or getattr(record, "display_signature_city", ""),
            "_seal_production_name": record.production_name or "",
            "_seal_representative": record.production_representative or "",
        }
        return snapshot, seal_args

    return {}, []


def process_waiver_signature(mode, record_id):
    """Aide pour les décharges où les données sont déjà sur l'enregistrement."""
    config = FLOW_CONFIG.get(mode)
    record = db.session.get(config["model"], record_id)
    return finalize_signed_document(
        mode, record_id, record.signature_data, record.signer_ip)


def process_inspection_signature(token_str: str, mode: str, signature_data: str, signed_ip: str, expected_record_id: int = None, user_agent: str = None) -> dict:
    """
    Traite et scelle cryptographiquement une signature d'inspection (checkout ou checkin)
    associée à un jeton à durée de validité limitée (24h).
    Effectue un verrouillage pessimiste, prévient toute réutilisation (single-use),
    vérifie la concordance d'entité et l'état de préparation du véhicule avant finalisation.
    """
    if mode not in FLOW_CONFIG or mode not in ("checkout", "checkin"):
        raise ValueError(f"Mode d'inspection non reconnu : {mode}")

    config = FLOW_CONFIG[mode]
    token_model = config["token_model"]

    if not token_str or not str(token_str).strip():
        raise ValueError("Le jeton de validation de signature est requis.")

    # 1. Verrouillage pessimiste de la ligne du jeton pour prévenir les race conditions
    entry = token_model.query.filter_by(token=token_str).with_for_update().first()
    if not entry:
        raise ValueError("Jeton de signature introuvable ou invalide.")

    # 2. Vérification de l'expiration du jeton (24h)
    if hasattr(entry, "is_expired") and entry.is_expired():
        raise ValueError("Le lien de signature a expiré (durée de validité de 24h dépassée).")

    # 3. Vérification de l'usage unique (anti-rejeu)
    if entry.signature:
        raise ValueError("Ce lien de signature a déjà été utilisé pour sceller le document.")

    # 4. Vérification de la correspondance de l'enregistrement cible
    if expected_record_id is not None:
        try:
            target_rec_id = int(entry.record_id)
            exp_rec_id = int(expected_record_id)
        except (ValueError, TypeError):
            raise ValueError("Identifiant d'enregistrement invalide dans le jeton.")

        if target_rec_id != exp_rec_id:
            raise ValueError("Le jeton fourni ne correspond pas à l'enregistrement d'inspection ciblé.")

    record_id = int(entry.record_id)
    record = db.session.get(config["model"], record_id)
    if not record or record.deleted_at is not None:
        raise ValueError(f"Enregistrement {mode} #{record_id} introuvable ou supprimé.")

    if getattr(record, "status", None) in ["signed", "completed"]:
        raise ValueError(f"Cet enregistrement {mode} #{record_id} a déjà été signé et validé.")

    doc_id = getattr(record, "inspection_number", getattr(record, "waiver_id", f"{mode}_{record_id}"))
    if db.session.get(config["signed_model"], doc_id):
        raise ValueError(f"Une archive scellée immuable existe déjà pour cette inspection ({doc_id}).")

    # 5. Vérification stricte de l'état de préparation du véhicule pour les départs (checkout)
    if mode == "checkout":
        from services.admin.utils import compute_inspection_readiness
        is_ready, failures = compute_inspection_readiness(
            record,
            vehicle_id=record.vehicle_id,
            is_checkout=True,
            battery_val=record.battery_level,
        )
        if not is_ready:
            fail_str = f" ({', '.join(failures)})" if failures else ""
            raise ValueError(f"Impossible de sceller le check-out : le véhicule n'est pas prêt{fail_str}.")

    # 6. Finalisation du document scellé et consommation atomique du jeton
    res = finalize_signed_document(
        mode, record_id, signature_data, signed_ip, user_agent=user_agent, token_entry=entry
    )

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

        if mode == "safety_rules":
            recipient_email = getattr(waiver, "signer_email", None)
            recipient_name = waiver.signer_name
            if not recipient_email and waiver.project:
                if waiver.project.pilot_contact and getattr(waiver, "signer_role", None) == "pilot":
                    recipient_email = waiver.project.pilot_contact.mail
                elif waiver.project.production_contact:
                    recipient_email = waiver.project.production_contact.mail
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
    verification_token = generate_document_verification_token(
        "incident", str(incident.incident_number), 1, current_hash
    )
    verification_url = (
        f"{base_url}/incidents/verify/{incident.incident_number}?"
        f"{urlencode({'version': 1, 't': verification_token})}"
    )
    qr_code_img = generate_qr_code(verification_url)

    company_address = ""
    company_name = "Belle Vitesse SAS"
    try:
        from utils.context_processors import DEFAULT_SETTINGS
        company_address = AppSetting.get(
            "company_address", DEFAULT_SETTINGS.get("company_address", ""))
        company_name = AppSetting.get(
            "company_name", DEFAULT_SETTINGS.get("company_name", "Belle Vitesse SAS"))
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

    output_base = current_app.config.get(
        "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))
    rel_pdf_path = os.path.relpath(file_path, output_base)

    incident.signed_pdf_path = rel_pdf_path
    incident.hash = current_hash
    incident.pdf_file_hash = ""
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
                pdf_file_hash="",
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
            signed_doc.pdf_file_hash = ""
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
            existing_doc.pdf_file_hash = ""
            existing_doc.data_snapshot = incident.to_dict()
            existing_doc.signature = incident.prod_signature_data or incident.bv_signature_data
            existing_doc.pdf_url = f"/incidents/document/{rel_pdf_path}"
            existing_doc.signed_at = (
                incident.prod_signed_at or _utcnow()).replace(tzinfo=None)
            db.session.commit()
        else:
            raise commit_err

    # Délégation asynchrone de la compilation WeasyPrint
    from services.common.pdf_tasks import dispatch_pdf_generation
    dispatch_pdf_generation(
        html_content=html,
        output_file_path=file_path,
        base_url=current_app.root_path,
        stylesheets=["css/styles.css",
                     "css/checkout.css", "css/incident_pdf.css"],
        compress=True,
        filename=filename,
        entity_type="incident",
        entity_id=incident.id,
    )

    try:
        if signed_doc:
            db.session.refresh(signed_doc)
        db.session.refresh(incident)
    except Exception:
        pass

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
