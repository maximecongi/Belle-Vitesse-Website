from flask import Blueprint, jsonify, current_app
from utils.jwt_auth import require_api_auth
from services.admin.calendar import get_calendar_events

api_dashboard_bp = Blueprint("api_dashboard", __name__)


@api_dashboard_bp.route("/calendar/events", methods=["GET"])
@require_api_auth("administrator", "manager", "user")
def api_calendar_events():
    try:
        events = get_calendar_events()
        return jsonify(events)
    except Exception as e:
        current_app.logger.error(f"❌ API calendar events error: {e}")
        return jsonify({"error": str(e)}), 500
