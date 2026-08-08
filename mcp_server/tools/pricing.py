"""Outils MCP : Domaine Tarification & Grilles Tarifaires."""
from typing import Optional, List, Dict, Any

from mcp_server.core import mcp
from mcp_server.decorators import run_in_flask_context, require_mcp_scope


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_equipment_rates() -> List[Dict[str, Any]]:
    """Récupère la grille tarifaire complète des équipements et véhicules."""
    from services.admin.pricing import list_equipment_rates as _list
    return _list()


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def update_equipment_daily_rate(table_name: str, record_id: int, value: float) -> Dict[str, Any]:
    """Met à jour le tarif journalier d'un équipement ou d'un véhicule."""
    from services.admin.pricing import update_equipment_daily_rate as _update
    success = _update(table_name, record_id, value)
    return {"success": success, "message": f"Tarif mis à jour à {value} €." if success else "Échec."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_salary_rates() -> List[Dict[str, Any]]:
    """Récupère les tarifs salariaux des techniciens / pilotes (1er assistant caméra, chef op, etc.)."""
    from services.admin.pricing import list_salary_rates as _list
    return _list()


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def update_salary_rate(rate_id: int, field: str, value: Any) -> Dict[str, Any]:
    """Met à jour un champ spécifique d'un tarif salarial de rôle/technicien."""
    from services.admin.pricing import update_salary_rate as _update
    success = _update(rate_id, field, value)
    return {"success": success is not None, "message": f"Tarif salarial #{rate_id} mis à jour." if success else "Échec."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("admin")
def delete_salary_rate(rate_id: int, confirm: bool = False) -> Dict[str, Any]:
    """
    Supprime un tarif salarial de rôle par son ID.
    ATTENTION: Action destructrice (Scope 'admin' requis).
    """
    from services.admin.pricing import delete_salary_rate as _delete
    if not confirm:
        return {
            "success": False,
            "status": "requires_confirmation",
            "rate_id": rate_id,
            "message": f"⚠️ ATTENTION : Vous êtes sur le point de supprimer le tarif salarial #{rate_id}. Confirmez avec confirm=True."
        }
    success = _delete(rate_id)
    return {"success": success, "message": f"Tarif salarial #{rate_id} supprimé." if success else "Échec."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_logistics_rates() -> List[Dict[str, Any]]:
    """Récupère les tarifs logistiques (kilométrage, carburant, convoyage)."""
    from services.admin.pricing import list_logistics_rates as _list
    return _list()


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def update_logistics_rate(rate_id: int, field: str, value: Any) -> Dict[str, Any]:
    """Met à jour un tarif logistique par son ID."""
    from services.admin.pricing import update_logistics_rate as _update
    success = _update(rate_id, field, value)
    return {"success": success is not None, "message": f"Tarif logistique #{rate_id} mis à jour." if success else "Échec."}

