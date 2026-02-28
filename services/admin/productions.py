import logging
from collections import defaultdict

from flask import url_for

from models import db, CheckoutVehicle, Production, Project

logger = logging.getLogger(__name__)


# ── Productions ──────────────────────────────────────────────────


def list_productions():
    """
    Fetch all production records and format for listing.

    Returns:
        list of production dicts.
    """
    records = Production.query.order_by(Production.nom).all()
    productions = []
    for r in records:
        productions.append({
            "id": r.id,
            "name": r.nom,
            "address": r.adresse or "—",
            "email": r.mail or "—",
            "phone": r.phone or "—",
        })
    return productions


def create_production(form):
    """Create a new production record in the database."""
    prod = Production(
        nom=form.get("name", ""),
        adresse=form.get("address", ""),
        mail=form.get("email", ""),
        phone=form.get("phone", "")
    )
    db.session.add(prod)
    db.session.commit()
    return True


def update_production(record_id, form):
    """Update an existing production record in the database."""
    prod = db.session.get(Production, record_id)
    if not prod:
        return False

    prod.nom = form.get("name", "")
    prod.adresse = form.get("address", "")
    prod.mail = form.get("email", "")
    prod.phone = form.get("phone", "")

    db.session.commit()
    return True


def get_production_for_edit(record_id):
    """
    Fetch a production record and format for editing.

    Returns:
        dict with form-ready keys, or None if not found.
    """
    prod = db.session.get(Production, record_id)
    if not prod:
        return None

    return {
        "name": prod.nom,
        "address": prod.adresse or "",
        "email": prod.mail or "",
        "phone": prod.phone or "",
    }


def delete_production(record_id):
    """Delete a production record from the database."""
    prod = db.session.get(Production, record_id)
    if prod:
        db.session.delete(prod)
        db.session.commit()


# ── Calendar ─────────────────────────────────────────────────────


def get_calendar_events():
    records = Project.query.all()
    events = []
    colors = [
        "#618b4a", "#5299d3", "#f59e0b", "#e05c5c", "#8b5cf6",
        "#06b6d4", "#f97316", "#ec4899", "#14b8a6", "#a855f7",
    ]

    for i, r in enumerate(records):
        name = r.nom or "Sans nom"
        color = colors[i % len(colors)]

        if r.date_depart:
            events.append({
                "title": f"🚚 Départ: {name}",
                "start": r.date_depart.isoformat(),
                "color": color,
                "url": url_for("admin_project_edit", record_id=r.id),
            })

        if r.date_debut_tournage:
            event = {
                "title": f"🎬 {name}",
                "start": r.date_debut_tournage.isoformat(),
                "color": color,
                "url": url_for("admin_project_edit", record_id=r.id),
            }
            if r.date_fin_tournage:
                event["end"] = r.date_fin_tournage.isoformat()
            events.append(event)

        if r.date_retour:
            events.append({
                "title": f"📦 Retour: {name}",
                "start": r.date_retour.isoformat(),
                "color": color,
                "url": url_for("admin_project_edit", record_id=r.id),
            })

    return events


# ── Stats (Chart.js) ─────────────────────────────────────────────


def get_checkout_stats():
    """
    Compute checkout statistics for Chart.js charts.

    Returns a dict with nested structure matching the frontend expectations:
        {
            'monthly_activity': { 'labels': [...], 'data': [...] },
            'status_distribution': { 'labels': [...], 'data': [...] },
        }
    """
    records = CheckoutVehicle.query.all()

    # ── Status counts ─────────────────────────────────────────────
    status_counts = defaultdict(int)
    for r in records:
        status = r.etat_controle or "Inconnu"
        status_counts[status] += 1

    # ── Monthly activity ──────────────────────────────────────────
    monthly = defaultdict(int)
    for r in records:
        if r.created_at:
            month_key = r.created_at.strftime("%Y-%m")
            monthly[month_key] += 1

    sorted_months = sorted(monthly.items())

    # ── Status labels in display order ────────────────────────────
    ordered_statuses = ["Signé", "Terminé", "À signer", "Inconnu"]
    status_labels = [
        s for s in ordered_statuses if status_counts.get(s, 0) > 0]
    # Add any extra statuses not in our ordered list
    for s in status_counts:
        if s not in status_labels:
            status_labels.append(s)

    return {
        "monthly_activity": {
            "labels": [m[0] for m in sorted_months],
            "data": [m[1] for m in sorted_months],
        },
        "status_distribution": {
            "labels": status_labels,
            "data": [status_counts[s] for s in status_labels],
        },
    }
