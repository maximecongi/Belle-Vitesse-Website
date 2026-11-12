from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from services.admin.calendar import get_calendar_events
from services.admin.vehicle_config import (
    get_all_checkpoints,
    get_vehicles_with_config,
    save_vehicle_checkpoint_config,
)
from utils.decorators import require_roles


api_bp = Blueprint('admin_api', __name__, url_prefix='/admin')
# ── API Administrative ────────────────────────────────────────


@api_bp.route("/api/events")
@require_roles('administrator', 'manager', 'commercial', 'user')
def admin_api_events():
    try:
        from services.admin.project_access import session_project_scope

        events = get_calendar_events(scope=session_project_scope())
        return jsonify(events)
    except Exception as e:
        current_app.logger.error(f"❌ Erreur dans admin_api_events : {e}")
        return jsonify([]), 500


def _handle_status_update(model, record_id):
    from models import db
    from services.admin.status_mapping import get_inspection_key
    try:
        from services.admin.project_access import can_access_project, session_project_scope

        record = db.session.get(model, record_id)
        scope = session_project_scope()
        if not record or (scope is not None and not can_access_project(record.project_id, scope)):
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
        current_app.logger.error(
            f"❌ Erreur lors de la mise à jour du statut : {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/checkouts/<int:record_id>/status", methods=["GET", "POST"])
@require_roles('administrator', 'manager', 'user')
def admin_api_checkout_status(record_id):
    from models import CheckoutVehicle
    return _handle_status_update(CheckoutVehicle, record_id)


@api_bp.route("/api/checkins/<int:record_id>/status", methods=["GET", "POST"])
@require_roles('administrator', 'manager', 'user')
def admin_api_checkin_status(record_id):
    from models import CheckinVehicle
    return _handle_status_update(CheckinVehicle, record_id)


@api_bp.route("/vehicle-configs")
@require_roles('administrator')
def admin_vehicle_configs():
    try:
        vehicles = get_vehicles_with_config()
        checkpoints = get_all_checkpoints()

        # Regroupement par catégorie en conservant l'ordre métier (Sécurité, Équipements, autres)
        checkpoint_groups = []
        for cp in checkpoints:
            if not checkpoint_groups or checkpoint_groups[-1]["category"] != cp["category"]:
                checkpoint_groups.append({"category": cp["category"], "checkpoints": []})
            checkpoint_groups[-1]["checkpoints"].append(cp)

        return render_template(
            "admin/vehicle_configs.html",
            vehicles=vehicles,
            possible_checkpoints=checkpoints,
            checkpoint_groups=checkpoint_groups,
        )
    except Exception as e:
        current_app.logger.error(
            f"❌ Erreur dans admin_vehicle_configs : {e}")
        flash(
            f"Erreur lors du chargement des configurations: {e}", "error")
        return redirect(url_for('admin_dashboard.admin_dashboard'))


@api_bp.route("/api/vehicle-configs", methods=["POST"])
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
            f"❌ Erreur dans admin_api_save_vehicle_config : {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/vehicle-configs/batch", methods=["POST"])
@require_roles('administrator')
def admin_api_save_vehicle_configs_batch():
    """Enregistre en une fois les lignes modifiées de la matrice points de contrôle × véhicules."""
    from services.admin.vehicle_config import save_vehicle_checkpoint_configs

    data = request.get_json(silent=True) or {}
    configs = data.get("configs")
    if not isinstance(configs, dict) or not configs:
        return jsonify({"success": False, "error": "Aucune modification à enregistrer."}), 400
    if not all(
        isinstance(vid, str) and vid and isinstance(keys, list) and all(isinstance(k, str) for k in keys)
        for vid, keys in configs.items()
    ):
        return jsonify({"success": False, "error": "Format de configuration invalide."}), 400

    try:
        count = save_vehicle_checkpoint_configs(configs)
        return jsonify({"success": True, "updated": count})
    except Exception as e:
        current_app.logger.error(f"❌ Erreur dans admin_api_save_vehicle_configs_batch : {e}")
        return jsonify({"success": False, "error": "Erreur lors de l'enregistrement de la matrice."}), 500


@api_bp.route("/api/search")
@require_roles('administrator', 'manager', 'commercial', 'user', 'technicien')
def admin_api_search():
    """Recherche globale multi-entités pour la Command Palette (Cmd+K)."""
    from services.admin.search import perform_global_search

    user_role = session.get('admin_user_role', 'user')
    q = request.args.get('q', '').strip()
    raw_scope = request.args.get('scope', 'all').strip().lower()
    return jsonify(perform_global_search(q, raw_scope, user_role, user_id=session.get('admin_user_id')))


# ── Pages épinglées (⌘ + ;) ───────────────────────────────────
# Toutes les opérations sont scopées sur l'utilisateur connecté.

_PIN_ROLES = ('administrator', 'manager', 'commercial', 'user', 'technicien')


def _pins_response(status=200, **extra):
    from services.admin.pins import list_pins
    return jsonify({"success": True, "pins": list_pins(session.get("admin_user_id")), **extra}), status


def _pin_user_id():
    return session.get("admin_user_id")


@api_bp.route("/api/pins", methods=["GET"])
@require_roles(*_PIN_ROLES)
def admin_api_pins_list():
    return _pins_response()


@api_bp.route("/api/pins", methods=["POST"])
@require_roles(*_PIN_ROLES)
def admin_api_pins_create():
    from services.admin.pins import PinError, upsert_pin
    user_id = _pin_user_id()
    if not user_id:
        return jsonify({"success": False, "error": "Utilisateur inconnu."}), 403
    data = request.get_json(silent=True) or {}
    try:
        pin = upsert_pin(user_id, data.get("url"), data.get("label"))
    except PinError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    return _pins_response(pin=pin.to_dict())


@api_bp.route("/api/pins/<int:pin_id>", methods=["PATCH"])
@require_roles(*_PIN_ROLES)
def admin_api_pins_rename(pin_id):
    from services.admin.pins import PinError, rename_pin
    data = request.get_json(silent=True) or {}
    try:
        pin = rename_pin(_pin_user_id(), pin_id, data.get("label"))
    except PinError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    if not pin:
        return jsonify({"success": False, "error": "Favori introuvable."}), 404
    return _pins_response(pin=pin.to_dict())


@api_bp.route("/api/pins/<int:pin_id>", methods=["DELETE"])
@require_roles(*_PIN_ROLES)
def admin_api_pins_delete(pin_id):
    from services.admin.pins import delete_pin
    if not delete_pin(_pin_user_id(), pin_id):
        return jsonify({"success": False, "error": "Favori introuvable."}), 404
    return _pins_response()


@api_bp.route("/api/pins/reorder", methods=["POST"])
@require_roles(*_PIN_ROLES)
def admin_api_pins_reorder():
    from services.admin.pins import PinError, reorder_pins
    data = request.get_json(silent=True) or {}
    ids = data.get("ids")
    if not isinstance(ids, list):
        return jsonify({"success": False, "error": "Ordre invalide."}), 400
    try:
        reorder_pins(_pin_user_id(), ids)
    except PinError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    return _pins_response()


def init_api_routes(app):
    """Enregistre le blueprint admin_api (compatibilité ascendante)."""
    if "admin_api" not in app.blueprints:
        app.register_blueprint(api_bp)
