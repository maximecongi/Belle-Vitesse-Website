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


def init_api_routes(app):
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

    @app.route("/admin/api/checkouts/<int:record_id>/status", methods=["GET", "POST"])
    @require_roles('administrator', 'manager', 'user')
    def admin_api_checkout_status(record_id):
        from models import db, CheckoutVehicle
        try:
            record = db.session.get(CheckoutVehicle, record_id)
            if not record:
                return jsonify({"error": "Not found"}), 404

            if request.method == "POST":
                data = request.get_json()
                new_status = data.get("status") if data else None
                if not new_status:
                    return jsonify({"error": "Missing status"}), 400

                record.etat_controle = new_status
                db.session.commit()
                return jsonify({"status": record.etat_controle, "message": "Statut mis à jour avec succès"})

            return jsonify({"status": record.etat_controle})
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"❌ Error in admin_api_checkout_status: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/admin/api/checkins/<int:record_id>/status", methods=["GET", "POST"])
    @require_roles('administrator', 'manager', 'user')
    def admin_api_checkin_status(record_id):
        from models import db, CheckinVehicle
        try:
            record = db.session.get(CheckinVehicle, record_id)
            if not record:
                return jsonify({"error": "Not found"}), 404

            if request.method == "POST":
                data = request.get_json()
                new_status = data.get("status") if data else None
                if not new_status:
                    return jsonify({"error": "Missing status"}), 400

                record.etat_controle = new_status
                db.session.commit()
                return jsonify({"status": record.etat_controle, "message": "Statut mis à jour avec succès"})

            return jsonify({"status": record.etat_controle})
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"❌ Error in admin_api_checkin_status: {e}")
            return jsonify({"error": str(e)}), 500
