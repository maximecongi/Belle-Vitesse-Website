from datetime import datetime

from flask import (
    current_app,
    render_template,
)

from services.admin import (
    list_projects,
)
from utils.decorators import require_roles


def init_dashboard_routes(app):
    # ── Dashboard ─────────────────────────────────────────────────

    @app.route("/admin")
    @app.route("/admin/dashboard")
    @require_roles('administrator', 'manager', 'user')
    def admin_dashboard():
        try:
            projects_data = list_projects()
            today_iso = datetime.now().strftime('%Y-%m-%d')

            # Consolidate projects that have activity today
            # (Check-out or Check-in)
            agenda = []
            for p in projects_data:
                is_checkout_today = p.get("raw_departure_date") == today_iso
                is_checkin_today = p.get("raw_checkin_date") == today_iso

                if is_checkout_today or is_checkin_today:
                    # Add flags to help template styling
                    p["is_checkout_today"] = is_checkout_today
                    p["is_checkin_today"] = is_checkin_today
                    agenda.append(p)

        except Exception as e:
            current_app.logger.error(f"❌ Error loading dashboard data: {e}")
            agenda = []

        return render_template("admin/dashboard.html", agenda=agenda)

