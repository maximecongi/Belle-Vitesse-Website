from datetime import timedelta
import logging

from flask import url_for
from sqlalchemy.orm import joinedload

from models import Project

logger = logging.getLogger(__name__)


def get_calendar_events():
    """
    Récupère tous les projets et les formate comme événements FullCalendar unifiés
    reliant départ, tournage et retour par un trait de continuité,
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

        dep_d = r.departure_date
        shoot_start = r.shoot_start_date
        shoot_end = r.shoot_end_date or r.shoot_start_date
        ret_d = r.return_date

        valid_dates = [d for d in [dep_d, shoot_start, shoot_end, ret_d] if d is not None]
        if not valid_dates:
            continue

        min_date = min(valid_dates)
        max_date = max(valid_dates)

        # FullCalendar end date is exclusive for all-day events
        # We add 1 day so that max_date is fully included
        start_str = min_date.isoformat()
        end_str = (max_date + timedelta(days=1)).isoformat()

        class_names = ["fc-event--unified"]
        if dep_d:
            class_names.append("has-checkout")
            class_names.append("fc-event--checkout")
        if shoot_start:
            class_names.append("has-project")
            class_names.append("fc-event--project")
        if ret_d:
            class_names.append("has-checkin")
            class_names.append("fc-event--checkin")

        events.append({
            "id": f"project-{r.id}",
            "title": f"Projet : {name}",
            "start": start_str,
            "end": end_str,
            "allDay": True,
            "classNames": class_names,
            "url": url_for("admin_projects_list", q=r.project_id) if getattr(r, "project_id", None) else "",
            "extendedProps": {
                "projectId": r.project_id or "",
                "projectName": name,
                "production": production_name,
                "departureDate": dep_d.isoformat() if dep_d else None,
                "shootStartDate": shoot_start.isoformat() if shoot_start else None,
                "shootEndDate": shoot_end.isoformat() if shoot_end else None,
                "returnDate": ret_d.isoformat() if ret_d else None,
                "hasCheckout": bool(dep_d),
                "hasProject": bool(shoot_start),
                "hasCheckin": bool(ret_d),
            },
        })

    return events
