"""
Route publique pour le flux calendrier ICS.
Accessible via un token unique dans l'URL : GET /cal/<token>.ics
"""
from datetime import datetime, timedelta
import os

from flask import Blueprint, Response, abort, current_app, redirect, request, url_for
from icalendar import Calendar, Event
from sqlalchemy.orm import joinedload

from extensions import limiter
from models import CalendarSubscription, Project, db, _utcnow
from utils.database import get_vehicles, get_heads

cal_feed_bp = Blueprint("cal_feed", __name__)


def _format_contact(contact, role_label):
    """Formate un contact pour l'affichage dans la description d'événement."""
    if not contact:
        return None
    name = f"{contact.first_name or ''} {contact.last_name or ''}".strip() or "Inconnu"
    phone_part = f" ({contact.phone})" if getattr(
        contact, "phone", None) else ""
    return f"• {role_label} : {name}{phone_part}"


def _build_event_description(project, phase_title, vehicle_map=None, head_map=None, base_url=None):
    """
    Construit une description complète et structurée pour les événements iCal,
    incluant l'équipe, le matériel assigné, le planning complet et les notes.
    """
    name = project.name or "Sans nom"
    lines = [
        f"PROJET : {name}",
        f"PHASE : {phase_title}",
    ]

    if project.production and project.production.name:
        lines.append(f"PRODUCTION : {project.production.name}")

    lines.append("")  # Séparateur

    # 1. Équipe & Contacts clés
    contact_lines = []
    if project.pilot_contact:
        contact_lines.append(_format_contact(project.pilot_contact, "Pilote"))
    if project.dop_contact:
        contact_lines.append(_format_contact(project.dop_contact, "DOP"))
    if project.first_ac_contact:
        contact_lines.append(_format_contact(
            project.first_ac_contact, "1er Ass. Caméra"))
    if project.key_grip_contact:
        contact_lines.append(_format_contact(
            project.key_grip_contact, "Chef Machiniste"))
    if project.production_contact:
        contact_lines.append(_format_contact(
            project.production_contact, "Contact Prod"))

    if contact_lines:
        lines.append("👥 ÉQUIPE & CONTACTS :")
        lines.extend(contact_lines)
        lines.append("")

    # 2. Matériel assigné
    veh_names = []
    if project.vehicles_to_check:
        v_map = vehicle_map or {}
        for vid in [v.strip() for v in project.vehicles_to_check.split(",") if v.strip()]:
            veh_names.append(v_map.get(vid, vid))

    head_names = []
    if project.heads_to_check:
        h_map = head_map or {}
        for hid in [h.strip() for h in project.heads_to_check.split(",") if h.strip()]:
            head_names.append(h_map.get(hid, hid))

    if veh_names or head_names:
        lines.append("🎥 MATÉRIEL :")
        if veh_names:
            lines.append(f"• Véhicule(s) : {', '.join(veh_names)}")
        if head_names:
            lines.append(f"• Machinerie / Tête(s) : {', '.join(head_names)}")
        lines.append("")

    # 3. Planning synthétique global du projet
    lines.append("📅 PLANNING COMPLET :")
    is_punctual = (getattr(project, "date_mode", "continuous") == "punctual")

    if project.departure_date:
        lines.append(
            f"• 🚚 Départ : {project.departure_date.strftime('%d/%m/%Y')}")

    if is_punctual and project.shoot_dates:
        parsed_dates = []
        for d in project.shoot_dates:
            try:
                parsed_dates.append(datetime.strptime(
                    str(d).strip(), "%Y-%m-%d").date())
            except Exception:
                pass
        parsed_dates = sorted(list(set(parsed_dates)))
        if parsed_dates:
            dates_fr = [d.strftime("%d/%m/%Y") for d in parsed_dates]
            lines.append(
                f"• 🎬 Tournage ({len(parsed_dates)}j) : {', '.join(dates_fr)}")

        # Intervalles intermédiaires
        intervals = project.get_inter_shoot_intervals() if hasattr(
            project, "get_inter_shoot_intervals") else []
        if intervals:
            for inter in intervals:
                try:
                    start_fr = datetime.strptime(
                        inter["start"], "%Y-%m-%d").strftime("%d/%m/%Y")
                    end_fr = datetime.strptime(
                        inter["end"], "%Y-%m-%d").strftime("%d/%m/%Y")
                    cnt = inter.get("days_count", len(inter.get("days", [])))
                    if inter.get("is_immobilized"):
                        lines.append(
                            f"  └ 🔒 Entre {start_fr} et {end_fr} : Immobilisé sur place ({cnt}j)")
                except Exception:
                    pass
    elif project.shoot_start_date:
        s_start_fr = project.shoot_start_date.strftime('%d/%m/%Y')
        if project.shoot_end_date and project.shoot_end_date != project.shoot_start_date:
            s_end_fr = project.shoot_end_date.strftime('%d/%m/%Y')
            lines.append(f"• 🎬 Tournage : du {s_start_fr} au {s_end_fr}")
        else:
            lines.append(f"• 🎬 Tournage : le {s_start_fr}")

    if project.return_date:
        lines.append(
            f"• 📦 Retour : {project.return_date.strftime('%d/%m/%Y')}")

    # 4. Notes et demandes spécifiques
    if project.notes:
        lines.append("")
        lines.append("📝 NOTES / DEMANDES SPÉCIFIQUES :")
        lines.append(project.notes.strip())

    # 5. Lien direct vers la fiche projet dans l'ERP
    if base_url and getattr(project, "project_id", None):
        lines.append("")
        lines.append(
            f"🔗 Fiche ERP : {base_url}/admin/projects?q={project.project_id}")

    return "\n".join(lines)


