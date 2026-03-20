from flask import render_template
from utils.decorators import require_roles


def init_tools_routes(app):
    @app.route("/admin/tools/signature-generator", endpoint='admin_signature_generator')
    @require_roles('administrator', 'manager', 'user')
    def admin_signature_generator():
        return render_template("admin/signature_generator.html")

    @app.route("/admin/tools/check-vehicles", endpoint='admin_check_vehicles')
    @require_roles('administrator', 'manager', 'user')
    def admin_check_vehicles():
        return render_template("admin/check_vehicles.html")

    @app.route("/admin/api-docs", endpoint='admin_api_docs')
    @require_roles('administrator', 'manager')
    def admin_api_docs():
        return render_template("admin/api_docs.html")

