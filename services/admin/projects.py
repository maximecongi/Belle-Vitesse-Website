import logging
import os
from utils.n8n import trigger_n8n_webhook

from sqlalchemy.orm import joinedload
from models import db, Production, Project, Contact
from utils.database import get_vehicles
from utils.formatting import format_date_fr
from services.admin.status_mapping import format_waiver_status

logger = logging.getLogger(__name__)


# ── Projects ─────────────────────────────────────────────────────


def _format_vehicle_state(project, vehicle_id, vehicle_map):
    """
    Format the checkout/checkin state for a single vehicle in a project.
    """
    # Find matching records in the pre-loaded project collections
    c_out = next((c for c in project.checkout_vehicles if c.vehicule_controle == vehicle_id), None)
    c_in = next((c for c in project.checkin_vehicles if c.vehicule_controle == vehicle_id), None)

    return {
        "id": vehicle_id,
        "fields": vehicle_map.get(vehicle_id, {}),
        "checkout_status": c_out.etat_controle if c_out else "",
        "checkout_id": c_out.id if c_out else "",
        "checkout_conform": "yes" if (c_out and c_out.vehicule_pret_depart) else "no",
        "checkout_ready": "Oui" if (c_out and c_out.vehicule_pret_depart) else ("Non" if c_out else "—"),
        "checkin_status": c_in.etat_controle if c_in else "",
        "checkin_id": c_in.id if c_in else "",
        "checkin_conform": "yes" if (c_in and c_in.vehicule_pret_retour) else "no",
        "checkin_ready": "Oui" if (c_in and c_in.vehicule_pret_retour) else ("Non" if c_in else "—"),
    }


def _format_project_admin(p, vehicle_map):
    """
    Format a single project record for the admin listing.
    """
    veh_ids = [v.strip() for v in (p.vehicles_to_check or "").split(",") if v.strip()]
    
    return {
        "id": p.id,
        "project_id": p.project_id,
        "name": p.name,
        "production": p.production.name if p.production else "—",
        "departure_date": format_date_fr(str(p.departure_date)) if p.departure_date else "—",
        "raw_departure_date": str(p.departure_date) if p.departure_date else "",
        "shoot_start": format_date_fr(str(p.shoot_start_date)) if p.shoot_start_date else "—",
        "shoot_end": format_date_fr(str(p.shoot_end_date)) if p.shoot_end_date else "—",
        "return_date": format_date_fr(str(p.return_date)) if p.return_date else "—",
        "raw_return_date": str(p.return_date) if p.return_date else "",
        "raw_checkin_date": str(p.return_date) if p.return_date else "",
        "contact_pilote": f"{p.contact_pilote_rel.first_name} {p.contact_pilote_rel.last_name}" if p.contact_pilote_rel else "—",
        "contact_production": f"{p.contact_production_rel.first_name} {p.contact_production_rel.last_name}" if p.contact_production_rel else "—",
        "vehicles": [_format_vehicle_state(p, vid, vehicle_map) for vid in veh_ids],
        "pilot_waiver": {
            "id": p.pilot_waiver.id if p.pilot_waiver else None,
            "waiver_num": p.pilot_waiver.waiver_id if p.pilot_waiver else "",
            "status": format_waiver_status(p.pilot_waiver.status) if p.pilot_waiver else "",
        },
        "production_waiver": {
            "id": p.production_waiver.id if p.production_waiver else None,
            "waiver_num": p.production_waiver.waiver_id if p.production_waiver else "",
            "status": format_waiver_status(p.production_waiver.status) if p.production_waiver else "",
        }
    }


def list_projects():
    """
    Fetch all project records and format for listing.
    """
    projects = Project.query.options(
        joinedload(Project.production),
        joinedload(Project.checkout_vehicles),
        joinedload(Project.checkin_vehicles),
        joinedload(Project.contact_pilote_rel),
        joinedload(Project.contact_production_rel),
        joinedload(Project.pilot_waiver),
        joinedload(Project.production_waiver)
    ).order_by(Project.name.desc()).all()

    vehicles = get_vehicles()
    vehicle_map = {v["id"]: v.get("fields", {}) for v in vehicles}

    return [_format_project_admin(p, vehicle_map) for p in projects]


