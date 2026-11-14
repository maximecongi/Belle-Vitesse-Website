"""
Périmètre d'accès aux projets par rôle.

Les rôles « privilégiés » (Commercial, Manager, Administrateur, Super Administrateur, Associé) voient tous
les projets. Les autres rôles (Technicien et tout rôle non reconnu, par sécurité) ne voient que les
projets dont ils font partie : Commercial du projet, Technicien BV, Référent plateau, ou contact
Pilote / Opérateur Remote Head rapproché de leur fiche utilisateur (même e-mail, sinon même nom).

Convention : un « scope » vaut `None` pour un accès complet, sinon l'ID de l'utilisateur dont on
restreint la vue (0 si l'utilisateur est inconnu : aucun projet visible).
"""
from typing import Optional

from flask import abort, g, has_request_context, session

from models import Project, User, db
from utils.decorators import normalize_role

FULL_ACCESS_ROLES = frozenset({
    "commercial", "manager", "administrateur", "super administrateur", "associé",
})


def is_project_restricted_role(role) -> bool:
    """Vrai si le rôle ne voit que les projets auxquels l'utilisateur est rattaché."""
    return normalize_role(role) not in FULL_ACCESS_ROLES


def project_scope_for(role, user_id) -> Optional[int]:
    """Calcule le scope d'un utilisateur à partir de son rôle et de son ID."""
    if not is_project_restricted_role(role):
        return None
    try:
        return int(user_id or 0)
    except (TypeError, ValueError):
        return 0


def project_scope_for_user(user) -> Optional[int]:
    """Scope d'une instance User (ex. propriétaire d'un abonnement calendrier)."""
    if user is None:
        return 0
    return project_scope_for(user.role, user.id)


def session_project_scope() -> Optional[int]:
    """Scope de l'utilisateur connecté à l'ERP (session admin)."""
    if not has_request_context():
        return None
    return project_scope_for(session.get("admin_user_role"), session.get("admin_user_id"))


def api_project_scope() -> Optional[int]:
    """Scope de l'utilisateur authentifié par JWT (API mobile)."""
    user = getattr(g, "current_user", None)
    return project_scope_for_user(user)


def matching_contact_ids(user_id: int) -> list:
    """
    IDs des contacts qui désignent le même utilisateur BV (même règle que Project._is_same_person :
    même e-mail, sinon même nom complet). Permet de retrouver un technicien affecté comme contact
    du projet (Pilote, Opérateur Remote Head).
    """
    from models import Contact

    user = db.session.get(User, user_id) if user_id else None
    if user is None:
        return []
    u_mail = (user.mail or "").strip().lower()
    u_last = (user.lastname or "").strip().lower()
    filters = []
    if u_mail:
        filters.append(db.func.lower(db.func.trim(Contact.mail)) == u_mail)
    if u_last:
        # Pré-filtre SQL sur le nom ; la comparaison exacte se fait via _is_same_person
        filters.append(db.func.lower(Contact.last_name).like(f"%{u_last}%"))
    if not filters:
        return []
    candidates = Contact.query.filter(db.or_(*filters)).all()
    return [c.id for c in candidates if Project._is_same_person(c, user)]


def project_member_condition(user_id: int):
    """
    Condition SQL : l'utilisateur fait partie de l'équipe du projet, soit par un rôle BV nominatif
    (Commercial, Technicien BV, Référent plateau), soit comme contact Pilote ou Opérateur Remote Head
    (ce dernier seulement si au moins une tête est affectée, comme dans l'affichage du projet).
    """
    conditions = [
        Project.commercial_user_id == user_id,
        Project.bv_technicians.any(User.id == user_id),
        Project.bv_referents.any(User.id == user_id),
    ]
    contact_ids = matching_contact_ids(user_id)
    if contact_ids:
        conditions.append(Project.pilot_contact_id.in_(contact_ids))
        conditions.append(db.and_(
            Project.remote_head_operator_contact_id.in_(contact_ids),
            Project.heads_to_check.isnot(None),
            db.func.trim(Project.heads_to_check) != "",
        ))
    return db.or_(*conditions)


