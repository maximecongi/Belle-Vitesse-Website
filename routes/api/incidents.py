"""
Routes API REST v1 pour la gestion des incidents de tournage.
Expose les endpoints de consultation, détail et indicateurs statistiques,
protégés par authentification par jeton JWT ou session active.
"""

from flask import Blueprint, current_app, jsonify, request

from models import Incident
from services.admin.incidents import get_incident_detail, list_incidents
from utils.jwt_auth import require_api_auth

api_incidents_bp = Blueprint("api_incidents", __name__)


@api_incidents_bp.route("/incidents", methods=["GET"])
@require_api_auth("administrator", "manager", "user")
def api_list_incidents():
    """
    Retourne la liste des incidents, avec filtres optionnels et pagination.
    Query params :
      - page: int (optionnel)
      - per_page: int (défaut 20, max 200)
      - status: str (ex: 'declared', 'in_progress', 'resolved')
      - severity: str (ex: 'low', 'medium', 'high', 'critical')
      - category: str (ex: 'vehicle', 'head', 'grip', 'third_party', 'human')
      - project_id: int
      - q: str (recherche textuelle libre)
    """
    try:
        page_val = request.args.get("page", type=int)
        per_page_val = request.args.get("per_page", default=20, type=int)
        status_val = request.args.get("status")
        severity_val = request.args.get("severity")
        category_val = request.args.get("category")
        project_id_val = request.args.get("project_id", type=int)
        query_val = request.args.get("q")

        result = list_incidents(
            status=status_val,
            severity=severity_val,
            category=category_val,
            project_id=project_id_val,
            query=query_val,
            page=page_val,
            per_page=per_page_val,
        )

        pagination = result.get("pagination")
        if pagination:
            return jsonify({
                "items": result["incidents"],
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "pages": pagination.pages,
                "stats": result.get("stats", {}),
            })

        return jsonify({
            "items": result.get("incidents", []),
            "total": result.get("total", len(result.get("incidents", []))),
            "stats": result.get("stats", {}),
        })
    except Exception as e:
        current_app.logger.error(f"❌ API list_incidents error: {e}")
        return jsonify({"error": str(e)}), 500


@api_incidents_bp.route("/incidents/<int:record_id>", methods=["GET"])
@require_api_auth("administrator", "manager", "user")
def api_get_incident(record_id: int):
    """
    Retourne le détail complet d'un incident par son identifiant unique.
    """
    try:
        data = get_incident_detail(record_id)
        if not data:
            return jsonify({"error": "Incident not found"}), 404
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"❌ API get_incident error: {e}")
        return jsonify({"error": str(e)}), 500


@api_incidents_bp.route("/incidents/stats", methods=["GET"])
@require_api_auth("administrator", "manager", "user")
def api_get_incidents_stats():
    """
    Retourne les métriques et indicateurs clés (KPI) sur l'ensemble des incidents actifs.
    """
    try:
        base_query = Incident.query.filter(Incident.deleted_at.is_(None))

        total = base_query.count()
        critical_count = base_query.filter(Incident.severity == "critique").count()
        active_count = base_query.filter(
            Incident.status.in_(["signale", "en_expertise", "en_reparation", "assurance"])
        ).count()
        resolved_count = base_query.filter(Incident.status == "resolu").count()
        closed_count = base_query.filter(Incident.status == "cloture").count()
        fully_signed_count = base_query.filter(
            Incident.bv_signed_at.isnot(None),
            Incident.prod_signed_at.isnot(None),
        ).count()

        return jsonify({
            "total": total,
            "active": active_count,
            "critical": critical_count,
            "resolved": resolved_count,
            "closed": closed_count,
            "fully_signed": fully_signed_count,
            "by_status": {
                "signale": base_query.filter(Incident.status == "signale").count(),
                "en_expertise": base_query.filter(Incident.status == "en_expertise").count(),
                "en_reparation": base_query.filter(Incident.status == "en_reparation").count(),
                "assurance": base_query.filter(Incident.status == "assurance").count(),
                "resolu": resolved_count,
                "cloture": closed_count,
            },
            "by_severity": {
                "mineur": base_query.filter(Incident.severity == "mineur").count(),
                "modere": base_query.filter(Incident.severity == "modere").count(),
                "critique": critical_count,
            },
        })
    except Exception as e:
        current_app.logger.error(f"❌ API incidents_stats error: {e}")
        return jsonify({"error": str(e)}), 500
