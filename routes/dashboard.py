from datetime import datetime
from flask import render_template, current_app, jsonify
from utils.decorators import require_roles
from services.projects import list_projects
from services.dashboard import get_calendar_events, get_checkout_stats


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

    # ── Admin API ─────────────────────────────────────────────────

    @app.route("/admin/api/events")
    @require_roles('administrator', 'manager', 'user')
    def admin_api_events():
        try:
            events = get_calendar_events()
            return jsonify(events)
        except Exception as e:
            current_app.logger.error(f"❌ Error in admin_api_events: {e}")
            return jsonify([]), 500

    @app.route("/admin/api/stats")
    @require_roles('administrator', 'manager', 'user')
    def admin_api_stats():
        try:
            stats = get_checkout_stats()
            return jsonify(stats)
        except Exception as e:
            current_app.logger.error(f"❌ Error in admin_api_stats: {e}")
            return jsonify({"error": str(e)}), 500
