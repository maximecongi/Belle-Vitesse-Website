"""
Admin service layer — business logic for admin CRUD and API endpoints.

Every function here is pure business logic: no Flask request/response handling.
Routes call these functions and handle HTTP concerns (flash, redirect, render).
"""

import logging
from collections import defaultdict
from datetime import date

from flask import url_for

from utils.airtable import get_vehicles
from utils.checkout import (
    format_checkout_data,
    format_date_fr,
    get_checkout_record,
    TABLE_CHECKOUT,
    TABLE_PROJECTS,
    TABLE_PRODUCTIONS,
    TABLE_USERS,
)

logger = logging.getLogger(__name__)


# ── Checkouts ────────────────────────────────────────────────────


def list_checkouts():
    """
    Fetch all checkout records, compute stats, and format for listing.

    Returns:
        dict with keys 'checkouts' (list) and 'stats' (dict).
    """
    records = TABLE_CHECKOUT.all()
    records.sort(key=lambda x: x.get("createdTime", ""), reverse=True)

    total_count = len(records)
    signed_count = sum(
        1 for r in records
        if r["fields"].get("État du contrôle") == "Signé"
    )
    pending_count = sum(
        1 for r in records
        if r["fields"].get("État du contrôle") == "Terminé"
    )

    stats = {
        "total_checkouts": total_count,
        "signed_checkouts": signed_count,
        "pending_checkouts": pending_count,
    }

    checkouts = []
    for r in records:
        data = format_checkout_data(r)
        checkouts.append({
            "id": r["id"],
            "inspection_id": data["inspection_id"],
            "project": data.get("project", "—"),
            "departure_date": data.get("departure_date", "—"),
            "control_date": data.get("control_date", "—"),
            "status": data.get("control_status", "—"),
            "controller": data.get("controller", "—"),
            "created_at": r.get("createdTime"),
            "ready": data.get("ready", "—"),
            "search_text": (
                f"{data['inspection_id']} "
                f"{data.get('project', '')} "
                f"{data.get('controller', {}).get('name', '')} "
                f"{data.get('control_status', '')}"
            ).lower(),
        })

    return {"checkouts": checkouts, "stats": stats}


def get_checkout_detail(record_id):
    """
    Fetch and format a single checkout record.

    Returns:
        dict of formatted checkout data, or None if not found.
    """
    record = get_checkout_record(record_id)
    if not record:
        return None
    data = format_checkout_data(record)

    # If signed, load the stable snapshot to get the real PDF URL and hash
    if data.get("control_status") == "Signé":
        from utils.database import get_signed_document
        from services.checkout import generate_pdf_access_token
        signed_doc = get_signed_document(data["inspection_id"])
        if signed_doc and signed_doc.get("pdf_url"):
            data["hash"] = signed_doc["hash"]
            pdf_url = signed_doc["pdf_url"]
            filename = pdf_url.split("/")[-1]
            token = generate_pdf_access_token(filename)
            data["pdf_url"] = f"{pdf_url}?t={token}"

    return data


def get_checkout_form_context():
    """
    Get the context needed for the checkout form (projects + vehicles selects).
    Resolves linked production record IDs to their display names.

    Returns:
        dict with 'projects' and 'vehicles' keys.
    """
    projects = TABLE_PROJECTS.all(sort=["Nom"])
    # Build a production-id → name lookup
    productions = TABLE_PRODUCTIONS.all()
    prod_names = {r["id"]: r.get("fields", {}).get("Nom", "—")
                  for r in productions}
    # Inject resolved production name + format dates in French
    for p in projects:
        f = p.get("fields", {})
        prod_ids = f.get("Production", [])
        if prod_ids:
            f["_production_name"] = prod_names.get(prod_ids[0], "—")
        else:
            f["_production_name"] = ""
        # Format dates to French
        for date_key in ("Date de départ", "Date de début de tournage", "Date de fin de tournage"):
            if f.get(date_key):
                f[date_key] = format_date_fr(f[date_key])
    vehicles = get_vehicles()
    # Build a vehicle-id → name lookup for the linked "Véhicule contrôlé" field
    vehicle_names = {v["id"]: v.get("fields", {}).get(
        "name", "—") for v in vehicles}
    for p in projects:
        f = p.get("fields", {})
        veh_ids = f.get("Véhicules à contrôler", [])
        if veh_ids and isinstance(veh_ids, list):
            f["_vehicle_name"] = vehicle_names.get(veh_ids[0], "—")
        else:
            f["_vehicle_name"] = ""

    # Build vehicle → latest checkout status
    checkouts = TABLE_CHECKOUT.all()
    vehicle_status = {}  # vehicle_id → status
    for c in checkouts:
        cf = c.get("fields", {})
        veh_ids = cf.get("Véhicule contrôlé", [])
        status = cf.get("État du contrôle", "")
        if veh_ids and isinstance(veh_ids, list) and status:
            vehicle_status[veh_ids[0]] = status
    # Inject status into vehicle records
    for v in vehicles:
        v["fields"]["_checkout_status"] = vehicle_status.get(v["id"], "")

    users = TABLE_USERS.all(sort=["firstname"])
    return {
        "projects": projects,
        "vehicles": vehicles,
        "users": users,
    }


