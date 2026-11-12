"""
Timeline commerciale d'un projet : saisie des prises de contact, statut commercial déduit,
calcul de la frise (espacement proportionnel au temps) et détection des devis à relancer.

Échelle de la frise :
- l'écart entre deux points est proportionnel au temps écoulé ;
- chaque intervalle reçoit une largeur minimale (points jamais superposés) ;
- un silence de plus de BREAK_THRESHOLD_DAYS jours est plafonné et signalé par une coupure « ≈ ».
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import func

from models import Contact, Project, User, db
from models.commercial_event import (
    CLOSED_COMMERCIAL_STATUSES,
    COMMERCIAL_STATUS_LABELS,
    COMMERCIAL_STATUS_VARIANTS,
    EVENT_TYPE_GROUPS,
    EVENT_TYPE_LABELS,
    EVENT_TYPE_MILESTONES,
    LOST_REASON_LABELS,
    LOST_REASONS,
    ProjectCommercialEvent,
)

PARIS_TZ = ZoneInfo("Europe/Paris")

# Échelle de la frise
BREAK_THRESHOLD_DAYS = 30      # au-delà, l'intervalle est compressé (coupure « ≈ »)
MIN_SEGMENT_PCT = 4.0          # largeur minimale d'un intervalle (% de la frise)
MIN_DATE_LABEL_GAP_PCT = 9.0   # écart minimal entre deux dates affichées sous la frise
MIN_GAP_LABEL_PCT = 7.0        # largeur minimale d'un intervalle pour afficher sa durée
MIN_GAP_LABEL_DAYS = 2         # durée minimale d'un intervalle pour l'afficher

# Relance des devis : délai sans réponse au-delà duquel une relance est conseillée
QUOTE_FOLLOWUP_DAYS = 10
# Événements « sortants » : s'ils sont les derniers, le client n'a pas encore répondu
OUTGOING_EVENT_TYPES = {"email_out", "call_out", "quote_sent", "quote_followup"}

_MONTHS_SHORT = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
                 "juil.", "août", "sept.", "oct.", "nov.", "déc."]
_DAYS_SHORT = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]


class CommercialEventNotFoundError(Exception):
    pass


# Valeur du sélecteur de contact signifiant « créer un nouveau contact »
NEW_CONTACT_VALUE = "__new__"


def paris_now():
    """Heure murale de Paris (naïve), cohérente avec la saisie des événements."""
    return datetime.now(PARIS_TZ).replace(tzinfo=None)


# ── Statut commercial ──────────────────────────────────────────

def _chronological(events):
    return sorted(events, key=lambda e: (e.occurred_at, e.id or 0))


def compute_commercial_status(events, current_status=None):
    """
    Statut atteint par le dernier jalon (devis, confirmation, facture, abandon…).
    Sans jalon : le projet reste « non suivi » (None) s'il l'était, sinon « Demande en cours ».
    """
    status = None
    for ev in _chronological(events):
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


def _clean(value):
    return (value or "").strip() or None


def _find_or_build_contact(project, data):
    """
    Contact saisi à la volée : réutilise un contact existant de même prénom + nom
    (de préférence de la même production) en complétant ses champs vides, sinon le crée
    rattaché à la production du projet. Aucun commit ici (transaction de l'événement).
    """
    first_name, last_name = _clean(data.get("first_name")), _clean(data.get("last_name"))
    if not first_name or not last_name:
        raise ValueError("Le prénom et le nom du nouveau contact sont requis.")
    attrs = {
        "phone": _clean(data.get("phone")),
        "mail": _clean(data.get("mail")),
        "job_title": _clean(data.get("job_title")),
    }
    query = Contact.query.filter(
        func.lower(func.trim(Contact.first_name)) == first_name.lower(),
        func.lower(func.trim(Contact.last_name)) == last_name.lower(),
    )
    if project.production_id:
        query = query.order_by((Contact.production_id == project.production_id).desc())
    contact = query.first()
    if contact:
        for attr, val in attrs.items():
            if val and not getattr(contact, attr):
                setattr(contact, attr, val)
        return contact
    contact = Contact(first_name=first_name, last_name=last_name,
                      production_id=project.production_id, **attrs)
    db.session.add(contact)
    return contact


def add_commercial_event(project_id, *, event_type, date_str, time_str=None, contact_id=None,
                         summary=None, lost_reason=None, user_id=None, now=None, new_contact=None):
    project = db.session.get(Project, project_id)
    if not project or project.deleted_at is not None:
        raise CommercialEventNotFoundError("Projet introuvable.")

    if event_type not in EVENT_TYPE_LABELS:
        raise ValueError("Type de prise de contact inconnu.")

    occurred_at = _parse_occurred_at(date_str, time_str)
    now = now or paris_now()
    if occurred_at.date() > now.date():
        raise ValueError("La date de la prise de contact ne peut pas être dans le futur.")

    if event_type == "lost":
        if lost_reason not in LOST_REASON_LABELS:
            raise ValueError("Indiquez le motif de l'abandon.")
    else:
        lost_reason = None

    # En dernier : un nouveau contact n'est ajouté à la session qu'une fois tout le reste validé
    contact = None
    if contact_id == NEW_CONTACT_VALUE:
        contact = _find_or_build_contact(project, new_contact or {})
    elif contact_id not in (None, ""):
        try:
            contact = db.session.get(Contact, int(contact_id))
        except (TypeError, ValueError):
            contact = None
        if not contact:
            raise ValueError("Contact introuvable.")

    summary = (summary or "").strip()[:500] or None

    author_name = None
    if user_id:
        user = db.session.get(User, user_id)
        if user:
            author_name = f"{user.firstname or ''} {user.lastname or ''}".strip() or None

    event = ProjectCommercialEvent(
        project=project,
        event_type=event_type,
        occurred_at=occurred_at,
        contact=contact,
        summary=summary,
        lost_reason=lost_reason,
        user_id=user_id,
        author_name=author_name,
    )
    db.session.add(event)
    db.session.flush()
    recompute_commercial_status(project)
    db.session.commit()
    return event


def delete_commercial_event(project_id, event_id):
    event = db.session.get(ProjectCommercialEvent, event_id)
    if not event or event.project_id != project_id:
        raise CommercialEventNotFoundError("Prise de contact introuvable.")
    project = event.project
    project.commercial_events.remove(event)
    db.session.delete(event)
    db.session.flush()
    recompute_commercial_status(project)
    db.session.commit()


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
    weights = [min(g, break_threshold_days) for g in gaps]

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
    if status != "quote_sent" or not events:
        return None
    last = _chronological(events)[-1]
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
                "last_event": _chronological(project.commercial_events)[-1],
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


def build_commercial_timeline(project, now=None):
    """Contexte complet du bloc « Timeline commerciale » de la fiche projet."""
    now = now or paris_now()
    events = _chronological(project.commercial_events)
    status = project.commercial_status
    is_closed = status in CLOSED_COMMERCIAL_STATUSES

    moments = [e.occurred_at for e in events]
    show_today = bool(events) and not is_closed and now > moments[-1]
    if show_today:
        moments.append(now)

    positions, segments = compute_timeline_layout(moments)
    multi_year = len({m.year for m in moments}) > 1 or (moments and moments[0].year != now.year)

    items, last_label_pct = [], None
    for ev, pct in zip(events, positions):
        show_date = last_label_pct is None or pct - last_label_pct >= MIN_DATE_LABEL_GAP_PCT
        if show_date:
            last_label_pct = pct
        items.append({
            "id": ev.id,
            "type": ev.event_type,
            "label": ev.type_label,
            "icon": ev.icon,
            "family": ev.family,
            "pct": pct,
            "show_date": show_date,
            "date_short": _short_date(ev.occurred_at, with_year=multi_year),
            "date_full": _full_datetime(ev.occurred_at),
            "contact_name": ev.contact_name,
            "summary": ev.summary,
            "lost_reason_label": ev.lost_reason_label,
            "author_name": ev.author_name,
        })

    for seg in segments:
        width = seg["end_pct"] - seg["start_pct"]
        seg["mid_pct"] = round((seg["start_pct"] + seg["end_pct"]) / 2, 3)
        seg["label"] = _duration_label(seg["days"])
        seg["show_label"] = seg["is_break"] or (
            seg["days"] >= MIN_GAP_LABEL_DAYS and width >= MIN_GAP_LABEL_PCT
        )
    if show_today and segments:
        segments[-1]["is_pending"] = True  # silence en cours, jusqu'à aujourd'hui

    first, last = (events[0].occurred_at, events[-1].occurred_at) if events else (None, None)
    return {
        "events": items,
        "segments": segments,
        "today_pct": positions[-1] if show_today else None,
        "count": len(events),
        "status": status,
        "status_label": COMMERCIAL_STATUS_LABELS.get(status) if status else None,
        "status_variant": COMMERCIAL_STATUS_VARIANTS.get(status, "neutral"),
        "span_days": (last - first).days if events else 0,
        "followup_days": followup_due(events, status, now=now),
        "followup_threshold": QUOTE_FOLLOWUP_DAYS,
        "type_groups": [
            (group, [(k, EVENT_TYPE_LABELS[k]) for k in keys]) for group, keys in EVENT_TYPE_GROUPS
        ],
        "lost_reasons": LOST_REASONS,
        "contact_choices": _contact_choices(project),
        "new_contact_value": NEW_CONTACT_VALUE,
        "default_date": now.date().isoformat(),
        "default_time": now.strftime("%H:%M"),
        "max_date": now.date().isoformat(),
    }
