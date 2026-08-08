"""Outils MCP : Domaine Véhicules & Configuration Checkpoints."""
from typing import Optional, List, Dict, Any

from mcp_server.core import mcp
from mcp_server.decorators import run_in_flask_context, require_mcp_scope


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_vehicles_with_config() -> List[Dict[str, Any]]:
    """Liste tous les véhicules avec leur configuration actuelle de points de contrôle."""
    from services.admin.vehicle_config import get_vehicles_with_config as _get
    return _get()


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def save_vehicle_checkpoint_config(vehicle_id: str, enabled_keys: List[str]) -> Dict[str, Any]:
    """Sauvegarde la configuration des points de contrôle activés pour un véhicule."""
    from services.admin.vehicle_config import save_vehicle_checkpoint_config as _save
    success = _save(vehicle_id, enabled_keys)
    return {"success": success, "message": "Configuration sauvegardée."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_checkpoints_for_vehicle(vehicle_id: str) -> List[Dict[str, Any]]:
    """Récupère la liste des points de contrôle applicables pour un véhicule spécifique."""
    from utils.checkpoints import get_checkpoints_for_vehicle as _get
    return _get(vehicle_id)
