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


def init_files_routes(app):
    # ── File Serving ──────────────────────────────────────────────

    @app.route("/files/<path:filename>")
    def serve_private_file(filename):
        # We don't use @require_roles here so public signature pages can also see photos
        # (seal verification page).
        from flask import send_from_directory
        private_folder = current_app.config.get("PRIVATE_FOLDER")
        directory = private_folder / "uploads"
        return send_from_directory(directory, filename)

