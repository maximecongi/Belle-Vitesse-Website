"""Outils MCP : Domaine Pré-Devis & Devis."""
from typing import Optional, List, Dict, Any

from mcp_server.core import mcp
from mcp_server.decorators import run_in_flask_context, require_mcp_scope


def _format_pre_quote(pq) -> Dict[str, Any]:
    if not pq:
        return {}
    data = pq.to_dict() if hasattr(pq, "to_dict") else dict(pq)
    data["prestations"] = pq.prestations or []
    data["versions"] = [
        v.to_dict() if hasattr(v, "to_dict") else dict(v)
        for v in getattr(pq, "versions", [])
    ]
    return data


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def list_pre_quotes(project_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Liste tous les pré-devis, facultativement filtrés par ID de projet."""
    from services.admin.pre_quote import list_pre_quotes as _list
    quotes = _list()
    if project_id:
        quotes = [q for q in quotes if q.project_id == project_id]
    return [_format_pre_quote(q) for q in quotes]


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_pre_quote(pre_quote_id: int) -> Optional[Dict[str, Any]]:
    """Récupère le détail d'un pré-devis par son ID."""
    from models import PreQuote
    pq = PreQuote.query.get(pre_quote_id)
    return _format_pre_quote(pq) if pq else None


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def create_pre_quote(
    project_id: Optional[int] = None,
    production_id: Optional[int] = None,
    version_label: Optional[str] = "V1",
    items: Optional[List[Dict[str, Any]]] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Crée un nouveau pré-devis pour un projet ou une société de production avec ses lignes d'équipements / prestations."""
    from services.admin.pre_quote import create_pre_quote as _create
    if project_id and not production_id:
        from models import Project
        proj = Project.query.get(project_id)
        if proj:
            production_id = proj.production_id

    if not production_id:
        from models import Production
        first_prod = Production.query.first()
        if first_prod:
            production_id = first_prod.id

    form_data = {
        "project_id": project_id,
        "production_id": production_id,
        "version_label": version_label or "V1",
        "prestations": items or [],
        "notes": notes or "",
    }
    pq = _create(form_data)
    return {"success": pq is not None, "pre_quote_id": pq.id if pq else None, "reference": pq.reference if pq else None, "message": "Pré-devis créé avec succès." if pq else "Échec de création."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def update_pre_quote(
    pre_quote_id: int,
    items: Optional[List[Dict[str, Any]]] = None,
    notes: Optional[str] = None,
    production_id: Optional[int] = None,
    project_name: Optional[str] = None,
    status: Optional[str] = None,
    show_discounts: Optional[bool] = None,
) -> Dict[str, Any]:
    """Met à jour un pré-devis existant (mode patch : conserve les champs non spécifiés)."""
    from models import PreQuote, db
    from services.admin.pre_quote import update_pre_quote as _update

    pq = db.session.get(PreQuote, pre_quote_id)
    if not pq:
        return {"success": False, "message": f"Pré-devis #{pre_quote_id} introuvable."}

    form_data = {}
    if items is not None:
        form_data["prestations"] = items
    if notes is not None:
        form_data["notes"] = notes
    if production_id is not None:
        form_data["production_id"] = production_id
    if project_name is not None:
        form_data["project_name"] = project_name
    if status is not None:
        form_data["status"] = status
    if show_discounts is not None:
        form_data["show_discounts"] = show_discounts

    updated_pq = _update(pre_quote_id, form_data)
    return {"success": updated_pq is not None, "message": "Pré-devis mis à jour." if updated_pq else "Échec de mise à jour."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("admin")
def delete_pre_quote(pre_quote_id: int, confirm: bool = False) -> Dict[str, Any]:
    """
    Supprime un pré-devis par son ID.
    ATTENTION: Action destructrice (Scope 'admin' requis).
    """
    from models import PreQuote
    from services.admin.pre_quote import delete_pre_quote as _delete
    pq = PreQuote.query.get(pre_quote_id)
    if not pq:
        return {"success": False, "message": f"Pré-devis #{pre_quote_id} introuvable."}

    if not confirm:
        return {
            "success": False,
            "status": "requires_confirmation",
            "pre_quote_id": pre_quote_id,
            "reference": pq.reference,
            "message": f"⚠️ ATTENTION : Vous êtes sur le point de supprimer le pré-devis #{pre_quote_id} ({pq.reference}). Confirmez avec confirm=True."
        }

    success = _delete(pre_quote_id)
    return {"success": success, "message": f"Pré-devis #{pre_quote_id} supprimé avec succès." if success else "Échec de suppression."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def create_pre_quote_version(pre_quote_id: int, version_label: str) -> Dict[str, Any]:
    """Duplique un pré-devis sous une nouvelle version (ex: V2, V3)."""
    from services.admin.pre_quote import create_pre_quote_version as _version
    ver = _version(pre_quote_id, version_label)
    return {"success": ver is not None, "new_version_id": ver.id if ver else None, "version_number": ver.version_number if ver else None, "message": f"Version {version_label} créée." if ver else "Échec."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_pre_quote_form_context(project_id: Optional[int] = None) -> Dict[str, Any]:
    """Récupère le contexte du formulaire pré-devis (grilles de prix, projets, paramètres livraison)."""
    from services.admin.pre_quote import get_delivery_config
    from services.admin.projects import list_projects
    from services.admin.pricing import list_equipment_rates, list_salary_rates, list_logistics_rates
    return {
        "delivery_config": get_delivery_config(),
        "projects": list_projects(),
        "equipment_rates": list_equipment_rates(),
        "salary_rates": list_salary_rates(),
        "logistics_rates": list_logistics_rates(),
    }

