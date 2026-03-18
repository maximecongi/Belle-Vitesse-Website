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
        name = r.nom or "Sans nom"
        color = colors[i % len(colors)]

        if r.date_depart:
            events.append({
                "title": f"🚚 Départ: {name}",
                "start": r.date_depart.isoformat(),
                "color": color,
                "url": url_for("admin_project_edit", record_id=r.id),
            })

        if r.date_debut_tournage:
            event = {
                "title": f"🎬 {name}",
                "start": r.date_debut_tournage.isoformat(),
                "color": color,
                "url": url_for("admin_project_edit", record_id=r.id),
            }
            if r.date_fin_tournage:
                event["end"] = r.date_fin_tournage.isoformat()
            events.append(event)

        if r.date_retour:
            events.append({
                "title": f"📦 Retour: {name}",
                "start": r.date_retour.isoformat(),
                "color": color,
                "url": url_for("admin_project_edit", record_id=r.id),
            })

    return events
