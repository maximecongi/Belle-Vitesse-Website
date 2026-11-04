"""
Blueprint d'administration pour les prévisualisations PDF directes (hors préfixe /admin).
Fournit les alias /preview/pdf/... pour les décharges et contrôles techniques.
"""

from flask import Blueprint

from utils.decorators import require_preview_access

preview_bp = Blueprint("admin_preview", __name__)


@preview_bp.route("/preview/pdf/checkout", methods=["GET"], endpoint="preview_pdf_checkout_alias")
@preview_bp.route("/preview/pdf/checkout/<int:record_id>", methods=["GET"], endpoint="preview_pdf_checkout_id_alias")
@require_preview_access
def preview_pdf_checkout_alias(record_id=None):
    from routes.admin.inspections import handle_inspection_preview_route
    return handle_inspection_preview_route("checkout", record_id=record_id)


@preview_bp.route("/preview/pdf/checkin", methods=["GET"], endpoint="preview_pdf_checkin_alias")
@preview_bp.route("/preview/pdf/checkin/<int:record_id>", methods=["GET"], endpoint="preview_pdf_checkin_id_alias")
@require_preview_access
def preview_pdf_checkin_alias(record_id=None):
    from routes.admin.inspections import handle_inspection_preview_route
    return handle_inspection_preview_route("checkin", record_id=record_id)


@preview_bp.route("/preview/pdf/cgl", methods=["GET"], endpoint="preview_pdf_cgl_alias")
@require_preview_access
def preview_pdf_cgl_alias():
    from routes.admin.waivers import admin_cgl_preview
    return admin_cgl_preview()


@preview_bp.route("/preview/pdf/safety-rules", methods=["GET"], endpoint="preview_pdf_safety_rules_alias")
@require_preview_access
def preview_pdf_safety_rules_alias():
    from routes.admin.waivers import admin_safety_rules_preview
    return admin_safety_rules_preview()


@preview_bp.route("/preview/pdf/pilot-waiver", methods=["GET"], endpoint="preview_pdf_pilot_waiver_alias")
@require_preview_access
def preview_pdf_pilot_waiver_alias():
    from routes.admin.waivers import admin_pilot_waivers_preview
    return admin_pilot_waivers_preview()

