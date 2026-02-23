"""
Admin service layer — business logic for admin CRUD and API endpoints.

Every function here is pure business logic: no Flask request/response handling.
Routes call these functions and handle HTTP concerns (flash, redirect, render).
"""

from flask import current_app
from werkzeug.utils import secure_filename
from models import CheckoutVehicle, CheckinVehicle
import json
import logging
import os
from pathlib import Path
from collections import defaultdict
from datetime import date

from flask import url_for

from utils.airtable import get_vehicles
from utils.formatting import format_date_fr
from models import db, Production, Project, User

logger = logging.getLogger(__name__)


# ── Checkouts ────────────────────────────────────────────────────


def _parse_photos_json(text):
    if not text:
        return []
    try:
        paths = json.loads(text)
        return [{"url": f"/files/{p}", "label": p.split("/")[-1]} for p in paths]
    except Exception:
        return [{"url": f"/files/{text}", "label": "File"}]


def _delete_inspection_files(record):
    """
    Delete all physical files associated with a checkout or checkin record.
    Includes odometer photos, interior/exterior photos, and the signed PDF.
    """
    private_folder = current_app.config.get("PRIVATE_FOLDER")
    if not private_folder:
        return

    # 1. Photos
    photo_fields = [record.photo_compteur,
                    record.photos_interieur, record.photos_exterieur]
    for field in photo_fields:
        if not field:
            continue
        try:
            # Field can be a JSON array or a single filename
            paths = json.loads(field) if isinstance(
                field, str) and field.startswith('[') else [field]
            for p in paths:
                # Sanitize p (it might be a full dict if not careful, but usually it's a string)
                if not isinstance(p, str):
                    continue
                full_path = Path(private_folder) / "uploads" / p
                if full_path.exists():
                    try:
                        os.remove(full_path)
                        logger.info(f"🗑️ Photo supprimée : {full_path}")
                    except Exception as e:
                        logger.error(
                            f"❌ Échec de la suppression de la photo {full_path}: {e}")
        except Exception as e:
            logger.warning(
                f"⚠️ Erreur lors du parsing des photos pour suppression: {e}")

    # 2. Signed PDF
    if record.pdf_scelle:
        # pdf_scelle is usually a URL: http://.../checkout/document/filename.pdf
        filename = record.pdf_scelle.split("/")[-1]
        if "?" in filename:
            filename = filename.split("?")[0]

        # Determine subfolder based on record type
        subfolder = "checkout_pdfs" if isinstance(
            record, CheckoutVehicle) else "checkin_pdfs"
        pdf_path = Path(private_folder) / subfolder / filename
        if pdf_path.exists():
            try:
                os.remove(pdf_path)
                logger.info(f"🗑️ PDF supprimé : {pdf_path}")
            except Exception as e:
                logger.error(
                    f"❌ Échec de la suppression du PDF {pdf_path}: {e}")


def _is_ready(form):
    """
    Calculate if the vehicle is ready based on inspection fields.
    Returns True if all critical fields are 'OK' or 'Non pertinent'.
    """
    checks = [
        "tires", "spare_tire", "brakes", "lights", "oil", "coolant",
        "engine_start", "wipers", "horn", "safety_triangle", "fire_extinguisher"
    ]
    for key in checks:
        val = form.get(key)
        if val not in ["OK", "Non pertinent"]:
            return False
    return True


