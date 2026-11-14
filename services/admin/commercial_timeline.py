"""
Timeline commerciale d'un projet : saisie des prises de contact, statut commercial déduit,
calcul de la frise (espacement proportionnel au temps) et détection des devis à relancer.

Échelle de la frise :
- un point par jour (les échanges d'une même journée sont regroupés, avec un compteur) ;
- l'écart entre deux points est proportionnel à la racine carrée du nombre de jours écoulés
  (les longs silences sont compressés, les écarts courts restent lisibles) ;
- chaque intervalle reçoit une largeur minimale (points jamais superposés) ;
- un silence de plus de BREAK_THRESHOLD_DAYS jours est plafonné et signalé par une coupure « ≈ » ;
- la partie « à venir » occupe au plus MAX_FUTURE_SHARE_PCT % de la largeur.
"""
import logging
import math
import os
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import func

from models import Contact, Production, Project, User, db
from models.commercial_event import (
    CLOSED_COMMERCIAL_STATUSES,
    COMMERCIAL_STATUS_LABELS,
    COMMERCIAL_STATUS_VARIANTS,
    EVENT_TYPE_GROUPS,
    EVENT_TYPE_LABELS,
    EVENT_TYPE_MILESTONES,
    LOST_REASON_LABELS,
    LOST_REASONS,
    PLANNABLE_EVENT_TYPES,
    PLANNED_ONLY_EVENT_TYPES,
    QUOTE_EVENT_TYPES,
    ProjectCommercialEvent,
)
from services.admin.contacts import NEW_CONTACT_VALUE, find_or_build_contact

PARIS_TZ = ZoneInfo("Europe/Paris")
logger = logging.getLogger(__name__)

# Échelle de la frise
BREAK_THRESHOLD_DAYS = 60      # au-delà, l'intervalle est plafonné (coupure « ≈ »)
MIN_SEGMENT_PCT = 4.0          # largeur minimale d'un intervalle (% de la frise)
MIN_DATE_LABEL_GAP_PCT = 9.0   # écart minimal entre deux dates affichées sous la frise
MIN_GAP_LABEL_PCT = 7.0        # largeur minimale d'un intervalle pour afficher sa durée
MIN_GAP_LABEL_DAYS = 2         # durée minimale d'un intervalle pour l'afficher
MAX_FUTURE_SHARE_PCT = 40.0    # part maximale de la frise occupée par les événements à venir

# Relance des devis : délai sans réponse au-delà duquel une relance est conseillée.
# Réglable via QUOTE_FOLLOWUP_DAYS dans le .env (badge de la fiche, tableau de bord, cron et MCP) ;
# l'application web le lit au démarrage, le cron à chaque exécution.
QUOTE_FOLLOWUP_DAYS = int(os.getenv("QUOTE_FOLLOWUP_DAYS", "10"))
# Événements « sortants » : s'ils sont les derniers, le client n'a pas encore répondu
OUTGOING_EVENT_TYPES = {"email_out", "call_out", "quote_sent", "quote_followup"}

_MONTHS_SHORT = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
                 "juil.", "août", "sept.", "oct.", "nov.", "déc."]
_DAYS_SHORT = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]


class CommercialEventNotFoundError(Exception):
    pass


def paris_now():
    """Heure murale de Paris (naïve), cohérente avec la saisie des événements."""
    return datetime.now(PARIS_TZ).replace(tzinfo=None)


# ── Statut commercial ──────────────────────────────────────────

def _chronological(events):
    return sorted(events, key=lambda e: (e.occurred_at, e.id or 0))


def _done(events):
    """Prises de contact réelles (les événements à venir / planifiés sont exclus)."""
    return [e for e in _chronological(events) if not e.is_planned]


def _planned(events):
    return [e for e in _chronological(events) if e.is_planned]


def reference_quote(events, until=None):
    """
    Devis de référence d'un projet : le plus récent « Devis envoyé » réalisé dont le montant HT est renseigné
    (un devis révisé remplace le précédent). `until` (datetime) : seuls les devis envoyés jusqu'à cette date.
    """
    quotes = [e for e in _done(events)
              if e.event_type in QUOTE_EVENT_TYPES and e.quote_amount is not None
              and (until is None or e.occurred_at <= until)]
    return quotes[-1] if quotes else None


def reference_quote_amount(events, until=None):
    quote = reference_quote(events, until=until)
    return quote.quote_total if quote else None


def pending_quotes_summary(projects):
    """
    Devis en attente de réponse (projets au statut « Devis envoyé ») : nombre, montant HT cumulé des devis
    de référence et nombre de devis sans montant renseigné.
    """
    pending = [p for p in projects if p.commercial_status == "quote_sent"]
    amounts = [reference_quote_amount(p.commercial_events) for p in pending]
    return {
        "count": len(pending),
        "amount": round(sum(a for a in amounts if a is not None), 2),
        "without_amount": sum(1 for a in amounts if a is None),
    }


def compute_commercial_status(events, current_status=None):
    """
    Statut atteint par le dernier jalon (devis, confirmation, facture, abandon…).
    Sans jalon : le projet reste « non suivi » (None) s'il l'était, sinon « Demande en cours ».
    """
    status = None
    for ev in _done(events):  # un événement à venir ne change jamais le statut
        milestone = EVENT_TYPE_MILESTONES.get(ev.event_type)
        if milestone:
            status = milestone
    if status:
        return status
    return None if current_status is None else "prospect"