def build_checkout_fields(form, is_create=False):
    """
    Build Airtable fields dict from checkout form data.

    Args:
        form: Flask request.form (ImmutableMultiDict)
        is_create: if True, sets initial status to "En cours"

    Returns:
        dict of Airtable-ready field names → values.
    """
    fields = {
        "État des pneus": form.get("tires"),
        "Roue de secours": form.get("spare_tire"),
        "État des freins": form.get("brakes"),
        "État éclairage extérieur": form.get("lights"),
        "Niveau huile": form.get("oil"),
        "Niveau liquide de refroidissement": form.get("coolant"),
        "Démarrage moteur": form.get("engine_start"),
        "État des essuie-glaces": form.get("wipers"),
        "État du klaxon": form.get("horn"),
        "Présence Triangle de signalisation et gilet orange": form.get("safety_triangle"),
        "Présence extincteur": form.get("fire_extinguisher"),
        "Observations générales": form.get("notes"),
    }

    if is_create:
        fields["État du contrôle"] = "En cours"
        fields["Date du contrôle"] = date.today().isoformat()

    if form.get("km"):
        fields["Kilométrage départ"] = int(form.get("km"))

    if form.get("battery"):
        fields["Charge de la batterie départ"] = int(form.get("battery"))

    if form.get("project_id"):
        fields["Projet"] = [form.get("project_id")]

    if form.get("vehicle_id"):
        fields["Véhicule contrôlé"] = [form.get("vehicle_id")]

    if form.get("controller_id"):
        fields["Reponsable du contrôle"] = [form.get("controller_id")]

    return fields


def _upload_photos_to_record(record_id, files):
    """
    Upload photo files to the Airtable record as attachments.

    Args:
        record_id: Airtable record ID
        files: Flask request.files (ImmutableMultiDict)
    """
    # Mapping: form field name → Airtable attachment field name
    photo_fields = {
        "odometer_photos": "Photo compteur",
        "exterior_photos": "Photos extérieur véhicule",
        "interior_photos": "Photos intérieur véhicule",
    }

    for form_field, airtable_field in photo_fields.items():
        uploaded = files.getlist(form_field)
        for f in uploaded:
            if f and f.filename:
                TABLE_CHECKOUT.upload_attachment(
                    record_id, airtable_field, f.filename, content=f.read()
                )


def create_checkout(form, files=None):
    """
    Create a new checkout record in Airtable.

    Args:
        form: Flask request.form
        files: Flask request.files (optional)

    Returns:
        True on success, raises on failure.
    """
    fields = build_checkout_fields(form, is_create=True)
    record = TABLE_CHECKOUT.create(fields)
    if files:
        _upload_photos_to_record(record["id"], files)
    return True


def update_checkout(record_id, form, files=None):
    """
    Update an existing checkout record in Airtable.

    Args:
        record_id: Airtable record ID
        form: Flask request.form
        files: Flask request.files (optional)

    Returns:
        True on success, raises on failure.
    """
    fields = build_checkout_fields(form, is_create=False)
    TABLE_CHECKOUT.update(record_id, fields)
    if files:
        _upload_photos_to_record(record_id, files)
    return True


def delete_checkout(record_id):
    """Delete a checkout record from Airtable."""
    TABLE_CHECKOUT.delete(record_id)


