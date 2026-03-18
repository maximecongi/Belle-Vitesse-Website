import json
import logging
import os
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename
from sqlalchemy.orm import joinedload

from models import db, CheckoutVehicle, CheckinVehicle, Project, User
from utils.database import get_vehicles
from utils.formatting import format_date_fr
from utils.checkpoints import get_checkpoints_for_vehicle, BASE_CHECKPOINTS, ALL_POSSIBLE_CHECKPOINTS, CHECKPOINT_TO_MODEL_MAP
from services.admin.utils import _parse_photos_json, _is_ready, _delete_inspection_files

logger = logging.getLogger(__name__)


# ── Configuration & Metadata ─────────────────────────────────────

def get_inspection_config(mode):
    """
    Returns model and metadata for a given inspection mode.
    """
    if mode == "checkout":
        from models import CheckoutToken, CheckoutSignedDocument
        return {
            "model": CheckoutVehicle,
            "token_model": CheckoutToken,
            "signed_model": CheckoutSignedDocument,
            "webhook_env": "N8N_WEBHOOK_CHECKOUT_SIGN",
            "photos_path_func": "get_checkout_photos_path",
            "responsible_attr": "responsible_user",
            "is_checkout": True,
            "stats_key": "checkouts"
        }
    else:
        from models import CheckinToken, CheckinSignedDocument
        return {
            "model": CheckinVehicle,
            "token_model": CheckinToken,
            "signed_model": CheckinSignedDocument,
            "webhook_env": "N8N_WEBHOOK_CHECKIN_SIGN",
            "photos_path_func": "get_checkin_photos_path",
            "responsible_attr": "responsible",
            "is_checkout": False,
            "stats_key": "checkins"
        }


# ── Core Operations (Unified) ───────────────────────────────────

def list_inspections_unified(mode):
    """
    Generic fetcher for Checkout or Checkin records.
    """
    config = get_inspection_config(mode)
    record_model = config["model"]
    resp_attr = config["responsible_attr"]

    records = record_model.query.options(
        joinedload(record_model.project).joinedload(Project.production),
        joinedload(getattr(record_model, resp_attr))
    ).order_by(record_model.created_at.desc()).all()

    vehicles = get_vehicles()
    vehicle_map = {v["id"]: v.get("fields", {}) for v in vehicles}

    from services.admin.vehicle_config import get_checkpoint_configs
    batch_configs = get_checkpoint_configs()

    total = len(records)
    signed = sum(1 for r in records if r.etat_controle == "Signé")
    pending = sum(1 for r in records if r.etat_controle == "Terminé")

    formatted = [_format_base_inspection_admin(
        r, vehicle_map, batch_configs) for r in records]

    return {
        config["stats_key"]: formatted,
        "stats": {
            f"total_{config['stats_key']}": total,
            f"signed_{config['stats_key']}": signed,
            f"pending_{config['stats_key']}": pending,
        }
    }


def get_inspection_detail_unified(mode, record_id):
    """
    Generic detail fetcher for a single inspection.
    """
    config = get_inspection_config(mode)
    record_model = config["model"]
    resp_attr = config["responsible_attr"]

    record = record_model.query.options(
        joinedload(record_model.project).joinedload(Project.production),
        joinedload(getattr(record_model, resp_attr))
    ).filter_by(id=record_id).first()

    if not record:
        return None

    vehicles = get_vehicles()
    vehicle_map = {v["id"]: v.get("fields", {}) for v in vehicles}
    data = _format_base_inspection_admin(record, vehicle_map)

    if data.get("control_status") == "Signé":
        from services.admin.documents import get_signed_document_info
        doc_info = get_signed_document_info(
            data["inspection_id"], is_checkout=config["is_checkout"])
        if doc_info:
            data.update(doc_info)

    return data


def delete_inspection_unified(mode, record_id):
    """
    Generic deletion for any inspection type.
    """
    config = get_inspection_config(mode)
    record = db.session.get(config["model"], record_id)
    if not record:
        return False

    from utils.n8n import trigger_n8n_webhook
    insp_id = record.numero_inspection

    if insp_id:
        # 1. Database Cleanup
        config["token_model"].query.filter_by(inspection_id=insp_id).delete()
        config["signed_model"].query.filter_by(inspection_id=insp_id).delete()

        # 2. Webhook
        webhook_url = os.getenv(config["webhook_env"])
        if webhook_url:
            trigger_n8n_webhook(
                webhook_url, method="DELETE",
                inspection_id=insp_id,
                project_id=record.project.project_id if record.project else None
            )

    # 3. Assets & Files
    _delete_inspection_files(record)

    # 4. Main Record
    db.session.delete(record)
    db.session.commit()
    return True


