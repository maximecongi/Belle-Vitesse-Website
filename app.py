# imports
import os
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
from utils.airtable import (
    init_cache,
    get_vehicles,
    get_heads,
    get_supports,
    get_vehicle_by_slug,
    get_head_by_slug,
    get_support_by_slug,
    get_configs_for_vehicle,
)

# -------------------------------------------------
# App config
# -------------------------------------------------

app = Flask(
    __name__,
    static_folder=os.getenv("STATIC_FOLDER"),
    static_url_path=os.getenv("STATIC_URL_PATH"),
)

# -------------------------------------------------
# Cache config
# -------------------------------------------------
def warm_cache():
    try:
        get_vehicles()
        get_heads()
        get_supports()
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
        "supports": get_supports(),
        "now": datetime.now(timezone.utc)
    }

# -------------------------------------------------
# Routes
# -------------------------------------------------

@app.route("/")
def home():
    return render_template("home.html")


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


@app.route("/supports")
def supports():
    return render_template("supports.html")


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


@app.route("/supports/<slug>")
def support(slug):
    support = get_support_by_slug(slug)
    if not support:
        abort(404)

    specs_left, specs_right = build_specs(support["fields"])

    return render_template(
        "support.html",
        support=support,
        specs_left=specs_left,
        specs_right=specs_right,
    )


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
        app.run(use_reloader=True)
