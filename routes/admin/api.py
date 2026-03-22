from flask import (
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from services.admin.calendar import get_calendar_events
from services.admin.vehicle_config import (
    get_vehicles_with_config,
    save_vehicle_checkpoint_config,
)
from utils.checkpoints import ALL_POSSIBLE_CHECKPOINTS
from utils.decorators import require_roles


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

    def _handle_status_update(model, record_id):
        from models import db
        from services.admin.status_mapping import get_inspection_key
        try:
            record = db.session.get(model, record_id)
            if not record:
                return jsonify({"error": "Not found"}), 404

            if request.method == "POST":
                data = request.get_json()
                new_status = data.get("status") if data else None
                if not new_status:
                    return jsonify({"error": "Missing status"}), 400

                record.status = new_status
                db.session.commit()
                from services.admin.status_mapping import INSPECTION_STATUS_MAP
                status_id = get_inspection_key(record.status)
                status_label = INSPECTION_STATUS_MAP.get(status_id, status_id)
                return jsonify({
                    "status": status_label, 
                    "status_id": status_id,
                    "message": "Statut mis à jour avec succès"
                })

            status_id = get_inspection_key(record.status)
            from services.admin.status_mapping import INSPECTION_STATUS_MAP
            status_label = INSPECTION_STATUS_MAP.get(status_id, status_id)
            return jsonify({
                "status": status_label,
                "status_id": status_id
            })
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"❌ Error in status update: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/admin/api/checkouts/<int:record_id>/status", methods=["GET", "POST"])
    @require_roles('administrator', 'manager', 'user')
    def admin_api_checkout_status(record_id):
        from models import CheckoutVehicle
        return _handle_status_update(CheckoutVehicle, record_id)

    @app.route("/admin/api/checkins/<int:record_id>/status", methods=["GET", "POST"])
    @require_roles('administrator', 'manager', 'user')
    def admin_api_checkin_status(record_id):
        from models import CheckinVehicle
        return _handle_status_update(CheckinVehicle, record_id)

    @app.route("/admin/vehicle-configs")
    @require_roles('administrator')
    def admin_vehicle_configs():
        try:
            vehicles = get_vehicles_with_config()
            return render_template(
                "admin/vehicle_configs.html",
                vehicles=vehicles,
                possible_checkpoints=ALL_POSSIBLE_CHECKPOINTS
            )
        except Exception as e:
            current_app.logger.error(f"❌ Error in admin_vehicle_configs: {e}")
            flash(
                f"Erreur lors du chargement des configurations: {e}", "error")
            return redirect(url_for('admin_dashboard'))

    @app.route("/admin/api/vehicle-configs", methods=["POST"])
    @require_roles('administrator')
    def admin_api_save_vehicle_config():
        try:
            data = request.get_json()
            vehicle_id = data.get("vehicle_id")
            enabled_keys = data.get("enabled_keys", [])

            if not vehicle_id:
                return jsonify({"error": "Missing vehicle_id"}), 400

            save_vehicle_checkpoint_config(vehicle_id, enabled_keys)
            return jsonify({"success": True})
        except Exception as e:
            current_app.logger.error(
                f"❌ Error in admin_api_save_vehicle_config: {e}")
            return jsonify({"error": str(e)}), 500
