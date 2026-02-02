import re
import os
from flask import render_template, abort, jsonify, request, Response
from datetime import datetime
from collections import defaultdict
from werkzeug.exceptions import HTTPException
from mysql.connector import Error

from services.airtable_service import (
    get_vehicles,
    get_vehicle_by_slug,
    get_configs_for_vehicle,
    get_heads,
    get_head_by_slug,
    get_grips_categories,
    get_grips_categories_by_slug,
    get_grips_products_for_category
)
from services.db_service import get_db_connection
from services.email_service import send_subscription_email
from utils.specs import build_specs
from itsdangerous import URLSafeSerializer
from utils.globals import BRANDS

def register_routes(app):

    @app.route("/")
    def home():
        return render_template(
            "home.html",
            brands=BRANDS,
            seo_title="Professional Camera Tracking Vehicles & Precision Grip",
            seo_description="Belle Vitesse provides world-class camera tracking solutions, high-speed chase vehicles, and precision remote heads for the film and advertising industry."
        )

    @app.route("/launch")
    def launch():
        return render_template("launch.html")

    # Error Handlers
    if app.config.get("FLASK_ENV") == "production":
        @app.errorhandler(HTTPException)
        def handle_http_exception(e):
            return render_template("error.html", error_title=f"{e.code} - {e.name}", error_message=e.description), e.code

        @app.errorhandler(Exception)
        def handle_exception(e):
            return render_template("error.html", error_title="500 - Internal Server Error", error_message="An unexpected error occurred."), 500

    # Lists
    @app.route("/vehicles")
    def vehicles():
        return render_template(
            "vehicles.html",
            seo_title="Tracking Vehicles Fleet",
            seo_description="Discover our fleet of high-performance camera tracking vehicles, from high-speed chase cars to versatile off-road platforms."
        )

    @app.route("/heads")
    def heads():
        return render_template(
            "heads.html",
            seo_title="Remote Heads & Stabilization",
            seo_description="Explore our range of stabilized remote heads, including Shotover and Scorpio, for perfectly steady shots in any conditions."
        )

    @app.route("/grips")
    def grips():
        return render_template(
            "grips.html",
            seo_title="Grip Equipment & Accessories",
            seo_description="High-quality grip equipment, shock arms, and custom mounting solutions for all your cinematography needs."
        )

    # Details
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
            seo_title=vehicle["fields"].get("name", "Vehicle"),
            seo_description=f"Specifications and configurations for the {vehicle['fields'].get('name')}. Explore its performance and equipment."
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
            seo_title=head["fields"].get("name", "Remote Head"),
            seo_description=f"Discover the capabilities of the {head['fields'].get('name')}. Precision stabilization for your next production."
        )

    @app.route("/grips/<slug>")
    def grip_products(slug):
        grips_category = get_grips_categories_by_slug(slug)
        if not grips_category:
            abort(404)
        grips_products = get_grips_products_for_category(grips_category["id"])
        return render_template("grip.html", grips_category=grips_category, grips_products_by_category=grips_products)

    # Static pages
    @app.route("/about-us")
    def about_us():
        return render_template(
            "about-us.html",
            seo_title="About Us | Precision Cinematography Solutions",
            seo_description="Learn about Belle Vitesse, our expertise in high-level cinematic movement, and our commitment to providing discreet and efficient motion platforms worldwide."
        )

    @app.route("/contact")
    def contact():
        return render_template(
            "contact.html",
            seo_title="Contact | High-Performance Camera Tracking",
            seo_description="Get in touch with Belle Vitesse for your camera tracking and precision grip needs. Based in Paris, operating worldwide."
        )

    @app.route("/terms-and-conditions")
    def terms_and_conditions():
        return render_template(
            "terms-and-conditions.html",
            seo_title="Terms and Conditions",
            seo_description="Legal terms and conditions for renting equipment and services from Belle Vitesse."
        )

    # Newsletter
    @app.route("/subscribe", methods=["POST"])
    def subscribe():
        email = request.form.get("email")
        if not email:
            return jsonify({"status": "error", "message": "Email is required"}), 400

        # Email Pattern Validation
        email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        if not re.match(email_regex, email):
            return jsonify({"status": "error", "message": "Invalid email address"}), 400

        # Rate Limiting (IP based, 10 requests per hour)
        from app import cache
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        rate_key = f"rate_limit_{ip}"
        requests_count = cache.get(rate_key) or 0

        if requests_count >= 10:
            return jsonify({"status": "error", "message": "Too many requests. Please try again later."}), 429

        cache.set(rate_key, requests_count + 1, timeout=3600)

        connection = None
        tunnel = None
        try:
            connection, tunnel = get_db_connection()
            cursor = connection.cursor()

            # Check if email already exists
            cursor.execute("SELECT id FROM newsletter_subscribers WHERE email = %s", (email,))
            if cursor.fetchone():
                return jsonify({"status": "error", "message": "You are already subscribed!"}), 400

            # Insert new subscriber
            cursor.execute("INSERT INTO newsletter_subscribers (email) VALUES (%s)", (email,))
            connection.commit()

            # Send welcome email
            send_subscription_email(email)

            return jsonify({"status": "success", "message": "Thank you for subscribing!"}), 200

        except Error as e:
            app.logger.error(f"Database error: {e}")
            return jsonify({"status": "error", "message": "A server error occurred. Please try again later."}), 500
        except Exception as e:
            app.logger.error(f"Unexpected error: {e}")
            return jsonify({"status": "error", "message": "An unexpected error occurred."}), 500
        finally:
            if connection:
                cursor.close()
                connection.close()
            if tunnel:
                tunnel.stop()

    @app.route("/unsubscribe/<token>", methods=["GET", "POST"])
    def unsubscribe(token):
        secret_key = app.config.get("SECRET_KEY")
        serializer = URLSafeSerializer(secret_key)
        try:
            email = serializer.loads(token)
        except Exception:
            if request.method == "POST":
                return jsonify({"status": "error", "message": "Invalid token"}), 400
            return render_template("unsubscribe_confirmation.html", status="error", message="Invalid or expired unsubscribe link.")

        # RFC 8058: One-Click Unsubscribe via POST
        if request.method == "POST":
            connection = None
            tunnel = None
            try:
                connection, tunnel = get_db_connection()
                cursor = connection.cursor()
                cursor.execute("DELETE FROM newsletter_subscribers WHERE email = %s", (email,))
                connection.commit()
                return jsonify({"status": "success", "message": "Unsubscribed"}), 200
            except Exception as e:
                app.logger.error(f"❌ Error during POST unsubscription ({email}): {e}")
                return jsonify({"status": "error", "message": str(e)}), 500
            finally:
                if connection:
                    cursor.close()
                    connection.close()
                if tunnel:
                    tunnel.stop()

        connection = None
        tunnel = None
        try:
            connection, tunnel = get_db_connection()
            cursor = connection.cursor()
            app.logger.info(f"🔎 Processing unsubscribe request for: {email}")
            cursor.execute("DELETE FROM newsletter_subscribers WHERE email = %s", (email,))
            connection.commit()
            return render_template("unsubscribe_confirmation.html", status="success", message="You have been successfully unsubscribed from our newsletter.")
        except Exception as e:
            app.logger.error(f"❌ Error during unsubscription ({email}): {e}")
            return render_template("unsubscribe_confirmation.html", status="error", message="A server error occurred. Please try again later.")
        finally:
            if connection:
                cursor.close()
                connection.close()
            if tunnel:
                tunnel.stop()

    # Cache management
    @app.route("/admin/cache/clear", methods=["POST"])
    def clear_cache():
        require_admin_token()
        from app import cache
        cache.clear()
        return jsonify({"status": "Cache cleared"}), 200

    @app.route("/admin/cache/clear/<key>", methods=["POST"])
    def clear_cache_key(key):
        require_admin_token()
        from app import cache
        cache.delete(key)
        return jsonify({"status": f"Cache key {key} cleared"}), 200

    @app.route("/sitemap.xml")
    def sitemap():
        pages = []
        base_url = request.host_url.rstrip('/')

        # Static pages
        static_pages = ["/", "/vehicles", "/heads", "/grips", "/about-us", "/contact", "/terms-and-conditions"]
        for page in static_pages:
            pages.append(f"{base_url}{page}")

        # Dynamic vehicles
        for v in get_vehicles():
            slug = v['fields'].get('slug')
            if slug:
                pages.append(f"{base_url}/vehicles/{slug}")

        # Dynamic heads
        for h in get_heads():
            slug = h['fields'].get('slug')
            if slug:
                pages.append(f"{base_url}/heads/{slug}")

        # Dynamic grips
        for g in get_grips_categories():
            slug = g['fields'].get('slug')
            if slug:
                pages.append(f"{base_url}/grips/{slug}")

        sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>'
        sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        for page in pages:
            sitemap_xml += f'<url><loc>{page}</loc><lastmod>{datetime.now().strftime("%Y-%m-%d")}</lastmod></url>'
        sitemap_xml += '</urlset>'

        return Response(sitemap_xml, mimetype='application/xml')

    @app.route("/robots.txt")
    def robots():
        base_url = request.host_url.rstrip('/')
        robots_txt = "User-agent: *\nAllow: /\n"
        robots_txt += f"Sitemap: {base_url}/sitemap.xml"
        return Response(robots_txt, mimetype='text/plain')

    def require_admin_token():
        token = request.headers.get("X-Admin-Token")
        if not token or token != app.config.get("ADMIN_CACHE_TOKEN"):
            abort(403)
