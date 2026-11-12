"""Outils MCP : timeline commerciale des projets (prises de contact, devis, factures, abandon) et statistiques."""
from typing import Any, Dict, Optional

from mcp_server.context import CURRENT_MCP_USER
from mcp_server.core import mcp
from mcp_server.decorators import require_mcp_scope, run_in_flask_context
from mcp_server.tools.projects import _resolve_project


def _mcp_user_id() -> Optional[int]:
    user = CURRENT_MCP_USER.get()
    return getattr(user, "id", None) if user else None


def _event_dict(event) -> Dict[str, Any]:
    from services.admin.commercial_timeline import paris_now

    data = event.to_dict()
    data["occurred_at"] = event.occurred_at.strftime("%Y-%m-%d %H:%M") if event.occurred_at else None
    data["is_late"] = event.is_late(paris_now().date())
    return data


def _timeline_payload(project) -> Dict[str, Any]:
    from models.commercial_event import COMMERCIAL_STATUS_LABELS
    from services.admin.commercial_timeline import QUOTE_FOLLOWUP_DAYS, _chronological, followup_due

    events = _chronological(project.commercial_events)
    status = project.commercial_status
    return {
        "project": {"id": project.id, "project_id": project.project_id, "name": project.name},
        "commercial_status": status,
        "commercial_status_label": COMMERCIAL_STATUS_LABELS.get(status) if status else "Non suivi",
        "followup_due_days": followup_due(events, status),
        "followup_threshold_days": QUOTE_FOLLOWUP_DAYS,
        "events": [_event_dict(e) for e in events],
    }


