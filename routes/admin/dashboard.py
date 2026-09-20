from datetime import datetime

from flask import (
    current_app,
    render_template,
)

from services.admin import (
    list_projects,
)
from utils.decorators import require_roles
from utils.formatting import get_today_paris_iso


def init_dashboard_routes(app):
    # ── Dashboard ─────────────────────────────────────────────────

    @app.route("/admin")
    @app.route("/admin/dashboard")
    @require_roles('administrator', 'manager', 'commercial', 'user')
    def admin_dashboard():
        try:
            projects_data = list_projects()
            today_iso = get_today_paris_iso()

            # Regroupe les projets ayant une activité aujourd'hui
            # (Départ ou Retour, avec fallback sur les dates de tournage si les dates de départ/retour ne sont pas définies)
            agenda = []
            for p in projects_data:
                effective_departure = p.get("raw_departure_date") or p.get("raw_shoot_start")
                effective_return = p.get("raw_checkin_date") or p.get("raw_shoot_end")

                is_checkout_today = effective_departure == today_iso
                is_checkin_today = effective_return == today_iso

                if is_checkout_today or is_checkin_today:
                    # Ajoute des drapeaux pour aider au style du template
                    p["is_checkout_today"] = is_checkout_today
                    p["is_checkin_today"] = is_checkin_today
                    agenda.append(p)

        except Exception as e:
            current_app.logger.error(f"❌ Erreur lors du chargement des données du tableau de bord : {e}")
            agenda = []

        return render_template("admin/dashboard.html", agenda=agenda)

