from itsdangerous import URLSafeSerializer
from collections import defaultdict
from flask import (
    Flask,
    render_template,
    abort,
    jsonify,
    request,
)
from werkzeug.exceptions import HTTPException
from flask_caching import Cache
from datetime import datetime, timezone

from utils.specs import build_specs
from utils.database import (
    init_cache,
    get_vehicles,
    get_static_by_lang,
    get_heads,
    get_grips_categories,
    get_grips_products_for_category,
    get_grips_categories_by_slug,
    get_vehicle_by_slug,
    get_head_by_slug,
    get_configs_for_vehicle,
    add_newsletter_subscriber,
    remove_newsletter_subscriber,
)
from utils.mailer import send_subscription_email

import os
import re

# -------------------------------------------------
# App config
# -------------------------------------------------

app = Flask(
    __name__,
    static_folder=os.getenv("STATIC_FOLDER"),
    static_url_path=os.getenv("STATIC_URL_PATH"),
)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "bv_super_secret_key_2026")
# -------------------------------------------------
# Cache config
# -------------------------------------------------


def warm_cache():
    try:
        get_vehicles()
        get_heads()
        get_grips_categories()
        get_static_by_lang("en")
        app.logger.info("🔥 Cache warmé avec succès")
    except Exception as e:
        app.logger.error(f"❌ Erreur warm cache : {e}")


cache = Cache()

if os.getenv("FLASK_ENV") == "production":
    app.config["CACHE_TYPE"] = "SimpleCache"
else:
    app.config["CACHE_TYPE"] = "SimpleCache"

app.config["CACHE_DEFAULT_TIMEOUT"] = 3600
app.config["CACHE_KEY_PREFIX"] = "myapp_"

cache.init_app(app)

# 🔌 Brancher le cache au service Airtable
init_cache(cache)

if os.getenv("FLASK_ENV") == "production":
    warm_cache()

# -------------------------------------------------
# Gestion des tokens admin
# -------------------------------------------------


def require_admin_token():
    token = request.headers.get("X-Admin-Token")
    if not token or token != os.getenv("ADMIN_CACHE_TOKEN"):
        abort(403)

# -------------------------------------------------
# Context processor (footer global)
# -------------------------------------------------


@app.context_processor
def inject_globals():
    return {
        "vehicles": get_vehicles(),
        "heads": get_heads(),
        "grips_categories": get_grips_categories(),
        "static": get_static_by_lang("en"),
        "now": datetime.now(timezone.utc)
    }


BRANDS = [
    {"slug": "academy", "label": "Academy", "url": "https://www.academyfilms.com/"},
    {"slug": "antiestatico", "label": "Antiestatico",
        "url": "https://antiestatico.com/"},
    {"slug": "biscuit", "label": "Biscuit", "url": "https://biscuitfilmworks.com/"},
    {"slug": "canal", "label": "Canal+", "url": "https://www.canalplusgroup.com/"},
    {"slug": "chifoumi", "label": "Chi-fou-mi",
        "url": "https://www.unifrance.org/annuaires/societe/351840/chi-fou-mi-productions"},
    {"slug": "lapac", "label": "La Pac", "url": "https://lepac.us/"},
    {"slug": "netflix", "label": "Netflix", "url": "https://about.netflix.com/"},
    {"slug": "somesuch", "label": "Somesuch", "url": "https://somesuch.co/"},
    {"slug": "unite", "label": "Unité", "url": "https://unite-films.com/"},
]

# -------------------------------------------------
# Filtres custom Jinja2
# -------------------------------------------------

app.jinja_env.filters['slugify'] = lambda s: s.lower().replace(" ", "_")


# -------------------------------------------------
# Routes
# -------------------------------------------------

@app.route("/")
def home():
    return render_template("home.html", brands=BRANDS)


@app.route("/launch")
def launch():
    return render_template("launch.html")


if os.getenv("FLASK_ENV") == "production":
    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        return render_template("error.html", error_title=f"{e.code} - {e.name}", error_message=e.description), e.code

    @app.errorhandler(Exception)
    def handle_exception(e):
        return render_template("error.html", error_title="500 - Internal Server Error", error_message="An unexpected error occurred."), 500

# -----------------------
# Lists
# -----------------------


@app.route("/vehicles")
def vehicles():
    return render_template("vehicles.html")


