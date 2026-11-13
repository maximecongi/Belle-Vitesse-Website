"""
Page Indicateurs (administrateurs) : métriques de pilotage de l'ERP, un onglet par domaine
(matériel, commercial, incidents) sur le même gabarit, et une période commune comparée à la
période précédente. Chaque domaine est calculé indépendamment : une erreur sur l'un
n'empêche pas l'affichage des autres.
"""
import logging

from flask import Blueprint, render_template, request

from services.admin.indicators import (
    DEFAULT_TAB,
    PERIODS,
    TABS,
    commercial_indicators,
    equipment_indicators,
    incidents_indicators,
    last_12_months,
    resolve_period,
)
from utils.decorators import require_roles

logger = logging.getLogger(__name__)

indicators_bp = Blueprint("admin_indicators", __name__, url_prefix="/admin")


@indicators_bp.route("/indicators", methods=["GET"], endpoint="admin_indicators")
@require_roles("administrator")
def admin_indicators():
    period = resolve_period(request.args.get("period"))
    months = last_12_months(period)
    tab = request.args.get("tab")
    tab = tab if tab in TABS else DEFAULT_TAB

    domains = {}
    for key, builder in (("commercial", commercial_indicators),
                         ("equipment", equipment_indicators),
                         ("incidents", incidents_indicators)):
        try:
            domains[key] = builder(period, months)
        except Exception as e:
            logger.error(f"❌ Indicateurs « {TABS[key]} » indisponibles : {e}", exc_info=True)
            domains[key] = None

    return render_template(
        "admin/indicators.html",
        period=period, periods=PERIODS, tabs=TABS, tab=tab, months=months, **domains,
    )
