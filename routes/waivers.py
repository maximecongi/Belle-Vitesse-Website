from flask import render_template, request, jsonify, current_app
from models import PilotWaiver, db
from utils.waivers import process_pilot_waiver_signature


def init_waiver_routes(app):
    @app.route("/sign/waiver/<token>", methods=["GET", "POST"])
    def sign_pilot_waiver(token):
        waiver = PilotWaiver.query.filter_by(signature_token=token).first()

        if request.method == "GET":
            if not waiver:
                return render_template("waivers/sign_pilot_waiver.html", waiver={"status": "invalid"})
            return render_template("waivers/sign_pilot_waiver.html", waiver=waiver)

        if request.method == "POST":
            if not waiver or waiver.status == 'signed':
                return jsonify({"success": False, "error": "Token invalide ou décharge déjà signée."})

            try:
                data = request.get_json()

                # Update waiver data
                waiver.pilot_first_name = data.get("first_name")
                waiver.pilot_last_name = data.get("last_name")
                waiver.pilot_dob = data.get("dob")
                waiver.pilot_license_number = data.get("license_number")
                waiver.pilot_address = data.get("address")
                waiver.pilot_insurance_company = data.get("insurance_company")
                waiver.pilot_insurance_policy = data.get("insurance_policy")
                waiver.signature_data = data.get("signature_data")

                signer_ip = request.headers.get(
                    'X-Forwarded-For', request.remote_addr)
                if signer_ip and ',' in signer_ip:
                    signer_ip = signer_ip.split(',')[0].strip()
                waiver.signer_ip = signer_ip

                db.session.commit()

                # Trigger background process or process synchronously
                process_pilot_waiver_signature(waiver.id)

                return jsonify({"success": True})

            except Exception as e:
                current_app.logger.error(
                    f"Error processing waiver signature: {e}")
                return jsonify({"success": False, "error": "Une erreur serveur est survenue."}), 500
