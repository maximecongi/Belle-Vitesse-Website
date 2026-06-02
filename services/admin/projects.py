import logging
import os

from sqlalchemy.orm import joinedload

from models import Contact, Production, Project, PreQuote, db
from services.admin.status_mapping import format_waiver_status
from utils.database import get_vehicles, get_heads
from utils.formatting import format_date_fr
from utils.n8n import trigger_n8n_webhook

from utils.document_utils import generate_pdf_access_token

logger = logging.getLogger(__name__)


def _get_secured_document_url(path, doc_type):
    """
    Génère une URL sécurisée et tokenisée pour un document PDF.
    Le token est limité dans le temps pour garantir la sécurité des accès.
    """
    if not path:
        return None
    # Nettoie le chemin des éventuels paramètres de requête existants
    clean_path = path.split('?')[0]
    segment = f"/{doc_type}/document/"
    # Extrait uniquement le nom du fichier du chemin complet
    if segment in clean_path:
        clean_path = clean_path.split(segment)[-1]
    elif "/document/" in clean_path:
        clean_path = clean_path.split("/document/")[-1]
    # Génère le token HMAC-SHA256 pour ce fichier
    token = generate_pdf_access_token(clean_path)
    return f"/{doc_type}/document/{clean_path}?t={token}"


# ── Projets (Gestion métier) ─────────────────────────────────────


def _format_vehicle_state(project, vehicle_id, vehicle_map):
    """
    Formate l'état des contrôles (départ/retour) pour un véhicule spécifique au sein d'un projet.
    """
    from services.admin.status_mapping import get_inspection_key

    # Recherche des enregistrements correspondants dans les collections pré-chargées du projet
    c_out = next(
        (c for c in project.checkout_vehicles if c.vehicle_id == vehicle_id), None)
    c_in = next(
        (c for c in project.checkin_vehicles if c.vehicle_id == vehicle_id), None)

    return {
        "id": vehicle_id,
        "fields": vehicle_map.get(vehicle_id, {}),
        "checkout_status": c_out.status if c_out else "",
        "checkout_status_id": get_inspection_key(c_out.status) if c_out else "to_check",
        "checkout_id": c_out.id if c_out else "",
        "checkout_pdf": _get_secured_document_url(c_out.signed_pdf_path, "checkout") if c_out else None,
        "checkout_conform": "true" if (c_out and c_out.vehicle_ready) else "false",
        "checkout_ready": "true" if (c_out and c_out.vehicle_ready) else ("false" if c_out else "—"),
        "checkin_status": c_in.status if c_in else "",
        "checkin_status_id": get_inspection_key(c_in.status) if c_in else "to_check",
        "checkin_id": c_in.id if c_in else "",
        "checkin_pdf": _get_secured_document_url(c_in.signed_pdf_path, "checkin") if c_in else None,
        "checkin_conform": "true" if (c_in and c_in.vehicle_ready) else "false",
        "checkin_ready": "true" if (c_in and c_in.vehicle_ready) else ("false" if c_in else "—"),
    }


def _format_project_admin(p, vehicle_map, heads_map):
    """
    Formate un enregistrement de projet pour l'affichage dans la liste d'administration.
    """
    veh_ids = [v.strip()
               for v in (p.vehicles_to_check or "").split(",") if v.strip()]
    head_ids = [h.strip()
                for h in (p.heads_to_check or "").split(",") if h.strip()]

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
        "notes": p.notes or "",
        "pilot_contact_name": f"{p.pilot_contact.first_name} {p.pilot_contact.last_name}" if p.pilot_contact else "—",
        "production_contact_name": f"{p.production_contact.first_name} {p.production_contact.last_name}" if p.production_contact else "—",
        "dop_contact_name": f"{p.dop_contact.first_name} {p.dop_contact.last_name}" if p.dop_contact else "—",
        "vehicles": [_format_vehicle_state(p, vid, vehicle_map) for vid in veh_ids],
        "heads": [{
            "id": hid,
            "name": heads_map.get(hid, {}).get("name", "Sans nom")
        } for hid in head_ids],
        "pilot_waiver": {
            "id": p.pilot_waiver.id if p.pilot_waiver else None,
            "waiver_num": p.pilot_waiver.waiver_id if p.pilot_waiver else "",
            "status": format_waiver_status(p.pilot_waiver.status) if p.pilot_waiver else "",
            "raw_status": p.pilot_waiver.status if p.pilot_waiver else "",
            "pdf_path": _get_secured_document_url(p.pilot_waiver.signed_pdf_path, "pilot-waiver") if p.pilot_waiver else None,
        },
        "production_waiver": {
            "id": p.production_waiver.id if p.production_waiver else None,
            "waiver_num": p.production_waiver.waiver_id if p.production_waiver else "",
            "status": format_waiver_status(p.production_waiver.status) if p.production_waiver else "",
            "raw_status": p.production_waiver.status if p.production_waiver else "",
            "pdf_path": _get_secured_document_url(p.production_waiver.signed_pdf_path, "production-waiver") if p.production_waiver else None,
        },
        "pre_quotes": [{
            "id": pq.id,
            "reference": pq.reference,
            "total_ht": float(pq.total_ht),
            "status": pq.status,
            "latest_version": max([v.version_number for v in pq.versions]) if pq.versions else None
        } for pq in p.pre_quotes] if getattr(p, 'pre_quotes', None) else []
    }


