from datetime import timedelta
import logging

from flask import url_for
from sqlalchemy.orm import joinedload

from models import Project

logger = logging.getLogger(__name__)


def get_calendar_events():
    """
    Récupère tous les projets et les formate comme événements FullCalendar
    en respectant le Design System de Belle Vitesse.
    """
    records = (
        Project.query.options(joinedload(Project.production))
        .filter(Project.deleted_at == None)
        .all()
    )
    events = []

    for r in records:
        name = r.name or "Sans nom"
        production_name = r.production.name if r.production else ""

        # Check-out (Départ)
        if r.departure_date:
            events.append({
                "id": f"checkout-{r.id}",
                "title": f"Départ : {name}",
                "start": r.departure_date.isoformat(),
                "classNames": ["fc-event--checkout"],
                "url": url_for("admin_projects_list", q=r.project_id),
                "extendedProps": {
                    "type": "checkout",
                    "typeLabel": "Départ",
                    "projectName": name,
                    "projectId": r.project_id,
                    "production": production_name,
                },
            })

        # Date de tournage (Projet)
        if r.shoot_start_date:
            event = {
                "id": f"project-{r.id}",
                "title": f"Tournage : {name}",
                "start": r.shoot_start_date.isoformat(),
                "classNames": ["fc-event--project"],
                "url": url_for("admin_projects_list", q=r.project_id),
                "extendedProps": {
                    "type": "project",
                    "typeLabel": "Tournage",
                    "projectName": name,
                    "projectId": r.project_id,
                    "production": production_name,
                },
            }
            if r.shoot_end_date:
                # FullCalendar end date is exclusive for all-day events
                # We add 1 day to make it inclusive (e.g. 16th April included)
                event["end"] = (r.shoot_end_date +
                                timedelta(days=1)).isoformat()
            events.append(event)

        # Check-in (Retour)
        if r.return_date:
            events.append({
                "id": f"checkin-{r.id}",
                "title": f"Retour : {name}",
                "start": r.return_date.isoformat(),
                "classNames": ["fc-event--checkin"],
                "url": url_for("admin_projects_list", q=r.project_id),
                "extendedProps": {
                    "type": "checkin",
                    "typeLabel": "Retour",
                    "projectName": name,
                    "projectId": r.project_id,
                    "production": production_name,
                },
            })

    return events
