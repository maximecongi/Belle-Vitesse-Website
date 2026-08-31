"""Outils MCP : Domaine Fiches & Documents PDF."""
from typing import Optional, List, Dict, Any

from mcp_server.core import mcp
from mcp_server.decorators import run_in_flask_context, require_mcp_scope


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_vehicle_sheet_data(vehicle_id: str) -> Optional[Dict[str, Any]]:
    """Récupère les caractéristiques techniques et données complètes d'une fiche véhicule PDF par son identifiant."""
    from models import Vehicle, db
    from utils.database import get_configs_for_vehicle
    v = db.session.get(Vehicle, vehicle_id)
    if not v:
        return None
    configs = get_configs_for_vehicle(vehicle_id)
    fields = v.fields or {}
    return {
        "id": v.id,
        "name": fields.get("name") or v.id,
        "daily_rate": float(v.daily_rate) if v.daily_rate else 0.0,
        "specs": {
            "max_speed": fields.get("max_speed"),
            "passengers": fields.get("passengers"),
            "setups": fields.get("setups"),
            "power": fields.get("power"),
            "weight": fields.get("weight"),
        },
        "configs": configs,
        "fields": fields,
    }


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def update_catalog_pdf(with_prices: bool = True) -> Dict[str, Any]:
    """Régénère le catalogue PDF des véhicules/équipements (avec ou sans tarifs)."""
    from services.admin.catalog import update_stored_catalog
    success, msg = update_stored_catalog(with_prices=with_prices)
    return {"success": success, "message": msg}

