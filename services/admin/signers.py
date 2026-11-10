"""
services/admin/signers.py — Annuaire des signataires (contacts ERP + équipe Belle Vitesse).

Sert l'autocomplétion des modales d'invitation (CGL, BVSR, BVPA, BVRA, incidents) et
le rattachement d'un document à la fiche contact de son signataire.
"""
import logging

from sqlalchemy import func, or_

from models import Contact, Project, User, db

logger = logging.getLogger(__name__)

PROJECT_CONTACT_ROLES = (
    ("production_contact", "Contact production"),
    ("pilot_contact", "Pilote"),
    ("dop_contact", "Chef opérateur"),
    ("first_ac_contact", "1er assistant caméra"),
    ("key_grip_contact", "Chef machiniste"),
)

GROUP_LABELS = {
    "project": "Contacts du projet",
    "production": "Contacts de la production",
    "contacts": "Autres contacts",
    "team": "Équipe Belle Vitesse",
}
GROUP_ORDER = ("project", "production", "contacts", "team")


def _clean(value):
    value = (value or "").strip()
    return value if value and value not in ("—", "None") else ""


def _contact_entry(c, group, project_role=None):
    production_name = c.production_rel.name if getattr(c, "production_rel", None) else ""
    return {
        "kind": "contact",
        "id": c.id,
        "first_name": _clean(c.first_name),
        "last_name": _clean(c.last_name),
        "full_name": f"{_clean(c.first_name)} {_clean(c.last_name)}".strip(),
        "mail": _clean(c.mail),
        "phone": _clean(c.phone),
        "job_title": _clean(c.job_title),
        "company": production_name,
        "project_role": project_role or "",
        "group": group,
        "group_label": GROUP_LABELS[group],
    }


def _user_entry(u):
    return {
        "kind": "user",
        "id": u.id,
        "first_name": _clean(u.firstname),
        "last_name": _clean(u.lastname),
        "full_name": f"{_clean(u.firstname)} {_clean(u.lastname)}".strip(),
        "mail": _clean(u.mail),
        "phone": _clean(u.phone),
        "job_title": _clean(u.job),
        "company": "Belle Vitesse",
        "project_role": "",
        "group": "team",
        "group_label": GROUP_LABELS["team"],
    }


def _token_filter(tokens, columns):
    """Chaque mot saisi doit apparaître dans au moins une des colonnes (insensible à la casse)."""
    clauses = []
    for tok in tokens:
        pattern = f"%{tok}%"
        clauses.append(or_(*[func.lower(func.coalesce(col, "")).like(pattern) for col in columns]))
    return clauses


def search_signers(query="", project_id=None, limit=12, include_team=True):
    """
    Recherche des signataires potentiels.

    Classement : contacts du projet → contacts de sa production → autres contacts → équipe BV.
    Sans saisie, seules les suggestions du projet et de sa production sont renvoyées.
    """
    tokens = [t for t in (query or "").lower().split() if t]
    limit = max(1, min(int(limit or 12), 50))

    project = db.session.get(Project, int(project_id)) if project_id and str(project_id).isdigit() else None

    project_roles = {}
    if project:
        for attr, label in PROJECT_CONTACT_ROLES:
            c = getattr(project, attr, None)
            if c is not None and c.id not in project_roles:
                project_roles[c.id] = label
    production_id = project.production_id if project else None

    contact_query = Contact.query
    if tokens:
        contact_query = contact_query.filter(*_token_filter(
            tokens, [Contact.first_name, Contact.last_name, Contact.mail, Contact.job_title]))
    elif project:
        scope = [Contact.id.in_(list(project_roles) or [-1])]
        if production_id:
            scope.append(Contact.production_id == production_id)
        contact_query = contact_query.filter(or_(*scope))
    else:
        contact_query = contact_query.filter(db.false())

    results = []
    for c in contact_query.order_by(Contact.last_name, Contact.first_name).limit(200).all():
        if c.id in project_roles:
            group = "project"
        elif production_id and c.production_id == production_id:
            group = "production"
        else:
            group = "contacts"
        results.append(_contact_entry(c, group, project_roles.get(c.id)))

    if include_team and tokens:
        users = User.query.filter(*_token_filter(
            tokens, [User.firstname, User.lastname, User.mail, User.job])).order_by(User.lastname).limit(50).all()
        results.extend(_user_entry(u) for u in users)

    results.sort(key=lambda r: (GROUP_ORDER.index(r["group"]), r["last_name"].lower(), r["first_name"].lower()))
    return results[:limit]


def project_default_signer(project, role):
    """Contact du projet pressenti pour un rôle donné (production pour les CGL, pilote...)."""
    if not project:
        return None
    if role == "production":
        return project.production_contact
    if role == "pilot":
        return project.pilot_contact
    return None


def upsert_signer_contact(project, first_name, last_name, mail=None, phone=None, job_title=None,
                          contact_id=None, user_id=None):
    """
    Retourne la fiche contact ERP du signataire, en la créant si besoin.

    - contact choisi dans l'autocomplétion : réutilisé (ses champs vides sont complétés) ;
    - membre de l'équipe BV : aucun contact créé (il existe déjà en tant qu'utilisateur) ;
    - saisie libre : recherche par e-mail puis par prénom + nom, sinon création rattachée
      à la production du projet.
    """
    first_name, last_name = _clean(first_name), _clean(last_name)
    mail, phone, job_title = _clean(mail) or None, _clean(phone) or None, _clean(job_title) or None

    if user_id and str(user_id).isdigit():
        return None

    contact = None
    if contact_id and str(contact_id).isdigit():
        contact = db.session.get(Contact, int(contact_id))

    if contact is None and mail:
        contact = Contact.query.filter(func.lower(func.trim(Contact.mail)) == mail.lower()).first()

    if contact is None:
        if not first_name or not last_name:
            return None
        production_id = project.production_id if project else None
        name_match = Contact.query.filter(
            func.lower(func.trim(Contact.first_name)) == first_name.lower(),
            func.lower(func.trim(Contact.last_name)) == last_name.lower(),
        )
        if production_id:
            name_match = name_match.order_by((Contact.production_id == production_id).desc())
        contact = name_match.first()

    if contact is None:
        contact = Contact(
            first_name=first_name,
            last_name=last_name,
            mail=mail,
            phone=phone,
            job_title=job_title,
            production_id=project.production_id if project else None,
        )
        db.session.add(contact)
        db.session.flush()
        logger.info(f"👤 Contact créé automatiquement depuis une invitation : {first_name} {last_name}")
        return contact

    # Enrichit les champs vides de la fiche existante sans rien écraser
    for attr, val in (("mail", mail), ("phone", phone), ("job_title", job_title)):
        if val and not _clean(getattr(contact, attr, None)):
            setattr(contact, attr, val)
    return contact
