
from flask import (
    Blueprint,
    current_app,
    render_template,
    session,
)

from services.admin import (
    list_projects,
)
from services.admin.equipment_stats import projects_pending_usage
from services.admin.project_access import session_project_scope
from utils.context_processors import role_can
from utils.decorators import require_roles, session_is_admin
from utils.formatting import get_today_paris_iso

dashboard_bp = Blueprint("admin_dashboard", __name__, url_prefix="/admin")


# ── Dashboard ─────────────────────────────────────────────────

@dashboard_bp.route("/dashboard", endpoint="admin_dashboard")
@dashboard_bp.route("", endpoint="admin_dashboard_root")
@dashboard_bp.route("/", endpoint="admin_dashboard_slash")
@require_roles('administrator', 'manager', 'commercial', 'user')
def admin_dashboard():
    try:
        # Un technicien ne voit que les projets de son équipe BV
        projects_data = list_projects(scope=session_project_scope())
        today_iso = get_today_paris_iso()

        # Regroupe les projets ayant une activité aujourd'hui
        # (Départ ou Retour, avec fallback sur les dates de tournage si les dates de départ/retour ne sont pas définies)
        agenda = []
        for p in projects_data:
            effective_departure = p.get("raw_departure_date") or p.get("raw_shoot_start")
            effective_return = p.get("raw_checkin_date") or p.get("raw_shoot_end")

            is_checkout_today = effective_departure == today_iso
            is_checkin_today = effective_return == today_iso

            if is_checkout_today or is_checkin_today:
                # Ajoute des drapeaux pour aider au style du template
                p["is_checkout_today"] = is_checkout_today
                p["is_checkin_today"] = is_checkin_today
                agenda.append(p)

    except Exception as e:
        current_app.logger.error(f"❌ Erreur lors du chargement des données du tableau de bord : {e}")
        agenda = []

    # Projets à pointer (pointage du matériel) : réservé aux administrateurs
    pending_usage = []
    if role_can(session.get("admin_user_role"), "equipment_usage_admin", is_admin=session_is_admin()):
        try:
            pending_usage = projects_pending_usage()
        except Exception as e:
            current_app.logger.error(f"❌ Erreur lors du calcul des projets à pointer : {e}")

    return render_template("admin/dashboard.html", agenda=agenda, pending_usage=pending_usage)


def init_dashboard_routes(app):
    """Enregistre le blueprint du tableau de bord admin (compatibilité ascendante)."""
    if "admin_dashboard" not in app.blueprints:
        app.register_blueprint(dashboard_bp)