# ── Projects ─────────────────────────────────────────────────────


def list_projects():
    """
    Fetch all project records and format for listing.
    Cross-references checkout records to determine each vehicle's control status.

    Returns:
        list of project dicts.
    """
    records = TABLE_PROJECTS.all(sort=["-Nom"])
    # Build vehicle-id → name lookup
    vehicles = get_vehicles()
    vehicle_names = {v["id"]: v.get("fields", {}).get(
        "name", "—") for v in vehicles}

    # Build production-id → name lookup
    productions = TABLE_PRODUCTIONS.all()
    prod_names = {p["id"]: p.get("fields", {}).get(
        "Nom", "—") for p in productions}

    # Build checkout_record_id → (vehicle_id, status) mapping
    checkouts = TABLE_CHECKOUT.all()
    checkout_info = {}
    for c in checkouts:
        cf = c.get("fields", {})
        veh_ids = cf.get("Véhicule contrôlé", [])
        status = cf.get("État du contrôle", "")
        ready = cf.get("Véhicule prêt au départ", "—")
        vid = veh_ids[0] if isinstance(veh_ids, list) and veh_ids else None
        checkout_info[c["id"]] = {"vehicle_id": vid,
                                  "status": status, "ready": ready}

    projects = []
    for r in records:
        fields = r.get("fields", {})
        veh_ids = fields.get("Véhicules à contrôler", [])
        # Use project's linked checkouts to build vehicle → status
        checkout_ids = fields.get("checkout_vehicles", [])
        proj_vehicle_status = {}
        if isinstance(checkout_ids, list):
            for cid in checkout_ids:
                ci = checkout_info.get(cid, {})
                if ci.get("vehicle_id"):
                    proj_vehicle_status[ci["vehicle_id"]] = {
                        "status": ci["status"],
                        "checkout_id": cid,
                        "ready": ci.get("ready", "—")
                    }
        veh_list = []
        if isinstance(veh_ids, list):
            for vid in veh_ids:
                v_info = proj_vehicle_status.get(vid, {})
                veh_list.append({
                    "id": vid,
                    "name": vehicle_names.get(vid, "—"),
                    "status": v_info.get("status", ""),
                    "checkout_id": v_info.get("checkout_id", ""),
                    "ready": v_info.get("ready", "—"),
                })
        prod_ids = fields.get("Production", [])
        prod_name = prod_names.get(prod_ids[0], "—") if isinstance(
            prod_ids, list) and prod_ids else "—"

        projects.append({
            "id": r["id"],
            "name": fields.get("Nom", "—"),
            "production": prod_name,
            "departure_date": format_date_fr(fields.get("Date de départ", "—")),
            "shoot_start": format_date_fr(fields.get("Date de début de tournage", "—")),
            "shoot_end": format_date_fr(fields.get("Date de fin de tournage", "—")),
            "vehicles": veh_list,
        })
    return projects


def get_project_form_context():
    """
    Get context for project form (productions + vehicles selects).

    Returns:
        dict with 'productions' and 'vehicles' keys.
    """
    return {
        "productions": TABLE_PRODUCTIONS.all(sort=["Nom"]),
        "vehicles": get_vehicles(),
    }


def build_project_fields(form):
    """
    Build Airtable fields dict from project form data.

    Returns:
        dict of Airtable-ready field names → values.
    """
    fields = {
        "Nom": form.get("name"),
        "Date de départ": form.get("departure_date"),
        "Date de début de tournage": form.get("shoot_start"),
        "Date de fin de tournage": form.get("shoot_end"),
    }

    if form.get("production_id"):
        fields["Production"] = [form.get("production_id")]

    vehicle_ids = form.getlist("vehicle_ids") if hasattr(
        form, 'getlist') else []
    fields["Véhicules à contrôler"] = vehicle_ids if vehicle_ids else []

    return fields


def create_project(form):
    """Create a new project record in Airtable."""
    fields = build_project_fields(form)
    TABLE_PROJECTS.create(fields)
    return True


def update_project(record_id, form):
    """Update an existing project record in Airtable."""
    fields = build_project_fields(form)
    TABLE_PROJECTS.update(record_id, fields)
    return True


