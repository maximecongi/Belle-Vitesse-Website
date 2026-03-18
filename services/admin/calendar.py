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
        "#618b4a", "#5299d3", "#f59e0b", "#e05c5c", "#8b5cf6",
        "#06b6d4", "#f97316", "#ec4899", "#14b8a6", "#a855f7",
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
