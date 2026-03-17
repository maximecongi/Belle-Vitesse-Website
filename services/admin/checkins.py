from utils.checkpoints import get_checkpoints_for_vehicle, BASE_CHECKPOINTS, ALL_POSSIBLE_CHECKPOINTS
from services.admin.utils import _parse_photos_json, _delete_inspection_files, _is_ready
from utils.n8n import trigger_n8n_webhook
import json
import logging
import os
from pathlib import Path
from datetime import date

from flask import current_app, url_for
from werkzeug.utils import secure_filename

from sqlalchemy.orm import joinedload
from models import db, CheckoutVehicle, CheckinVehicle, Project, User
from utils.database import get_vehicles
from utils.formatting import format_date_fr

logger = logging.getLogger(__name__)


# ── Checkins ────────────────────────────────────────────────────


def _format_checkin_admin(c: CheckinVehicle, vehicle_map, batch_configs=None):
    project_name = c.project.nom if c.project else "—"
    v_data = vehicle_map.get(c.vehicule_controle, {})
    vehicle_name = v_data.get("name", "—")
    unique_id = v_data.get("unique_id", "—")
    controller_name = f"{c.responsible.firstname} {c.responsible.lastname}" if c.responsible else "—"
    status = c.etat_controle or "—"
    ready = "Oui" if c.vehicule_pret_retour else "Non"
    c_date = format_date_fr(str(c.date_controle)) if c.date_controle else "—"
    d_date = format_date_fr(str(c.project.date_depart)
                            ) if c.project and c.project.date_depart else "—"
    r_date = format_date_fr(str(c.project.date_retour)
                            ) if c.project and c.project.date_retour else "—"

    data = {
        "id": c.id,  # DB ID
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

    # Detail fields (for checkin_detail.html)
    data["control_status"] = status
    data["battery_charge"] = c.charge_batterie_retour if c.charge_batterie_retour is not None else None
    data["battery"] = str(
        c.charge_batterie_retour) if c.charge_batterie_retour is not None else ""
    data["tires"] = c.etat_pneus or "—"
    data["spare_tire"] = c.roue_secours or "—"
    data["oil"] = c.niveau_huile or "—"
    data["coolant"] = c.niveau_liquide_refroidissement or "—"
    data["brakes"] = c.etat_freins or "—"
    data["lights"] = c.etat_eclairage_exterieur or "—"
    data["engine_start"] = c.demarrage_moteur or "—"
    data["wipers"] = c.etat_essuie_glaces or "—"
    data["horn"] = c.etat_klaxon or "—"
    data["safety_triangle"] = c.presence_triangle_gilet or "—"
    data["fire_extinguisher"] = c.presence_extincteur or "—"

    # New checkpoints
    data["fonctionnement_vitesses"] = c.fonctionnement_vitesses or "—"
    data["moteur_assistance"] = c.moteur_assistance or "—"
    data["test_roulage"] = c.test_roulage or "—"
    data["serrage_roues"] = c.serrage_roues or "—"
    data["tension_chaine"] = c.tension_chaine or "—"
    data["serrage_arceau"] = c.serrage_arceau or "—"
    data["serrage_plaques_sieges"] = c.serrage_plaques_sieges or "—"
    data["ceinture_securite"] = c.ceinture_securite or "—"
    data["casques_passagers"] = c.casques_passagers or "—"
    data["protections_pilote"] = c.protections_pilote or "—"
    data["systeme_communication"] = c.systeme_communication or "—"
    data["mallette_accessoires"] = c.mallette_accessoires or "—"

    data["interior_photos"] = _parse_photos_json(c.photos_interieur)
    data["exterior_photos"] = _parse_photos_json(c.photos_exterieur)
    data["notes"] = c.observations or ""

    # Used for PDF regeneration
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

        # Get vehicle name for display
        from utils.database import get_vehicles
        vehicles = get_vehicles()
        v_name = "—"
        for v in vehicles:
            if v['id'] == c.vehicule_controle:
                v_name = v['fields'].get('name', '—')
                break
        data["vehicle_name"] = v_name

    return data


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

    checkins = [_format_checkin_admin(
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
    data = _format_checkin_admin(record, vehicle_map)

    # If signed, load the stable snapshot to get the real PDF URL and hash
    if data.get("control_status") == "Signé":
        from models import CheckinSignedDocument
        from services.checkin import generate_pdf_access_token
        signed_doc = db.session.get(
            CheckinSignedDocument, data["inspection_id"])
        if signed_doc and signed_doc.pdf_url:
            data["hash"] = signed_doc.hash
            pdf_url = signed_doc.pdf_url
            path_part = pdf_url.split("/document/")[-1].split("?")[0]
            token = generate_pdf_access_token(path_part)
            data["pdf_url"] = url_for(
                "download_checkin_document", filepath=path_part, t=token)

    return data


def get_checkin_form_context():
    """
    Get the context needed for the checkin form (projects + vehicles selects).
    """
    projects = Project.query.options(joinedload(
        Project.production)).order_by(Project.nom).all()
    vehicles = get_vehicles()
    users = User.query.order_by(User.firstname).all()

    checkins = CheckinVehicle.query.all()
    checkouts = CheckoutVehicle.query.all()

    # Map for checkin status: {vehicule_id: {project_id: status}}
    vehicle_checkin_statuses = {}
    for c in checkins:
        if c.vehicule_controle and c.etat_controle and c.project_id:
            vid = c.vehicule_controle
            if vid not in vehicle_checkin_statuses:
                vehicle_checkin_statuses[vid] = {}
            # We keep the latest one (overwriting)
            vehicle_checkin_statuses[vid][str(c.project_id)] = c.etat_controle

    # Map for latest checkout status: {vehicule_id: {project_id: status}}
    vehicle_checkout_statuses = {}
    for c in checkouts:
        if c.vehicule_controle and c.etat_controle and c.project_id:
            vid = c.vehicule_controle
            if vid not in vehicle_checkout_statuses:
                vehicle_checkout_statuses[vid] = {}
            # We keep the latest one (overwriting)
            vehicle_checkout_statuses[vid][str(c.project_id)] = c.etat_controle

    for v in vehicles:
        vid = v["id"]
        v.setdefault("fields", {})[
            "_checkin_statuses"] = vehicle_checkin_statuses.get(vid, {})
        v.setdefault("fields", {})[
            "_checkout_statuses"] = vehicle_checkout_statuses.get(vid, {})

    projects_formatted = []
    for p in projects:
        veh_ids = [v.strip() for v in (
            p.vehicules_a_controler or "").split(",") if v.strip()]
        v_name = ""
        if veh_ids:
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

    users_formatted = []
    for u in users:
        users_formatted.append({
            "id": str(u.id),
            "fields": {"firstname": u.firstname, "lastname": u.lastname}
        })

    # Build mapping for frontend filtering
    checkpoints_mapping = {}
    for v in vehicles:
        vid = v["id"]
        vname = v.get("fields", {}).get("name")
        # Use ID as primary key for mapping, get config using the same ID or name fallback
        checkpoints_mapping[vid] = get_checkpoints_for_vehicle(
            vid, vehicle_name=vname)

    return {
        "projects": projects_formatted,
        "vehicles": vehicles,
        "users": users_formatted,
        "checkpoints": ALL_POSSIBLE_CHECKPOINTS,
        "checkpoints_config_json": json.dumps(checkpoints_mapping),
        "default_checkpoints_json": json.dumps(BASE_CHECKPOINTS),
    }


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
        charge_batterie_retour=float(
            form.get("battery")) if form.get("battery") else None,
        etat_pneus=get_val("tires"),
        roue_secours=get_val("spare_tire"),
        etat_freins=get_val("brakes"),
        etat_eclairage_exterieur=get_val("lights"),
        niveau_huile=get_val("oil"),
        niveau_liquide_refroidissement=get_val("coolant"),
        demarrage_moteur=get_val("engine_start"),
        etat_essuie_glaces=get_val("wipers"),
        etat_klaxon=get_val("horn"),
        presence_triangle_gilet=get_val("safety_triangle"),
        presence_extincteur=get_val("fire_extinguisher"),
        fonctionnement_vitesses=get_val("fonctionnement_vitesses"),
        moteur_assistance=get_val("moteur_assistance"),
        test_roulage=get_val("test_roulage"),
        serrage_roues=get_val("serrage_roues"),
        tension_chaine=get_val("tension_chaine"),
        serrage_arceau=get_val("serrage_arceau"),
        serrage_plaques_sieges=get_val("serrage_plaques_sieges"),
        ceinture_securite=get_val("ceinture_securite"),
        casques_passagers=get_val("casques_passagers"),
        protections_pilote=get_val("protections_pilote"),
        systeme_communication=get_val("systeme_communication"),
        mallette_accessoires=get_val("mallette_accessoires"),
        observations=form.get("notes"),
    )

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

    record.vehicule_pret_retour = _is_ready(
        form, record.vehicule_controle, is_checkout=False)
    db.session.add(record)
    db.session.commit()

    if files:
        _upload_checkin_photos_local(record, files)

    return True


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

    # Determine pertinent status fields for this vehicle
    vehicle_id = record.vehicule_controle
    from utils.checkpoints import get_checkpoints_for_vehicle
    checkpoints = get_checkpoints_for_vehicle(vehicle_id)
    pertinent_keys = {cp['key']
                      for cp in checkpoints if cp.get('type') == 'status'}

    def get_val(key):
        if key not in pertinent_keys:
            return "Non pertinent"
        return form.get(key, "À vérifier")

    record.etat_pneus = get_val("tires")
    record.roue_secours = get_val("spare_tire")
    record.etat_freins = get_val("brakes")
    record.etat_eclairage_exterieur = get_val("lights")
    record.niveau_huile = get_val("oil")
    record.niveau_liquide_refroidissement = get_val("coolant")
    record.demarrage_moteur = get_val("engine_start")
    record.etat_essuie_glaces = get_val("wipers")
    record.etat_klaxon = get_val("horn")
    record.presence_triangle_gilet = get_val("safety_triangle")
    record.presence_extincteur = get_val("fire_extinguisher")
    record.fonctionnement_vitesses = get_val("fonctionnement_vitesses")
    record.moteur_assistance = get_val("moteur_assistance")
    record.test_roulage = get_val("test_roulage")
    record.serrage_roues = get_val("serrage_roues")
    record.tension_chaine = get_val("tension_chaine")
    record.serrage_arceau = get_val("serrage_arceau")
    record.serrage_plaques_sieges = get_val("serrage_plaques_sieges")
    record.ceinture_securite = get_val("ceinture_securite")
    record.casques_passagers = get_val("casques_passagers")
    record.protections_pilote = get_val("protections_pilote")
    record.systeme_communication = get_val("systeme_communication")
    record.mallette_accessoires = get_val("mallette_accessoires")
    record.observations = form.get("notes")
    record.vehicule_pret_retour = _is_ready(
        form, record.vehicule_controle, is_checkout=False)

    db.session.commit()

    if files:
        _upload_checkin_photos_local(record, files)

    return True


def delete_checkin(record_id):
    """Delete a checkin record and its associated files."""
    record = db.session.get(CheckinVehicle, record_id)
    if record:
        # Trigger n8n delete before database deletion
        webhook_url = os.getenv("N8N_WEBHOOK_CHECKIN_SIGN")
        if webhook_url:
            trigger_n8n_webhook(webhook_url, method="DELETE",
                                inspection_id=record.numero_inspection,
                                project_id=record.project.project_id if record.project else None)

        _delete_inspection_files(record)
        db.session.delete(record)
        db.session.commit()
