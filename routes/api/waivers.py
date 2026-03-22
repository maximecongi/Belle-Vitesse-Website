from flask import Blueprint, current_app, jsonify, request

from services.admin.waivers import (
    create_pilot_waiver,
    create_production_waiver,
    generate_pilot_waiver,
    generate_production_waiver,
    list_pilot_waivers,
    list_production_waivers,
    reset_pilot_waiver,
    reset_production_waiver,
    send_pilot_waiver,
    send_production_waiver,
)
from utils.jwt_auth import require_api_auth

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


@api_waivers_bp.route("/pilot-waivers/<int:record_id>/finalize", methods=["POST"])
@require_api_auth("administrator", "manager")
def api_finalize_pilot_waiver(record_id):
    """
    Finalize a pilot waiver with provided data and signature.
    """
    from models import PilotWaiver, db
    from services.common.signatures import finalize_signed_document
    try:
        data = request.get_json(silent=True) or {}
        signature_data = data.get("signature_data")
        if not signature_data:
            return jsonify({"error": "signature_data requis"}), 400

        record = db.session.get(PilotWaiver, record_id)
        if not record:
            return jsonify({"error": "Waiver non trouvé"}), 404

        # Map optional data fields from JSON
        record.pilot_first_name = data.get("first_name", record.pilot_first_name)
        record.pilot_last_name = data.get("last_name", record.pilot_last_name)
        record.pilot_dob = data.get("dob", record.pilot_dob)
        record.pilot_license_number = data.get("license_number", record.pilot_license_number)
        record.pilot_address = data.get("address", record.pilot_address)
        record.pilot_insurance_company = data.get("insurance_company", record.pilot_insurance_company)
        record.pilot_insurance_policy = data.get("insurance_policy", record.pilot_insurance_policy)

        signer_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if signer_ip and ',' in signer_ip:
            signer_ip = signer_ip.split(',')[0].strip()
        record.signer_ip = signer_ip

        db.session.commit()

        result = finalize_signed_document("pilot", record_id, signature_data, signer_ip)
        
        return jsonify({
            "message": "Décharge pilote finalisée",
            "document_id": result.get("document_id"),
            "pdf_url": result.get("pdf_url")
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ API finalize_pilot_waiver error: {e}")
        return jsonify({"error": str(e)}), 500


@api_waivers_bp.route("/production-waivers/<int:record_id>/finalize", methods=["POST"])
@require_api_auth("administrator", "manager")
def api_finalize_production_waiver(record_id):
    """
    Finalize a production waiver with provided data and signature.
    """
    from models import ProductionWaiver, db
    from services.common.signatures import finalize_signed_document
    try:
        data = request.get_json(silent=True) or {}
        signature_data = data.get("signature_data")
        if not signature_data:
            return jsonify({"error": "signature_data requis"}), 400

        record = db.session.get(ProductionWaiver, record_id)
        if not record:
            return jsonify({"error": "Waiver non trouvé"}), 404

        # Map optional data fields from JSON
        record.production_name = data.get("production_name", record.production_name)
        record.production_representative = data.get("representative", record.production_representative)
        record.production_address = data.get("address", record.production_address)
        record.production_siret = data.get("siret", record.production_siret)
        record.production_vat = data.get("vat_number", record.production_vat)
        record.production_insurance_company = data.get("insurance_company", record.production_insurance_company)
        record.production_insurance_policy = data.get("insurance_policy", record.production_insurance_policy)

        signer_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if signer_ip and ',' in signer_ip:
            signer_ip = signer_ip.split(',')[0].strip()
        record.signer_ip = signer_ip

        db.session.commit()

        result = finalize_signed_document("production", record_id, signature_data, signer_ip)
        
        return jsonify({
            "message": "Décharge production finalisée",
            "document_id": result.get("document_id"),
            "pdf_url": result.get("pdf_url")
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ API finalize_production_waiver error: {e}")
        return jsonify({"error": str(e)}), 500