def list_projects():
    """
    Récupère tous les projets et les formate pour la liste d'administration (avec chargement lié optimisé).
    """
    projects = Project.query.filter(Project.deleted_at == None).options(
        joinedload(Project.production),
        joinedload(Project.checkout_vehicles),
        joinedload(Project.checkin_vehicles),
        joinedload(Project.pilot_contact),
        joinedload(Project.production_contact),
        joinedload(Project.dop_contact),
        joinedload(Project.pilot_waiver),
        joinedload(Project.production_waiver),
        joinedload(Project.pre_quotes).joinedload(PreQuote.versions)
    ).order_by(Project.departure_date.desc(), Project.name.asc()).all()

    vehicles = get_vehicles()
    vehicle_map = {v["id"]: v.get("fields", {}) for v in vehicles}

    heads = get_heads()
    heads_map = {h["id"]: h.get("fields", {}) for h in heads}

    return [_format_project_admin(p, vehicle_map, heads_map) for p in projects]


def get_project_form_context():
    """
    Récupère le contexte nécessaire pour le formulaire de projet (listes de sélections).
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
        "heads": get_heads(),
    }


def _parse_date(d):
    """Utilitaire pour parser les dates du formulaire (gère les vides)."""
    return d if d else None


def create_project(form):
    """Crée un nouvel enregistrement de projet en base de données."""
    veh_ids = form.getlist("vehicle_ids") if hasattr(form, 'getlist') else []
    head_ids = form.getlist("head_ids") if hasattr(form, 'getlist') else []
    project = Project(
        name=form.get("name"),
        production_id=form.get("production_id") if form.get(
            "production_id") else None,
        pilot_contact_id=form.get("pilot_contact_id") if form.get(
            "pilot_contact_id") else None,
        production_contact_id=form.get("production_contact_id") if form.get(
            "production_contact_id") else None,
        dop_contact_id=form.get("dop_contact_id") if form.get(
            "dop_contact_id") else None,
        notes=form.get("notes"),
        departure_date=_parse_date(form.get("departure_date")),
        shoot_start_date=_parse_date(form.get("shoot_start")),
        shoot_end_date=_parse_date(form.get("shoot_end")),
        return_date=_parse_date(form.get("return_date")),
        vehicles_to_check=",".join(veh_ids),
        heads_to_check=",".join(head_ids)
    )
    db.session.add(project)
    db.session.flush() # Permet d'obtenir l'ID du projet avant le commit final

    db.session.commit()

    # Création automatique des décharges associées au projet
    from services.admin.waivers import create_pilot_waiver, create_production_waiver
    create_pilot_waiver(project.id)
    create_production_waiver(project.id)

    # Déclenchement du webhook n8n pour notifier d'autres services
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
    """Met à jour un projet existant en base de données."""
    project = db.session.get(Project, record_id)
    if not project:
        return False

    veh_ids = form.getlist("vehicle_ids") if hasattr(form, 'getlist') else []
    head_ids = form.getlist("head_ids") if hasattr(form, 'getlist') else []
    project.name = form.get("name")
    project.production_id = form.get(
        "production_id") if form.get("production_id") else None
    project.pilot_contact_id = form.get(
        "pilot_contact_id") if form.get("pilot_contact_id") else None
    project.production_contact_id = form.get(
        "production_contact_id") if form.get("production_contact_id") else None
    project.dop_contact_id = form.get(
        "dop_contact_id") if form.get("dop_contact_id") else None
    project.notes = form.get("notes")
    project.departure_date = _parse_date(form.get("departure_date"))
    project.shoot_start_date = _parse_date(form.get("shoot_start"))
    project.shoot_end_date = _parse_date(form.get("shoot_end"))
    project.return_date = _parse_date(form.get("return_date"))
    project.vehicles_to_check = ",".join(veh_ids)
    project.heads_to_check = ",".join(head_ids)

    db.session.commit()
    return True


def get_project_for_edit(record_id):
    """
    Récupère un projet et le formate spécifiquement pour le pré-remplissage du formulaire d'édition.
    """
    p = db.session.get(Project, record_id)
    if not p:
        return None

    veh_ids = [v.strip() for v in (p.vehicles_to_check or "").split(
        ",")] if p.vehicles_to_check else []
    head_ids = [h.strip() for h in (p.heads_to_check or "").split(
        ",")] if p.heads_to_check else []

    return {
        "project_id": p.project_id,
        "name": p.name,
        "departure_date_raw": str(p.departure_date) if p.departure_date else "",
        "shoot_start_raw": str(p.shoot_start_date) if p.shoot_start_date else "",
        "shoot_end_raw": str(p.shoot_end_date) if p.shoot_end_date else "",
        "return_date_raw": str(p.return_date) if p.return_date else "",
        "production_id": str(p.production_id) if p.production_id else "",
        "pilot_contact_id": str(p.pilot_contact_id) if p.pilot_contact_id else "",
        "production_contact_id": str(p.production_contact_id) if p.production_contact_id else "",
        "dop_contact_id": str(p.dop_contact_id) if p.dop_contact_id else "",
        "notes": p.notes or "",
        "vehicle_ids": veh_ids,
        "head_ids": head_ids,
    }


def delete_project(record_id):
    """Supprime un projet et ses décharges associées de la base de données via soft-delete."""
    p = db.session.get(Project, record_id)
    if p:
        from models.db import _utcnow
        from services.admin.waivers import (
            delete_pilot_waiver_internal,
            delete_production_waiver_internal,
        )
        # Supprime d'abord les décharges liées pour respecter l'intégrité
        delete_pilot_waiver_internal(record_id)
        delete_production_waiver_internal(record_id)
        p.deleted_at = _utcnow()
        db.session.commit()
    return True
