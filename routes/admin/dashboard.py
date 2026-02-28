from utils.decorators import require_roles
from datetime import datetime
from flask import (
    render_template,
    current_app,
)


from services.admin import (
    list_projects,
)


def init_dashboard_routes(app):
    # ── Dashboard ─────────────────────────────────────────────────

    @app.route("/admin")
    @app.route("/admin/dashboard")
    @require_roles('administrator', 'manager', 'user')
    def admin_dashboard():
        try:
            projects_data = list_projects()
            today_iso = datetime.now().strftime('%Y-%m-%d')
            today_checkouts = [p for p in projects_data
                               if p.get("raw_departure_date") == today_iso]
            today_checkins = [p for p in projects_data
                              if p.get("raw_checkin_date") == today_iso]

        except Exception as e:
            current_app.logger.error(f"❌ Error loading dashboard data: {e}")
            today_checkouts = []
            today_checkins = []
            projects_data = []

        return render_template("admin/dashboard.html", today_checkouts=today_checkouts, today_checkins=today_checkins)

