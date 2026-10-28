"""
Routes publiques pour les constats d'incidents : signature contradictoire et vérification de conformité.
"""

from flask import (
    abort,
    jsonify,
    render_template,
    request,
)

from extensions import csrf, limiter
from models import Incident, IncidentSignedDocument, db
from routes.public.shared_docs import handle_document_download, handle_document_verify
from services.admin.incidents import (
    get_incident_detail,
    sign_incident_prod,
    validate_incident_token,
)


def init_incident_public_routes(app):
    """Initialise les routes publiques pour les incidents : signature, contrôle d'intégrité, téléchargement."""

    @app.route("/incidents/sign/<token>", methods=["GET"])
    def incident_sign_page(token):
        res, status_code = validate_incident_token(token)
        if not res:
            abort(status_code)

        token_entry, incident = res
        incident_data = get_incident_detail(incident.id)
        is_already_signed = incident.is_signed_prod

        default_signer = ""
        if incident.project and incident.project.production_contact:
            c = incident.project.production_contact
            default_signer = f"{c.first_name or ''} {c.last_name or ''}".strip()

        return render_template(
            "public/incident_sign.html",
            incident=incident_data,
            token=token,
            is_already_signed=is_already_signed,
            default_signer_name=default_signer,
        )

    @app.route("/incidents/sign/<token>", methods=["POST"])
    @csrf.exempt
    def incident_submit_signature(token):
        res, status_code = validate_incident_token(token)
        if not res:
            error_messages = {
                404: "Jeton de signature invalide ou incident introuvable.",
                410: "Ce lien de signature a expiré (délai de 48 heures dépassé).",
            }
            return jsonify({"error": error_messages.get(status_code, "Erreur de validation du jeton.")}), status_code

        token_entry, incident = res

        payload = request.get_json(silent=True) or {}
        if not payload and request.form:
            payload = request.form

        signer_name = (payload.get("signer_name") or "").strip()
        signer_role = (payload.get("signer_role") or "").strip()
        signature_data = (payload.get("signature") or payload.get("signature_data") or "").strip()

        if not signer_name:
            return jsonify({"error": "Le nom et prénom du signataire sont requis."}), 400
        if not signer_role:
            return jsonify({"error": "La qualité / fonction du signataire est requise."}), 400
        if not signature_data:
            return jsonify({"error": "Le tracé manuscrit de signature est requis."}), 400

        from utils.request_utils import get_client_ip
        ip_addr = get_client_ip()

        try:
            sign_res = sign_incident_prod(
                incident_id=incident.id,
                signer_name=signer_name,
                signer_role=signer_role,
                signature_data=signature_data,
                ip_address=ip_addr,
                token_str=token,
            )

            return jsonify({
                "status": "signed",
                "success": True,
                "message": sign_res.get("message", "Signature enregistrée avec succès."),
                **sign_res,
            }), 200

        except Exception as e:
            app.logger.error(f"❌ Erreur lors de la signature contradictoire de l'incident : {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/incidents/verify/<string:incident_number>", methods=["GET", "POST"])
    @limiter.limit("20 per minute")
    @csrf.exempt
    def incident_verify_doc(incident_number):
        config = {
            "mode": "incident",
            "signed_model": IncidentSignedDocument,
            "seal_prefix": "INCIDENT",
            "template_verify": "public/incident_verify.html",
            "route_base": "incidents",
            "get_seal_args": lambda data, signed_doc: [
                data.get("incident_number", ""),
                data.get("bv_signer_name", "") or "",
                data.get("bv_signature_data", "") or "",
                data.get("bv_signed_at", "") or "",
                data.get("prod_signer_name", "") or "",
                data.get("prod_signature_data", "") or "",
                data.get("prod_signed_at", "") or "",
            ],
        }
        return handle_document_verify(config, incident_number)

    @app.route("/incidents/document/<path:filepath>")
    @csrf.exempt
    def incident_document_download(filepath):
        return handle_document_download(filepath)
