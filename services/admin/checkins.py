from services.admin.documents import get_signed_document_info
from services.admin.inspections import _format_base_inspection_admin, get_unified_form_context, apply_inspection_data
from services.admin.utils import _delete_inspection_files, handle_admin_service_error
from utils.n8n import trigger_n8n_webhook
import json
import logging
import os
from pathlib import Path
from datetime import date

from flask import current_app
from werkzeug.utils import secure_filename

from sqlalchemy.orm import joinedload
from models import db, CheckoutVehicle, CheckinVehicle, Project
from utils.database import get_vehicles

logger = logging.getLogger(__name__)


# ── Checkins ────────────────────────────────────────────────────


def list_checkins():
    """
    Fetch all checkin records, compute stats, and format for listing.
    Uses eager loading to avoid N+1 queries.
    """
    records = CheckinVehicle.query.options(
        joinedload(CheckinVehicle.project).joinedload(Project.production),
        joinedload(CheckinVehicle.responsible)
    ).order_by(CheckinVehicle.created_at.desc()).all()

    vehicles = get_vehicles()
    vehicle_map = {v["id"]: v.get("fields", {}) for v in vehicles}

    # Batch load all vehicle configurations (cached)
    from services.admin.vehicle_config import get_checkpoint_configs
    batch_configs = get_checkpoint_configs()

    total_count = len(records)
    signed_count = sum(1 for r in records if r.etat_controle == "Signé")
    pending_count = sum(1 for r in records if r.etat_controle == "Terminé")

    stats = {
        "total_checkins": total_count,
        "signed_checkins": signed_count,
        "pending_checkins": pending_count,
    }

    checkins = [_format_base_inspection_admin(
        r, vehicle_map, batch_configs) for r in records]
    return {"checkins": checkins, "stats": stats}


def get_checkin_detail(record_id):
    """
    Fetch and format a single checkin record.
    """
    record = CheckinVehicle.query.options(
        joinedload(CheckinVehicle.project).joinedload(Project.production),
        joinedload(CheckinVehicle.responsible)
    ).filter_by(id=record_id).first()
    if not record:
        return None

    vehicles = get_vehicles()
    vehicle_map = {v["id"]: v.get("fields", {}) for v in vehicles}
    data = _format_base_inspection_admin(record, vehicle_map)

    # If signed, load the stable snapshot to get the real PDF URL and hash
    if data.get("control_status") == "Signé":
        doc_info = get_signed_document_info(
            data["inspection_id"], is_checkout=False)
        if doc_info:
            data.update(doc_info)

    return data


def get_checkin_form_context():
    return get_unified_form_context(mode="checkin")


def _upload_checkin_photos_local(record: CheckinVehicle, files):
    if not files:
        return

    from utils.storage import get_checkin_photos_path, ensure_dir
    upload_dir = Path(ensure_dir(get_checkin_photos_path(
        record.project, record.numero_inspection)))

    photo_fields = {
        "exterior_photos": "photos_exterieur",
        "interior_photos": "photos_interieur",
    }

    output_base = current_app.config.get(
        "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))

    for form_field, model_attr in photo_fields.items():
        uploaded = files.getlist(form_field)
        paths = []
        for f in uploaded:
            if f and f.filename:
                filename = secure_filename(f.filename)
                file_path = upload_dir / filename
                f.save(file_path)

                # Store relative path from output base
                rel_path = os.path.relpath(file_path, output_base)
                paths.append(rel_path)

        if paths:
            setattr(record, model_attr, json.dumps(paths))

    db.session.commit()


@handle_admin_service_error
def create_checkin(form, files=None):
    """Create a new checkin record in the database."""
    pid = form.get("project_id")
    uid = form.get("controller_id")
    # Safety: ensure uid is an integer
    try:
        user_id = int(uid) if uid and uid != "None" else None
    except (ValueError, TypeError):
        current_app.logger.warning(
            f"⚠️ Invalid controller_id detected: {uid}. Record will be created without user.")
        user_id = None

    # Determine pertinent status fields for this vehicle
    vehicle_id = form.get("vehicle_id")
    from utils.checkpoints import get_checkpoints_for_vehicle
    checkpoints = get_checkpoints_for_vehicle(vehicle_id)
    pertinent_keys = {cp['key']
                      for cp in checkpoints if cp.get('type') == 'status'}

    def get_val(key):
        if key not in pertinent_keys:
            return "Non pertinent"
        return form.get(key, "À vérifier")

    record = CheckinVehicle(
        etat_controle="En cours",
        date_controle=date.today(),
        project_id=int(pid) if pid and pid != "None" else None,
        user_id=user_id,
        vehicule_controle=vehicle_id if vehicle_id != "None" else None,
    )

    # Use unified helper to apply all checkpoints & battery & ready state
    apply_inspection_data(record, form, is_checkout=False)

    # Safety: ensure latest checkout is signed
    if record.vehicule_controle:
        latest_checkout = CheckoutVehicle.query.filter_by(
            vehicule_controle=record.vehicule_controle).order_by(CheckoutVehicle.id.desc()).first()
        if not latest_checkout or latest_checkout.etat_controle not in ["Signé", "Validé"]:
            current_app.logger.error(
                f"❌ Blocage Checkin : Le véhicule {record.vehicule_controle} "
                f"n'a pas de checkout signé (état actuel: {latest_checkout.etat_controle if latest_checkout else 'Néant'})")
            raise ValueError(
                "Le départ de ce véhicule n'a pas été validé par une signature.")

    db.session.add(record)
    db.session.commit()

    if files:
        _upload_checkin_photos_local(record, files)

    return True


@handle_admin_service_error
def update_checkin(record_id, form, files=None):
    """Update an existing checkin record in the database."""
    record = db.session.get(CheckinVehicle, record_id)
    if not record:
        return False

    pid = form.get("project_id")
    uid = form.get("controller_id")

    record.project_id = int(pid) if pid and pid != "None" else None
    record.user_id = int(uid) if uid and uid != "None" else None
    record.vehicule_controle = form.get("vehicle_id") if form.get(
        "vehicle_id") != "None" else None
    if form.get("battery"):
        record.charge_batterie_retour = float(form.get("battery"))

    # Use unified helper to apply all checkpoints & battery & ready state
    apply_inspection_data(record, form, is_checkout=False)

    db.session.commit()

    if files:
        _upload_checkin_photos_local(record, files)

    return True


@handle_admin_service_error
def delete_checkin(record_id):
    """Delete a checkin record and its associated files & tokens."""
    record = db.session.get(CheckinVehicle, record_id)
    if record:
        # 1. Clean up database records related to this inspection
        if record.numero_inspection:
            from models import CheckinToken, CheckinSignedDocument
            # Delete tokens
            CheckinToken.query.filter_by(
                inspection_id=record.numero_inspection).delete()
            # Delete signed document snapshot
            CheckinSignedDocument.query.filter_by(
                inspection_id=record.numero_inspection).delete()

        # 2. Trigger n8n delete before database deletion
        webhook_url = os.getenv("N8N_WEBHOOK_CHECKIN_SIGN")
        if webhook_url:
            trigger_n8n_webhook(webhook_url, method="DELETE",
                                inspection_id=record.numero_inspection,
                                project_id=record.project.project_id if record.project else None)

        # 3. Delete physical files
        _delete_inspection_files(record)

        # 4. Delete the main record
        db.session.delete(record)
        db.session.commit()
    return True
