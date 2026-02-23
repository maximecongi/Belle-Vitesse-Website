"""
Dashboard service layer — business logic for the dashboard statistics and calendar.
"""

from collections import defaultdict
from flask import url_for
from utils.checkout import TABLE_PROJECTS, TABLE_CHECKOUT


def get_calendar_events():
    records = TABLE_PROJECTS.all()
    events = []
    colors = [
        "#618b4a", "#5299d3", "#f59e0b", "#e05c5c", "#8b5cf6",
        "#06b6d4", "#f97316", "#ec4899", "#14b8a6", "#a855f7",
    ]

    for i, r in enumerate(records):
        fields = r.get("fields", {})
        name = fields.get("Nom", "Sans nom")
        start = fields.get("Date de départ")
        shoot_start = fields.get("Date de début de tournage")
        shoot_end = fields.get("Date de fin de tournage")
        return_date = fields.get("Date de retour")
        color = colors[i % len(colors)]

        # Since project edition will be under routes/projects.py, the route endpoint should dynamically point to "admin_project_edit".
        # Note: at runtime, ensure the route blueprint/app module implements these endpoint mappings.

        if start:
            events.append({
                "title": f"🚚 Départ: {name}",
                "start": start,
                "color": color,
                "url": url_for("admin_project_edit", record_id=r["id"]),
            })

        if shoot_start:
            event = {
                "title": f"🎬 {name}",
                "start": shoot_start,
                "color": color,
                "url": url_for("admin_project_edit", record_id=r["id"]),
            }
            if shoot_end:
                event["end"] = shoot_end
            events.append(event)

        if return_date:
            events.append({
                "title": f"📦 Retour: {name}",
                "start": return_date,
                "color": color,
                "url": url_for("admin_project_edit", record_id=r["id"]),
            })

    return events


def get_checkout_stats():
    """Compute checkout statistics for Chart.js charts."""
    records = TABLE_CHECKOUT.all()

    status_counts = defaultdict(int)
    for r in records:
        status = r["fields"].get("État du contrôle", "Inconnu")
        status_counts[status] += 1

    monthly = defaultdict(int)
    for r in records:
        created = r.get("createdTime", "")
        if created:
            month_key = created[:7]  # "2026-02"
            monthly[month_key] += 1

    sorted_months = sorted(monthly.items())

    ordered_statuses = ["Signé", "Terminé", "À signer", "Inconnu"]
    status_labels = [
        s for s in ordered_statuses if status_counts.get(s, 0) > 0]
    for s in status_counts:
        if s not in status_labels:
            status_labels.append(s)

    return {
        "monthly_activity": {
            "labels": [m[0] for m in sorted_months],
            "data": [m[1] for m in sorted_months],
        },
        "status_distribution": {
            "labels": status_labels,
            "data": [status_counts[s] for s in status_labels],
        },
    }