@app.route("/heads")
def heads():
    return render_template("heads.html")


@app.route("/grips")
def grips():
    return render_template("grips.html")


# -----------------------
# Details
# -----------------------

@app.route("/vehicles/<slug>")
def vehicle(slug):
    vehicle = get_vehicle_by_slug(slug)
    if not vehicle:
        abort(404)

    configs = get_configs_for_vehicle(vehicle["id"])

    grouped = defaultdict(list)
    for config in configs:
        type_name = config["fields"].get("type", "Sans type")
        grouped[type_name].append(config)

    specs_left, specs_right = build_specs(vehicle["fields"])

    return render_template(
        "vehicle.html",
        vehicle=vehicle,
        configs_grouped=dict(reversed(grouped.items())),
        specs_left=specs_left,
        specs_right=specs_right,
    )


@app.route("/heads/<slug>")
def head(slug):
    head = get_head_by_slug(slug)
    if not head:
        abort(404)

    specs_left, specs_right = build_specs(head["fields"])

    return render_template(
        "head.html",
        head=head,
        specs_left=specs_left,
        specs_right=specs_right,
    )


@app.route("/grips/<slug>")
def grip_products(slug):
    grips_category = get_grips_categories_by_slug(slug)
    if not grips_category:
        abort(404)
    grips_products = get_grips_products_for_category(grips_category["id"])
    return render_template("grip.html", grips_category=grips_category, grips_products_by_category=grips_products)

# -----------------------
# Static pages
# -----------------------


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

    # 1. Email Pattern Validation
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    if not re.match(email_regex, email):
        return jsonify({"status": "error", "message": "Invalid email address"}), 400

    # 2. Rate Limiting (IP based, 10 requests per hour)
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    rate_key = f"rate_limit_{ip}"
    requests_count = cache.get(rate_key) or 0

    if requests_count >= 10:
        return jsonify({"status": "error", "message": "Too many requests. Please try again later."}), 429

    cache.set(rate_key, requests_count + 1, timeout=3600)

    try:
        success = add_newsletter_subscriber(email)
        if not success:
            return jsonify({"status": "error", "message": "You are already subscribed!"}), 400

        # Send welcome email
        send_subscription_email(email)

        return jsonify({"status": "success", "message": "Thank you for subscribing!"}), 200

    except Exception as e:
        app.logger.error(f"Unexpected error: {e}")
        return jsonify({"status": "error", "message": "An unexpected error occurred."}), 500


@app.route("/unsubscribe/<token>", methods=["GET", "POST"])
def unsubscribe(token):
    secret_key = app.config.get("SECRET_KEY") or "bv_super_secret_key_2026"
    serializer = URLSafeSerializer(secret_key)
    try:
        email = serializer.loads(token)
    except Exception:
        if request.method == "POST":
            return jsonify({"status": "error", "message": "Invalid token"}), 400
        return render_template("unsubscribe_confirmation.html", status="error", message="Invalid or expired unsubscribe link.")

    # RFC 8058: One-Click Unsubscribe via POST
    if request.method == "POST":
        try:
            remove_newsletter_subscriber(email)
            return jsonify({"status": "success", "message": "Unsubscribed"}), 200
        except Exception as e:
            app.logger.error(f"❌ Error during POST unsubscription ({email}): {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    try:
        # Log for debugging
        app.logger.info(f"🔎 Processing unsubscribe request for: {email}")

        # Delete subscriber
        removed = remove_newsletter_subscriber(email)
        
        app.logger.info(f"🗑️ Record removed: {removed}")

        return render_template("unsubscribe_confirmation.html", status="success", message="You have been successfully unsubscribed from our newsletter.")

    except Exception as e:
        app.logger.error(f"❌ Error during unsubscription ({email}): {e}")
        return render_template("unsubscribe_confirmation.html", status="error", message="A server error occurred. Please try again later.")

# -------------------------------------------------
# Cache management
# -------------------------------------------------

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


# -------------------------------------------------
# Run
# -------------------------------------------------
if __name__ == "__main__":
    if os.getenv("FLASK_ENV") == "production":
        app.run()
    else:
        app.config["TEMPLATES_AUTO_RELOAD"] = True
        app.run(debug=True, use_reloader=True, port=5001)