def get_project_form_context():
    """
    Get context for project form (productions + vehicles selects).
    """
    prods = Production.query.order_by(Production.name).all()
    productions_formatted = [
        {"id": str(p.id), "fields": {"Nom": p.name}} for p in prods]

    contacts = Contact.query.order_by(Contact.last_name).all()
    contacts_formatted = [
        {"id": str(c.id), "name": f"{c.first_name} {c.last_name} ({c.job_title})" if c.job_title else f"{c.first_name} {c.last_name}"} for c in contacts
    ]

    return {
        "productions": productions_formatted,
        "contacts": contacts_formatted,
        "vehicles": get_vehicles(),
    }


def _parse_date(d):
    return d if d else None


def create_project(form):
    """Create a new project record in the database."""
    veh_ids = form.getlist("vehicle_ids") if hasattr(form, 'getlist') else []
    project = Project(
        name=form.get("name"),
        production_id=form.get("production_id") if form.get(
            "production_id") else None,
        contact_pilote_id=form.get("contact_pilote_id") if form.get(
            "contact_pilote_id") else None,
        contact_production_id=form.get("contact_production_id") if form.get(
            "contact_production_id") else None,
        departure_date=_parse_date(form.get("departure_date")),
        shoot_start_date=_parse_date(form.get("shoot_start")),
        shoot_end_date=_parse_date(form.get("shoot_end")),
        return_date=_parse_date(form.get("return_date")),
        vehicles_to_check=",".join(veh_ids)
    )
    db.session.add(project)
    # To get the project ID before commit if needed, though commit is fine too
    db.session.flush()

    db.session.commit()

    # Trigger n8n webhook
    webhook_url = os.getenv("N8N_WEBHOOK_PROJECT")
    if webhook_url:
        trigger_n8n_webhook(
            webhook_url,
            event="project_created",
            project_id=project.project_id,
            project=project.name,
            production=project.production.name if project.production else "—",
            year=str(project.departure_date.strftime("%Y")
                     ) if project.departure_date else "—",
            month=str(project.departure_date.strftime("%m")
                      ) if project.departure_date else "—",
        )

    return True


def update_project(record_id, form):
    """Update an existing project record in the database."""
    project = db.session.get(Project, record_id)
    if not project:
        return False

    veh_ids = form.getlist("vehicle_ids") if hasattr(form, 'getlist') else []
    project.name = form.get("name")
    project.production_id = form.get(
        "production_id") if form.get("production_id") else None
    project.contact_pilote_id = form.get(
        "contact_pilote_id") if form.get("contact_pilote_id") else None
    project.contact_production_id = form.get(
        "contact_production_id") if form.get("contact_production_id") else None
    project.departure_date = _parse_date(form.get("departure_date"))
    project.shoot_start_date = _parse_date(form.get("shoot_start"))
    project.shoot_end_date = _parse_date(form.get("shoot_end"))
    project.return_date = _parse_date(form.get("return_date"))
    project.vehicles_to_check = ",".join(veh_ids)

    db.session.commit()
    return True


def get_project_for_edit(record_id):
    """
    Fetch a project record and format for editing.
    """
    p = db.session.get(Project, record_id)
    if not p:
        return None

    veh_ids = [v.strip() for v in (p.vehicles_to_check or "").split(
        ",")] if p.vehicles_to_check else []

    return {
        "project_id": p.project_id,
        "name": p.name,
        "departure_date_raw": str(p.departure_date) if p.departure_date else "",
        "shoot_start_raw": str(p.shoot_start_date) if p.shoot_start_date else "",
        "shoot_end_raw": str(p.shoot_end_date) if p.shoot_end_date else "",
        "return_date_raw": str(p.return_date) if p.return_date else "",
        "production_id": str(p.production_id) if p.production_id else "",
        "contact_pilote_id": str(p.contact_pilote_id) if p.contact_pilote_id else "",
        "contact_production_id": str(p.contact_production_id) if p.contact_production_id else "",
        "vehicle_ids": veh_ids,
    }


def delete_project(record_id):
    """Delete a project record from the database and its associated pilot waiver."""
    p = db.session.get(Project, record_id)
    if p:

        from services.admin.waivers import delete_pilot_waiver_internal, delete_production_waiver_internal
        delete_pilot_waiver_internal(record_id)
        delete_production_waiver_internal(record_id)
        db.session.delete(p)
        db.session.commit()
