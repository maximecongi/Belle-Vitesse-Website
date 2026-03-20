from flask import Blueprint, request, jsonify, current_app
from utils.jwt_auth import require_api_auth
from services.admin.waivers import (
    list_pilot_waivers,
    create_pilot_waiver,
    generate_pilot_waiver,
    send_pilot_waiver,
    reset_pilot_waiver,
    list_production_waivers,
    create_production_waiver,
    generate_production_waiver,
    send_production_waiver,
    reset_production_waiver,
)

api_waivers_bp = Blueprint("api_waivers", __name__)


# ── Pilot Waivers ────────────────────────────────────────────────

@api_waivers_bp.route("/pilot-waivers", methods=["GET"])
@require_api_auth("administrator", "manager", "user")
def api_list_pilot_waivers():
    try:
        result = list_pilot_waivers()
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"❌ API list_pilot_waivers error: {e}")
        return jsonify({"error": str(e)}), 500


@api_waivers_bp.route("/pilot-waivers", methods=["POST"])
@require_api_auth("administrator", "manager")
def api_create_pilot_waiver():
    """Create a pilot waiver for a given project_id."""
    try:
        data = request.get_json(silent=True) or {}
        project_id = data.get("project_id")
        if not project_id:
            return jsonify({"error": "project_id requis"}), 400
        create_pilot_waiver(project_id)
        return jsonify({"message": "Décharge pilote créée"}), 201
    except Exception as e:
        current_app.logger.error(f"❌ API create_pilot_waiver error: {e}")
        return jsonify({"error": str(e)}), 500


@api_waivers_bp.route("/pilot-waivers/<waiver_id>/generate", methods=["POST"])
@require_api_auth("administrator", "manager")
def api_generate_pilot_waiver(waiver_id):
    try:
        generate_pilot_waiver(waiver_id)
        return jsonify({"message": "Décharge pilote générée"})
    except Exception as e:
        current_app.logger.error(f"❌ API generate_pilot_waiver error: {e}")
        return jsonify({"error": str(e)}), 500


@api_waivers_bp.route("/pilot-waivers/<waiver_id>/send", methods=["POST"])
@require_api_auth("administrator", "manager")
def api_send_pilot_waiver(waiver_id):
    try:
        send_pilot_waiver(waiver_id)
        return jsonify({"message": "Décharge pilote envoyée"})
    except Exception as e:
        current_app.logger.error(f"❌ API send_pilot_waiver error: {e}")
        return jsonify({"error": str(e)}), 500


@api_waivers_bp.route("/pilot-waivers/<waiver_id>/reset", methods=["POST"])
@require_api_auth("administrator", "manager")
def api_reset_pilot_waiver(waiver_id):
    try:
        reset_pilot_waiver(waiver_id)
        return jsonify({"message": "Décharge pilote réinitialisée"})
    except Exception as e:
        current_app.logger.error(f"❌ API reset_pilot_waiver error: {e}")
        return jsonify({"error": str(e)}), 500


# ── Production Waivers ────────────────────────────────────────────

@api_waivers_bp.route("/production-waivers", methods=["GET"])
@require_api_auth("administrator", "manager", "user")
def api_list_production_waivers():
    try:
        result = list_production_waivers()
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"❌ API list_production_waivers error: {e}")
        return jsonify({"error": str(e)}), 500


@api_waivers_bp.route("/production-waivers", methods=["POST"])
@require_api_auth("administrator", "manager")
def api_create_production_waiver():
    """Create a production waiver for a given project_id."""
    try:
        data = request.get_json(silent=True) or {}
        project_id = data.get("project_id")
        if not project_id:
            return jsonify({"error": "project_id requis"}), 400
        create_production_waiver(project_id)
        return jsonify({"message": "Décharge production créée"}), 201
    except Exception as e:
        current_app.logger.error(f"❌ API create_production_waiver error: {e}")
        return jsonify({"error": str(e)}), 500


@api_waivers_bp.route("/production-waivers/<waiver_id>/generate", methods=["POST"])
@require_api_auth("administrator", "manager")
def api_generate_production_waiver(waiver_id):
    try:
        generate_production_waiver(waiver_id)
        return jsonify({"message": "Décharge production générée"})
    except Exception as e:
        current_app.logger.error(f"❌ API generate_production_waiver error: {e}")
        return jsonify({"error": str(e)}), 500


@api_waivers_bp.route("/production-waivers/<waiver_id>/send", methods=["POST"])
@require_api_auth("administrator", "manager")
def api_send_production_waiver(waiver_id):
    try:
        send_production_waiver(waiver_id)
        return jsonify({"message": "Décharge production envoyée"})
    except Exception as e:
        current_app.logger.error(f"❌ API send_production_waiver error: {e}")
        return jsonify({"error": str(e)}), 500


@api_waivers_bp.route("/production-waivers/<waiver_id>/reset", methods=["POST"])
@require_api_auth("administrator", "manager")
def api_reset_production_waiver(waiver_id):
    try:
        reset_production_waiver(waiver_id)
        return jsonify({"message": "Décharge production réinitialisée"})
    except Exception as e:
        current_app.logger.error(f"❌ API reset_production_waiver error: {e}")
        return jsonify({"error": str(e)}), 500