def scope_project_query(query, scope: Optional[int]):
    """Restreint une requête (portant sur Project ou jointe à Project) au périmètre du scope."""
    if scope is None:
        return query
    return query.filter(project_member_condition(scope))


def can_access_project(project_id, scope: Optional[int]) -> bool:
    """Vrai si le projet (ID interne ou code métier BVPR-*) est visible pour ce scope."""
    if scope is None:
        return True
    if project_id in (None, ""):
        return False
    from utils.entity_resolvers import resolve_project

    project = resolve_project(project_id)
    if project is None:
        return False
    return bool(db.session.query(
        Project.query.filter(Project.id == project.id, project_member_condition(scope)).exists()
    ).scalar())


def install_project_scope_guard(bp, resolve_access):
    """
    Installe sur un blueprint admin un contrôle d'accès exécuté avant chaque vue :
    - `resolve_access(view_args, scope)` renvoie False si l'enregistrement ciblé par l'URL est hors
      périmètre (→ 404) ; None/True sinon.
    - en écriture (POST/PUT/PATCH), un `project_id` soumis par formulaire/JSON doit être accessible,
      pour empêcher de rattacher un enregistrement à un projet hors périmètre.
    Sans effet pour les rôles à accès complet et pour les visiteurs non authentifiés (laissés au
    décorateur `require_roles`, qui redirige vers la connexion).
    """
    from flask import request

    @bp.before_request
    def _project_scope_guard():
        if not session.get("admin_authenticated"):
            return None
        scope = session_project_scope()
        if scope is None:
            return None
        if resolve_access(request.view_args or {}, scope) is False:
            abort(404)
        if request.method in ("POST", "PUT", "PATCH"):
            payload = request.form or request.get_json(silent=True) or {}
            submitted = payload.get("project_id") if hasattr(payload, "get") else None
            if submitted not in (None, "") and not can_access_project(submitted, scope):
                abort(404)
        return None

    return _project_scope_guard


# Contrôles de périmètre des blueprints de l'API mobile : {nom du blueprint: resolve_access}.
# Exécutés par `utils.jwt_auth.require_api_auth` une fois l'utilisateur JWT authentifié.
API_SCOPE_GUARDS = {}


def install_api_project_scope_guard(bp, resolve_access):
    """Équivalent API (JWT) de `install_project_scope_guard`."""
    API_SCOPE_GUARDS[bp.name] = resolve_access


def check_api_project_scope() -> bool:
    """Vrai si la requête API courante respecte le périmètre projets de l'utilisateur JWT."""
    from flask import request

    scope = api_project_scope()
    if scope is None:
        return True
    resolve_access = API_SCOPE_GUARDS.get(request.blueprint)
    if resolve_access is not None and resolve_access(request.view_args or {}, scope) is False:
        return False
    if request.method in ("POST", "PUT", "PATCH"):
        payload = request.get_json(silent=True) or request.form or {}
        submitted = payload.get("project_id") if hasattr(payload, "get") else None
        if submitted not in (None, "") and not can_access_project(submitted, scope):
            return False
    return True


_SESSION = object()


def ensure_project_access(project_id, scope=_SESSION) -> None:
    """Interrompt la requête par une 404 si le projet n'est pas accessible (session admin par défaut)."""
    if scope is _SESSION:
        scope = session_project_scope()
    if not can_access_project(project_id, scope):
        abort(404)


def scope_incident_query(query, scope: Optional[int]):
    """
    Restreint une requête sur Incident (avec Project en jointure externe) au périmètre du scope :
    incidents des projets de l'équipe BV, plus les incidents sans projet que l'utilisateur a
    lui-même signalés.
    """
    if scope is None:
        return query
    from models import Incident

    return query.filter(db.or_(
        project_member_condition(scope),
        db.and_(Incident.project_id.is_(None), Incident.reported_by_id == scope),
    ))


def can_access_incident(incident, scope: Optional[int]) -> bool:
    """Vrai si l'incident est visible pour ce scope (mêmes règles que `scope_incident_query`)."""
    if scope is None:
        return True
    if incident is None:
        return False
    if incident.project_id:
        return can_access_project(incident.project_id, scope)
    return bool(incident.reported_by_id) and incident.reported_by_id == scope
