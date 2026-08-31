"""Ressources MCP : Expose les contextes de données en lecture directe via le protocole MCP."""
import json
from mcp_server.core import mcp, flask_app
from mcp_server.tools.projects import get_dashboard_summary


@mcp.resource("bv://pricing/rates")
def resource_pricing_rates() -> str:
    """Grille tarifaire complète de Belle Vitesse (Équipements, Salaires conventionnels, Logistique)."""
    with flask_app.app_context():
        from services.admin.pricing import (
            list_equipment_rates,
            list_salary_rates,
            list_logistics_rates,
        )
        data = {
            "equipment": list_equipment_rates(),
            "salaries": list_salary_rates(),
            "logistics": list_logistics_rates(),
        }
        return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.resource("bv://dashboard/summary")
def resource_dashboard_summary() -> str:
    """Synthèse opérationnelle en direct : tournages en cours, tournages sous 15 jours, décharges et devis récents."""
    with flask_app.app_context():
        summary = get_dashboard_summary()
        return json.dumps(summary, ensure_ascii=False, indent=2)


@mcp.resource("bv://vehicles/catalog")
def resource_vehicles_catalog() -> str:
    """Catalogue complet des véhicules de prise de vues et travelling de Belle Vitesse avec spécifications."""
    with flask_app.app_context():
        from utils.database import get_vehicles
        return json.dumps(get_vehicles(), ensure_ascii=False, indent=2)
