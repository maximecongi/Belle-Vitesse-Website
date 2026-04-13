"""
Route publique pour le flux calendrier ICS.
Accessible via un token unique dans l'URL : GET /cal/<token>.ics
"""
from datetime import datetime, timedelta

from flask import Blueprint, Response, abort, current_app, request
from icalendar import Calendar, Event

from sqlalchemy.orm import joinedload

from extensions import limiter
from models import CalendarSubscription, Project, db

cal_feed_bp = Blueprint("cal_feed", __name__)


@cal_feed_bp.route("/cal/<token>.ics")
@limiter.limit("30 per hour")
def calendar_feed(token):
    """Génère dynamiquement un flux ICS à partir des projets en base."""

    # 1. Valider le token
    sub = CalendarSubscription.query.filter_by(
        token=token, is_active=True
    ).first()

    if not sub:
        abort(404)

    # 2. Mettre à jour le dernier accès
    try:
        sub.last_accessed_at = datetime.utcnow()
        db.session.commit()
    except Exception:
        db.session.rollback()

    current_app.logger.info(
        f"📅 Accès calendrier ICS : token={token[:8]}... "
        f"user_id={sub.user_id} IP={request.remote_addr}"
    )

    # 3. Récupérer tous les projets avec au moins une date
    projects = Project.query.options(
        joinedload(Project.production),
        joinedload(Project.pilot_contact),
        joinedload(Project.production_contact)
    ).filter(
        db.or_(
            Project.departure_date.isnot(None),
            Project.shoot_start_date.isnot(None),
            Project.return_date.isnot(None),
        )
    ).all()

    # 4. Construire le calendrier ICS
    cal = Calendar()
    cal.add("prodid", "-//Belle Vitesse SAS//Calendrier Projets//FR")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", "Belle Vitesse — Projets")
    cal.add("x-wr-timezone", "Europe/Paris")
    # Suggérer un rafraîchissement toutes les 30 minutes
    cal.add("refresh-interval;value=duration", "PT30M")
    cal.add("x-published-ttl", "PT30M")

    for project in projects:
        name = project.name or "Sans nom"

        # Déterminer la date de début et de fin de l'événement multi-jours
        start_date = (
            project.departure_date
            or project.shoot_start_date
        )
        end_date = (
            project.return_date
            or project.shoot_end_date
            or project.shoot_start_date
            or project.departure_date
        )

        if not start_date:
            continue

        # Pour un événement multi-jours (all-day), la date de fin en ICS est
        # exclusive — il faut ajouter 1 jour
        end_date_exclusive = end_date + timedelta(days=1) if end_date else start_date + timedelta(days=1)

        event = Event()
        event.add("uid", f"bv-project-{project.id}@bellevitesse.com")
        event.add("dtstart", start_date)
        event.add("dtend", end_date_exclusive)
        event.add("summary", f"🎬 {name}")
        event.add("dtstamp", datetime.utcnow())

        # Construire la description
        desc_parts = [f"Projet : {name}"]
        
        if project.production:
            desc_parts.append(f"Production : {project.production.name}")
            
        if project.pilot_contact:
            desc_parts.append(f"Pilote : {project.pilot_contact.first_name} {project.pilot_contact.last_name}")
            
        if project.production_contact:
            desc_parts.append(f"Contact Prod : {project.production_contact.first_name} {project.production_contact.last_name}")

        desc_parts.append("") # Ligne vide pour aérer
        
        if project.departure_date:
            desc_parts.append(f"🚚 Départ : {project.departure_date.strftime('%d/%m/%Y')}")
        if project.shoot_start_date:
            desc_parts.append(f"🎬 Début tournage : {project.shoot_start_date.strftime('%d/%m/%Y')}")
        if project.shoot_end_date:
            desc_parts.append(f"🏁 Fin tournage : {project.shoot_end_date.strftime('%d/%m/%Y')}")
        if project.return_date:
            desc_parts.append(f"📦 Retour : {project.return_date.strftime('%d/%m/%Y')}")

        event.add("description", "\n".join(desc_parts))

        # Catégorie pour le filtrage côté client
        event.add("categories", ["Belle Vitesse", "Tournage"])

        cal.add_component(event)

    # 5. Retourner la réponse
    return Response(
        cal.to_ical(),
        mimetype="text/calendar",
        headers={
            "Content-Disposition": "attachment; filename=bellevitesse.ics",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )
