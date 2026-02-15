import requests
import os
import re
import uuid
import secrets
import hmac
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
    compute_document_seal,
    verify_document_seal,
    compute_pdf_hash,
    verify_pdf_hash,
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


def init_routes(app):
    BRANDS = [
        {"slug": "academy", "label": "Academy",
            "url": "https://www.academyfilms.com/"},
        {
            "slug": "antiestatico",
            "label": "Antiestatico",
            "url": "https://antiestatico.com/",
        },
        {"slug": "biscuit", "label": "Biscuit",
            "url": "https://biscuitfilmworks.com/"},
        {"slug": "canal", "label": "Canal+",
            "url": "https://www.canalplusgroup.com/"},
        {
            "slug": "chifoumi",
            "label": "Chi-fou-mi",
            "url": "https://www.unifrance.org/annuaires/societe/351840/chi-fou-mi-productions",
        },
        {"slug": "lapac", "label": "La Pac", "url": "https://lepac.us/"},
        {"slug": "netflix", "label": "Netflix",
            "url": "https://about.netflix.com/"},
        {"slug": "somesuch", "label": "Somesuch", "url": "https://somesuch.co/"},
        {"slug": "unite", "label": "Unité", "url": "https://unite-films.com/"},
    ]

    # ── Admin Auth ────────────────────────────────────────────────

    def require_admin_token():
        """Guard for admin routes. Uses a dedicated ADMIN_CACHE_TOKEN env var."""
        token = request.headers.get("X-Admin-Token")
        if not token or token != os.getenv("ADMIN_CACHE_TOKEN"):
            abort(403)

    # ── Checkout Auth ─────────────────────────────────────────────

    def require_checkout_token():
        """
        Guard for the /checkout/generate endpoint.

        Uses CHECKOUT_API_TOKEN — a dedicated secret, separate from Flask's SECRET_KEY.
        Generate with: python -c "import secrets; print(secrets.token_hex(32))"
        Add to your .env: CHECKOUT_API_TOKEN=<generated_value>

        ⚠️  Do NOT reuse SECRET_KEY here: Flask's SECRET_KEY signs sessions and cookies.
        Exposing it via an API route enlarges the attack surface significantly.
        """
        token = request.headers.get("X-Checkout-Token")
        expected = os.getenv("CHECKOUT_API_TOKEN")
        if not expected:
            current_app.logger.error(
                "❌ CHECKOUT_API_TOKEN is not set. Set it in your .env file."
            )
            abort(500)
        if not token or not secrets.compare_digest(token, expected):
            abort(403)

    # ── PDF Access Auth ───────────────────────────────────────────

    def _validate_pdf_access_token(filename: str, provided_token: str) -> bool:
        """
        Validate a time-limited, HMAC-signed access token for a PDF filename.

        The token is produced by generate_pdf_access_token() and encodes:
          {filename}:{timestamp_utc_minutes}
        signed with HASH_SECRET_KEY via HMAC-SHA256.

        Tokens are valid for PDF_ACCESS_TOKEN_TTL_MINUTES (default: 60 minutes).
        """

        secret = os.getenv("HASH_SECRET_KEY", "").encode("utf-8")
        ttl = int(os.getenv("PDF_ACCESS_TOKEN_TTL_MINUTES", "60"))
        now_minutes = int(datetime.now(timezone.utc).timestamp() // 60)

        # Accept tokens for the current and any window within TTL
        for delta in range(ttl + 1):
            ts = now_minutes - delta
            payload = f"{filename}:{ts}".encode("utf-8")
            expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
            if hmac.compare_digest(expected, provided_token):
                return True
        return False

    # ── Standard Routes ───────────────────────────────────────────

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
        secret_key = current_app.config.get(
            "SECRET_KEY") or "bv_super_secret_key_2026"
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
            current_app.logger.info(
                f"🔎 Processing unsubscribe request for: {email}")
            removed = remove_newsletter_subscriber(email)
            current_app.logger.info(f"🗑️ Record removed: {removed}")
            return render_template(
                "unsubscribe_confirmation.html",
                status="success",
                message="You have been successfully unsubscribed from our newsletter.",
            )
        except Exception as e:
            current_app.logger.error(
                f"❌ Error during unsubscription ({email}): {e}")
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

    # ── Checkout Routes ───────────────────────────────────────────

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
        """
        Protected endpoint: creates a one-time signing token for an inspection record.
        Requires X-Checkout-Token header matching CHECKOUT_API_TOKEN env var.
        """
        require_checkout_token()
        payload = request.get_json(silent=True)
        if not payload or "record_id" not in payload:
            return jsonify({"error": "record_id is required"}), 400

        record = get_checkout_record(payload["record_id"])
        if not record:
            return jsonify({"error": "Record not found in Airtable"}), 404

        data = format_checkout_data(record)
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
                {"État du contrôle": "Terminé"},
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

        # 1. Mark token as used in DB + update Airtable status
        update_checkout_token_signature(token, signature_data)

        try:
            TABLE_CHECKOUT.update(record_id, {"État du contrôle": "Signé"})
        except Exception as e:
            current_app.logger.error(
                f"❌ Failed to update Airtable for {inspection_id}: {e}"
            )

        # 2. Fetch fresh record for PDF generation
        record = get_checkout_record(record_id)
        if not record:
            return jsonify({"error": "Record not found"}), 404

        data = format_checkout_data(record)
        data["signed_at"] = datetime.now(
            timezone.utc).strftime("%d/%m/%Y %H:%M")
        data["signed_ip"] = signed_ip

        # 3. Compute HMAC-SHA256 digital seal
        #    Uses vehicle_id (stable Airtable record ID) instead of str(data['vehicle'])
        #    to guarantee a reproducible, canonical hash.
        current_hash = compute_document_seal(
            inspection_id=inspection_id,
            vehicle_id=data["vehicle_id"],
            km=str(data["km"]),
            signature_data=signature_data,
            signed_at=signed_at,
        )

        # 4. Generate QR Code pointing to the verification page
        base_url = os.getenv("BASE_URL", "https://bellevitesse.com")
        verification_url = f"{base_url}/checkout/verify/{inspection_id}"
        qr_code_img = generate_qr_code(verification_url)

        # 5. Render HTML & generate PDF
        html_content = render_template(
            "checkout.html",
            data=data,
            signature=signature_data,
            qr=qr_code_img,
            hash=current_hash,
        )
        pdf_bytes = generate_checkout_pdf(html_content, base_url=base_url)

        # 6. Save PDF — filename includes a 16-char random token (not just hash prefix)
        #    to prevent enumeration/brute-force of the download URL.
        random_token = secrets.token_hex(8)  # 16 hex chars, 64-bit entropy
        filename = f"{inspection_id}_{random_token}.pdf"
        private_folder = current_app.config.get("PRIVATE_FOLDER")
        file_path = os.path.join(private_folder, "checkout_pdfs", filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(pdf_bytes)

        # 7. Build the public PDF URL (access is protected by time-limited token — see route below)
        pdf_public_url = f"{base_url}/checkout/document/{filename}"

        # 8. Store immutable snapshot in MySQL (source of truth for verification)
        #    We store:
        #      - current_hash   : HMAC seal over critical fields (proves data integrity)
        #      - pdf_file_hash  : SHA-256 of the raw PDF binary (proves file integrity)
        #    Both are needed to fully verify a document presented later.
        pdf_file_hash = compute_pdf_hash(pdf_bytes)

        store_success = store_signed_document(
            inspection_id=inspection_id,
            file_hash=current_hash,
            pdf_file_hash=pdf_file_hash,
            data_snapshot={
                **data,
                # Persist the exact scalar values used in seal computation
                "_seal_vehicle_id": data["vehicle_id"],
                "_seal_km": str(data["km"]),
                "_seal_signed_at": signed_at,
            },
            signature=signature_data,
            pdf_url=pdf_public_url,
            signed_at=datetime.now(timezone.utc),
        )
        if store_success:
            current_app.logger.info(
                f"✅ Document {inspection_id} frozen in MySQL.")
        else:
            current_app.logger.error(
                f"❌ Failed to freeze document {inspection_id} in MySQL."
            )

        # 9. Update Airtable with hash and PDF URL
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

        current_app.logger.info(
            f"✅ Signature processed for {inspection_id}. PDF saved at {file_path}"
        )

        # 10. Trigger n8n webhook
        try:
            n8n_webhook_url = os.getenv("N8N_WEBHOOK_CHECKOUT_SIGN")
            secret = os.getenv("HASH_SECRET_KEY").encode()
            ts = int(datetime.now(timezone.utc).timestamp() // 60)
            token_payload = f"{filename}:{ts}".encode()
            token_n8n = hmac.new(secret, token_payload,
                                 hashlib.sha256).hexdigest()
            pdf_url_signed = f"{base_url}/checkout/document/{filename}?t={token_n8n}"

            if n8n_webhook_url:
                # Parse year/month from control_date (format: "16 février 2026")
                _date_parts = data.get("control_date", "").split()
                _year = _date_parts[2] if len(_date_parts) >= 3 else "—"
                _month_name = _date_parts[1].lower() if len(
                    _date_parts) >= 3 else ""

                _MOIS_NUM = {
                    "janvier": "01", "février": "02", "mars": "03",
                    "avril": "04", "mai": "05", "juin": "06",
                    "juillet": "07", "août": "08", "septembre": "09",
                    "octobre": "10", "novembre": "11", "décembre": "12",
                }
                _month = _MOIS_NUM.get(_month_name, "—")

                webhook_payload = {
                    "inspection_id": inspection_id,
                    "pdf_url": pdf_url_signed,
                    "hash": current_hash,
                    "production": data.get("production", "—"),
                    "project": data.get("project", "—"),
                    "control_date": data.get("control_date", "—"),
                    "year": _year,
                    "month": _month,
                }
                response = requests.post(n8n_webhook_url, json=webhook_payload)
                if response.status_code == 200:
                    current_app.logger.info(
                        f"✅ n8n webhook triggered for {inspection_id}"
                    )
                else:
                    current_app.logger.error(
                        f"❌ n8n webhook failed for {inspection_id}: {response.status_code}"
                    )
        except Exception as e:
            current_app.logger.error(
                f"❌ n8n webhook exception for {inspection_id}: {e}"
            )

        # 11. Invalidate one-time token
        delete_checkout_token(token)

        return jsonify(
            {
                "status": "signed",
                "inspection_id": inspection_id,
                "pdf_url": pdf_public_url,
                "hash": current_hash,
            }
        ), 200

    @app.route("/checkout/verify/<inspection_id>", methods=["GET", "POST"])
    def checkout_verify(inspection_id):
        """
        Verify the integrity of a signed checkout document.

        GET  → displays the inspection data from MySQL with a PDF upload form
        POST → receives the uploaded PDF, recomputes its SHA-256, and compares
               to the hash stored at signing time

        Two-level verification:
          1. HMAC seal  — proves the inspection data fields were not altered in DB
          2. PDF hash   — proves the exact file presented is the one that was signed
        """
        signed_doc = get_signed_document(inspection_id)

        # ── No MySQL snapshot → cannot verify ────────────────────
        if not signed_doc:
            record = get_checkout_by_inspection_id(inspection_id)
            if not record:
                abort(404)
            data = format_checkout_data(record)
            current_app.logger.warning(
                f"⚠️ Verify fallback to Airtable for {inspection_id} — no MySQL snapshot."
            )
            return render_template(
                "checkout_verify.html",
                data=data,
                seal_valid=False,
                pdf_valid=None,
                source="airtable",
                inspection_id=inspection_id,
            )

        # ── Retrieve stored values ────────────────────────────────
        data = signed_doc["data_snapshot"]
        stored_hash = signed_doc["hash"]
        stored_signature = signed_doc["signature"]
        stored_pdf_file_hash = signed_doc.get("pdf_file_hash")

        seal_vehicle_id = data.get(
            "_seal_vehicle_id", data.get("vehicle_id", "—"))
        seal_km = data.get("_seal_km", str(data.get("km", "")))
        seal_signed_at = data.get("_seal_signed_at", "")

        # ── 1. Verify HMAC seal (data integrity) ─────────────────
        seal_valid = verify_document_seal(
            inspection_id=inspection_id,
            vehicle_id=seal_vehicle_id,
            km=seal_km,
            signature_data=stored_signature,
            signed_at=seal_signed_at,
            expected_hash=stored_hash,
        )
        if not seal_valid:
            current_app.logger.warning(
                f"⚠️ Seal mismatch for {inspection_id} — data may have been tampered with."
            )

        data["hash"] = stored_hash
        data["pdf_url"] = signed_doc["pdf_url"]

        # ── GET → show data + upload form ─────────────────────────
        if request.method == "GET":
            return render_template(
                "checkout_verify.html",
                data=data,
                seal_valid=seal_valid,
                pdf_valid=None,  # Not yet checked — waiting for upload
                source="mysql",
                inspection_id=inspection_id,
                has_pdf_hash=bool(stored_pdf_file_hash),
            )

        # ── POST → verify uploaded PDF ────────────────────────────
        uploaded_file = request.files.get("pdf")
        if not uploaded_file:
            return render_template(
                "checkout_verify.html",
                data=data,
                seal_valid=seal_valid,
                pdf_valid=None,
                pdf_error="Aucun fichier reçu.",
                source="mysql",
                inspection_id=inspection_id,
                has_pdf_hash=bool(stored_pdf_file_hash),
            )

        if not uploaded_file.filename.lower().endswith(".pdf"):
            return render_template(
                "checkout_verify.html",
                data=data,
                seal_valid=seal_valid,
                pdf_valid=None,
                pdf_error="Le fichier doit être un PDF.",
                source="mysql",
                inspection_id=inspection_id,
                has_pdf_hash=bool(stored_pdf_file_hash),
            )

        if not stored_pdf_file_hash:
            # Document was signed before pdf_file_hash was introduced
            return render_template(
                "checkout_verify.html",
                data=data,
                seal_valid=seal_valid,
                pdf_valid=None,
                pdf_error="Ce document a été signé avant l'introduction de la vérification PDF. Seul le sceau de données est disponible.",
                source="mysql",
                inspection_id=inspection_id,
                has_pdf_hash=False,
            )

        # Read uploaded bytes and verify hash
        uploaded_bytes = uploaded_file.read()
        pdf_valid = verify_pdf_hash(uploaded_bytes, stored_pdf_file_hash)

        if not pdf_valid:
            current_app.logger.warning(
                f"⚠️ PDF hash mismatch for {inspection_id} — uploaded file differs from signed original."
            )
        else:
            current_app.logger.info(
                f"✅ PDF verified for {inspection_id} — file matches signed original."
            )

        return render_template(
            "checkout_verify.html",
            data=data,
            seal_valid=seal_valid,
            pdf_valid=pdf_valid,
            source="mysql",
            inspection_id=inspection_id,
            has_pdf_hash=True,
        )

    @app.route("/checkout/document/<filename>")
    def download_checkout_document(filename):
        """
        Serve a signed checkout PDF.

        Access is protected by a time-limited HMAC token passed as ?t=<token>.
        Without a valid token the file is not served — prevents enumeration of filenames.

        To generate a valid access token server-side:
            import hmac, hashlib, time
            secret = os.getenv("HASH_SECRET_KEY").encode()
            ts = int(time.time() // 60)
            payload = f"{filename}:{ts}".encode()
            token = hmac.new(secret, payload, hashlib.sha256).hexdigest()
            url = f"/checkout/document/{filename}?t={token}"
        """
        access_token = request.args.get("t", "")

        # Reject requests without a valid time-limited access token
        if not access_token or not _validate_pdf_access_token(filename, access_token):
            abort(403)

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
