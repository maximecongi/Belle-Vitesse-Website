"""Outils MCP : Domaine Contacts."""
from typing import Optional, List, Dict, Any

from mcp_server.core import mcp
from mcp_server.decorators import run_in_flask_context, require_mcp_scope


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def list_contacts(
    query: Optional[str] = None,
    production_id: Optional[int] = None,
    limit: Optional[int] = 50,
    offset: Optional[int] = 0,
) -> List[Dict[str, Any]]:
    """
    Liste les contacts professionnels avec recherche textuelle et pagination.
    - query: Recherche par nom, prénom, poste, email, téléphone ou nom de production
    - production_id: Filtrer par identifiant de société de production
    - limit: Nombre maximum d'enregistrements retournés (défaut 50, max 500)
    - offset: Décalage pour la pagination
    """
    from services.admin.contacts import list_contacts as _list
    from mcp_server.utils import matches_search_query, apply_pagination

    all_contacts = _list()
    filtered = []
    for c in all_contacts:
        if production_id is not None:
            c_pid = c.get("production_id")
            if c_pid != production_id and str(c_pid) != str(production_id):
                continue
        if query and not matches_search_query(
            c, query, ["first_name", "last_name", "job", "job_title", "mail", "email", "phone", "production_name"]
        ):
            continue
        filtered.append(c)

    return apply_pagination(filtered, limit=limit, offset=offset)


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_contact(contact_id: int) -> Optional[Dict[str, Any]]:
    """Récupère les détails d'un contact par son ID."""
    from services.admin.contacts import get_contact_for_edit
    res = get_contact_for_edit(contact_id)
    if res:
        res["job"] = res.get("job_title", "")
        res["email"] = res.get("mail", "")
    return res


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def create_contact(
    first_name: str,
    last_name: str,
    job: Optional[str] = None,
    production_id: Optional[int] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Crée un nouveau contact professionnel."""
    from services.admin.contacts import create_contact as _create
    form = {
        "first_name": first_name,
        "last_name": last_name,
        "job": job or "",
        "production_id": str(production_id) if production_id else "",
        "email": email or "",
        "phone": phone or "",
        "notes": notes or "",
    }
    success = _create(form)
    return {"success": success, "message": "Contact créé avec succès." if success else "Échec de création."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def update_contact(
    contact_id: int,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    job: Optional[str] = None,
    production_id: Optional[int] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Met à jour un contact existant (mode patch : conserve les champs non spécifiés)."""
    from models import Contact, db
    from services.admin.contacts import update_contact as _update

    contact = db.session.get(Contact, contact_id)
    if not contact:
        return {"success": False, "message": f"Contact #{contact_id} introuvable."}

    form = {
        "first_name": first_name if first_name is not None else contact.first_name,
        "last_name": last_name if last_name is not None else contact.last_name,
        "job": job if job is not None else (contact.job_title or ""),
        "production_id": str(production_id) if production_id is not None else (str(contact.production_id) if contact.production_id else ""),
        "email": email if email is not None else (contact.mail or ""),
        "phone": phone if phone is not None else (contact.phone or ""),
        "notes": notes if notes is not None else "",
    }
    success = _update(contact_id, form)
    return {"success": success, "message": "Contact mis à jour." if success else "Contact introuvable."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("admin")
def delete_contact(contact_id: int, confirm: bool = False) -> Dict[str, Any]:
    """
    Supprime un contact par son ID.
    ATTENTION: Action destructrice (Scope 'admin' requis).
    L'IA doit obligatoirement l'exécuter d'abord avec confirm=False pour simuler l'impact et demander la confirmation à l'utilisateur humain.
    """
    from services.admin.contacts import get_contact_for_edit, delete_contact as _delete
    cnt = get_contact_for_edit(contact_id)
    if not cnt:
        return {"success": False, "message": f"Contact #{contact_id} introuvable."}

    if not confirm:
        cnt_name = f"{cnt.get('first_name', '')} {cnt.get('last_name', '')}".strip()
        return {
            "success": False,
            "status": "requires_confirmation",
            "contact_id": contact_id,
            "contact_name": cnt_name,
            "message": (
                f"⚠️ ATTENTION : Vous êtes sur le point de supprimer le contact #{contact_id} '{cnt_name}'. "
                "Veuillez demander la confirmation explicite à l'utilisateur humain devant son écran, "
                "puis ré-exécutez cet outil avec confirm=True."
            )
        }

    success = _delete(contact_id)
    return {"success": success, "message": f"Contact #{contact_id} supprimé." if success else "Échec de suppression."}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_contact_form_context() -> Dict[str, Any]:
    """Récupère la liste des sociétés de production pour alimenter le formulaire de contact."""
    from models import Production
    prods = Production.query.order_by(Production.name).all()
    return {
        "productions": [
            {
                "id": p.id,
                "name": p.name,
                "email": p.mail or "",
                "phone": p.phone or "",
                "address": p.address or "",
            }
            for p in prods
        ]
    }

