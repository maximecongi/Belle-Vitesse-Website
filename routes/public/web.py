import os
import re
from collections import defaultdict

from flask import (
    abort,
    current_app,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from itsdangerous import URLSafeSerializer

from extensions import cache, csrf
from services.public.newsletter import (
    add_newsletter_subscriber,
    remove_newsletter_subscriber,
)
from utils.database import (
    get_configs_for_vehicle,
    get_grips_categories_by_slug,
    get_grips_products_for_category,
    get_head_by_slug,
    get_vehicle_by_slug,
)
from utils.specs import build_specs

SUPPORTED_LANGS = ('en', 'fr')
DEFAULT_LANG = 'en'


def init_web_routes(app):
    """Routes publiques du site : pages, newsletter, cache, sitemap."""

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

    # ── Protection Admin (pour les endpoints du cache) ─────────────

    def require_admin_token():
        """Protection pour les routes de cache admin. Utilise ADMIN_CACHE_TOKEN."""
        token = request.headers.get("X-Admin-Token")
        if not token or token != os.getenv("ADMIN_CACHE_TOKEN"):
            abort(403)

    # ── Redirection racine ────────────────────────────────────────

    @app.route("/")
    def root():
        """Redirige / selon : 1) session, 2) langue du navigateur (Accept-Language), 3) défaut."""
        from flask import session
        # 1. Vérifie la session
        saved_lang = session.get('lang')
        if saved_lang in SUPPORTED_LANGS:
            return redirect(url_for('home', lang=saved_lang), code=302)

        # 2. Détecte la langue du navigateur
        best = request.accept_languages.best_match(
            SUPPORTED_LANGS, default=DEFAULT_LANG)
        return redirect(url_for('home', lang=best), code=302)

    @app.before_request
    def redirect_to_launch():
        if os.getenv("LAUNCH_MODE") == "true" \
                and request.endpoint not in ('launch', 'privacy_policy', 'terms_and_conditions') \
                and not request.path.startswith('/static') \
                and not request.path.startswith('/subscribe') \
                and not request.path.startswith('/unsubscribe') \
                and not request.path.startswith('/admin') \
                and not request.path.startswith('/verify/') \
                and not request.path.startswith('/sign/') \
                and not request.path.startswith('/pilot-waiver/') \
                and not request.path.startswith('/production-waiver/'):
            return redirect(url_for('launch'))

    # ── Pages (toutes préfixées par /<lang>/) ──────────────────────

    @app.route("/launch")
    def launch():
        if os.getenv("LAUNCH_MODE") != "true":
            return redirect(url_for('root'))
        return render_template("public/launch.html")

    @app.route("/<lang>/")
    def home():
        return render_template("public/home.html", brands=BRANDS)

    @app.route("/<lang>/vehicles")
    def vehicles():
        return render_template("public/vehicles.html")

    @app.route("/<lang>/heads")
    def heads():
        return render_template("public/heads.html")

    @app.route("/<lang>/grips")
    def grips():
        return render_template("public/grips.html")

    @app.route("/<lang>/vehicles/<slug>")
    def vehicle(slug):
        vehicle_data = get_vehicle_by_slug(slug)
        if not vehicle_data:
            abort(404)

        configs = get_configs_for_vehicle(vehicle_data["id"])
        grouped = defaultdict(list)
        for config in configs:
            type_name = config["fields"].get("type", "Sans type")
            grouped[type_name].append(config)

        for type_name in grouped:
            grouped[type_name].sort(key=lambda c: c["fields"].get("order", 0))

        specs = build_specs(vehicle_data["fields"])

        return render_template(
            "public/vehicle.html",
            vehicle=vehicle_data,
            configs_grouped=dict(reversed(grouped.items())),
            specs=specs,
        )

    @app.route("/<lang>/heads/<slug>")
    def head(slug):
        head_data = get_head_by_slug(slug)
        if not head_data:
            abort(404)

        specs = build_specs(head_data["fields"])

        return render_template(
            "public/head.html",
            head=head_data,
            specs=specs,
        )

    @app.route("/<lang>/grips/<slug>")
    def grip_products(slug):
        grips_category = get_grips_categories_by_slug(slug)
        if not grips_category:
            abort(404)
        grips_products = get_grips_products_for_category(grips_category["id"])
        return render_template(
            "public/grip.html",
            grips_category=grips_category,
            grips_products_by_category=grips_products,
        )

    @app.route("/<lang>/about-us")
    def about_us():
        return render_template("public/about-us.html")

    @app.route("/<lang>/contact")
    def contact():
        return render_template("public/contact.html")

    @app.route("/<lang>/terms-and-conditions")
    def terms_and_conditions():
        return render_template("public/terms-and-conditions.html")

    @app.route("/<lang>/privacy-policy")
    def privacy_policy():
        return render_template("public/privacy-policy.html")

    # ── Newsletter ────────────────────────────────────────────────

    @app.route("/subscribe", methods=["POST"])
    @csrf.exempt
    def subscribe():
        from utils.mailer import send_subscription_email
        
        # Déterminer la langue pour les messages de feedback
        # Toujours forcer l'anglais si la requête vient de la page /launch
        referrer = request.referrer or ""
        if "/launch" in referrer or request.form.get("lang") == "en":
            req_lang = "en"
        else:
            req_lang = g.get('lang', 'en')

        messages = {
            "fr": {
                "email_required": "L'adresse email est requise.",
                "invalid_email": "Adresse email invalide.",
                "too_many_requests": "Trop de requêtes. Veuillez réessayer plus tard.",
                "already_subscribed": "Vous êtes déjà inscrit !",
                "success": "Merci pour votre inscription !",
                "error": "Une erreur inattendue est survenue."
            },
            "en": {
                "email_required": "Email address is required.",
                "invalid_email": "Invalid email address.",
                "too_many_requests": "Too many requests. Please try again later.",
                "already_subscribed": "You are already subscribed!",
                "success": "Thank you for subscribing!",
                "error": "An unexpected error occurred."
            }
        }
        msg = messages.get(req_lang, messages["en"])

        email = request.form.get("email")
        if not email:
            return jsonify({"status": "error", "message": msg["email_required"]}), 400

        email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(email_regex, email):
            return jsonify({"status": "error", "message": msg["invalid_email"]}), 400

        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        rate_key = f"rate_limit_{ip}"
        requests_count = cache.get(rate_key) or 0

        if requests_count >= 10:
            return jsonify({"status": "error", "message": msg["too_many_requests"]}), 429

        cache.set(rate_key, requests_count + 1, timeout=3600)

        try:
            success = add_newsletter_subscriber(email)
            if not success:
                return jsonify({"status": "error", "message": msg["already_subscribed"]}), 400

            send_subscription_email(email)
            return jsonify({"status": "success", "message": msg["success"]}), 200

        except Exception as e:
            current_app.logger.error(f"Unexpected error: {e}")
            return jsonify({"status": "error", "message": msg["error"]}), 500

    @app.route("/unsubscribe/<token>", methods=["GET", "POST"])
    def unsubscribe(token):
        secret_key = current_app.config.get("SECRET_KEY")
        serializer = URLSafeSerializer(secret_key)
        try:
            email = serializer.loads(token)
        except Exception:
            if request.method == "POST":
                return jsonify({"status": "error", "message": "Jeton invalide"}), 400
            return render_template(
                "public/unsubscribe_confirmation.html",
                status="error",
                message="Lien de désinscription invalide ou expiré.",
            )

        if request.method == "POST":
            try:
                remove_newsletter_subscriber(email)
                return jsonify({"status": "success", "message": "Désinscription réussie"}), 200
            except Exception as e:
                current_app.logger.error(
                    f"❌ Error during POST unsubscription ({email}): {e}"
                )
                return jsonify({"status": "error", "message": str(e)}), 500

        try:
            current_app.logger.info(
                f"🔎 Traitement d'une demande de désinscription pour : {email}")
            removed = remove_newsletter_subscriber(email)
            current_app.logger.info(f"🗑️ Enregistrement supprimé : {removed}")
            return render_template(
                "public/unsubscribe_confirmation.html",
                status="success",
                message="Vous avez été désinscrit avec succès de notre newsletter.",
            )
        except Exception as e:
            current_app.logger.error(
                f"❌ Error during unsubscription ({email}): {e}")
            return render_template(
                "public/unsubscribe_confirmation.html",
                status="error",
                message="Une erreur serveur est survenue. Veuillez réessayer plus tard.",
            )

    # ── Gestion du Cache ──────────────────────────────────────────

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
