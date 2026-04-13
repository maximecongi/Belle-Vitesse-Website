from datetime import timedelta
import logging

from flask import url_for

from models import Project

logger = logging.getLogger(__name__)


def get_calendar_events():
    """
    Récupère tous les projets et les formate comme événements FullCalendar.
    """
    records = Project.query.all()
    events = []
    colors = [
        "#618b4acc", "#5299d3cc", "#f59e0bcc", "#e05c5ccc", "#8b5cf6cc",
        "#06b6d4cc", "#f97316cc", "#ec4899cc", "#14b8a6cc", "#a855f7cc",
    ]

    for i, r in enumerate(records):
        name = r.name or "Sans nom"
        color = colors[i % len(colors)]

        if r.departure_date:
            events.append({
                "title": f"🚚 Départ : {name}",
                "start": r.departure_date.isoformat(),
                "color": color,
                "url": url_for("admin_project_edit", record_id=r.id),
            })

        # Date de tournage 
        if r.shoot_start_date:
            event = {
                "title": f"🎬 {name}",
                "start": r.shoot_start_date.isoformat(),
                "color": color,
                "url": url_for("admin_project_edit", record_id=r.id),
            }
            if r.shoot_end_date:
                # FullCalendar end date is exclusive for all-day events
                # We add 1 day to make it inclusive (e.g. 16th April included)
                event["end"] = (r.shoot_end_date + timedelta(days=1)).isoformat()
            events.append(event)

        if r.return_date:
            events.append({
                "title": f"📦 Retour : {name}",
                "start": r.return_date.isoformat(),
                "color": color,
                "url": url_for("admin_project_edit", record_id=r.id),
            })

    return events
