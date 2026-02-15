import requests
import os
import re
import uuid
import hashlib
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from flask import (
    render_template,
    abort,
    jsonify,
    request,
    current_app,
    send_from_directory,
)

from itsdangerous import URLSafeSerializer
from werkzeug.exceptions import HTTPException

from extensions import cache
from utils.specs import build_specs
from utils.database import (
    get_grips_products_for_category,
    get_grips_categories_by_slug,
    get_vehicle_by_slug,
    get_head_by_slug,
    get_configs_for_vehicle,
    add_newsletter_subscriber,
    remove_newsletter_subscriber,
)
from utils.mailer import send_subscription_email
from utils.checkout import (
    get_checkout_by_inspection_id,
    get_checkout_record,
    format_checkout_data,
    generate_qr_code,
    generate_checkout_pdf,
    TABLE_CHECKOUT,
)
from utils.database import (
    store_signed_document,
    get_signed_document,
    store_checkout_token,
    get_checkout_token,
    update_checkout_token_signature,
    delete_checkout_token,
)

# In-memory token store REMOVED in favor of MySQL checkout_tokens table
# _checkout_tokens = {}


def init_routes(app):
    BRANDS = [
        {"slug": "academy", "label": "Academy", "url": "https://www.academyfilms.com/"},
        {
            "slug": "antiestatico",
            "label": "Antiestatico",
            "url": "https://antiestatico.com/",
        },
        {"slug": "biscuit", "label": "Biscuit", "url": "https://biscuitfilmworks.com/"},
        {"slug": "canal", "label": "Canal+", "url": "https://www.canalplusgroup.com/"},
        {
            "slug": "chifoumi",
            "label": "Chi-fou-mi",
            "url": "https://www.unifrance.org/annuaires/societe/351840/chi-fou-mi-productions",
        },
        {"slug": "lapac", "label": "La Pac", "url": "https://lepac.us/"},
        {"slug": "netflix", "label": "Netflix", "url": "https://about.netflix.com/"},
        {"slug": "somesuch", "label": "Somesuch", "url": "https://somesuch.co/"},
        {"slug": "unite", "label": "Unité", "url": "https://unite-films.com/"},
    ]

    def require_admin_token():
        token = request.headers.get("X-Admin-Token")
        if not token or token != os.getenv("ADMIN_CACHE_TOKEN"):
            abort(403)

    @app.route("/launch")
    def launch():
        return render_template("launch.html")

    @app.route("/")
    def home():
        return render_template("home.html", brands=BRANDS)

    @app.route("/vehicles")
    def vehicles():
        return render_template("vehicles.html")

    @app.route("/heads")
    def heads():
        return render_template("heads.html")

    @app.route("/grips")
    def grips():
        return render_template("grips.html")

    @app.route("/vehicles/<slug>")
    def vehicle(slug):
        vehicle_data = get_vehicle_by_slug(slug)
        if not vehicle_data:
            abort(404)

        configs = get_configs_for_vehicle(vehicle_data["id"])
        grouped = defaultdict(list)
        for config in configs:
            type_name = config["fields"].get("type", "Sans type")
            grouped[type_name].append(config)

        specs_left, specs_right = build_specs(vehicle_data["fields"])

        return render_template(
            "vehicle.html",
            vehicle=vehicle_data,
            configs_grouped=dict(reversed(grouped.items())),
            specs_left=specs_left,
            specs_right=specs_right,
        )

    @app.route("/heads/<slug>")
    def head(slug):
        head_data = get_head_by_slug(slug)
        if not head_data:
            abort(404)

        specs_left, specs_right = build_specs(head_data["fields"])

        return render_template(
            "head.html",
            head=head_data,
            specs_left=specs_left,
            specs_right=specs_right,
        )

    @app.route("/grips/<slug>")
    def grip_products(slug):
        grips_category = get_grips_categories_by_slug(slug)
        if not grips_category:
            abort(404)
        grips_products = get_grips_products_for_category(grips_category["id"])
        return render_template(
            "grip.html",
            grips_category=grips_category,
            grips_products_by_category=grips_products,
        )

    @app.route("/about-us")
    def about_us():
        return render_template("about-us.html")

    @app.route("/contact")
    def contact():
        return render_template("contact.html")

    @app.route("/terms-and-conditions")
    def terms_and_conditions():
        return render_template("terms-and-conditions.html")

    @app.route("/subscribe", methods=["POST"])
    def subscribe():
        email = request.form.get("email")
        if not email:
            return jsonify({"status": "error", "message": "Email is required"}), 400

        email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(email_regex, email):
            return jsonify({"status": "error", "message": "Invalid email address"}), 400

        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        rate_key = f"rate_limit_{ip}"
        requests_count = cache.get(rate_key) or 0

        if requests_count >= 10:
            return jsonify(
                {
                    "status": "error",
                    "message": "Too many requests. Please try again later.",
                }
            ), 429

        cache.set(rate_key, requests_count + 1, timeout=3600)

        try:
            success = add_newsletter_subscriber(email)
            if not success:
                return jsonify(
                    {"status": "error", "message": "You are already subscribed!"}
                ), 400

            send_subscription_email(email)
            return jsonify(
                {"status": "success", "message": "Thank you for subscribing!"}
            ), 200

        except Exception as e:
            current_app.logger.error(f"Unexpected error: {e}")
            return jsonify(
                {"status": "error", "message": "An unexpected error occurred."}
            ), 500

    @app.route("/unsubscribe/<token>", methods=["GET", "POST"])
    def unsubscribe(token):
        secret_key = current_app.config.get("SECRET_KEY") or "bv_super_secret_key_2026"
        serializer = URLSafeSerializer(secret_key)
        try:
            email = serializer.loads(token)
        except Exception:
            if request.method == "POST":
                return jsonify({"status": "error", "message": "Invalid token"}), 400
            return render_template(
                "unsubscribe_confirmation.html",
                status="error",
                message="Invalid or expired unsubscribe link.",
            )

        if request.method == "POST":
            try:
                remove_newsletter_subscriber(email)
                return jsonify({"status": "success", "message": "Unsubscribed"}), 200
            except Exception as e:
                current_app.logger.error(
                    f"❌ Error during POST unsubscription ({email}): {e}"
                )
                return jsonify({"status": "error", "message": str(e)}), 500

        try:
            current_app.logger.info(f"🔎 Processing unsubscribe request for: {email}")
            removed = remove_newsletter_subscriber(email)
            current_app.logger.info(f"🗑️ Record removed: {removed}")
            return render_template(
                "unsubscribe_confirmation.html",
                status="success",
                message="You have been successfully unsubscribed from our newsletter.",
            )
        except Exception as e:
            current_app.logger.error(f"❌ Error during unsubscription ({email}): {e}")
            return render_template(
                "unsubscribe_confirmation.html",
                status="error",
                message="A server error occurred. Please try again later.",
            )

    @app.route("/admin/cache/clear", methods=["POST"])
    def clear_cache():
        require_admin_token()
        cache.clear()
        return jsonify({"status": "Cache cleared"}), 200

    @app.route("/admin/cache/clear/<key>", methods=["POST"])
    def clear_cache_key(key):
        require_admin_token()
        cache.delete(key)
        return jsonify({"status": f"Cache key {key} cleared"}), 200

    @app.route("/sitemap.xml")
    def sitemap():
        return send_from_directory(app.static_folder, "sitemap.xml")

    @app.route("/robots.txt")
    def robots():
        return send_from_directory(app.static_folder, "robots.txt")

    # ── Checkout Routes ──────────────────────────────────────────

    def require_checkout_token():
        token = request.headers.get("X-Checkout-Token")
        expected = os.getenv("SECRET_KEY")
        if not expected or token != expected:
            abort(403)

    @app.route("/checkout/<inspection_id>")
    def checkout_view(inspection_id):
        record = get_checkout_by_inspection_id(inspection_id)
        if not record:
            abort(404)
        data = format_checkout_data(record)
        return render_template(
            "checkout.html", data=data, signature=None, qr=None, hash=None
        )

    @app.route("/checkout/generate", methods=["POST"])
    def checkout_generate():
        require_checkout_token()
        payload = request.get_json(silent=True)
        if not payload or "record_id" not in payload:
            return jsonify({"error": "record_id is required"}), 400

        record = get_checkout_record(payload["record_id"])
        if not record:
            return jsonify({"error": "Record not found in Airtable"}), 404

        data = format_checkout_data(record)
        token = str(uuid.uuid4())

        token = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc)

        store_checkout_token(
            token=token,
            record_id=payload["record_id"],
            inspection_id=data["inspection_id"],
            created_at=created_at,
        )
        try:
            TABLE_CHECKOUT.update(
                payload["record_id"],
                {
                    "État du contrôle": "Terminé",
                },
            )
        except Exception as e:
            current_app.logger.error(
                f"❌ Failed to update Airtable for {data['inspection_id']}: {e}"
            )

        base_url = os.getenv("BASE_URL", "https://bellevitesse.com")
        return jsonify(
            {
                "status": "draft_ready",
                "inspection_id": data["inspection_id"],
                "token": token,
                "sign_url": f"{base_url}/checkout/sign/{token}",
            }
        ), 201

    @app.route("/checkout/sign/<token>", methods=["GET"])
    def checkout_sign_page(token):
        entry = get_checkout_token(token)
        if not entry:
            abort(404)

        # Handle timezone for expiry check
        created_at = entry["created_at"]
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) - created_at > timedelta(hours=24):
            delete_checkout_token(token)
            abort(410)

        if entry["signature"]:
            abort(400)

        record = get_checkout_record(entry["record_id"])
        if not record:
            abort(404)
        data = format_checkout_data(record)
        return render_template("checkout_sign.html", data=data, token=token)

    @app.route("/checkout/sign/<token>", methods=["POST"])
    def checkout_submit_signature(token):
        entry = get_checkout_token(token)
        if not entry:
            return jsonify({"error": "Invalid or expired token"}), 404

        # Check expiry (safety double-check)
        created_at = entry["created_at"]
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) - created_at > timedelta(hours=24):
            delete_checkout_token(token)
            return jsonify({"error": "Token expired"}), 410

        if entry["signature"]:
            return jsonify({"error": "Already signed"}), 400

        payload = request.get_json(silent=True)
        if not payload or "signature" not in payload:
            return jsonify({"error": "signature data is required"}), 400

        signature_data = payload["signature"]
        record_id = entry["record_id"]
        inspection_id = entry["inspection_id"]
        signed_at = datetime.now(timezone.utc).isoformat()
        signed_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

        # 1. Update entry state in DB (mark as signed) and Airtable
        update_checkout_token_signature(token, signature_data)

        try:
            TABLE_CHECKOUT.update(
                record_id,
                {
                    "État du contrôle": "Signé",
                },
            )
        except Exception as e:
            current_app.logger.error(
                f"❌ Failed to update Airtable for {inspection_id}: {e}"
            )

        # 2. Prepare Data for PDF
        record = get_checkout_record(record_id)
        if not record:
            return jsonify({"error": "Record not found"}), 404

        data = format_checkout_data(record)
        # Inject signature metadata into data dict for template context if needed
        data["signed_at"] = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")
        data["signed_ip"] = signed_ip

        # 3. Compute Digital Seal (Hash of critical data + signature)
        # We use a string representation of the key data to freeze the state
        seal_content = f"{inspection_id}|{data['vehicle']}|{data['km']}|{signature_data}|{signed_at}"
        current_hash = hashlib.sha256(seal_content.encode("utf-8")).hexdigest()

        # 4. Generate QR Code
        base_url = os.getenv("BASE_URL", "https://bellevitesse.com")
        verification_url = f"{base_url}/checkout/verify/{inspection_id}"
        qr_code_img = generate_qr_code(verification_url)

        # 5. Render HTML & Generate PDF
        html_content = render_template(
            "checkout.html",
            data=data,
            signature=signature_data,
            qr=qr_code_img,
            hash=current_hash,
        )
        pdf_bytes = generate_checkout_pdf(html_content, base_url=base_url)

        # 6. Save PDF Privately
        filename = f"{inspection_id}_{current_hash[:8]}.pdf"
        private_folder = current_app.config.get("PRIVATE_FOLDER")

        file_path = os.path.join(private_folder, "checkout_pdfs", filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(pdf_bytes)

        # 7. Update Airtable
        pdf_public_url = f"{base_url}/checkout/document/{filename}"

        # 8. Store immutable snapshot in MySQL
        store_success = store_signed_document(
            inspection_id=inspection_id,
            file_hash=current_hash,
            data_snapshot=data,
            signature=signature_data,
            pdf_url=pdf_public_url,
            signed_at=datetime.now(timezone.utc),
        )
        if store_success:
            current_app.logger.info(f"✅ Document {inspection_id} frozen in MySQL.")
        else:
            current_app.logger.error(
                f"❌ Failed to freeze document {inspection_id} in MySQL."
            )

        try:
            TABLE_CHECKOUT.update(
                record_id,
                {
                    "État du contrôle": "Signé",
                    "PDF scellé": pdf_public_url,
                    "Hash": current_hash,
                },
            )
        except Exception as e:
            current_app.logger.error(
                f"❌ Failed to update Airtable for {inspection_id}: {e}"
            )
            # We don't fail the request, but we log the error. The PDF is generated.

        current_app.logger.info(
            f"✅ Signature processed for {inspection_id}. PDF saved at {file_path}"
        )

        # 9. Trigger n8n webhook
        try:
            n8n_webhook_url = os.getenv("N8N_WEBHOOK_CHECKOUT_SIGN")
            if n8n_webhook_url:
                payload = {
                    "inspection_id": inspection_id,
                    "pdf_url": pdf_public_url,
                    "hash": current_hash,
                }
                response = requests.post(n8n_webhook_url, json=payload)
                if response.status_code == 200:
                    current_app.logger.info(
                        f"✅ n8n webhook triggered for {inspection_id}"
                    )
                else:
                    current_app.logger.error(
                        f"❌ Failed to trigger n8n webhook for {inspection_id}: {response.status_code}"
                    )
        except Exception as e:
            current_app.logger.error(
                f"❌ Failed to trigger n8n webhook for {inspection_id}: {e}"
            )

        # Cleanup token from DB
        delete_checkout_token(token)

        return jsonify(
            {
                "status": "signed",
                "inspection_id": inspection_id,
                "pdf_url": pdf_public_url,
                "hash": current_hash,
            }
        ), 200

    @app.route("/checkout/verify/<inspection_id>")
    def checkout_verify(inspection_id):
        # 1. Try to get from MySQL (Immutable Source of Truth)
        signed_doc = get_signed_document(inspection_id)

        if signed_doc:
            # Trusted data from database
            data = signed_doc["data_snapshot"]
            # Ensure hash and PDF url are from the trusted record
            data["hash"] = signed_doc["hash"]
            data["pdf_url"] = signed_doc["pdf_url"]
            # We can flag it as "Certified"
            return render_template(
                "checkout_verify.html", data=data, valid=True, source="mysql"
            )

        # 2. Fallback to Airtable (Live data - potentially mutable)
        record = get_checkout_by_inspection_id(inspection_id)
        if not record:
            abort(404)

        data = format_checkout_data(record)
        # Warning: Source is Airtable
        return render_template(
            "checkout_verify.html", data=data, valid=True, source="airtable"
        )

    @app.route("/checkout/document/<filename>")
    def download_checkout_document(filename):
        """Serve secure checkout document."""
        private_folder = current_app.config.get("PRIVATE_FOLDER")
        directory = os.path.join(private_folder, "checkout_pdfs")

        try:
            return send_from_directory(directory, filename)
        except Exception:
            abort(404)


def init_error_handlers(app):
    if os.getenv("FLASK_ENV") == "production":

        @app.errorhandler(HTTPException)
        def handle_http_exception(e):
            return render_template(
                "error.html",
                error_title=f"{e.code} - {e.name}",
                error_message=e.description,
            ), e.code

        @app.errorhandler(Exception)
        def handle_exception(e):
            return render_template(
                "error.html",
                error_title="500 - Internal Server Error",
                error_message="An unexpected error occurred.",
            ), 500
