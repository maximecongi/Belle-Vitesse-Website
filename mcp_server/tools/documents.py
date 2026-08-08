"""Outils MCP : Domaine Fiches & Documents PDF."""
from typing import Optional, List, Dict, Any

from mcp_server.core import mcp
from mcp_server.decorators import run_in_flask_context, require_mcp_scope


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_vehicle_sheet_data(vehicle_id: str) -> Optional[Dict[str, Any]]:
    """Récupère les caractéristiques techniques et données complètes d'une fiche véhicule PDF par son identifiant."""
    from services.admin.vehicle_sheets import get_vehicle_sheet_data as _get
    return _get(vehicle_id)


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def update_catalog_pdf(category: str, new_url: str) -> Dict[str, Any]:
    """Met à jour l'URL du catalogue PDF de véhicules/équipements."""
    from services.admin.vehicle_sheets import update_catalog_pdf as _update
    success = _update(category, new_url)
    return {"success": success, "message": f"Catalogue '{category}' mis à jour." if success else "Échec."}