def get_project_for_edit(record_id):
    """
    Fetch a project record and format for editing.

    Returns:
        dict with form-ready keys, or None if not found.
    """
    record = TABLE_PROJECTS.get(record_id)
    if not record:
        return None

    fields = record.get("fields", {})
    prod_ids = fields.get("Production", [])
    production_id = prod_ids[0] if isinstance(
        prod_ids, list) and prod_ids else ""

    veh_ids = fields.get("Véhicules à contrôler", [])
    vehicle_ids = veh_ids if isinstance(veh_ids, list) else []

    return {
        "name": fields.get("Nom", ""),
        "departure_date_raw": fields.get("Date de départ", ""),
        "shoot_start_raw": fields.get("Date de début de tournage", ""),
        "shoot_end_raw": fields.get("Date de fin de tournage", ""),
        "production_id": production_id,
        "vehicle_ids": vehicle_ids,
    }


def delete_project(record_id):
    """Delete a project record from Airtable."""
    TABLE_PROJECTS.delete(record_id)


# ── Productions ──────────────────────────────────────────────────


def list_productions():
    """
    Fetch all production records and format for listing.

    Returns:
        list of production dicts.
    """
    records = TABLE_PRODUCTIONS.all(sort=["Nom"])
    productions = []
    for r in records:
        fields = r.get("fields", {})
        productions.append({
            "id": r["id"],
            "name": fields.get("Nom", "—"),
            "address": fields.get("Adresse", "—"),
            "email": fields.get("Mail", "—"),
            "phone": fields.get("Téléphone", "—"),
        })
    return productions


def build_production_fields(form):
    """Build Airtable fields dict from production form data."""
    return {
        "Nom": form.get("name"),
        "Adresse": form.get("address"),
        "Mail": form.get("email"),
        "Téléphone": form.get("phone"),
    }


def create_production(form):
    """Create a new production record in Airtable."""
    fields = build_production_fields(form)
    TABLE_PRODUCTIONS.create(fields)
    return True


def update_production(record_id, form):
    """Update an existing production record in Airtable."""
    fields = build_production_fields(form)
    TABLE_PRODUCTIONS.update(record_id, fields)
    return True


def get_production_for_edit(record_id):
    """
    Fetch a production record and format for editing.

    Returns:
        dict with form-ready keys, or None if not found.
    """
    record = TABLE_PRODUCTIONS.get(record_id)
    if not record:
        return None

    fields = record.get("fields", {})
    return {
        "name": fields.get("Nom", ""),
        "address": fields.get("Adresse", ""),
        "email": fields.get("Mail", ""),
        "phone": fields.get("Téléphone", ""),
    }


def delete_production(record_id):
    """Delete a production record from Airtable."""
    TABLE_PRODUCTIONS.delete(record_id)


# ── Calendar ─────────────────────────────────────────────────────


def get_calendar_events():
    """
    Build calendar events from project records.

    Returns:
        list of FullCalendar-compatible event dicts.
    """
    records = TABLE_PROJECTS.all()
    events = []

    for r in records:
        fields = r.get("fields", {})
        name = fields.get("Nom", "Sans nom")
        start = fields.get("Date de départ")
        shoot_start = fields.get("Date de début de tournage")
        shoot_end = fields.get("Date de fin de tournage")

        if start:
            events.append({
                "title": f"🚚 Départ: {name}",
                "start": start,
                "color": "rgb(255 152 0 / 92%)",
                "url": url_for("admin_project_edit", record_id=r["id"]),
            })

        if shoot_start:
            event = {
                "title": f"🎬 {name}",
                "start": shoot_start,
                "color": "rgb(76 175 80 / 90%)",
                "url": url_for("admin_project_edit", record_id=r["id"]),
            }
            if shoot_end:
                event["end"] = shoot_end
            events.append(event)

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
    records = TABLE_CHECKOUT.all()

    # ── Status counts ─────────────────────────────────────────────
    status_counts = defaultdict(int)
    for r in records:
        status = r["fields"].get("État du contrôle", "Inconnu")
        status_counts[status] += 1

    # ── Monthly activity ──────────────────────────────────────────
    monthly = defaultdict(int)
    for r in records:
        created = r.get("createdTime", "")
        if created:
            month_key = created[:7]  # "2026-02"
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
