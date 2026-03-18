import logging
from models import db, Production

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


    if prod:
        db.session.delete(prod)
        db.session.commit()
