"""Outils MCP : Domaine Productions."""
from typing import Optional, List, Dict, Any

from mcp_server.core import mcp
from mcp_server.decorators import run_in_flask_context, require_mcp_scope


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def list_productions(
    query: Optional[str] = None,
    limit: Optional[int] = 50,
    offset: Optional[int] = 0,
) -> List[Dict[str, Any]]:
    """
    Liste les sociétés de production avec recherche textuelle et pagination.
    - query: Recherche par nom, email, téléphone ou adresse
    - limit: Nombre maximum d'enregistrements retournés (défaut 50, max 500)
    - offset: Décalage pour la pagination
    """
    from services.admin.productions import list_productions as _list
    from mcp_server.utils import matches_search_query, apply_pagination

    all_prods = _list()
    filtered = []
    for p in all_prods:
        if query and not matches_search_query(p, query, ["name", "email", "phone", "address"]):
            continue
        filtered.append(p)

    return apply_pagination(filtered, limit=limit, offset=offset)


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_production(production_id: int) -> Optional[Dict[str, Any]]:
    """Récupère les détails complets d'une société de production par son ID, incluant ses contacts et projets récents."""
    from models import Production, db

    prod = db.session.get(Production, production_id)
    if not prod:
        return None

    contacts_list = [
        {
            "id": c.id,
            "first_name": c.first_name,
            "last_name": c.last_name,
            "job": c.job_title or "",
            "job_title": c.job_title or "",
            "email": c.mail or "",
            "phone": c.phone or "",
        }
        for c in (prod.contacts or [])
    ]

    recent_projects = [
        {
            "id": p.id,
            "project_id": p.project_id,
            "name": p.name,
            "shoot_start": p.shoot_start_date.strftime("%Y-%m-%d") if p.shoot_start_date else None,
            "shoot_end": p.shoot_end_date.strftime("%Y-%m-%d") if p.shoot_end_date else None,
        }
        for p in (prod.projects or [])
        if not getattr(p, "deleted_at", None)
    ][:5]

    return {
        "id": prod.id,
        "name": prod.name,
        "address": prod.address or "",
        "email": prod.mail or "",
        "phone": prod.phone or "",
        "contacts": contacts_list,
        "contacts_count": len(contacts_list),
        "recent_projects": recent_projects,
        "projects_count": len(prod.projects or []),
    }


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def create_production(
    name: str,
    address: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
) -> Dict[str, Any]:
    """Crée une nouvelle société de production."""
    from services.admin.productions import create_production as _create
    form = {"name": name, "address": address or "", "email": email or "", "phone": phone or ""}
    success = _create(form)
    return {"success": success, "message": "Production créée." if success else "Échec de création."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def update_production(
    production_id: int,
    name: Optional[str] = None,
    address: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
) -> Dict[str, Any]:
    """Met à jour une société de production (mode patch : conserve les champs non spécifiés)."""
    from models import Production, db
    from services.admin.productions import update_production as _update

    prod = db.session.get(Production, production_id)
    if not prod:
        return {"success": False, "message": f"Production #{production_id} introuvable."}

    form = {
        "name": name if name is not None else prod.name,
        "address": address if address is not None else (prod.address or ""),
        "email": email if email is not None else (prod.mail or ""),
        "phone": phone if phone is not None else (prod.phone or ""),
    }
    success = _update(production_id, form)
    return {"success": success, "message": "Production mise à jour." if success else "Production introuvable."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("admin")
def delete_production(production_id: int, confirm: bool = False) -> Dict[str, Any]:
    """
    Supprime une société de production par son ID.
    ATTENTION: Action destructrice (Scope 'admin' requis).
    L'IA doit obligatoirement l'exécuter d'abord avec confirm=False pour simuler l'impact et demander la confirmation à l'utilisateur humain.
    """
    from services.admin.productions import get_production_for_edit, delete_production as _delete
    prod = get_production_for_edit(production_id)
    if not prod:
        return {"success": False, "message": f"Production #{production_id} introuvable."}

    if not confirm:
        prod_name = prod.get("name", "Sans nom")
        return {
            "success": False,
            "status": "requires_confirmation",
            "production_id": production_id,
            "production_name": prod_name,
            "message": (
                f"⚠️ ATTENTION : Vous êtes sur le point de supprimer la société de production #{production_id} '{prod_name}'. "
                "Veuillez demander la confirmation explicite à l'utilisateur humain devant son écran, "
                "puis ré-exécutez cet outil avec confirm=True."
            )
        }

    success = _delete(production_id)
    return {"success": success, "message": f"Production #{production_id} supprimée." if success else "Échec de suppression."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_production_form_context() -> Dict[str, Any]:
    """Récupère le contexte du formulaire de production."""
    return {"fields": ["name", "address", "email", "phone"]}

