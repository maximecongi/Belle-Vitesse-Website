import os
import re

from flask import (
    render_template,
    abort,
    jsonify,
    request,
    current_app,
    send_from_directory,
    redirect,
    url_for
)
from itsdangerous import URLSafeSerializer
from collections import defaultdict

from extensions import cache, csrf
from utils.specs import build_specs
from utils.airtable import (
    get_grips_products_for_category,
    get_grips_categories_by_slug,
    get_vehicle_by_slug,
    get_head_by_slug,
    get_configs_for_vehicle,
)
from services.newsletter import (
    add_newsletter_subscriber,
    remove_newsletter_subscriber,
)


def init_web_routes(app):
    """Public website routes: pages, newsletter, cache, sitemap."""

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

    # ── Admin Auth Guard (for cache endpoints) ────────────────────

    def require_admin_token():
        """Guard for admin cache routes. Uses ADMIN_CACHE_TOKEN env var."""
        token = request.headers.get("X-Admin-Token")
        if not token or token != os.getenv("ADMIN_CACHE_TOKEN"):
            abort(403)

    # ── Pages ─────────────────────────────────────────────────────

    @app.before_request
    def redirect_to_launch():
        if os.getenv("LAUNCH_MODE") == "true" \
                and request.endpoint != 'launch' \
                and not request.path.startswith('/static') \
                and not request.path.startswith('/subscribe') \
                and not request.path.startswith('/unsubscribe') \
                and not request.path.startswith('/admin'):
            return redirect(url_for('launch'))

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

    # ── Newsletter ────────────────────────────────────────────────

    @app.route("/subscribe", methods=["POST"])
    @csrf.exempt
    def subscribe():
        from utils.mailer import send_subscription_email
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

    # ── Cache Management ──────────────────────────────────────────

    @app.route("/admin/cache/clear", methods=["POST"])
    @csrf.exempt
    def clear_cache():
        require_admin_token()
        cache.clear()
        return jsonify({"status": "Cache cleared"}), 200

    @app.route("/admin/cache/clear/<key>", methods=["POST"])
    @csrf.exempt
    def clear_cache_key(key):
        require_admin_token()
        cache.delete(key)
        return jsonify({"status": f"Cache key {key} cleared"}), 200

    # ── SEO ───────────────────────────────────────────────────────

    @app.route("/sitemap.xml")
    def sitemap():
        return send_from_directory(app.static_folder, "sitemap.xml")

    @app.route("/robots.txt")
    def robots():
        return send_from_directory(app.static_folder, "robots.txt")