def upload_inspection_photos_shared(mode, record, files):
    """
    Universal photo uploader for inspections.
    """
    if not files:
        return

    config = get_inspection_config(mode)
    # Dynamic import to avoid circular dependency
    import utils.storage as storage
    path_func = getattr(storage, config["photos_path_func"])

    upload_dir = Path(storage.ensure_dir(path_func(
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
                paths.append(os.path.relpath(file_path, output_base))

        if paths:
            setattr(record, model_attr, json.dumps(paths))

    db.session.commit()


# ── Internal Helpers ───────────────────────────────────────────

def apply_inspection_data(record, form, is_checkout=True):
    """
    Dynamically maps form fields to model attributes based on ALL_POSSIBLE_CHECKPOINTS.
    Handles battery and ready state calculation.
    """
    vehicle_id = form.get("vehicle_id") or getattr(
        record, 'vehicule_controle', None)
    checkpoints = get_checkpoints_for_vehicle(vehicle_id)
    pertinent_keys = {cp['key']
                      for cp in checkpoints if cp.get('type') == 'status'}

    def get_val(key):
        if key not in pertinent_keys:
            return "Non pertinent"
        return form.get(key, "À vérifier")

    # 1. Map all standard status checkpoints
    for cp in ALL_POSSIBLE_CHECKPOINTS:
        key = cp['key']
        if cp.get('type') == 'status':
            column = CHECKPOINT_TO_MODEL_MAP.get(key, key)
            if hasattr(record, column):
                setattr(record, column, get_val(key))

    # 2. Handle Battery (Value type)
    battery_val = form.get("battery")
    if battery_val:
        try:
            val = float(battery_val)
            if is_checkout:
                record.charge_batterie_depart = val
            else:
                record.charge_batterie_retour = val
        except (ValueError, TypeError):
            pass

    # 3. Handle readiness state
    if is_checkout:
        record.vehicule_pret_depart = _is_ready(
            form, vehicle_id, is_checkout=True)
    else:
        record.vehicule_pret_retour = _is_ready(
            form, vehicle_id, is_checkout=False)

    record.observations = form.get("notes")


def _format_base_inspection_admin(c, vehicle_map, batch_configs=None):
    """
    Common formatter for CheckoutVehicle and CheckinVehicle.
    """
    is_checkout = isinstance(c, CheckoutVehicle)

    project_name = c.project.nom if c.project else "—"
    v_data = vehicle_map.get(c.vehicule_controle, {})
    vehicle_name = v_data.get("name", "—")
    unique_id = v_data.get("unique_id", "—")

    # Handle relation names: responsible_user vs responsible
    responsible = getattr(c, 'responsible_user', None) if is_checkout else getattr(
        c, 'responsible', None)
    controller_name = f"{responsible.firstname} {responsible.lastname}" if responsible else "—"

    status = c.etat_controle or "—"

    # Handle readiness field: vehicule_pret_depart vs vehicule_pret_retour
    ready_field = 'vehicule_pret_depart' if is_checkout else 'vehicule_pret_retour'
    ready = "Oui" if getattr(c, ready_field, False) else "Non"

    c_date = format_date_fr(str(c.date_controle)) if c.date_controle else "—"
    d_date = format_date_fr(str(c.project.date_depart)
                            ) if c.project and c.project.date_depart else "—"
    r_date = format_date_fr(str(c.project.date_retour)
                            ) if c.project and c.project.date_retour else "—"

    data = {
        "id": c.id,
        "inspection_id": c.numero_inspection or "—",
        "project": project_name,
        "departure_date": d_date,
        "return_date": r_date,
        "vehicle": {"fields": {"name": vehicle_name, "unique_id": unique_id}},
        "control_date": c_date,
        "status": status,
        "controller": {
            "id": c.user_id,
            "name": controller_name
        },
        "created_at": c.created_at.isoformat() if c.created_at else "",
        "ready": ready,
        "controller_id": c.user_id,
    }

    data["search_text"] = f"{data['inspection_id']} {project_name} {controller_name} {status}".lower(
    )
    data["check_items"] = get_checkpoints_for_vehicle(
        c.vehicule_controle, batch_configs=batch_configs)

    # Detail fields
    data["control_status"] = status

    # Handle battery: charge_batterie_depart vs charge_batterie_retour
    battery_field = 'charge_batterie_depart' if is_checkout else 'charge_batterie_retour'
    battery_val = getattr(c, battery_field, None)
    data["battery_charge"] = battery_val if battery_val is not None else None
    data["battery"] = str(battery_val) if battery_val is not None else ""

    # Map all checkpoints dynamically
    for cp in ALL_POSSIBLE_CHECKPOINTS:
        key = cp['key']
        if cp.get('type') == 'status':
            column = CHECKPOINT_TO_MODEL_MAP.get(key, key)
            data[key] = getattr(c, column, "—") or "—"

    data["interior_photos"] = _parse_photos_json(c.photos_interieur)
    data["exterior_photos"] = _parse_photos_json(c.photos_exterieur)
    data["notes"] = c.observations or ""

    if c.project:
        data["production"] = c.project.production.nom if c.project.production else "—"
        data["shoot_start"] = format_date_fr(
            str(c.project.date_debut_tournage)) if c.project.date_debut_tournage else "—"
        data["shoot_end"] = format_date_fr(
            str(c.project.date_fin_tournage)) if c.project.date_fin_tournage else "—"
        data["vehicle_id"] = c.vehicule_controle
        data["project_id"] = str(c.project.id)
        data["project_id_unique"] = c.project.project_id
        data["project_name"] = c.project.nom

        # Cache vehicle name in data for convenience
        data["vehicle_name"] = vehicle_name

    return data


def get_unified_form_context(mode="checkout"):
    """
    Unifies get_checkout_form_context and get_checkin_form_context.
    """
    projects = Project.query.options(joinedload(
        Project.production)).order_by(Project.nom).all()
    vehicles = get_vehicles()
    users = User.query.order_by(User.firstname).all()

    checkouts = CheckoutVehicle.query.all()
    checkins = CheckinVehicle.query.all()

    # Pre-calculate project names mapping
    project_names = {str(p.id): p.nom for p in projects}

    # Map for statuses: {vehicule_id: {project_id: status}}
    vehicle_checkout_statuses = {}
    for c in checkouts:
        if c.vehicule_controle and c.etat_controle and c.project_id:
            vid = c.vehicule_controle
            pid = str(c.project_id)
            if vid not in vehicle_checkout_statuses:
                vehicle_checkout_statuses[vid] = {}
            vehicle_checkout_statuses[vid][pid] = c.etat_controle

    vehicle_checkin_statuses = {}
    for c in checkins:
        if c.vehicule_controle and c.etat_controle and c.project_id:
            vid = c.vehicule_controle
            pid = str(c.project_id)
            if vid not in vehicle_checkin_statuses:
                vehicle_checkin_statuses[vid] = {}
            vehicle_checkin_statuses[vid][pid] = c.etat_controle

    # Specifically for checkout: blocking projects logic
    blocking_projects = {}
    if mode == "checkout":
        for vid, p_statuses in vehicle_checkout_statuses.items():
            for pid, status in p_statuses.items():
                if status in ["Signé", "Validé"]:
                    # Has it been checked in?
                    has_checkin = False
                    for ci in checkins:
                        if ci.vehicule_controle == vid and str(ci.project_id) == pid and ci.etat_controle in ["Signé", "Validé"]:
                            has_checkin = True
                            break
                    if not has_checkin:
                        blocking_projects[vid] = project_names.get(
                            pid, "Projet inconnu")

    # Enrich vehicle data
    for v in vehicles:
        vid = v["id"]
        f = v.setdefault("fields", {})
        f["_checkout_statuses"] = vehicle_checkout_statuses.get(vid, {})
        f["_checkin_statuses"] = vehicle_checkin_statuses.get(vid, {})

        if mode == "checkout" and vid in blocking_projects:
            f["_blocked_by"] = blocking_projects[vid]

    # Format projects
    projects_formatted = []
    for p in projects:
        veh_ids = [v.strip() for v in (
            p.vehicules_a_controler or "").split(",") if v.strip()]
        v_name = "—"
        if veh_ids:
            # Simple match for the first vehicle name to show in select
            for v in vehicles:
                if v["id"] == veh_ids[0]:
                    v_name = v.get("fields", {}).get("name", "—")
                    break

        projects_formatted.append({
            "id": str(p.id),
            "fields": {
                "Nom": p.nom,
                "_production_name": p.production.nom if p.production else "—",
                "Date de départ": format_date_fr(str(p.date_depart)) if p.date_depart else "—",
                "Date de début de tournage": format_date_fr(str(p.date_debut_tournage)) if p.date_debut_tournage else "—",
                "Date de fin de tournage": format_date_fr(str(p.date_fin_tournage)) if p.date_fin_tournage else "—",
                "Véhicules à contrôler": veh_ids,
                "_vehicle_name": v_name
            }
        })

    users_formatted = [{"id": str(u.id), "fields": {
        "firstname": u.firstname, "lastname": u.lastname}} for u in users]

    # Checkpoints mapping (for frontend filtering)
    checkpoints_mapping = {v["id"]: get_checkpoints_for_vehicle(
        v["id"], vehicle_name=v.get("fields", {}).get("name")) for v in vehicles}

    return {
        "projects": projects_formatted,
        "vehicles": vehicles,
        "users": users_formatted,
        "checkpoints": ALL_POSSIBLE_CHECKPOINTS,
        "checkpoints_config_json": json.dumps(checkpoints_mapping),
        "default_checkpoints_json": json.dumps(BASE_CHECKPOINTS),
    }
