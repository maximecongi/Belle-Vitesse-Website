"""
Routes admin pour le calendrier de booking matériel.
Affiche un diagramme Gantt des réservations par équipement.
"""
import logging
from datetime import timedelta

from flask import jsonify, render_template, request
from sqlalchemy.orm import joinedload

from models import Project
from utils.database import get_vehicles, get_heads
from utils.decorators import require_roles

logger = logging.getLogger(__name__)

# Palette de couleurs pour distinguer les projets
BOOKING_COLORS = [
    "#618b4acc", "#5299d3cc", "#f59e0bcc", "#e05c5ccc", "#8b5cf6cc",
    "#06b6d4cc", "#f97316cc", "#ec4899cc", "#14b8a6cc", "#a855f7cc",
]


def init_booking_routes(app):
    """Initialise les routes du calendrier de booking matériel."""

    @app.route("/admin/booking", endpoint="admin_booking")
    @require_roles("administrator", "manager")
    def admin_booking():
        """Page du calendrier de booking matériel (Gantt)."""
        return render_template("admin/booking_calendar.html")

    @app.route("/admin/api/booking-data", endpoint="admin_booking_data")
    @require_roles("administrator", "manager")
    def admin_booking_data():
        """
        API JSON retournant les données de booking pour le Gantt.
        Paramètres query string :
          - category: 'vehicle' ou 'head' (défaut: 'vehicle')
          - item_id:  ID spécifique d'un item (optionnel, sinon tous)
        """
        category = request.args.get("category", "vehicle")
        item_id = request.args.get("item_id", "")

        # Récupérer tous les items de la catégorie
        if category == "head":
            all_items = get_heads()
            field_name = "heads_to_check"
        else:
            all_items = get_vehicles()
            field_name = "vehicles_to_check"

        # Construire la map id → item
        item_map = {}
        for item in all_items:
            item_map[item["id"]] = {
                "id": item["id"],
                "name": item.get("fields", {}).get("name", "Sans nom"),
            }

        # Si un item spécifique est demandé, filtrer
        if item_id and item_id in item_map:
            filtered_items = {item_id: item_map[item_id]}
        else:
            filtered_items = item_map

        # Récupérer tous les projets avec dates
        all_projects = Project.query.options(
            joinedload(Project.production)
        ).all()

        # Dédupliquer les projets par ID pour éviter les doublons ORM/Join
        projects = []
        seen_ids = set()
        for p in all_projects:
            if p.id not in seen_ids:
                projects.append(p)
                seen_ids.add(p.id)

        # Construire les bookings
        bookings = []
        for i, project in enumerate(projects):
            # Déterminer la période de booking (departure → return, ou shoot_start → shoot_end)
            start = project.departure_date or project.shoot_start_date
            end = project.return_date or project.shoot_end_date

            if not start:
                continue

            # Si pas de date de fin, c'est un event d'un seul jour
            if not end:
                end = start

            # Récupérer les items assignés à ce projet et les dédupliquer
            raw_value = getattr(project, field_name, "") or ""
            assigned_ids = list(set([v.strip() for v in raw_value.split(",") if v.strip()]))

            color = BOOKING_COLORS[i % len(BOOKING_COLORS)]

            for assigned_id in assigned_ids:
                if assigned_id in filtered_items:
                    bookings.append({
                        "item_id": assigned_id,
                        "project_id": project.id,
                        "project_code": project.project_id,
                        "project_name": project.name or "Sans nom",
                        "production": project.production.name if project.production else "—",
                        "start": start.isoformat(),
                        "end": end.isoformat(),
                        "color": color,
                    })

        # Liste des items pour le dropdown
        items_list = [
            {"id": k, "name": v["name"]}
            for k, v in filtered_items.items()
        ]

        return jsonify({
            "items": items_list,
            "bookings": bookings,
        })
