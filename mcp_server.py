"""
Serveur MCP (Model Context Protocol) Admin — Belle Vitesse (BV-MCP)
Expose les services d'administration de l'application Flask aux agents IA via SSE.
"""
import os
import json
import logging
from typing import Optional, List, Dict, Any

from mcp.server.fastmcp import FastMCP, Context
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app import create_app
from mcp_auth.auth import authenticate_mcp_token, check_user_has_role

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BV-MCP")

# Initialisation de l'application Flask pour l'accès aux services et modèles
flask_app = create_app()

# Initialisation de FastMCP
mcp = FastMCP("BV-MCP", host="0.0.0.0", port=int(os.getenv("MCP_SERVER_PORT", "8080")))


# ── Middleware d'authentification ──────────────────────────────────

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Laisser passer le healthcheck
        if request.url.path == "/health":
            try:
                with flask_app.app_context():
                    from models import db
                    from sqlalchemy import text
                    db.session.execute(text("SELECT 1"))
                return JSONResponse({"status": "healthy", "service": "BV-MCP"}, status_code=200)
            except Exception as e:
                return JSONResponse({"status": "unhealthy", "error": str(e)}, status_code=500)

        # Extraction du Token (Header Authorization: Bearer <token> ou Paramètre URL ?token=<token>)
        raw_token = None
        auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            raw_token = auth_header.split("Bearer ")[-1].strip()
        elif "token" in request.query_params:
            raw_token = request.query_params.get("token")
        elif "api_key" in request.query_params:
            raw_token = request.query_params.get("api_key")

        if not raw_token:
            logger.warning(f"⛔ Tentative d'accès MCP sans token depuis {request.client.host if request.client else 'inconnu'}")
            return JSONResponse({"error": "Authentification requise. Token manquant via Header Authorization ou paramètre URL ?token=<token>."}, status_code=401)

        with flask_app.app_context():
            user = authenticate_mcp_token(raw_token)
            if not user:
                logger.warning(f"⛔ Token MCP invalide fourni par {request.client.host if request.client else 'inconnu'}")
                return JSONResponse({"error": "Token API MCP invalide, révoqué ou expiré."}, status_code=401)

            # Attacher l'utilisateur au state de la requête Starlette
            request.state.user = user
            logger.info(f"🔑 Connexion MCP autorisée : User #{user.id} ({user.mail}) - Rôle: {user.role}")

        response = await call_next(request)
        return response


from functools import wraps

# ── Décorateur d'exécution sécurisée dans le contexte Flask ─────────

def run_in_flask_context(func):
    """Exécute une fonction dans le contexte d'application Flask."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        with flask_app.app_context():
            return func(*args, **kwargs)
    return wrapper


# ══════════════════════════════════════════════════════════════════
# 1. DOMAINE : PROJETS
# ══════════════════════════════════════════════════════════════════

@mcp.tool()
@run_in_flask_context
def list_projects() -> List[Dict[str, Any]]:
    """Liste tous les projets actifs avec détails complets (véhicules, décharges, contacts, pré-devis)."""
    from services.admin.projects import list_projects as _list_projects
    return _list_projects()


@mcp.tool()
@run_in_flask_context
def get_project(project_id: int) -> Optional[Dict[str, Any]]:
    """Récupère les détails d'un projet par son ID pour édition/affichage."""
    from services.admin.projects import get_project_for_edit
    return get_project_for_edit(project_id)


