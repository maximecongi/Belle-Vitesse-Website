from utils.decorators import require_roles
from datetime import datetime, timezone
from flask import (
    render_template,
    abort,
    jsonify,
    request,
    current_app,
    session,
    redirect,
    url_for,
    flash,
)

from extensions import csrf
from extensions import limiter
from utils.mailer import send_newsletter_campaign

from services.admin import (
    list_checkouts,
    get_checkout_detail,
    get_checkout_form_context,
    create_checkout,
    update_checkout,
    delete_checkout,
    list_checkins,
    get_checkin_detail,
    get_checkin_form_context,
    create_checkin,
    update_checkin,
    delete_checkin,
    list_projects,
    get_project_form_context,
    create_project,
    update_project,
    get_project_for_edit,
    delete_project,
    list_productions,
    create_production,
    update_production,
    get_production_for_edit,
    delete_production,
    get_calendar_events,
    get_checkout_stats,
)
from services.auth import request_magic_link, verify_magic_link
from services.newsletter import (
    list_newsletter_subscribers,
    remove_newsletter_subscriber_by_id,
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