@cal_feed_bp.route("/cal/<token>")
@cal_feed_bp.route("/cal/<token>.ics")
@cal_feed_bp.route("/calendar/feed.ics")
@cal_feed_bp.route("/calendar/feed")
@limiter.limit("30 per hour")
def calendar_feed(token=None):
    """Génère dynamiquement un flux ICS à partir des projets en base."""

    # Si token non présent dans l'URL (ex: /calendar/feed.ics?token=xxx)
    if not token:
        token = request.args.get("token")

    if not token:
        abort(404)

    # 1. Valider le token d'abonnement
    sub = CalendarSubscription.query.filter_by(token=token).first()
    if not sub:
        abort(404)

    # Si le token a été révoqué ou régénéré, chercher si l'utilisateur possède un nouvel abonnement actif
    if not sub.is_active:
        active_sub = CalendarSubscription.query.filter_by(
            user_id=sub.user_id, is_active=True
        ).order_by(CalendarSubscription.id.desc()).first()
        if active_sub:
            current_app.logger.info(
                f"🔄 Redirection d'un ancien token révoqué ({token[:8]}...) vers le token actif ({active_sub.token[:8]}...) pour l'utilisateur {sub.user_id}"
            )
            return redirect(url_for("cal_feed.calendar_feed", token=active_sub.token), code=302)
        abort(404)

    # 2. Mettre à jour la date de dernier accès
    try:
        sub.last_accessed_at = _utcnow()
        db.session.commit()
    except Exception:
        db.session.rollback()

    current_app.logger.info(
        f"📅 Accès calendrier ICS : token={token[:8]}... "
        f"user_id={sub.user_id} IP={request.remote_addr}"
    )

    # 3. Récupérer tous les projets avec au moins une date (et non archivés/supprimés)
    projects = (
        Project.query.filter(Project.deleted_at == None)
        .options(
            joinedload(Project.production),
            joinedload(Project.pilot_contact),
            joinedload(Project.production_contact),
            joinedload(Project.dop_contact),
            joinedload(Project.first_ac_contact),
            joinedload(Project.key_grip_contact),
        )
        .filter(
            db.or_(
                Project.departure_date.isnot(None),
                Project.shoot_start_date.isnot(None),
                Project.return_date.isnot(None),
                Project.shoot_dates.isnot(None),
            )
        )
        .all()
    )

    # 4. Déterminer l'URL racine pour les liens directs vers l'ERP
    base_url = (
        current_app.config.get("APP_BASE_URL")
        or os.getenv("APP_BASE_URL")
        or os.getenv("BASE_URL")
    )
    if not base_url:
        if request and "127.0.0.1" not in request.host and "localhost" not in request.host:
            base_url = request.host_url.rstrip("/")
        else:
            base_url = "https://bellevitesse.com"
    base_url = base_url.rstrip("/")
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"

    # 5. Dictionnaires de résolution du matériel assigné
    try:
        raw_veh = get_vehicles() or []
        vehicle_map = {str(v["id"]): v.get("fields", {}).get(
            "name", f"ID {v['id']}") for v in raw_veh}
    except Exception as e:
        current_app.logger.warning(
            f"Erreur chargement véhicules pour calendar_feed: {e}")
        vehicle_map = {}

    try:
        raw_heads = get_heads() or []
        head_map = {str(h["id"]): h.get("fields", {}).get(
            "name", f"ID {h['id']}") for h in raw_heads}
    except Exception as e:
        current_app.logger.warning(
            f"Erreur chargement têtes pour calendar_feed: {e}")
        head_map = {}

    # 6. Construire le calendrier ICS
    cal = Calendar()
    cal.add("prodid", "-//Belle Vitesse SAS//Calendrier Projets//FR")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", "Belle Vitesse — Projets")
    cal.add("x-wr-timezone", "Europe/Paris")
    # Suggérer un rafraîchissement toutes les 30 minutes
    cal.add("refresh-interval;value=duration", "PT30M")
    cal.add("x-published-ttl", "PT30M")

    now_utc = _utcnow()

    for project in projects:
        name = project.name or "Sans nom"
        is_punctual = (getattr(project, "date_mode",
                       "continuous") == "punctual")
        project_url = (
            f"{base_url}/admin/projects?q={project.project_id}"
            if getattr(project, "project_id", None)
            else None
        )

        # ── A. JALON DÉPART (Check-out) ──
        if project.departure_date:
            checkout_evt = Event()
            checkout_evt.add(
                "uid", f"bv-project-{project.id}-checkout@bellevitesse.com")
            checkout_evt.add("dtstart", project.departure_date)
            checkout_evt.add(
                "dtend", project.departure_date + timedelta(days=1))
            checkout_evt.add("summary", f"🚚 Départ : {name}")
            checkout_evt.add("dtstamp", now_utc)
            checkout_evt.add("categories", ["Belle Vitesse", "Départ"])
            if project_url:
                checkout_evt.add("url", project_url)
            checkout_evt.add(
                "description",
                _build_event_description(
                    project,
                    "🚚 Départ (Check-out)",
                    vehicle_map=vehicle_map,
                    head_map=head_map,
                    base_url=base_url,
                ),
            )
            cal.add_component(checkout_evt)

        # ── B. TOURNAGES & IMMOBILISATIONS ──
        if is_punctual:
            # Traitement des dates ponctuelles ordonnées
            parsed_dates = []
            for d_str in (project.shoot_dates or []):
                try:
                    parsed_dates.append(datetime.strptime(
                        str(d_str).strip(), "%Y-%m-%d").date())
                except Exception:
                    pass
            parsed_dates = sorted(list(set(parsed_dates)))

            if parsed_dates:
                # Regroupement des dates consécutives en blocs continus
                shoot_chunks = []
                cur_chunk = [parsed_dates[0]]
                for d in parsed_dates[1:]:
                    if (d - cur_chunk[-1]).days == 1:
                        cur_chunk.append(d)
                    else:
                        shoot_chunks.append(cur_chunk)
                        cur_chunk = [d]
                if cur_chunk:
                    shoot_chunks.append(cur_chunk)

                # Génération des événements de tournage par bloc
                for c_idx, chunk in enumerate(shoot_chunks, 1):
                    c_start = chunk[0]
                    c_end = chunk[-1]
                    total_chunks = len(shoot_chunks)

                    phase_label = (
                        f"🎬 Tournage (Bloc {c_idx}/{total_chunks})"
                        if total_chunks > 1
                        else "🎬 Tournage"
                    )

                    shoot_evt = Event()
                    shoot_evt.add(
                        "uid", f"bv-project-{project.id}-shoot-{c_idx}@bellevitesse.com")
                    shoot_evt.add("dtstart", c_start)
                    shoot_evt.add("dtend", c_end + timedelta(days=1))
                    shoot_evt.add("summary", f"🎬 Tournage : {name}")
                    shoot_evt.add("dtstamp", now_utc)
                    shoot_evt.add("categories", ["Belle Vitesse", "Tournage"])
                    if project_url:
                        shoot_evt.add("url", project_url)
                    shoot_evt.add(
                        "description",
                        _build_event_description(
                            project,
                            phase_label,
                            vehicle_map=vehicle_map,
                            head_map=head_map,
                            base_url=base_url,
                        ),
                    )
                    cal.add_component(shoot_evt)

                # Génération des événements d'immobilisation pour les intervalles bloqués
                intervals = project.get_inter_shoot_intervals() if hasattr(
                    project, "get_inter_shoot_intervals") else []
                for i_idx, inter in enumerate(intervals, 1):
                    if inter.get("is_immobilized") and inter.get("days"):
                        day_dates = []
                        for d_s in inter["days"]:
                            try:
                                day_dates.append(datetime.strptime(
                                    str(d_s).strip(), "%Y-%m-%d").date())
                            except Exception:
                                pass
                        day_dates = sorted(list(set(day_dates)))
                        if day_dates:
                            immob_start = day_dates[0]
                            immob_end = day_dates[-1]
                            count_days = len(day_dates)

                            immob_evt = Event()
                            immob_evt.add(
                                "uid", f"bv-project-{project.id}-immob-{i_idx}@bellevitesse.com")
                            immob_evt.add("dtstart", immob_start)
                            immob_evt.add("dtend", immob_end +
                                          timedelta(days=1))
                            immob_evt.add("summary", f"🔒 Immobilisé : {name}")
                            immob_evt.add("dtstamp", now_utc)
                            immob_evt.add(
                                "categories", ["Belle Vitesse", "Immobilisation"])
                            if project_url:
                                immob_evt.add("url", project_url)
                            immob_evt.add(
                                "description",
                                _build_event_description(
                                    project,
                                    f"🔒 Immobilisation sur place ({count_days}j)",
                                    vehicle_map=vehicle_map,
                                    head_map=head_map,
                                    base_url=base_url,
                                ),
                            )
                            cal.add_component(immob_evt)
            elif project.shoot_start_date:
                # Fallback ponctuel sans shoot_dates détaillées
                s_start = project.shoot_start_date
                s_end = project.shoot_end_date or project.shoot_start_date
                shoot_evt = Event()
                shoot_evt.add(
                    "uid", f"bv-project-{project.id}-shoot@bellevitesse.com")
                shoot_evt.add("dtstart", s_start)
                shoot_evt.add("dtend", s_end + timedelta(days=1))
                shoot_evt.add("summary", f"🎬 Tournage : {name}")
                shoot_evt.add("dtstamp", now_utc)
                shoot_evt.add("categories", ["Belle Vitesse", "Tournage"])
                if project_url:
                    shoot_evt.add("url", project_url)
                shoot_evt.add(
                    "description",
                    _build_event_description(
                        project,
                        "🎬 Tournage",
                        vehicle_map=vehicle_map,
                        head_map=head_map,
                        base_url=base_url,
                    ),
                )
                cal.add_component(shoot_evt)
        else:
            # Mode continu classique
            if project.shoot_start_date:
                s_start = project.shoot_start_date
                s_end = project.shoot_end_date or project.shoot_start_date
                shoot_evt = Event()
                shoot_evt.add(
                    "uid", f"bv-project-{project.id}-shoot@bellevitesse.com")
                shoot_evt.add("dtstart", s_start)
                shoot_evt.add("dtend", s_end + timedelta(days=1))
                shoot_evt.add("summary", f"🎬 Tournage : {name}")
                shoot_evt.add("dtstamp", now_utc)
                shoot_evt.add("categories", ["Belle Vitesse", "Tournage"])
                if project_url:
                    shoot_evt.add("url", project_url)
                shoot_evt.add(
                    "description",
                    _build_event_description(
                        project,
                        "🎬 Tournage",
                        vehicle_map=vehicle_map,
                        head_map=head_map,
                        base_url=base_url,
                    ),
                )
                cal.add_component(shoot_evt)

        # ── C. JALON RETOUR (Check-in) ──
        if project.return_date:
            checkin_evt = Event()
            checkin_evt.add(
                "uid", f"bv-project-{project.id}-checkin@bellevitesse.com")
            checkin_evt.add("dtstart", project.return_date)
            checkin_evt.add("dtend", project.return_date + timedelta(days=1))
            checkin_evt.add("summary", f"📦 Retour : {name}")
            checkin_evt.add("dtstamp", now_utc)
            checkin_evt.add("categories", ["Belle Vitesse", "Retour"])
            if project_url:
                checkin_evt.add("url", project_url)
            checkin_evt.add(
                "description",
                _build_event_description(
                    project,
                    "📦 Retour (Check-in)",
                    vehicle_map=vehicle_map,
                    head_map=head_map,
                    base_url=base_url,
                ),
            )
            cal.add_component(checkin_evt)

    # 7. Retourner la réponse ICS avec les en-têtes de cache appropriés
    return Response(
        cal.to_ical(),
        mimetype="text/calendar",
        headers={
            "Content-Disposition": "inline; filename=bellevitesse.ics",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )
