import logging

from sqlalchemy.orm import joinedload
from models import db, Production, Project
from utils.database import get_vehicles
from utils.formatting import format_date_fr

logger = logging.getLogger(__name__)


# ── Projects ─────────────────────────────────────────────────────
def _check_conformity(record):
    if not record:
        return "yes"
    # Check all status fields for "Défaut"
    status_fields = [
        'etat_pneus', 'roue_secours', 'niveau_huile', 'niveau_liquide_refroidissement',
        'etat_freins', 'etat_eclairage_exterieur', 'demarrage_moteur', 'etat_essuie_glaces',
        'etat_klaxon', 'presence_triangle_gilet', 'presence_extincteur'
    ]
    for field in status_fields:
        if getattr(record, field, None) == "Défaut":
            return "no"
    return "yes"


def list_projects():
    """
    Fetch all project records and format for listing.
    Cross-references checkout records to determine each vehicle's control status.
    """
    projects = Project.query.options(
        joinedload(Project.production),
        joinedload(Project.checkout_vehicles),
        joinedload(Project.checkin_vehicles)
    ).order_by(Project.nom.desc()).all()
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
                "checkout_conform": _check_conformity(c_out),
                "checkout_ready": "Oui" if (c_out and c_out.vehicule_pret_depart) else ("Non" if c_out else "—"),
                "checkin_status": c_in.etat_controle if c_in else "",
                "checkin_id": c_in.id if c_in else "",
                "checkin_conform": _check_conformity(c_in),
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