def recompute_commercial_status(project):
    project.commercial_status = compute_commercial_status(
        project.commercial_events, project.commercial_status
    )
    return project.commercial_status


# ── Saisie ─────────────────────────────────────────────────────

def _parse_occurred_at(date_str, time_str):
    try:
        day = datetime.strptime((date_str or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("La date de la prise de contact est invalide.")
    at = time(0, 0)
    if time_str and time_str.strip():
        try:
            at = datetime.strptime(time_str.strip(), "%H:%M").time()
        except ValueError:
            raise ValueError("L'heure de la prise de contact est invalide.")
    return datetime.combine(day, at)


def _new_contact_production_id(project, new_contact):
    """
    Production rattachée au nouveau contact : celle choisie dans la saisie (vide = freelance),
    ou par défaut celle du projet quand le choix n'est pas fourni (ex. outil MCP).
    """
    if not new_contact or new_contact.get("production_id") is None:
        return project.production_id
    raw = str(new_contact.get("production_id")).strip()
    if not raw:
        return None
    try:
        production = db.session.get(Production, int(raw))
    except (TypeError, ValueError):
        production = None
    if not production:
        raise ValueError("Production du nouveau contact introuvable.")
    return production.id


def _as_bool(value):
    return str(value).strip().lower() in ("1", "true", "on", "yes", "oui") if value is not None else False


def _validated_fields(project, *, event_type, date_str, time_str, contact_id, summary,
                      lost_reason, new_contact, now, is_planned=False, quote_amount=None):
    """Valide la saisie (ajout ou modification) et retourne les valeurs à enregistrer."""
    if event_type not in EVENT_TYPE_LABELS:
        raise ValueError("Type de prise de contact inconnu.")

    is_planned = _as_bool(is_planned)
    occurred_at = _parse_occurred_at(date_str, time_str)
    today = (now or paris_now()).date()
    if is_planned:
        if event_type not in PLANNABLE_EVENT_TYPES:
            raise ValueError(f"« {EVENT_TYPE_LABELS[event_type]} » ne peut pas être planifié.")
        if occurred_at.date() < today:
            raise ValueError("La date d'un événement à venir ne peut pas être dans le passé.")
    else:
        if event_type in PLANNED_ONLY_EVENT_TYPES:
            raise ValueError(f"« {EVENT_TYPE_LABELS[event_type]} » ne peut être qu'un événement à venir.")
        if occurred_at.date() > today:
            raise ValueError("La date de la prise de contact ne peut pas être dans le futur. "
                             "Pour un échange prévu, choisissez « À venir ».")

    if event_type == "lost":
        if lost_reason not in LOST_REASON_LABELS:
            raise ValueError("Indiquez le motif de l'abandon.")
    else:
        lost_reason = None

    # Montant total HT du devis : facultatif, uniquement sur « Devis envoyé » (0 ou vide = non renseigné)
    amount = None
    if event_type in QUOTE_EVENT_TYPES:
        from services.admin.projects.crud import _parse_amount
        amount = _parse_amount(quote_amount, "montant total HT du devis") or None

    # En dernier : un nouveau contact n'est ajouté à la session qu'une fois tout le reste validé
    contact = None
    if contact_id == NEW_CONTACT_VALUE:
        contact = find_or_build_contact(new_contact or {}, production_id=_new_contact_production_id(project, new_contact))
    elif contact_id not in (None, ""):
        try:
            contact = db.session.get(Contact, int(contact_id))
        except (TypeError, ValueError):
            contact = None
        if not contact:
            raise ValueError("Contact introuvable.")

    return {
        "event_type": event_type,
        "is_planned": is_planned,
        "occurred_at": occurred_at,
        "contact": contact,
        "summary": (summary or "").strip()[:500] or None,
        "lost_reason": lost_reason,
        "quote_amount": amount,
    }


# ── Fichier du devis (« Devis envoyé ») ────────────────────────
# Copie locale : OUTPUT_FOLDER/DEVIS/<id projet>/<id événement>_<nom>, envoyée dans 1_DEVIS sur kDrive.

def _quote_file_rel_path(event, filename):
    from werkzeug.utils import secure_filename
    return f"DEVIS/{event.project_id}/{event.id}_{secure_filename(filename) or 'devis'}"


def _checked_quote_file(quote_file):
    """(nom, contenu) contrôlés (PDF, PNG ou JPG, 10 Mo max), ou None sans fichier."""
    if not quote_file:
        return None
    filename, content = quote_file
    if not filename and not content:
        return None
    from services.admin.projects.invoices import check_document_file
    return check_document_file(filename, content, kind="devis"), content


def _apply_quote_file(event, upload, remove):
    """
    Avant commit (id de l'événement connu) : écrit le fichier envoyé, ou retire le fichier joint
    (retrait demandé, ou l'événement n'est plus un devis). Retourne les opérations à finaliser :
    {"written": nouveau fichier (à effacer si le commit échoue), "obsolete": ancien fichier, "sync": bool}.
    """
    from services.admin.projects.crud import _output_root

    ops = {"written": None, "obsolete": None, "sync": False}
    if upload and event.is_quote:
        name, content = upload
        rel_path = _quote_file_rel_path(event, name)
        dest = _output_root() / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        if event.file_path and event.file_path != rel_path:
            ops["obsolete"] = event.file_path
        event.file_path, event.file_name = rel_path, name
        ops.update(written=rel_path, sync=True)
    elif event.file_path and (remove or not event.is_quote):
        ops.update(obsolete=event.file_path, sync=True)
        event.file_path = event.file_name = None
    return ops


def _commit_with_quote_file(event, ops):
    """Commit, puis nettoyage de l'ancien fichier et synchronisation kDrive (1_DEVIS)."""
    from services.admin.projects.crud import _remove_local_file
    from services.common.kdrive.tasks import dispatch_sync_quote_file

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        if ops["written"]:
            _remove_local_file(ops["written"])
        raise
    if ops["obsolete"]:
        _remove_local_file(ops["obsolete"])
    if ops["sync"]:
        dispatch_sync_quote_file(event.project_id, event.kdrive_entity_id, event.file_path, event.file_name)


def quote_file_path(project_id, event_id):
    """(chemin absolu, nom d'origine) du fichier d'un devis, ou None s'il n'existe pas."""
    from services.admin.projects.crud import _output_root

    event = db.session.get(ProjectCommercialEvent, event_id)
    if not event or event.project_id != project_id or not event.file_path:
        return None
    root = _output_root().resolve()
    path = (root / event.file_path).resolve()
    if root not in path.parents or not path.is_file():
        return None
    return path, event.file_name or path.name


def _active_project(project_id):
    project = db.session.get(Project, project_id)
    if not project or project.deleted_at is not None:
        raise CommercialEventNotFoundError("Projet introuvable.")
    return project


def add_commercial_event(project_id, *, event_type, date_str, time_str=None, contact_id=None,
                         summary=None, lost_reason=None, user_id=None, now=None, new_contact=None,
                         is_planned=False, quote_amount=None, quote_file=None):
    """
    Ajoute une prise de contact. Pour « Devis envoyé » : quote_amount (montant total HT) et
    quote_file = (nom, contenu), tous deux facultatifs ; le fichier est déposé dans 1_DEVIS sur kDrive.
    """
    project = _active_project(project_id)
    upload = _checked_quote_file(quote_file)
    fields = _validated_fields(
        project, event_type=event_type, date_str=date_str, time_str=time_str, contact_id=contact_id,
        summary=summary, lost_reason=lost_reason, new_contact=new_contact, now=now, is_planned=is_planned,
        quote_amount=quote_amount,
    )

    author_name = None
    if user_id:
        user = db.session.get(User, user_id)
        if user:
            author_name = f"{user.firstname or ''} {user.lastname or ''}".strip() or None

    event = ProjectCommercialEvent(project=project, user_id=user_id, author_name=author_name, **fields)
    db.session.add(event)
    db.session.flush()
    recompute_commercial_status(project)
    _commit_with_quote_file(event, _apply_quote_file(event, upload, remove=False))
    return event


def update_commercial_event(project_id, event_id, *, event_type, date_str, time_str=None, contact_id=None,
                            summary=None, lost_reason=None, now=None, new_contact=None, is_planned=None,
                            quote_amount=None, quote_file=None, remove_quote_file=False):
    """
    Modifie une prise de contact (l'auteur d'origine est conservé) et recalcule le statut.
    `is_planned` à None conserve la nature actuelle (réalisé / à venir).
    Devis : quote_amount remplace le montant (vide = retiré) ; quote_file = (nom, contenu) remplace le
    fichier ; remove_quote_file le retire. Un événement qui n'est plus un devis perd montant et fichier.
    """
    project = _active_project(project_id)
    event = db.session.get(ProjectCommercialEvent, event_id)
    if not event or event.project_id != project.id:
        raise CommercialEventNotFoundError("Prise de contact introuvable.")
    upload = _checked_quote_file(quote_file)
    fields = _validated_fields(
        project, event_type=event_type, date_str=date_str, time_str=time_str, contact_id=contact_id,
        summary=summary, lost_reason=lost_reason, new_contact=new_contact, now=now,
        is_planned=event.is_planned if is_planned is None else is_planned, quote_amount=quote_amount,
    )
    for attr, value in fields.items():
        setattr(event, attr, value)
    db.session.flush()
    recompute_commercial_status(project)
    _commit_with_quote_file(event, _apply_quote_file(event, upload, remove=_as_bool(remove_quote_file)))
    return event


def set_quote_file(event, quote_file=None, remove=False):
    """Joint / remplace (quote_file = (nom, contenu)) ou retire (remove) le fichier d'un « Devis envoyé »."""
    if not event.is_quote:
        raise ValueError(f"« {event.type_label} » ne porte pas de devis : seul « Devis envoyé » accepte un fichier.")
    upload = _checked_quote_file(quote_file)
    if not upload and not remove:
        raise ValueError("Aucun fichier fourni.")
    if remove and not event.file_path:
        raise ValueError("Ce devis n'a pas de fichier joint.")
    _commit_with_quote_file(event, _apply_quote_file(event, upload, remove=remove))
    return event


def complete_commercial_event(project_id, event_id, now=None):
    """
    Marque un événement à venir comme « fait » : il devient une prise de contact réelle.
    Fait en avance (date future) : il prend la date et l'heure du moment.
    """
    project = _active_project(project_id)
    event = db.session.get(ProjectCommercialEvent, event_id)
    if not event or event.project_id != project.id:
        raise CommercialEventNotFoundError("Prise de contact introuvable.")
    if not event.is_planned:
        raise ValueError("Cette prise de contact a déjà eu lieu.")
    if event.event_type in PLANNED_ONLY_EVENT_TYPES:
        raise ValueError(f"« {event.type_label} » ne peut pas être marqué comme fait : modifiez-le ou supprimez-le.")
    now = now or paris_now()
    if event.occurred_at.date() > now.date():
        event.occurred_at = now.replace(second=0, microsecond=0)
    event.is_planned = False
    db.session.flush()
    recompute_commercial_status(project)
    db.session.commit()
    return event


def delete_commercial_event(project_id, event_id):
    project = _active_project(project_id)  # projet supprimé : refus, comme l'ajout et la modification
    event = db.session.get(ProjectCommercialEvent, event_id)
    if not event or event.project_id != project.id:
        raise CommercialEventNotFoundError("Prise de contact introuvable.")
    file_path, entity_id = event.file_path, event.kdrive_entity_id
    project.commercial_events.remove(event)
    db.session.delete(event)
    db.session.flush()
    recompute_commercial_status(project)
    db.session.commit()
    if file_path:  # devis joint : copie locale et fichier dans 1_DEVIS sur kDrive
        from services.admin.projects.crud import _remove_local_file
        from services.common.kdrive.tasks import dispatch_sync_quote_file

        _remove_local_file(file_path)
        dispatch_sync_quote_file(project_id, entity_id, None, None)


# ── Frise : calcul de l'échelle ────────────────────────────────

def _gap_days(a, b):
    return max(0.0, (b - a).total_seconds() / 86400)


def compute_timeline_layout(moments, break_threshold_days=BREAK_THRESHOLD_DAYS,
                            min_segment_pct=MIN_SEGMENT_PCT):
    """
    Positionne des instants triés sur une frise de 0 à 100 %.

    Retourne (positions, segments) :
    - positions : un pourcentage par instant ;
    - segments : pour chaque intervalle, {start_pct, end_pct, days, is_break}.
    """
    n = len(moments) - 1
    if n < 0:
        return [], []
    if n == 0:
        return [50.0], []

    gaps = [_gap_days(moments[i], moments[i + 1]) for i in range(n)]
    # Racine du temps : les longs silences sont compressés, les écarts courts dilatés ; au-delà du seuil,
    # l'intervalle est plafonné (coupure « ≈ »). Rendu stable d'un projet à l'autre.
    weights = [math.sqrt(min(g, break_threshold_days)) for g in gaps]

    min_pct = min(min_segment_pct, 100.0 / n)
    free = 100.0 - n * min_pct
    total = sum(weights)
    widths = [
        min_pct + (free * w / total if total > 0 else free / n)
        for w in weights
    ]

    positions = [0.0]
    for w in widths:
        positions.append(positions[-1] + w)
    positions[-1] = 100.0  # absorbe les erreurs d'arrondi

    segments = [
        {
            "start_pct": round(positions[i], 3),
            "end_pct": round(positions[i + 1], 3),
            "days": gaps[i],
            "is_break": gaps[i] > break_threshold_days,
        }
        for i in range(n)
    ]
    return [round(p, 3) for p in positions], segments


def _short_date(dt, with_year=False):
    label = f"{dt.day} {_MONTHS_SHORT[dt.month - 1]}"
    return f"{label} {dt.year}" if with_year else label


def _full_datetime(dt):
    label = f"{_DAYS_SHORT[dt.weekday()]} {dt.day} {_MONTHS_SHORT[dt.month - 1]} {dt.year}"
    if dt.hour or dt.minute:
        label += f" · {dt.hour:02d}:{dt.minute:02d}"
    return label


def _duration_label(days):
    if days >= 1:
        return f"{round(days)} j"
    hours = round(days * 24)
    return f"{hours} h" if hours >= 1 else "< 1 h"


# ── Relances ───────────────────────────────────────────────────

def followup_due(events, status, now=None, days=QUOTE_FOLLOWUP_DAYS):
    """
    Nombre de jours d'attente si une relance est conseillée, sinon None :
    devis envoyé, dernier échange sortant (pas de réponse du client) depuis au moins `days` jours.
    """
    done = _done(events)
    if status != "quote_sent" or not done:
        return None
    # Une relance de devis déjà planifiée : pas de rappel
    if any(e.event_type == "quote_followup" for e in _planned(events)):
        return None
    last = done[-1]
    if last.event_type not in OUTGOING_EVENT_TYPES:
        return None
    waited = ((now or paris_now()) - last.occurred_at).days
    return waited if waited >= days else None


def find_projects_awaiting_quote_reply(days=QUOTE_FOLLOWUP_DAYS, now=None):
    """
    Projets dont le devis attend une réponse depuis au moins `days` jours (à brancher sur le cron).
    Retourne une liste triée (attente la plus longue d'abord) de
    {project, last_event, days_waiting}.
    """
    now = now or paris_now()
    projects = Project.query.filter(
        Project.deleted_at.is_(None),
        Project.commercial_status == "quote_sent",
    ).all()
    results = []
    for project in projects:
        waited = followup_due(project.commercial_events, project.commercial_status, now=now, days=days)
        if waited is not None:
            results.append({
                "project": project,
                "last_event": _done(project.commercial_events)[-1],
                "days_waiting": waited,
            })
    results.sort(key=lambda r: r["days_waiting"], reverse=True)
    return results


# ── Contexte de la fiche projet ────────────────────────────────

def _contact_choices(project):
    """
    Contacts proposés dans le formulaire : d'abord ceux du projet (rôles clés puis contacts
    de la production), puis tous les autres contacts de l'annuaire.
    Retourne {"project": [(id, libellé)], "others": [(id, libellé)]}.
    """
    seen, project_choices = set(), []
    pairs = list(project.key_contacts)
    if project.production:
        pairs += [(None, c) for c in project.production.contacts]
    for label, c in pairs:
        if not c or c.id in seen:
            continue
        seen.add(c.id)
        name = f"{c.first_name} {c.last_name}".strip()
        project_choices.append((c.id, f"{name} ({label})" if label else name))

    others = []
    for c in Contact.query.order_by(Contact.last_name, Contact.first_name).all():
        if c.id in seen:
            continue
        name = f"{c.first_name} {c.last_name}".strip()
        detail = c.production_rel.name if c.production_rel else (c.job_title or "")
        others.append((c.id, f"{name} — {detail}" if detail else name))
    return {"project": project_choices, "others": others}


def cap_future_share(positions, segments, today_idx, max_future_pct=MAX_FUTURE_SHARE_PCT):
    """
    Plafonne la part « à venir » (à droite du repère Aujourd'hui) à `max_future_pct` % de la frise,
    pour qu'un horizon planifié lointain n'écrase pas l'historique. Les proportions restent exactes
    à l'intérieur de chaque partie (passé d'un côté, avenir de l'autre). Sans passé : inchangé.
    """
    if today_idx is None or today_idx == 0 or not positions:
        return positions, segments
    today_pct = positions[today_idx]
    if 100.0 - today_pct <= max_future_pct:
        return positions, segments
    new_today = 100.0 - max_future_pct

    def remap(p):
        if p <= today_pct:
            return round(p * new_today / today_pct, 3)
        return round(new_today + (p - today_pct) * max_future_pct / (100.0 - today_pct), 3)

    new_segments = []
    for seg in segments:
        seg = dict(seg)
        seg["start_pct"], seg["end_pct"] = remap(seg["start_pct"]), remap(seg["end_pct"])
        new_segments.append(seg)
    return [remap(p) for p in positions], new_segments


def _relative_label(day, today):
    """« aujourd'hui », « demain », « dans 3 j » ou « date dépassée de 2 j »."""
    delta = (day - today).days
    if delta == 0:
        return "aujourd'hui"
    if delta == 1:
        return "demain"
    if delta > 1:
        return f"dans {delta} j"
    return f"date dépassée de {-delta} j"


def _midnight(d):
    return datetime.combine(d, time(0, 0))


def build_commercial_timeline(project, now=None):
    """
    Contexte complet du bloc « Timeline commerciale » de la fiche projet.

    Frise : prises de contact réelles à gauche, repère « Aujourd'hui », puis événements à venir
    (zone teintée). Un événement prévu dont la date est passée reste à sa date, signalé « en retard ».
    """
    from services.admin.projects.crud import _format_amount

    now = now or paris_now()
    today_d = now.date()
    events = _chronological(project.commercial_events)
    done = [e for e in events if not e.is_planned]
    status = project.commercial_status
    is_closed = status in CLOSED_COMMERCIAL_STATUSES
    has_upcoming = any(e.is_planned and not e.is_late(today_d) for e in events)

    # Un point (« nœud ») par jour : les échanges d'une même journée sont regroupés (compteur), en séparant
    # le réalisé / en retard (rang 0) de l'à venir (rang 2) ; le repère « Aujourd'hui » a le rang 1.
    def rank(ev):
        return 2 if (ev.is_planned and not ev.is_late(today_d)) else 0

    last_past_day = max((e.occurred_at.date() for e in events if rank(e) == 0), default=None)
    show_today = has_upcoming or (bool(done) and not is_closed and last_past_day is not None
                                  and last_past_day < today_d)

    groups = {}
    for ev in events:
        groups.setdefault((ev.occurred_at.date(), rank(ev)), []).append(ev)
    keys = sorted(groups)
    if show_today:
        keys.append((today_d, 1))
        keys.sort()

    positions, segments = compute_timeline_layout([_midnight(day) for day, _ in keys])
    today_idx = keys.index((today_d, 1)) if show_today else None
    positions, segments = cap_future_share(positions, segments, today_idx)
    multi_year = len({d.year for d, _ in keys}) > 1 or any(d.year != today_d.year for d, _ in keys)
    today_pct = positions[today_idx] if today_idx is not None else None

    def event_item(ev, pct):
        return {
            "id": ev.id,
            "type": ev.event_type,
            "label": ev.type_label,
            "icon": ev.icon,
            "family": ev.family,
            "pct": pct,
            "date_short": _short_date(ev.occurred_at, with_year=multi_year),
            "date_full": _full_datetime(ev.occurred_at),
            "contact_name": ev.contact_name,
            "contact_preposition": ev.contact_preposition,
            "contact_details": ev.contact_details,
            "headline": ev.headline,
            "summary": ev.summary,
            "lost_reason_label": ev.lost_reason_label,
            "author_name": ev.author_name,
            "is_planned": bool(ev.is_planned),
            "is_late": ev.is_late(today_d),
            "can_complete": bool(ev.is_planned) and ev.event_type not in PLANNED_ONLY_EVENT_TYPES,
            "relative": _relative_label(ev.occurred_at.date(), today_d) if ev.is_planned else None,
            "quote_file_name": ev.file_name if ev.file_path else None,
            "edit": {
                "event_type": ev.event_type,
                "is_planned": "1" if ev.is_planned else "0",
                "date": ev.occurred_at.date().isoformat(),
                "time": ev.occurred_at.strftime("%H:%M") if (ev.occurred_at.hour or ev.occurred_at.minute) else "",
                "contact_id": str(ev.contact_id) if ev.contact_id else "",
                "lost_reason": ev.lost_reason or "",
                "summary": ev.summary or "",
                "quote_amount": _format_amount(ev.quote_amount),
                "quote_file_name": ev.file_name if ev.file_path else "",
            },
        }

    nodes, items, last_label_pct = [], [], None
    for (day, rk), pct in zip(keys, positions):
        if rk == 1:
            continue  # repère « Aujourd'hui »
        node_events = [event_item(ev, pct) for ev in groups[(day, rk)]]
        items.extend(node_events)
        # Point représentatif : le dernier jalon du jour (devis, confirmation…), sinon le dernier échange
        lead = next((e for e in reversed(node_events) if e["type"] in EVENT_TYPE_MILESTONES), node_events[-1])
        late = any(e["is_late"] for e in node_events)
        show_date = (last_label_pct is None or pct - last_label_pct >= MIN_DATE_LABEL_GAP_PCT) and (
            today_pct is None or abs(pct - today_pct) >= MIN_DATE_LABEL_GAP_PCT
        )
        if show_date:
            last_label_pct = pct
        count = len(node_events)
        date_label = _short_date(datetime.combine(day, time(0, 0)), with_year=multi_year)
        if count == 1:
            title = f"{lead['headline']} — {lead['date_full']}"
        else:
            title = f"{count} échanges le {date_label} : " + ", ".join(e["label"] for e in node_events)
        if late:
            title += " (en retard)"
        elif rk == 2:
            title += f" (prévu, {_relative_label(day, today_d)})"
        nodes.append({
            "id": f"{day.isoformat()}-{'p' if rk == 2 else 'r'}",
            "pct": pct,
            "count": count,
            "icon": lead["icon"],
            "family": lead["family"],
            "state": "late" if late else ("planned" if rk == 2 else "done"),
            "show_date": show_date,
            "date_short": date_label,
            "title": title,
            "events": node_events,
        })

    for i, seg in enumerate(segments):
        width = seg["end_pct"] - seg["start_pct"]
        seg["mid_pct"] = round((seg["start_pct"] + seg["end_pct"]) / 2, 3)
        seg["is_future"] = today_idx is not None and i >= today_idx
        seg["is_pending"] = today_idx is not None and i + 1 == today_idx and seg["days"] > 0
        if seg["is_future"] and i == today_idx and seg["days"] >= 1:
            seg["label"] = f"dans {round(seg['days'])} j"
        else:
            seg["label"] = _duration_label(seg["days"])
        seg["show_label"] = seg["is_break"] or (
            seg["days"] >= MIN_GAP_LABEL_DAYS and width >= MIN_GAP_LABEL_PCT
        )

    # Point sélectionné par défaut : un événement en retard, sinon le prochain à venir, sinon le dernier contact
    late = [it for it in items if it["is_late"]]
    upcoming = [it for it in items if it["is_planned"] and not it["is_late"]]
    if late:
        selected_id = late[0]["id"]
    elif upcoming:
        selected_id = upcoming[0]["id"]
    else:
        selected_id = items[-1]["id"] if items else None
    selected_node = next((n["id"] for n in nodes if any(e["id"] == selected_id for e in n["events"])), None)
    nxt = upcoming[0] if upcoming else None

    first, last = (done[0].occurred_at, done[-1].occurred_at) if done else (None, None)
    return {
        "events": items,
        "nodes": nodes,
        "segments": segments,
        "today_pct": today_pct,
        "future_zone": has_upcoming and today_idx is not None,
        "selected_id": selected_id,
        "selected_node": selected_node,
        "count": len(done),
        "upcoming_count": len(upcoming),
        "late_count": len(late),
        "next_upcoming": {"label": nxt["label"], "relative": nxt["relative"]} if nxt else None,
        "status": status,
        "status_label": COMMERCIAL_STATUS_LABELS.get(status) if status else None,
        "status_variant": COMMERCIAL_STATUS_VARIANTS.get(status, "neutral"),
        "span_days": (last - first).days if done else 0,
        "followup_days": followup_due(events, status, now=now),
        "followup_threshold": QUOTE_FOLLOWUP_DAYS,
        "type_groups": [
            (group, [(k, EVENT_TYPE_LABELS[k], k in PLANNABLE_EVENT_TYPES, k in PLANNED_ONLY_EVENT_TYPES)
                     for k in keys])
            for group, keys in EVENT_TYPE_GROUPS
        ],
        "lost_reasons": LOST_REASONS,
        "quote_types": sorted(QUOTE_EVENT_TYPES),
        "contact_choices": _contact_choices(project),
        "production_choices": [(p.id, p.name) for p in Production.query.order_by(Production.name).all()],
        "new_contact_value": NEW_CONTACT_VALUE,
        "default_date": today_d.isoformat(),
        "default_time": "",  # heure facultative : vide par défaut (sinon ce serait l'heure de la saisie)
        "today": today_d.isoformat(),
    }


# ── Agenda des événements à venir (tableau de bord, mail du matin) ──

UPCOMING_WINDOW_DAYS = 7


def planned_agenda(now=None, days_ahead=UPCOMING_WINDOW_DAYS):
    """
    Événements à venir de tous les projets actifs :
    - overdue : date dépassée, pas encore marqués « fait » (le plus ancien d'abord) ;
    - today : prévus aujourd'hui ;
    - upcoming : prévus dans les `days_ahead` prochains jours (hors aujourd'hui).
    Chaque élément : {project, event, days} (days = écart en jours avec aujourd'hui).
    """
    today_d = (now or paris_now()).date()
    rows = (
        ProjectCommercialEvent.query.join(Project, ProjectCommercialEvent.project_id == Project.id)
        .filter(ProjectCommercialEvent.is_planned.is_(True), Project.deleted_at.is_(None))
        .order_by(ProjectCommercialEvent.occurred_at)
        .all()
    )
    agenda = {"overdue": [], "today": [], "upcoming": []}
    for ev in rows:
        delta = (ev.occurred_at.date() - today_d).days
        item = {"project": ev.project, "event": ev, "days": delta}
        if delta < 0:
            agenda["overdue"].append(item)
        elif delta == 0:
            agenda["today"].append(item)
        elif delta <= days_ahead:
            agenda["upcoming"].append(item)
    return agenda


# ── Statistiques commerciales (tableau de bord) ───────────────

WON_COMMERCIAL_STATUSES = {"confirmed", "invoiced", "paid"}


def commercial_stats(now=None, followup_days=QUOTE_FOLLOWUP_DAYS):
    """
    Indicateurs commerciaux calculés sur les projets suivis (statut non NULL) :
    - répartition par statut ;
    - taux de transformation = gagnés / (gagnés + abandonnés) ;
    - délai moyen entre la première prise de contact et la confirmation ;
    - motifs d'abandon (dernier abandon de chaque projet abandonné) ;
    - devis à relancer (cf. find_projects_awaiting_quote_reply).
    """
    now = now or paris_now()
    projects = Project.query.filter(
        Project.deleted_at.is_(None),
        Project.commercial_status.isnot(None),
    ).all()

    by_status = {key: 0 for key in COMMERCIAL_STATUS_LABELS}
    reasons = {key: 0 for key in LOST_REASON_LABELS}
    delays = []
    for project in projects:
        by_status[project.commercial_status] = by_status.get(project.commercial_status, 0) + 1
        events = _done(project.commercial_events)
        if not events:
            continue
        confirmed = next((e for e in events if e.event_type == "confirmed"), None)
        if confirmed:
            delays.append((confirmed.occurred_at - events[0].occurred_at).total_seconds() / 86400)
        if project.commercial_status == "lost":
            lost = [e for e in events if e.event_type == "lost"]
            if lost and lost[-1].lost_reason in reasons:
                reasons[lost[-1].lost_reason] += 1

    pending_quotes = pending_quotes_summary(projects)
    won = sum(by_status.get(s, 0) for s in WON_COMMERCIAL_STATUSES)
    lost_count = by_status.get("lost", 0)
    decided = won + lost_count
    max_reason = max(reasons.values()) if reasons else 0

    return {
        "tracked": len(projects),
        "by_status": [
            (key, COMMERCIAL_STATUS_LABELS[key], COMMERCIAL_STATUS_VARIANTS[key], by_status.get(key, 0))
            for key in COMMERCIAL_STATUS_LABELS
        ],
        "prospects": by_status.get("prospect", 0),
        "quotes_pending": by_status.get("quote_sent", 0),
        "quotes_pending_amount": pending_quotes["amount"],
        "quotes_pending_without_amount": pending_quotes["without_amount"],
        "won": won,
        "lost": lost_count,
        "conversion_rate": round(100 * won / decided) if decided else None,
        "avg_days_to_confirm": round(sum(delays) / len(delays), 1) if delays else None,
        "confirmed_sample": len(delays),
        "lost_reasons": [
            {
                "key": key,
                "label": LOST_REASON_LABELS[key],
                "count": count,
                "pct": round(100 * count / max_reason) if max_reason else 0,
            }
            for key, count in sorted(reasons.items(), key=lambda kv: kv[1], reverse=True)
            if count
        ],
        "followups": find_projects_awaiting_quote_reply(days=followup_days, now=now),
        "followup_threshold": followup_days,
        "agenda": planned_agenda(now=now),
        "agenda_window_days": UPCOMING_WINDOW_DAYS,
    }


# ── Relance des devis : récapitulatif par e-mail (cron) ────────

# Rôles recevant tous les devis à relancer ; un commercial ne reçoit que les projets dont il est le commercial
_FOLLOWUP_ALL_ROLES = ("administrateur", "super administrateur", "manager")


def _digest_items_for(user, items):
    """Éléments d'un récapitulatif visibles par un utilisateur (tous, ou ceux de ses projets), ou None."""
    from utils.decorators import normalize_role

    role = normalize_role(user.role)
    if role in _FOLLOWUP_ALL_ROLES:
        return list(items)
    if role == "commercial":
        return [i for i in items if i["project"].commercial_user_id == user.id]
    return None


def followup_digest_recipients(followups):
    """
    Destinataires du récapitulatif : {e-mail: [relances]}.
    Administrateurs / managers : toutes les relances. Commercial : celles de ses projets.
    """
    recipients = {}
    for user in User.query.all():
        mail = (user.mail or "").strip()
        items = _digest_items_for(user, followups) if mail else None
        if items:
            recipients[mail] = items
    return recipients


def send_quote_followup_digest(base_url=None, dry_run=False, now=None, days=QUOTE_FOLLOWUP_DAYS):
    """
    Mail du matin du suivi commercial :
    - devis sans réponse depuis au moins `days` jours ;
    - événements prévus aujourd'hui et événements prévus en retard (date dépassée, non marqués « fait »).
    Administrateurs / managers : tout ; commerciaux : leurs projets. Aucun e-mail s'il n'y a rien à signaler.
    Retourne {"followups", "planned", "recipients", "sent"}.
    """
    from flask import url_for
    from utils.mailer import EmailService
    from utils.request_utils import resolve_base_url

    followups = find_projects_awaiting_quote_reply(days=days, now=now)
    agenda = planned_agenda(now=now)
    planned = agenda["overdue"] + agenda["today"]

    per_user = {}
    for user in User.query.all():
        mail = (user.mail or "").strip()
        if not mail:
            continue
        f_items = _digest_items_for(user, followups) or []
        p_items = _digest_items_for(user, planned) or []
        if f_items or p_items:
            per_user[mail] = (f_items, p_items)

    result = {"followups": followups, "planned": planned, "recipients": sorted(per_user), "sent": 0}
    if not per_user or dry_run:
        return result

    root = resolve_base_url(base_url).rstrip("/")

    def project_url(p):
        return root + url_for("admin_projects.admin_project_detail", record_id=p.id) + "#commercial-timeline"

    def commercial_name(p):
        u = p.commercial_user
        return f"{u.firstname or ''} {u.lastname or ''}".strip() if u else None

    def followup_row(f):
        p, last = f["project"], f["last_event"]
        return {
            "name": p.name,
            "production": p.production.name if p.production else "—",
            "commercial": commercial_name(p),
            "last_label": last.type_label,
            "last_date": last.occurred_at.strftime("%d/%m/%Y"),
            "contact": last.contact_name,
            "days": f["days_waiting"],
            "url": project_url(p),
        }

    def planned_row(item):
        p, ev = item["project"], item["event"]
        has_time = ev.occurred_at.hour or ev.occurred_at.minute
        return {
            "name": p.name,
            "production": p.production.name if p.production else "—",
            "headline": ev.headline,
            "summary": ev.summary,
            "when": ev.occurred_at.strftime("%d/%m/%Y") + (ev.occurred_at.strftime(" à %H:%M") if has_time else ""),
            "late_days": -item["days"] if item["days"] < 0 else 0,
            "url": project_url(p),
        }

    list_url = root + url_for("admin_projects.admin_projects_list", commercial="quote_sent")
    for to, (f_items, p_items) in per_user.items():
        projects = [followup_row(f) for f in f_items]
        agenda_rows = [planned_row(i) for i in p_items]
        parts = []
        if projects:
            parts.append(f"{len(projects)} devis à relancer")
        n_today = sum(1 for r in agenda_rows if not r["late_days"])
        n_late = len(agenda_rows) - n_today
        if n_today:
            parts.append(f"{n_today} échange{'s' if n_today > 1 else ''} prévu{'s' if n_today > 1 else ''} aujourd'hui")
        if n_late:
            parts.append(f"{n_late} en retard")
        subject = "Suivi commercial : " + ", ".join(parts)
        lines = [subject, ""]
        lines += [f"- [Agenda] {r['headline']} — {r['name']} ({r['production']}) : {r['when']}"
                  f"{' (en retard de ' + str(r['late_days']) + ' j)' if r['late_days'] else ''} — {r['url']}"
                  for r in agenda_rows]
        lines += [f"- [Relance] {r['name']} ({r['production']}) : {r['last_label'].lower()} le {r['last_date']}, "
                  f"{r['days']} j sans réponse — {r['url']}" for r in projects]
        if EmailService.send_templated_email(
            to_email=to, subject=subject, template_name="emails/quote_followup_digest.html",
            context={"projects": projects, "agenda": agenda_rows, "days": days, "list_url": list_url},
            text_content="\n".join(lines), sender_type="contact",
        ):
            result["sent"] += 1
    return result
