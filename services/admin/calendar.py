import logging
from flask import url_for
from models import Project

logger = logging.getLogger(__name__)


def get_calendar_events():
    """
    Fetch all projects and format as FullCalendar events.
    """
    records = Project.query.all()
    events = []
    colors = [
        "#618b4ae6", "#5299d3e6", "#f59e0be6", "#e05c5ce6", "#8b5cf6e6",
        "#06b6d4e6", "#f97316e6", "#ec4899e6", "#14b8a6e6", "#a855f7e6",
    ]

    for i, r in enumerate(records):
        name = r.name or "Sans nom"
        color = colors[i % len(colors)]

        if r.departure_date:
            events.append({
                "title": f"🚚 Départ: {name}",
                "start": r.departure_date.isoformat(),
                "color": color,
                "url": url_for("admin_project_edit", record_id=r.id),
            })

        if r.shoot_start_date:
            event = {
                "title": f"🎬 {name}",
                "start": r.shoot_start_date.isoformat(),
                "color": color,
                "url": url_for("admin_project_edit", record_id=r.id),
            }
            if r.shoot_end_date:
                event["end"] = r.shoot_end_date.isoformat()
            events.append(event)

        if r.return_date:
            events.append({
                "title": f"📦 Retour: {name}",
                "start": r.return_date.isoformat(),
                "color": color,
                "url": url_for("admin_project_edit", record_id=r.id),
            })

    return events