def _format_checkout_admin(c: CheckoutVehicle, vehicle_names):
    project_name = c.project.nom if c.project else "—"
    vehicle_name = vehicle_names.get(c.vehicule_controle, "—")
    controller_name = f"{c.responsible_user.firstname} {c.responsible_user.lastname}" if c.responsible_user else "—"
    status = c.etat_controle or "—"
    ready = "Oui" if c.vehicule_pret_depart else "Non"
    c_date = format_date_fr(str(c.date_controle)) if c.date_controle else "—"
    d_date = format_date_fr(str(c.project.date_depart)
                            ) if c.project and c.project.date_depart else "—"

    data = {
        "id": c.id,  # DB ID
        "inspection_id": c.numero_inspection or "—",
        "project": project_name,
        "departure_date": d_date,
        "vehicle": {"fields": {"name": vehicle_name}},
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

    # Detail fields (for checkout_detail.html)
    data["control_status"] = status
    data["km"] = str(
        c.kilometrage_depart) if c.kilometrage_depart is not None else ""
    data["battery"] = str(
        c.charge_batterie_depart) if c.charge_batterie_depart is not None else ""
    data["odometer_photos"] = _parse_photos_json(c.photo_compteur)
    data["odometer_photo"] = data["odometer_photos"][0]["url"] if data["odometer_photos"] else None
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
        data["return_date"] = format_date_fr(
            str(c.project.date_retour)) if c.project.date_retour else "—"
        data["vehicle_id"] = c.vehicule_controle
        data["project_id"] = str(c.project.id)

    return data


def list_checkouts():
    """
    Fetch all checkout records, compute stats, and format for listing.
    """
    records = CheckoutVehicle.query.order_by(
        CheckoutVehicle.created_at.desc()).all()
    vehicles = get_vehicles()
    vehicle_names = {v["id"]: v.get("fields", {}).get(
        "name", "—") for v in vehicles}

    total_count = len(records)
    signed_count = sum(1 for r in records if r.etat_controle == "Signé")
    pending_count = sum(1 for r in records if r.etat_controle == "Terminé")

    stats = {
        "total_checkouts": total_count,
        "signed_checkouts": signed_count,
        "pending_checkouts": pending_count,
    }

    checkouts = [_format_checkout_admin(r, vehicle_names) for r in records]
    return {"checkouts": checkouts, "stats": stats}


def get_checkout_detail(record_id):
    """
    Fetch and format a single checkout record.
    """
    record = db.session.get(CheckoutVehicle, record_id)
    if not record:
        return None

    vehicles = get_vehicles()
    vehicle_names = {v["id"]: v.get("fields", {}).get(
        "name", "—") for v in vehicles}
    data = _format_checkout_admin(record, vehicle_names)

    # If signed, load the stable snapshot to get the real PDF URL and hash
    if data.get("control_status") == "Signé":
        from models import CheckoutSignedDocument
        from services.checkout import generate_pdf_access_token
        signed_doc = db.session.get(
            CheckoutSignedDocument, data["inspection_id"])
        if signed_doc and signed_doc.pdf_url:
            data["hash"] = signed_doc.hash
            pdf_url = signed_doc.pdf_url
            filename = pdf_url.split("/")[-1]
            token = generate_pdf_access_token(filename)
            data["pdf_url"] = url_for(
                "download_checkout_document", filename=filename, t=token)

    return data


def get_checkout_form_context():
    """
    Get the context needed for the checkout form (projects + vehicles selects).
    Resolves linked production record IDs to their display names.

    Returns:
        dict with 'projects' and 'vehicles' keys.
    """
    projects = Project.query.order_by(Project.nom).all()
    vehicles = get_vehicles()
    users = User.query.order_by(User.firstname).all()

    checkouts = CheckoutVehicle.query.all()
    vehicle_status = {}
    for c in checkouts:
        if c.vehicule_controle and c.etat_controle:
            vehicle_status[c.vehicule_controle] = c.etat_controle

    for v in vehicles:
        if v["id"] in vehicle_status:
            v.setdefault("fields", {})[
                "_checkout_status"] = vehicle_status[v["id"]]

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

    return {
        "projects": projects_formatted,
        "vehicles": vehicles,
        "users": users_formatted,
    }


def _upload_checkout_photos_local(record: CheckoutVehicle, files):
    if not files:
        return

    upload_dir = current_app.config["PRIVATE_FOLDER"] / \
        "uploads" / "checkouts" / record.numero_inspection
    upload_dir.mkdir(parents=True, exist_ok=True)

    photo_fields = {
        "odometer_photos": "photo_compteur",
        "exterior_photos": "photos_exterieur",
        "interior_photos": "photos_interieur",
    }

    for form_field, model_attr in photo_fields.items():
        uploaded = files.getlist(form_field)
        paths = []
        for f in uploaded:
            if f and f.filename:
                filename = secure_filename(f.filename)
                file_path = upload_dir / filename
                f.save(file_path)
                rel_path = f"checkouts/{record.numero_inspection}/{filename}"
                paths.append(rel_path)

        if paths:
            setattr(record, model_attr, json.dumps(paths))

    db.session.commit()


def create_checkout(form, files=None):
    """Create a new checkout record in the database."""
    pid = form.get("project_id")
    uid = form.get("controller_id")
    # Safety: ensure uid is an integer (legacy sessions might send 'rec...')
    try:
        user_id = int(uid) if uid and uid != "None" else None
    except (ValueError, TypeError):
        current_app.logger.warning(
            f"⚠️ Invalid controller_id detected: {uid}. Record will be created without user.")
        user_id = None

    record = CheckoutVehicle(
        etat_controle="En cours",
        date_controle=date.today(),
        project_id=int(pid) if pid and pid != "None" else None,
        user_id=user_id,
        vehicule_controle=form.get("vehicle_id") if form.get(
            "vehicle_id") != "None" else None,
        kilometrage_depart=float(form.get("km")) if form.get("km") else None,
        charge_batterie_depart=float(
            form.get("battery")) if form.get("battery") else None,
        etat_pneus=form.get("tires"),
        roue_secours=form.get("spare_tire"),
        etat_freins=form.get("brakes"),
        etat_eclairage_exterieur=form.get("lights"),
        niveau_huile=form.get("oil"),
        niveau_liquide_refroidissement=form.get("coolant"),
        demarrage_moteur=form.get("engine_start"),
        etat_essuie_glaces=form.get("wipers"),
        etat_klaxon=form.get("horn"),
        presence_triangle_gilet=form.get("safety_triangle"),
        presence_extincteur=form.get("fire_extinguisher"),
        observations=form.get("notes"),
    )
    record.vehicule_pret_depart = _is_ready(form)
    db.session.add(record)
    db.session.commit()

    if files:
        _upload_checkout_photos_local(record, files)

    return True


def update_checkout(record_id, form, files=None):
    """Update an existing checkout record in the database."""
    record = db.session.get(CheckoutVehicle, record_id)
    if not record:
        return False

    pid = form.get("project_id")
    uid = form.get("controller_id")

    record.project_id = int(pid) if pid and pid != "None" else None
    record.user_id = int(uid) if uid and uid != "None" else None
    record.vehicule_controle = form.get("vehicle_id") if form.get(
        "vehicle_id") != "None" else None
    if form.get("km"):
        record.kilometrage_depart = float(form.get("km"))
    if form.get("battery"):
        record.charge_batterie_depart = float(form.get("battery"))

    record.etat_pneus = form.get("tires")
    record.roue_secours = form.get("spare_tire")
    record.etat_freins = form.get("brakes")
    record.etat_eclairage_exterieur = form.get("lights")
    record.niveau_huile = form.get("oil")
    record.niveau_liquide_refroidissement = form.get("coolant")
    record.demarrage_moteur = form.get("engine_start")
    record.etat_essuie_glaces = form.get("wipers")
    record.etat_klaxon = form.get("horn")
    record.presence_triangle_gilet = form.get("safety_triangle")
    record.presence_extincteur = form.get("fire_extinguisher")
    record.observations = form.get("notes")
    record.vehicule_pret_depart = _is_ready(form)

    db.session.commit()

    if files:
        _upload_checkout_photos_local(record, files)

    return True


def delete_checkout(record_id):
    """Delete a checkout record and its associated files."""
    record = db.session.get(CheckoutVehicle, record_id)
    if record:
        _delete_inspection_files(record)
        db.session.delete(record)
        db.session.commit()


# ── Checkins ────────────────────────────────────────────────────


def _format_checkin_admin(c: CheckinVehicle, vehicle_names):
    project_name = c.project.nom if c.project else "—"
    vehicle_name = vehicle_names.get(c.vehicule_controle, "—")
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
        "vehicle": {"fields": {"name": vehicle_name}},
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

    # Detail fields (for checkin_detail.html)
    data["control_status"] = status
    data["km"] = str(
        c.kilometrage_retour) if c.kilometrage_retour is not None else ""
    data["battery"] = str(
        c.charge_batterie_retour) if c.charge_batterie_retour is not None else ""
    data["odometer_photos"] = _parse_photos_json(c.photo_compteur)
    data["odometer_photo"] = data["odometer_photos"][0]["url"] if data["odometer_photos"] else None
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

    return data


def list_checkins():
    """
    Fetch all checkin records, compute stats, and format for listing.
    """
    records = CheckinVehicle.query.order_by(
        CheckinVehicle.created_at.desc()).all()
    vehicles = get_vehicles()
    vehicle_names = {v["id"]: v.get("fields", {}).get(
        "name", "—") for v in vehicles}

    total_count = len(records)
    signed_count = sum(1 for r in records if r.etat_controle == "Signé")
    pending_count = sum(1 for r in records if r.etat_controle == "Terminé")

    stats = {
        "total_checkins": total_count,
        "signed_checkins": signed_count,
        "pending_checkins": pending_count,
    }

    checkins = [_format_checkin_admin(r, vehicle_names) for r in records]
    return {"checkins": checkins, "stats": stats}


def get_checkin_detail(record_id):
    """
    Fetch and format a single checkin record.
    """
    record = db.session.get(CheckinVehicle, record_id)
    if not record:
        return None

    vehicles = get_vehicles()
    vehicle_names = {v["id"]: v.get("fields", {}).get(
        "name", "—") for v in vehicles}
    data = _format_checkin_admin(record, vehicle_names)

    # If signed, load the stable snapshot to get the real PDF URL and hash
    if data.get("control_status") == "Signé":
        from models import CheckinSignedDocument
        from services.checkin import generate_pdf_access_token
        signed_doc = db.session.get(
            CheckinSignedDocument, data["inspection_id"])
        if signed_doc and signed_doc.pdf_url:
            data["hash"] = signed_doc.hash
            pdf_url = signed_doc.pdf_url
            filename = pdf_url.split("/")[-1]
            token = generate_pdf_access_token(filename)
            data["pdf_url"] = url_for(
                "download_checkin_document", filename=filename, t=token)

    return data


def get_checkin_form_context():
    """
    Get the context needed for the checkin form (projects + vehicles selects).
    """
    projects = Project.query.order_by(Project.nom).all()
    vehicles = get_vehicles()
    users = User.query.order_by(User.firstname).all()

    checkins = CheckinVehicle.query.all()
    vehicle_status = {}
    for c in checkins:
        if c.vehicule_controle and c.etat_controle:
            vehicle_status[c.vehicule_controle] = c.etat_controle

    for v in vehicles:
        if v["id"] in vehicle_status:
            v.setdefault("fields", {})[
                "_checkin_status"] = vehicle_status[v["id"]]

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

    return {
        "projects": projects_formatted,
        "vehicles": vehicles,
        "users": users_formatted,
    }


def _upload_checkin_photos_local(record: CheckinVehicle, files):
    if not files:
        return

    upload_dir = current_app.config["PRIVATE_FOLDER"] / \
        "uploads" / "checkins" / record.numero_inspection
    upload_dir.mkdir(parents=True, exist_ok=True)

    photo_fields = {
        "odometer_photos": "photo_compteur",
        "exterior_photos": "photos_exterieur",
        "interior_photos": "photos_interieur",
    }

    for form_field, model_attr in photo_fields.items():
        uploaded = files.getlist(form_field)
        paths = []
        for f in uploaded:
            if f and f.filename:
                filename = secure_filename(f.filename)
                file_path = upload_dir / filename
                f.save(file_path)
                rel_path = f"checkins/{record.numero_inspection}/{filename}"
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

    record = CheckinVehicle(
        etat_controle="En cours",
        date_controle=date.today(),
        project_id=int(pid) if pid and pid != "None" else None,
        user_id=user_id,
        vehicule_controle=form.get("vehicle_id") if form.get(
            "vehicle_id") != "None" else None,
        kilometrage_retour=float(form.get("km")) if form.get("km") else None,
        charge_batterie_retour=float(
            form.get("battery")) if form.get("battery") else None,
        etat_pneus=form.get("tires"),
        roue_secours=form.get("spare_tire"),
        etat_freins=form.get("brakes"),
        etat_eclairage_exterieur=form.get("lights"),
        niveau_huile=form.get("oil"),
        niveau_liquide_refroidissement=form.get("coolant"),
        demarrage_moteur=form.get("engine_start"),
        etat_essuie_glaces=form.get("wipers"),
        etat_klaxon=form.get("horn"),
        presence_triangle_gilet=form.get("safety_triangle"),
        presence_extincteur=form.get("fire_extinguisher"),
        observations=form.get("notes"),
    )
    record.vehicule_pret_retour = _is_ready(form)
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
    if form.get("km"):
        record.kilometrage_retour = float(form.get("km"))
    if form.get("battery"):
        record.charge_batterie_retour = float(form.get("battery"))

    record.etat_pneus = form.get("tires")
    record.roue_secours = form.get("spare_tire")
    record.etat_freins = form.get("brakes")
    record.etat_eclairage_exterieur = form.get("lights")
    record.niveau_huile = form.get("oil")
    record.niveau_liquide_refroidissement = form.get("coolant")
    record.demarrage_moteur = form.get("engine_start")
    record.etat_essuie_glaces = form.get("wipers")
    record.etat_klaxon = form.get("horn")
    record.presence_triangle_gilet = form.get("safety_triangle")
    record.presence_extincteur = form.get("fire_extinguisher")
    record.observations = form.get("notes")
    record.vehicule_pret_retour = _is_ready(form)

    db.session.commit()

    if files:
        _upload_checkin_photos_local(record, files)

    return True


def delete_checkin(record_id):
    """Delete a checkin record and its associated files."""
    record = db.session.get(CheckinVehicle, record_id)
    if record:
        _delete_inspection_files(record)
        db.session.delete(record)
        db.session.commit()


# ── Projects ─────────────────────────────────────────────────────


def list_projects():
    """
    Fetch all project records and format for listing.
    Cross-references checkout records to determine each vehicle's control status.
    """
    projects = Project.query.order_by(Project.nom.desc()).all()
    vehicles = get_vehicles()
    vehicle_names = {v["id"]: v.get("fields", {}).get(
        "name", "—") for v in vehicles}

    result = []
    for p in projects:
        # Get checkout and checkin statuses for vehicles in this project
        checkout_map = {c.vehicule_controle: c for c in p.checkout_vehicles}
        checkin_map = {c.vehicule_controle: c for c in p.checkin_vehicles}

        veh_ids = [v.strip() for v in (
            p.vehicules_a_controler or "").split(",") if v.strip()]
        veh_list = []
        for vid in veh_ids:
            c_out = checkout_map.get(vid)
            c_in = checkin_map.get(vid)

            veh_list.append({
                "id": vid,
                "name": vehicle_names.get(vid, "—"),
                "checkout_status": c_out.etat_controle if c_out else "",
                "checkout_id": c_out.id if c_out else "",
                "checkout_ready": "Oui" if (c_out and c_out.vehicule_pret_depart) else ("Non" if c_out else "—"),
                "checkin_status": c_in.etat_controle if c_in else "",
                "checkin_id": c_in.id if c_in else "",
                "checkin_ready": "Oui" if (c_in and c_in.vehicule_pret_retour) else ("Non" if c_in else "—"),
            })

        result.append({
            "id": p.id,
            "name": p.nom,
            "production": p.production.nom if p.production else "—",
            "departure_date": format_date_fr(str(p.date_depart)) if p.date_depart else "—",
            "raw_departure_date": str(p.date_depart) if p.date_depart else "",
            "shoot_start": format_date_fr(str(p.date_debut_tournage)) if p.date_debut_tournage else "—",
            "shoot_end": format_date_fr(str(p.date_fin_tournage)) if p.date_fin_tournage else "—",
            "return_date": format_date_fr(str(p.date_retour)) if p.date_retour else "—",
            "raw_return_date": str(p.date_retour) if p.date_retour else "",
            "raw_checkin_date": str(p.date_retour) if p.date_retour else "",
            "vehicles": veh_list,
        })
    return result


def get_project_form_context():
    """
    Get context for project form (productions + vehicles selects).
    """
    prods = Production.query.order_by(Production.nom).all()
    # Format productions exactly as the template expects: {"id":..., "fields": {"Nom":...}}
    productions_formatted = [
        {"id": str(p.id), "fields": {"Nom": p.nom}} for p in prods]

    return {
        "productions": productions_formatted,
        "vehicles": get_vehicles(),
    }


def _parse_date(d):
    return d if d else None


def create_project(form):
    """Create a new project record in the database."""
    veh_ids = form.getlist("vehicle_ids") if hasattr(form, 'getlist') else []
    project = Project(
        nom=form.get("name"),
        production_id=form.get("production_id") if form.get(
            "production_id") else None,
        date_depart=_parse_date(form.get("departure_date")),
        date_debut_tournage=_parse_date(form.get("shoot_start")),
        date_fin_tournage=_parse_date(form.get("shoot_end")),
        date_retour=_parse_date(form.get("return_date")),
        vehicules_a_controler=",".join(veh_ids)
    )
    db.session.add(project)
    db.session.commit()
    return True


def update_project(record_id, form):
    """Update an existing project record in the database."""
    project = db.session.get(Project, record_id)
    if not project:
        return False

    veh_ids = form.getlist("vehicle_ids") if hasattr(form, 'getlist') else []
    project.nom = form.get("name")
    project.production_id = form.get(
        "production_id") if form.get("production_id") else None
    project.date_depart = _parse_date(form.get("departure_date"))
    project.date_debut_tournage = _parse_date(form.get("shoot_start"))
    project.date_fin_tournage = _parse_date(form.get("shoot_end"))
    project.date_retour = _parse_date(form.get("return_date"))
    project.vehicules_a_controler = ",".join(veh_ids)

    db.session.commit()
    return True


def get_project_for_edit(record_id):
    """
    Fetch a project record and format for editing.
    """
    p = db.session.get(Project, record_id)
    if not p:
        return None

    veh_ids = [v.strip() for v in (p.vehicules_a_controler or "").split(
        ",")] if p.vehicules_a_controler else []

    return {
        "name": p.nom,
        "departure_date_raw": str(p.date_depart) if p.date_depart else "",
        "shoot_start_raw": str(p.date_debut_tournage) if p.date_debut_tournage else "",
        "shoot_end_raw": str(p.date_fin_tournage) if p.date_fin_tournage else "",
        "return_date_raw": str(p.date_retour) if p.date_retour else "",
        "production_id": str(p.production_id) if p.production_id else "",
        "vehicle_ids": veh_ids,
    }


def delete_project(record_id):
    """Delete a project record from the database."""
    p = db.session.get(Project, record_id)
    if p:
        db.session.delete(p)
        db.session.commit()


# ── Productions ──────────────────────────────────────────────────


def list_productions():
    """
    Fetch all production records and format for listing.

    Returns:
        list of production dicts.
    """
    records = Production.query.order_by(Production.nom).all()
    productions = []
    for r in records:
        productions.append({
            "id": r.id,
            "name": r.nom,
            "address": r.adresse or "—",
            "email": r.mail or "—",
            "phone": r.phone or "—",
        })
    return productions


def create_production(form):
    """Create a new production record in the database."""
    prod = Production(
        nom=form.get("name", ""),
        adresse=form.get("address", ""),
        mail=form.get("email", ""),
        phone=form.get("phone", "")
    )
    db.session.add(prod)
    db.session.commit()
    return True


def update_production(record_id, form):
    """Update an existing production record in the database."""
    prod = db.session.get(Production, record_id)
    if not prod:
        return False

    prod.nom = form.get("name", "")
    prod.adresse = form.get("address", "")
    prod.mail = form.get("email", "")
    prod.phone = form.get("phone", "")

    db.session.commit()
    return True


def get_production_for_edit(record_id):
    """
    Fetch a production record and format for editing.

    Returns:
        dict with form-ready keys, or None if not found.
    """
    prod = db.session.get(Production, record_id)
    if not prod:
        return None

    return {
        "name": prod.nom,
        "address": prod.adresse or "",
        "email": prod.mail or "",
        "phone": prod.phone or "",
    }


def delete_production(record_id):
    """Delete a production record from the database."""
    prod = db.session.get(Production, record_id)
    if prod:
        db.session.delete(prod)
        db.session.commit()


# ── Calendar ─────────────────────────────────────────────────────


def get_calendar_events():
    records = Project.query.all()
    events = []
    colors = [
        "#618b4a", "#5299d3", "#f59e0b", "#e05c5c", "#8b5cf6",
        "#06b6d4", "#f97316", "#ec4899", "#14b8a6", "#a855f7",
    ]

    for i, r in enumerate(records):
        name = r.nom or "Sans nom"
        color = colors[i % len(colors)]

        if r.date_depart:
            events.append({
                "title": f"🚚 Départ: {name}",
                "start": r.date_depart.isoformat(),
                "color": color,
                "url": url_for("admin_project_edit", record_id=r.id),
            })

        if r.date_debut_tournage:
            event = {
                "title": f"🎬 {name}",
                "start": r.date_debut_tournage.isoformat(),
                "color": color,
                "url": url_for("admin_project_edit", record_id=r.id),
            }
            if r.date_fin_tournage:
                event["end"] = r.date_fin_tournage.isoformat()
            events.append(event)

        if r.date_retour:
            events.append({
                "title": f"📦 Retour: {name}",
                "start": r.date_retour.isoformat(),
                "color": color,
                "url": url_for("admin_project_edit", record_id=r.id),
            })

    return events


# ── Stats (Chart.js) ─────────────────────────────────────────────


def get_checkout_stats():
    """
    Compute checkout statistics for Chart.js charts.

    Returns a dict with nested structure matching the frontend expectations:
        {
            'monthly_activity': { 'labels': [...], 'data': [...] },
            'status_distribution': { 'labels': [...], 'data': [...] },
        }
    """
    records = CheckoutVehicle.query.all()

    # ── Status counts ─────────────────────────────────────────────
    status_counts = defaultdict(int)
    for r in records:
        status = r.etat_controle or "Inconnu"
        status_counts[status] += 1

    # ── Monthly activity ──────────────────────────────────────────
    monthly = defaultdict(int)
    for r in records:
        if r.created_at:
            month_key = r.created_at.strftime("%Y-%m")
            monthly[month_key] += 1

    sorted_months = sorted(monthly.items())

    # ── Status labels in display order ────────────────────────────
    ordered_statuses = ["Signé", "Terminé", "À signer", "Inconnu"]
    status_labels = [
        s for s in ordered_statuses if status_counts.get(s, 0) > 0]
    # Add any extra statuses not in our ordered list
    for s in status_counts:
        if s not in status_labels:
            status_labels.append(s)

    return {
        "monthly_activity": {
            "labels": [m[0] for m in sorted_months],
            "data": [m[1] for m in sorted_months],
        },
        "status_distribution": {
            "labels": status_labels,
            "data": [status_counts[s] for s in status_labels],
        },
    }