@mcp.tool()
@run_in_flask_context
def create_project(
    name: str,
    production_id: Optional[int] = None,
    pilot_contact_id: Optional[int] = None,
    production_contact_id: Optional[int] = None,
    dop_contact_id: Optional[int] = None,
    notes: Optional[str] = None,
    departure_date: Optional[str] = None,
    shoot_start: Optional[str] = None,
    shoot_end: Optional[str] = None,
    return_date: Optional[str] = None,
    vehicle_ids: Optional[List[str]] = None,
    head_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Crée un nouveau projet et génère automatiquement ses décharges pilote/production."""
    from services.admin.projects import create_project as _create_project

    class MultiDictMock(dict):
        def getlist(self, key):
            if key == "vehicle_ids":
                return vehicle_ids or []
            if key == "head_ids":
                return head_ids or []
            return []

    form_data = MultiDictMock({
        "name": name,
        "production_id": str(production_id) if production_id else "",
        "pilot_contact_id": str(pilot_contact_id) if pilot_contact_id else "",
        "production_contact_id": str(production_contact_id) if production_contact_id else "",
        "dop_contact_id": str(dop_contact_id) if dop_contact_id else "",
        "notes": notes or "",
        "departure_date": departure_date or "",
        "shoot_start": shoot_start or "",
        "shoot_end": shoot_end or "",
        "return_date": return_date or "",
    })

    success = _create_project(form_data)
    return {"success": success, "message": "Projet créé avec succès." if success else "Échec de la création."}


@mcp.tool()
@run_in_flask_context
def update_project(
    project_id: int,
    name: str,
    production_id: Optional[int] = None,
    pilot_contact_id: Optional[int] = None,
    production_contact_id: Optional[int] = None,
    dop_contact_id: Optional[int] = None,
    notes: Optional[str] = None,
    departure_date: Optional[str] = None,
    shoot_start: Optional[str] = None,
    shoot_end: Optional[str] = None,
    return_date: Optional[str] = None,
    vehicle_ids: Optional[List[str]] = None,
    head_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Met à jour un projet existant par son ID."""
    from services.admin.projects import update_project as _update_project

    class MultiDictMock(dict):
        def getlist(self, key):
            if key == "vehicle_ids":
                return vehicle_ids or []
            if key == "head_ids":
                return head_ids or []
            return []

    form_data = MultiDictMock({
        "name": name,
        "production_id": str(production_id) if production_id else "",
        "pilot_contact_id": str(pilot_contact_id) if pilot_contact_id else "",
        "production_contact_id": str(production_contact_id) if production_contact_id else "",
        "dop_contact_id": str(dop_contact_id) if dop_contact_id else "",
        "notes": notes or "",
        "departure_date": departure_date or "",
        "shoot_start": shoot_start or "",
        "shoot_end": shoot_end or "",
        "return_date": return_date or "",
    })

    success = _update_project(project_id, form_data)
    return {"success": success, "message": "Projet mis à jour." if success else "Projet introuvable."}


@mcp.tool()
@run_in_flask_context
def delete_project(project_id: int) -> Dict[str, Any]:
    """Supprime un projet par soft-delete et nettoie ses décharges associées."""
    from services.admin.projects import delete_project as _delete_project
    success = _delete_project(project_id)
    return {"success": success, "message": "Projet supprimé." if success else "Projet introuvable."}


@mcp.tool()
@run_in_flask_context
def get_project_form_context() -> Dict[str, Any]:
    """Récupère le contexte nécessaire aux formulaires de projet (listes de sélections)."""
    from services.admin.projects import get_project_form_context as _context
    return _context()


# ══════════════════════════════════════════════════════════════════
# 2. DOMAINE : INSPECTIONS (CHECKOUTS & CHECKINS)
# ══════════════════════════════════════════════════════════════════

@mcp.tool()
@run_in_flask_context
def list_checkouts() -> Dict[str, Any]:
    """Liste toutes les inspections de départ (Checkouts) avec leurs statistiques."""
    from services.admin.inspections import list_inspections_unified
    return list_inspections_unified("checkout")


@mcp.tool()
@run_in_flask_context
def list_checkins() -> Dict[str, Any]:
    """Liste toutes les inspections de retour (Checkins) avec leurs statistiques."""
    from services.admin.inspections import list_inspections_unified
    return list_inspections_unified("checkin")


@mcp.tool()
@run_in_flask_context
def get_inspection_detail(mode: str, record_id: int) -> Optional[Dict[str, Any]]:
    """Récupère les détails d'une inspection ('checkout' ou 'checkin') par ID."""
    from services.admin.inspections import get_inspection_detail_unified
    return get_inspection_detail_unified(mode, record_id)


@mcp.tool()
@run_in_flask_context
def delete_inspection(mode: str, record_id: int) -> Dict[str, Any]:
    """Supprime une inspection ('checkout' ou 'checkin') et ses fichiers associés."""
    from services.admin.inspections import delete_inspection_unified
    success = delete_inspection_unified(mode, record_id)
    return {"success": success, "message": "Inspection supprimée." if success else "Inspection introuvable."}


@mcp.tool()
@run_in_flask_context
def get_inspection_form_context(mode: str = "checkout") -> Dict[str, Any]:
    """Récupère le contexte du formulaire d'inspection (projets, véhicules, utilisateurs, checkpoints)."""
    from services.admin.inspections import get_unified_form_context
    return get_unified_form_context(mode)


# ══════════════════════════════════════════════════════════════════
# 3. DOMAINE : DÉCHARGES (WAIVERS)
# ══════════════════════════════════════════════════════════════════

@mcp.tool()
@run_in_flask_context
def list_pilot_waivers() -> List[Dict[str, Any]]:
    """Liste toutes les décharges de responsabilité pilote."""
    from services.admin.waivers import list_pilot_waivers as _list
    return _list()


@mcp.tool()
@run_in_flask_context
def list_production_waivers() -> List[Dict[str, Any]]:
    """Liste toutes les décharges de responsabilité production."""
    from services.admin.waivers import list_production_waivers as _list
    return _list()


@mcp.tool()
@run_in_flask_context
def generate_pilot_waiver(waiver_id: str) -> Dict[str, Any]:
    """Génère (fige le snapshot) une décharge pilote."""
    from services.admin.waivers import generate_pilot_waiver as _gen
    success, msg = _gen(waiver_id)
    return {"success": success, "message": msg}


@mcp.tool()
@run_in_flask_context
def generate_production_waiver(waiver_id: str) -> Dict[str, Any]:
    """Génère (fige le snapshot) une décharge production."""
    from services.admin.waivers import generate_production_waiver as _gen
    success, msg = _gen(waiver_id)
    return {"success": success, "message": msg}


@mcp.tool()
@run_in_flask_context
def send_pilot_waiver(waiver_id: str) -> Dict[str, Any]:
    """Envoie une décharge pilote par email au pilote."""
    from services.admin.waivers import send_pilot_waiver as _send
    success, msg = _send(waiver_id)
    return {"success": success, "message": msg}


@mcp.tool()
@run_in_flask_context
def send_production_waiver(waiver_id: str) -> Dict[str, Any]:
    """Envoie une décharge production par email au contact production."""
    from services.admin.waivers import send_production_waiver as _send
    success, msg = _send(waiver_id)
    return {"success": success, "message": msg}


@mcp.tool()
@run_in_flask_context
def reset_pilot_waiver(waiver_id: str) -> Dict[str, Any]:
    """Réinitialise complètement une décharge pilote."""
    from services.admin.waivers import reset_pilot_waiver as _reset
    success, msg = _reset(waiver_id)
    return {"success": success, "message": msg}


@mcp.tool()
@run_in_flask_context
def reset_production_waiver(waiver_id: str) -> Dict[str, Any]:
    """Réinitialise complètement une décharge production."""
    from services.admin.waivers import reset_production_waiver as _reset
    success, msg = _reset(waiver_id)
    return {"success": success, "message": msg}


# ══════════════════════════════════════════════════════════════════
# 4. DOMAINE : CONTACTS & PRODUCTIONS
# ══════════════════════════════════════════════════════════════════

@mcp.tool()
@run_in_flask_context
def list_contacts() -> List[Dict[str, Any]]:
    """Liste tous les contacts professionnels."""
    from services.admin.contacts import list_contacts as _list
    return _list()


@mcp.tool()
@run_in_flask_context
def create_contact(
    first_name: str,
    last_name: str,
    mail: Optional[str] = None,
    phone: Optional[str] = None,
    job_title: Optional[str] = None,
    production_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Crée un nouveau contact professionnel."""
    from services.admin.contacts import create_contact as _create
    form = {
        "first_name": first_name,
        "last_name": last_name,
        "mail": mail or "",
        "phone": phone or "",
        "job_title": job_title or "",
        "production_id": str(production_id) if production_id else None,
    }
    success = _create(form)
    return {"success": success, "message": "Contact créé." if success else "Échec de création."}


@mcp.tool()
@run_in_flask_context
def update_contact(
    contact_id: int,
    first_name: str,
    last_name: str,
    mail: Optional[str] = None,
    phone: Optional[str] = None,
    job_title: Optional[str] = None,
    production_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Met à jour un contact existant."""
    from services.admin.contacts import update_contact as _update
    form = {
        "first_name": first_name,
        "last_name": last_name,
        "mail": mail or "",
        "phone": phone or "",
        "job_title": job_title or "",
        "production_id": str(production_id) if production_id else None,
    }
    success = _update(contact_id, form)
    return {"success": success, "message": "Contact mis à jour." if success else "Contact introuvable."}


@mcp.tool()
@run_in_flask_context
def delete_contact(contact_id: int) -> Dict[str, Any]:
    """Supprime un contact."""
    from services.admin.contacts import delete_contact as _delete
    success = _delete(contact_id)
    return {"success": success, "message": "Contact supprimé." if success else "Contact introuvable."}


@mcp.tool()
@run_in_flask_context
def list_productions() -> List[Dict[str, Any]]:
    """Liste toutes les sociétés de production."""
    from services.admin.productions import list_productions as _list
    return _list()


@mcp.tool()
@run_in_flask_context
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
def update_production(
    production_id: int,
    name: str,
    address: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
) -> Dict[str, Any]:
    """Met à jour une société de production."""
    from services.admin.productions import update_production as _update
    form = {"name": name, "address": address or "", "email": email or "", "phone": phone or ""}
    success = _update(production_id, form)
    return {"success": success, "message": "Production mise à jour." if success else "Production introuvable."}


@mcp.tool()
@run_in_flask_context
def delete_production(production_id: int) -> Dict[str, Any]:
    """Supprime une société de production."""
    from services.admin.productions import delete_production as _delete
    success = _delete(production_id)
    return {"success": success, "message": "Production supprimée." if success else "Production introuvable."}


# ══════════════════════════════════════════════════════════════════
# 5. DOMAINE : UTILISATEURS
# ══════════════════════════════════════════════════════════════════

@mcp.tool()
@run_in_flask_context
def list_users() -> List[Dict[str, Any]]:
    """Liste tous les utilisateurs du système."""
    from services.admin.users import list_users as _list
    users = _list()
    return [u.to_dict() for u in users]


@mcp.tool()
@run_in_flask_context
def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Récupère les détails d'un utilisateur par son ID."""
    from services.admin.users import get_user as _get
    u = _get(user_id)
    return u.to_dict() if u else None


@mcp.tool()
@run_in_flask_context
def create_user(
    firstname: str,
    lastname: str,
    mail: str,
    role: str = "User",
    phone: Optional[str] = None,
    job: Optional[str] = None,
) -> Dict[str, Any]:
    """Crée un nouvel utilisateur."""
    from services.admin.users import create_user as _create
    data = {"firstname": firstname, "lastname": lastname, "mail": mail, "role": role, "phone": phone, "job": job}
    u = _create(data)
    return {"success": u is not None, "user": u.to_dict() if u else None}


@mcp.tool()
@run_in_flask_context
def update_user(
    user_id: int,
    firstname: Optional[str] = None,
    lastname: Optional[str] = None,
    mail: Optional[str] = None,
    role: Optional[str] = None,
    phone: Optional[str] = None,
    job: Optional[str] = None,
) -> Dict[str, Any]:
    """Met à jour les informations d'un utilisateur."""
    from services.admin.users import update_user as _update
    data = {}
    if firstname is not None: data["firstname"] = firstname
    if lastname is not None: data["lastname"] = lastname
    if mail is not None: data["mail"] = mail
    if role is not None: data["role"] = role
    if phone is not None: data["phone"] = phone
    if job is not None: data["job"] = job

    u = _update(user_id, data)
    return {"success": u is not None, "user": u.to_dict() if u else None}


@mcp.tool()
@run_in_flask_context
def delete_user(user_id: int) -> Dict[str, Any]:
    """Supprime un utilisateur du système."""
    from services.admin.users import delete_user as _delete
    success = _delete(user_id)
    return {"success": success, "message": "Utilisateur supprimé." if success else "Utilisateur introuvable."}


# ══════════════════════════════════════════════════════════════════
# 6. DOMAINE : TARIFICATION / PRICING
# ══════════════════════════════════════════════════════════════════

@mcp.tool()
@run_in_flask_context
def list_equipment_rates() -> Dict[str, Any]:
    """Liste tous les tarifs des équipements (véhicules, têtes, grip)."""
    from services.admin.pricing import list_equipment_rates as _list
    return _list()


@mcp.tool()
@run_in_flask_context
def update_equipment_daily_rate(table_name: str, record_id: str, value: float) -> Dict[str, Any]:
    """Met à jour le tarif journalier (daily_rate) d'un équipement ('vehicles', 'heads', 'grip_products')."""
    from services.admin.pricing import update_equipment_daily_rate as _update
    try:
        res = _update(table_name, record_id, value)
        return {"success": True, "item": res}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
@run_in_flask_context
def list_salary_rates() -> Dict[str, Any]:
    """Liste la grille complète des salaires groupée par poste."""
    from services.admin.pricing import list_salary_rates_grouped
    return dict(list_salary_rates_grouped())


@mcp.tool()
@run_in_flask_context
def add_salary_rate(group_name: str = "", annexe: str = "Annexe 1") -> Dict[str, Any]:
    """Ajoute une nouvelle position dans la grille des salaires."""
    from services.admin.pricing import add_salary_rate as _add
    return _add(group_name, annexe)


@mcp.tool()
@run_in_flask_context
def update_salary_rate(rate_id: int, field: str, value: Any) -> Dict[str, Any]:
    """Modifie un champ d'un tarif salarial (avec recalcul automatique des colonnes dépendantes)."""
    from services.admin.pricing import update_salary_rate as _update
    try:
        res = _update(rate_id, field, value)
        return {"success": True, "result": res}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
@run_in_flask_context
def delete_salary_rate(rate_id: int) -> Dict[str, Any]:
    """Supprime une position salariale."""
    from services.admin.pricing import delete_salary_rate as _delete
    try:
        success = _delete(rate_id)
        return {"success": success}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
@run_in_flask_context
def list_logistics_rates() -> List[Dict[str, Any]]:
    """Liste les tarifs logistiques."""
    from services.admin.pricing import list_logistics_rates as _list
    return _list()


@mcp.tool()
@run_in_flask_context
def add_logistics_rate() -> Dict[str, Any]:
    """Ajoute un nouveau tarif logistique."""
    from services.admin.pricing import add_logistics_rate as _add
    return _add()


@mcp.tool()
@run_in_flask_context
def update_logistics_rate(rate_id: int, field: str, value: Any) -> Dict[str, Any]:
    """Met à jour un champ d'un tarif logistique."""
    from services.admin.pricing import update_logistics_rate as _update
    try:
        res = _update(rate_id, field, value)
        return {"success": True, "rate": res}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
@run_in_flask_context
def get_invoice_factor() -> float:
    """Récupère le coefficient de conversion intermittent -> facture."""
    from services.admin.pricing import get_invoice_factor as _get
    return _get()


# ══════════════════════════════════════════════════════════════════
# 7. DOMAINE : PRÉ-DEVIS (PRE-QUOTES)
# ══════════════════════════════════════════════════════════════════

@mcp.tool()
@run_in_flask_context
def list_pre_quotes() -> List[Dict[str, Any]]:
    """Liste tous les pré-devis."""
    from services.admin.pre_quote import list_pre_quotes as _list
    quotes = _list()
    return [q.to_dict() for q in quotes]


@mcp.tool()
@run_in_flask_context
def get_pre_quote(quote_id: int) -> Optional[Dict[str, Any]]:
    """Récupère un pré-devis par son ID."""
    from models import PreQuote
    q = PreQuote.query.get(quote_id)
    if not q:
        return None
    d = q.to_dict()
    d["prestations"] = q.prestations
    return d


@mcp.tool()
@run_in_flask_context
def create_pre_quote(
    production_id: int,
    project_name: Optional[str] = None,
    prestations: Optional[List[Dict[str, Any]]] = None,
    tva_rate: float = 20.0,
    insurance_rate: float = 10.0,
    insurance_based_on_undiscounted: bool = False,
    status: str = "draft",
    project_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Crée un nouveau pré-devis pour une production."""
    from services.admin.pre_quote import create_pre_quote as _create
    data = {
        "production_id": production_id,
        "project_name": project_name,
        "prestations": prestations or [],
        "tva_rate": tva_rate,
        "insurance_rate": insurance_rate,
        "insurance_based_on_undiscounted": insurance_based_on_undiscounted,
        "status": status,
        "project_id": project_id,
    }
    q = _create(data)
    return {"success": True, "pre_quote": q.to_dict()}


@mcp.tool()
@run_in_flask_context
def update_pre_quote(quote_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """Met à jour un pré-devis existant."""
    from services.admin.pre_quote import update_pre_quote as _update
    q = _update(quote_id, data)
    return {"success": True, "pre_quote": q.to_dict()}


@mcp.tool()
@run_in_flask_context
def delete_pre_quote(quote_id: int) -> Dict[str, Any]:
    """Supprime un pré-devis."""
    from services.admin.pre_quote import delete_pre_quote as _delete
    success = _delete(quote_id)
    return {"success": success, "message": "Pré-devis supprimé." if success else "Introuvable."}


@mcp.tool()
@run_in_flask_context
def create_pre_quote_version(quote_id: int, note: str = "") -> Dict[str, Any]:
    """Crée une version archivée (snapshot PDF) d'un pré-devis."""
    from services.admin.pre_quote import create_pre_quote_version as _ver
    v = _ver(quote_id, note)
    return {"success": True, "version": v.to_dict()}


# ══════════════════════════════════════════════════════════════════
# 8. DOMAINE : CALENDRIER & ABONNEMENTS
# ══════════════════════════════════════════════════════════════════

@mcp.tool()
@run_in_flask_context
def get_calendar_events() -> List[Dict[str, Any]]:
    """Récupère les événements du calendrier des tournages/départs/retours."""
    from services.admin.calendar import get_calendar_events as _events
    return _events()


@mcp.tool()
@run_in_flask_context
def list_calendar_subscriptions() -> List[Dict[str, Any]]:
    """Liste tous les abonnements calendrier ICS actifs."""
    from services.admin.calendar_subscriptions import list_all_subscriptions
    subs = list_all_subscriptions()
    return [s.to_dict() for s in subs]


@mcp.tool()
@run_in_flask_context
def create_calendar_subscription(user_id: int) -> Dict[str, Any]:
    """Crée un abonnement calendrier ICS pour un utilisateur."""
    from services.admin.calendar_subscriptions import create_subscription
    s = create_subscription(user_id)
    return {"success": s is not None, "subscription": s.to_dict() if s else None}


# ══════════════════════════════════════════════════════════════════
# 9. DOMAINE : CATALOGUE & AIRTABLE
# ══════════════════════════════════════════════════════════════════

@mcp.tool()
@run_in_flask_context
def get_catalog_data(with_prices: bool = True) -> Dict[str, Any]:
    """Récupère les données complètes du catalogue (véhicules, têtes, specs, configs)."""
    from services.admin.catalog import get_catalog_data as _data
    return _data(with_prices=with_prices)


@mcp.tool()
@run_in_flask_context
def sync_airtable(sync_images: bool = False) -> Dict[str, Any]:
    """Déclenche la synchronisation depuis Airtable vers MySQL."""
    from services.sync_airtable import run_sync
    config = {
        "airtable_token": os.getenv("AIRTABLE_SECRET_TOKEN"),
        "airtable_base_id": os.getenv("AIRTABLE_BASE_ID"),
        "mysql_host": os.getenv("MYSQL_HOST", "bv_mysql"),
        "mysql_user": os.getenv("MYSQL_USER", "Maxcongi"),
        "mysql_password": os.getenv("MYSQL_PASSWORD", ""),
        "mysql_database": os.getenv("MYSQL_DATABASE", "BelleVitesse"),
        "use_ssh_tunnel": False if os.getenv("FLASK_ENV") == "production" else True,
    }
    try:
        run_sync(config, sync_db=True, sync_images=sync_images)
        return {"success": True, "message": "Synchronisation Airtable effectuée."}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
@run_in_flask_context
def update_catalog_pdf(with_prices: bool = True) -> Dict[str, Any]:
    """Régénère le PDF du catalogue et l'enregistre sur le serveur."""
    from services.admin.catalog import update_stored_catalog
    success, msg = update_stored_catalog(with_prices=with_prices)
    return {"success": success, "message": msg}


# ══════════════════════════════════════════════════════════════════
# 10. DOMAINE : SYSTÈME & PARAMÈTRES
# ══════════════════════════════════════════════════════════════════

@mcp.tool()
@run_in_flask_context
def get_app_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Récupère un paramètre global de l'application par sa clé."""
    from models import AppSetting
    return AppSetting.get(key, default)


@mcp.tool()
@run_in_flask_context
def set_app_setting(key: str, value: str) -> Dict[str, Any]:
    """Définit la valeur d'un paramètre global de l'application."""
    from models import AppSetting
    s = AppSetting.set(key, value)
    return {"success": True, "key": s.key, "value": s.value}


@mcp.tool()
@run_in_flask_context
def list_app_settings() -> Dict[str, str]:
    """Liste tous les paramètres globaux de l'application."""
    from models import AppSetting
    settings = AppSetting.query.all()
    return {s.key: s.value for s in settings}


@mcp.tool()
@run_in_flask_context
def health_check() -> Dict[str, Any]:
    """Vérifie l'état du serveur et de la connexion à la base de données."""
    from models import db
    from sqlalchemy import text
    try:
        db.session.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected", "env": os.getenv("FLASK_ENV")}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@mcp.tool()
@run_in_flask_context
def clear_cache() -> Dict[str, Any]:
    """Vide le cache Flask-Caching."""
    from extensions import cache
    try:
        cache.clear()
        return {"success": True, "message": "Cache vider avec succès."}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
@run_in_flask_context
def get_newsletter_subscribers() -> List[Dict[str, Any]]:
    """Liste les abonnés à la newsletter."""
    from models import NewsletterSubscriber
    subs = NewsletterSubscriber.query.all()
    return [{"id": s.id, "email": s.email, "subscribed_at": s.subscribed_at.isoformat() if s.subscribed_at else None} for s in subs]


# ══════════════════════════════════════════════════════════════════
# 11. DOMAINE : VEHICLES & CHECKPOINTS
# ══════════════════════════════════════════════════════════════════

@mcp.tool()
@run_in_flask_context
def get_vehicles_with_config() -> List[Dict[str, Any]]:
    """Liste tous les véhicules avec leur configuration actuelle de points de contrôle."""
    from services.admin.vehicle_config import get_vehicles_with_config as _get
    return _get()


@mcp.tool()
@run_in_flask_context
def save_vehicle_checkpoint_config(vehicle_id: str, enabled_keys: List[str]) -> Dict[str, Any]:
    """Sauvegarde la configuration des points de contrôle activés pour un véhicule."""
    from services.admin.vehicle_config import save_vehicle_checkpoint_config as _save
    success = _save(vehicle_id, enabled_keys)
    return {"success": success, "message": "Configuration sauvegardée."}


@mcp.tool()
@run_in_flask_context
def get_checkpoints_for_vehicle(vehicle_id: str) -> List[Dict[str, Any]]:
    """Récupère la liste des points de contrôle applicables pour un véhicule spécifique."""
    from utils.checkpoints import get_checkpoints_for_vehicle as _get
    return _get(vehicle_id)


# ── Configuration du serveur Starlette avec le middleware d'auth ───

if __name__ == "__main__":
    port = int(os.getenv("MCP_SERVER_PORT", "8080"))
    logger.info(f"🚀 Lancement du serveur BV-MCP sur 0.0.0.0:{port}...")

    # FastMCP SSE app initialization with AuthMiddleware
    try:
        import uvicorn
        sse_app = getattr(mcp, "_sse_app", None) or getattr(mcp, "sse_app", None)
        if callable(sse_app):
            asgi_app = AuthMiddleware(sse_app())
            uvicorn.run(asgi_app, host="0.0.0.0", port=port)
        else:
            mcp.run(transport="sse")
    except Exception as err:
        logger.warning(f"⚠️ Démarrage avec fallback mcp.run: {err}")
        mcp.run(transport="sse")
