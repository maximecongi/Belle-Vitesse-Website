from services.admin.utils import _delete_inspection_files
from utils.n8n import trigger_n8n_webhook
import json
import logging
import os
from pathlib import Path
from datetime import date

from flask import current_app
from werkzeug.utils import secure_filename

from sqlalchemy.orm import joinedload
from models import db, CheckoutVehicle, Project, CheckoutSignedDocument, CheckoutToken
from utils.database import get_vehicles
from services.admin.inspections import _format_base_inspection_admin, get_unified_form_context, apply_inspection_data
from services.admin.documents import get_signed_document_info
from services.admin.utils import handle_admin_service_error

logger = logging.getLogger(__name__)


def list_checkouts():
    """
    Fetch all checkout records, compute stats, and format for listing.
    Uses eager loading to avoid N+1 queries.
    """
    records = CheckoutVehicle.query.options(
        joinedload(CheckoutVehicle.project).joinedload(Project.production),
        joinedload(CheckoutVehicle.responsible_user)
    ).order_by(CheckoutVehicle.created_at.desc()).all()

    vehicles = get_vehicles()
    vehicle_map = {v["id"]: v.get("fields", {}) for v in vehicles}

    # Batch load all vehicle configurations (cached)
    from services.admin.vehicle_config import get_checkpoint_configs
    batch_configs = get_checkpoint_configs()

    total_count = len(records)
    signed_count = sum(1 for r in records if r.etat_controle == "Signé")
    pending_count = sum(1 for r in records if r.etat_controle == "Terminé")

    stats = {
        "total_checkouts": total_count,
        "signed_checkouts": signed_count,
        "pending_checkouts": pending_count,
    }

    checkouts = [_format_base_inspection_admin(
        r, vehicle_map, batch_configs) for r in records]
    return {"checkouts": checkouts, "stats": stats}


def get_checkout_detail(record_id):
    """
    Fetch and format a single checkout record.
    """
    record = CheckoutVehicle.query.options(
        joinedload(CheckoutVehicle.project).joinedload(Project.production),
        joinedload(CheckoutVehicle.responsible_user)
    ).filter_by(id=record_id).first()
    if not record:
        return None

    vehicles = get_vehicles()
    vehicle_map = {v["id"]: v.get("fields", {}) for v in vehicles}
    data = _format_base_inspection_admin(record, vehicle_map)

    # If signed, load the stable snapshot to get the real PDF URL and hash
    if data.get("control_status") == "Signé":
        doc_info = get_signed_document_info(
            data["inspection_id"], is_checkout=True)
        if doc_info:
            data.update(doc_info)

    return data


def get_checkout_form_context():
    return get_unified_form_context(mode="checkout")


def _upload_checkout_photos_local(record: CheckoutVehicle, files):
    if not files:
        return

    from utils.storage import get_checkout_photos_path, ensure_dir
    upload_dir = Path(ensure_dir(get_checkout_photos_path(
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
def create_checkout(form, files=None):
    """Create a new checkout record in the database."""
    pid = form.get("project_id")
    uid = form.get("controller_id")
    # Safety: ensure uid is an integer
    try:
        user_id = int(uid) if uid and uid != "None" else None
    except (ValueError, TypeError):
        user_id = None

    vehicle_id = form.get("vehicle_id")

    record = CheckoutVehicle(
        etat_controle="En cours",
        date_controle=date.today(),
        project_id=int(pid) if pid and pid != "None" else None,
        user_id=user_id,
        vehicule_controle=vehicle_id if vehicle_id != "None" else None,
    )

    # Use unified helper to apply all checkpoints & battery & ready state
    apply_inspection_data(record, form, is_checkout=True)

    db.session.add(record)
    db.session.commit()

    if files:
        _upload_checkout_photos_local(record, files)

    return True


@handle_admin_service_error
def update_checkout(record_id, form, files=None):
    """Update an existing checkout record in the database."""
    record = db.session.get(CheckoutVehicle, record_id)
    if not record:
        return False

    # Use unified helper to apply all checkpoints & battery & ready state
    apply_inspection_data(record, form, is_checkout=True)

    db.session.commit()

    if files:
        _upload_checkout_photos_local(record, files)

    return True


@handle_admin_service_error
def delete_checkout(record_id):
    """Delete a checkout record and its associated files & tokens."""
    record = db.session.get(CheckoutVehicle, record_id)
    if record:
        # 1. Clean up database records related to this inspection
        if record.numero_inspection:
            # Delete tokens
            CheckoutToken.query.filter_by(
                inspection_id=record.numero_inspection).delete()
            # Delete signed document snapshot
            CheckoutSignedDocument.query.filter_by(
                inspection_id=record.numero_inspection).delete()

        # 2. Trigger n8n delete before database deletion
        webhook_url = os.getenv("N8N_WEBHOOK_CHECKOUT_SIGN")
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