def _new_contact(first_name, last_name, phone, mail) -> Optional[Dict[str, Any]]:
    if not (first_name or last_name):
        return None
    return {"first_name": first_name, "last_name": last_name, "phone": phone, "mail": mail}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_project_commercial_timeline(project_id: Any) -> Dict[str, Any]:
    """
    Timeline commerciale d'un projet : prises de contact chronologiques (mails, appels, devis, factures,
    abandon), statut commercial déduit et relance conseillée éventuelle.
    - project_id: Identifiant numérique du projet ou code BVPR (ex: 'BVPR-0RLY80RD5LZB' ou 46)
    """
    p = _resolve_project(project_id)
    if not p:
        return {"status": "error", "message": f"Projet '{project_id}' introuvable."}
    return _timeline_payload(p)


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_commercial_event_types() -> Dict[str, Any]:
    """
    Référentiel de la timeline commerciale : types d'événements (et statut commercial qu'ils déclenchent),
    motifs d'abandon et statuts commerciaux. À consulter avant add_commercial_event.
    """
    from models.commercial_event import COMMERCIAL_EVENT_TYPES, COMMERCIAL_STATUSES, LOST_REASONS

    return {
        "event_types": [
            {"key": key, "label": label, "sets_status": milestone}
            for key, label, _icon, _family, milestone in COMMERCIAL_EVENT_TYPES
        ],
        "lost_reasons": [{"key": k, "label": label} for k, label in LOST_REASONS],
        "statuses": [{"key": k, "label": label} for k, label, _ in COMMERCIAL_STATUSES],
    }


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def add_commercial_event(
    project_id: Any,
    event_type: str,
    date: str,
    time: Optional[str] = None,
    contact_id: Optional[int] = None,
    summary: Optional[str] = None,
    lost_reason: Optional[str] = None,
    is_planned: bool = False,
    new_contact_first_name: Optional[str] = None,
    new_contact_last_name: Optional[str] = None,
    new_contact_phone: Optional[str] = None,
    new_contact_mail: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Ajoute une prise de contact à la timeline commerciale d'un projet (le statut commercial est recalculé).
    - project_id: Identifiant numérique du projet ou code BVPR
    - event_type: first_request, email_in, email_out, call_in, call_out, meeting, quote_sent, quote_followup,
      confirmed, invoice_sent, invoice_paid ou lost (cf. get_commercial_event_types)
    - date: AAAA-MM-JJ (pas dans le futur) ; time: HH:MM (optionnel)
    - contact_id: contact existant (optionnel). Ou new_contact_first_name + new_contact_last_name
      (+ phone / mail) pour créer le contact à la volée, rattaché à la production du projet
      (un homonyme existant est réutilisé)
    - summary: résumé libre (500 caractères max)
    - lost_reason: obligatoire si event_type = lost (price, dates, competitor, no_answer, cancelled, other)
    - is_planned: true pour un échange À VENIR (date du jour ou future) ; types planifiables : meeting,
      call_out, email_out, quote_followup, deadline (échéance). Ne change pas le statut commercial tant qu'il
      n'est pas marqué fait (complete_commercial_event)
    """
    from services.admin.commercial_timeline import (
        NEW_CONTACT_VALUE,
        CommercialEventNotFoundError,
        add_commercial_event as _add,
    )
    from models import db

    p = _resolve_project(project_id)
    if not p:
        return {"status": "error", "message": f"Projet '{project_id}' introuvable."}
    new_contact = _new_contact(new_contact_first_name, new_contact_last_name, new_contact_phone, new_contact_mail)
    try:
        event = _add(
            p.id, event_type=event_type, date_str=date, time_str=time,
            contact_id=NEW_CONTACT_VALUE if new_contact else contact_id,
            summary=summary, lost_reason=lost_reason, user_id=_mcp_user_id(), new_contact=new_contact,
            is_planned=is_planned,
        )
    except (ValueError, CommercialEventNotFoundError) as e:
        db.session.rollback()
        return {"status": "error", "message": str(e)}
    return {"status": "success", "event": _event_dict(event), "commercial_status": p.commercial_status}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def update_commercial_event(
    event_id: int,
    event_type: Optional[str] = None,
    date: Optional[str] = None,
    time: Optional[str] = None,
    contact_id: Optional[int] = None,
    summary: Optional[str] = None,
    lost_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Modifie une prise de contact. Les champs non fournis conservent leur valeur actuelle
    (passer contact_id=0 pour retirer le contact, time="" pour retirer l'heure).
    - event_id: identifiant de la prise de contact (cf. get_project_commercial_timeline)
    """
    from models import ProjectCommercialEvent, db
    from services.admin.commercial_timeline import CommercialEventNotFoundError, update_commercial_event as _update

    event = db.session.get(ProjectCommercialEvent, event_id)
    if not event:
        return {"status": "error", "message": f"Prise de contact #{event_id} introuvable."}
    current_time = event.occurred_at.strftime("%H:%M") if (event.occurred_at.hour or event.occurred_at.minute) else ""
    if contact_id is None:
        contact_value = event.contact_id
    else:
        contact_value = contact_id or None
    try:
        updated = _update(
            event.project_id, event.id,
            event_type=event_type or event.event_type,
            date_str=date or event.occurred_at.date().isoformat(),
            time_str=current_time if time is None else time,
            contact_id=contact_value,
            summary=event.summary if summary is None else summary,
            lost_reason=lost_reason or event.lost_reason,
        )
    except (ValueError, CommercialEventNotFoundError) as e:
        db.session.rollback()
        return {"status": "error", "message": str(e)}
    return {"status": "success", "event": _event_dict(updated), "commercial_status": updated.project.commercial_status}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def complete_commercial_event(event_id: int) -> Dict[str, Any]:
    """
    Marque un échange à venir (is_planned) comme fait : il devient une prise de contact réelle et le statut
    commercial est recalculé. Fait en avance (date future) : il prend la date et l'heure du moment.
    - event_id: identifiant de l'événement prévu
    """
    from models import ProjectCommercialEvent, db
    from services.admin.commercial_timeline import CommercialEventNotFoundError, complete_commercial_event as _complete

    event = db.session.get(ProjectCommercialEvent, event_id)
    if not event:
        return {"status": "error", "message": f"Prise de contact #{event_id} introuvable."}
    try:
        done = _complete(event.project_id, event.id)
    except (ValueError, CommercialEventNotFoundError) as e:
        db.session.rollback()
        return {"status": "error", "message": str(e)}
    return {"status": "success", "event": _event_dict(done), "commercial_status": done.project.commercial_status}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("write")
def delete_commercial_event(event_id: int, confirm: bool = False) -> Dict[str, Any]:
    """
    Supprime une prise de contact de la timeline (le statut commercial est recalculé).
    - event_id: identifiant de la prise de contact
    - confirm: doit valoir true pour exécuter la suppression
    """
    from models import ProjectCommercialEvent, db
    from services.admin.commercial_timeline import CommercialEventNotFoundError, delete_commercial_event as _delete

    event = db.session.get(ProjectCommercialEvent, event_id)
    if not event:
        return {"status": "error", "message": f"Prise de contact #{event_id} introuvable."}
    if not confirm:
        return {
            "status": "confirmation_required",
            "message": f"Confirmez la suppression de « {event.type_label} » du "
                       f"{event.occurred_at.strftime('%d/%m/%Y')} en relançant avec confirm=true.",
        }
    project = event.project
    try:
        _delete(event.project_id, event.id)
    except CommercialEventNotFoundError as e:
        return {"status": "error", "message": str(e)}
    return {"status": "success", "deleted_id": event_id, "commercial_status": project.commercial_status}


@mcp.tool()
@run_in_flask_context
@require_mcp_scope("read_only")
def get_commercial_stats(followup_days: Optional[int] = None) -> Dict[str, Any]:
    """
    Statistiques commerciales : répartition par statut, taux de transformation, délai moyen entre
    premier contact et confirmation, motifs d'abandon, devis à relancer et agenda des échanges prévus
    (overdue = en retard, today, upcoming = 7 prochains jours).
    - followup_days: seuil de relance en jours sans réponse (défaut : 10)
    """
    from services.admin.commercial_timeline import QUOTE_FOLLOWUP_DAYS, commercial_stats

    st = commercial_stats(followup_days=followup_days or QUOTE_FOLLOWUP_DAYS)
    st["by_status"] = [{"key": k, "label": label, "count": n} for k, label, _v, n in st["by_status"]]
    st["followups"] = [
        {
            "project": {"id": f["project"].id, "project_id": f["project"].project_id, "name": f["project"].name},
            "last_event": _event_dict(f["last_event"]),
            "days_waiting": f["days_waiting"],
        }
        for f in st["followups"]
    ]
    st["agenda"] = {
        key: [
            {
                "project": {"id": i["project"].id, "project_id": i["project"].project_id, "name": i["project"].name},
                "event": _event_dict(i["event"]),
                "days_from_today": i["days"],
            }
            for i in items
        ]
        for key, items in st["agenda"].items()
    }
    return st
