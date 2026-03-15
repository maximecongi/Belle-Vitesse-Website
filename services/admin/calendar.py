import logging
from datetime import datetime

from flask import url_for

from models import Project

logger = logging.getLogger(__name__)


# ── Calendar ─────────────────────────────────────────────────────


def get_calendar_events():
    records = Project.query.all()
    events = []
    colors = [
        "#618b4a", "#5299d3", "#f59e0b", "#e05c5c", "#8b5cf6",
        "#06b6d4", "#f97316", "#ec4899", "#14b8a6", "#a855f7",
    ]

    today_iso = datetime.now().strftime('%Y-%m-%d')

    for i, r in enumerate(records):
        name = r.nom or "Sans nom"
        color = colors[i % len(colors)]
        group_id = f"project-{r.id}"

        # Determine which list to redirect to based on the return date
        # Matching logic in routes/admin/projects.py
        is_archive = r.date_retour and r.date_retour.isoformat() < today_iso
        route_name = "admin_projects_archives" if is_archive else "admin_projects_list"

        if r.date_depart:
            events.append({
                "title": f"🚚 Départ: {name}",
                "start": r.date_depart.isoformat(),
                "color": color,
                "groupId": group_id,
                "order": i,
                "url": url_for(route_name, q=r.project_id),
            })

        if r.date_debut_tournage:
            event_data = {
                "title": f"🎬 Tournage: {name}",
                "start": r.date_debut_tournage.isoformat(),
                "color": color,
                "groupId": group_id,
                "order": i,
                "url": url_for(route_name, q=r.project_id),
            }
            if r.date_fin_tournage:
                event_data["end"] = r.date_fin_tournage.isoformat()
            events.append(event_data)

        if r.date_retour:
            events.append({
                "title": f"📦 Retour: {name}",
                "start": r.date_retour.isoformat(),
                "color": color,
                "groupId": group_id,
                "order": i,
                "url": url_for(route_name, q=r.project_id),
            })

    return events
