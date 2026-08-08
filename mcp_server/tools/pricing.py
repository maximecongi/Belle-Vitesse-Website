"""Outils MCP : Domaine Tarification & Grilles Tarifaires."""
from typing import Optional, List, Dict, Any

from mcp_server.core import mcp
from mcp_server.decorators import run_in_flask_context, require_mcp_scope


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_equipment_rates() -> List[Dict[str, Any]]:
    """Récupère la grille tarifaire complète des équipements et véhicules."""
    from services.admin.rates import get_equipment_rates as _get
    return _get()


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def update_equipment_daily_rate(item_id: str, daily_rate: float) -> Dict[str, Any]:
    """Met à jour le tarif journalier d'un équipement ou d'un véhicule."""
    from services.admin.rates import update_equipment_daily_rate as _update
    success = _update(item_id, daily_rate)
    return {"success": success, "message": f"Tarif de '{item_id}' mis à jour à {daily_rate} €." if success else "Échec."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_salary_rates() -> List[Dict[str, Any]]:
    """Récupère les tarifs salariaux des techniciens / pilotes."""
    from services.admin.rates import get_salary_rates as _get
    return _get()


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def update_salary_rate(role_name: str, daily_rate: float) -> Dict[str, Any]:
    """Met à jour le tarif journalier d'un rôle de technicien/pilote."""
    from services.admin.rates import update_salary_rate as _update
    success = _update(role_name, daily_rate)
    return {"success": success, "message": f"Tarif salarial de '{role_name}' mis à jour à {daily_rate} €." if success else "Échec."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("admin")
def delete_salary_rate(role_name: str, confirm: bool = False) -> Dict[str, Any]:
    """
    Supprime un tarif salarial de rôle.
    ATTENTION: Action destructrice (Scope 'admin' requis).
    """
    from services.admin.rates import delete_salary_rate as _delete
    if not confirm:
        return {
            "success": False,
            "status": "requires_confirmation",
            "role_name": role_name,
            "message": f"⚠️ ATTENTION : Vous êtes sur le point de supprimer le tarif salarial du rôle '{role_name}'. Confirmez avec confirm=True."
        }
    success = _delete(role_name)
    return {"success": success, "message": f"Tarif salarial '{role_name}' supprimé." if success else "Échec."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_logistics_rates() -> List[Dict[str, Any]]:
    """Récupère les tarifs logistiques (kilométrage, carburant, convoyage)."""
    from services.admin.rates import get_logistics_rates as _get
    return _get()


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def update_logistics_rate(item_name: str, rate: float) -> Dict[str, Any]:
    """Met à jour un tarif logistique."""
    from services.admin.rates import update_logistics_rate as _update
    success = _update(item_name, rate)
    return {"success": success, "message": f"Tarif logistique '{item_name}' mis à jour à {rate} €." if success else "Échec."}
