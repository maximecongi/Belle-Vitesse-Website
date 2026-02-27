import logging
from models import db, Contact, Production

logger = logging.getLogger(__name__)


def list_contacts():
    """Fetch all contacts, joined with their production if any."""
    records = Contact.query.order_by(Contact.nom, Contact.prenom).all()
    contacts = []
    for r in records:
        contacts.append({
            "id": r.id,
            "prenom": r.prenom,
            "nom": r.nom,
            "telephone": r.telephone or "—",
            "mail": r.mail or "—",
            "metier": r.metier or "—",
            "production_name": r.production_rel.nom if r.production_rel else "Freelance",
        })
    return contacts


def create_contact(form):
    """Create a new contact record."""
    production_id = form.get("production_id") or None
    contact = Contact(
        prenom=form.get("prenom", ""),
        nom=form.get("nom", ""),
        telephone=form.get("telephone", ""),
        mail=form.get("mail", ""),
        production_id=int(production_id) if production_id else None,
        metier=form.get("metier", ""),
    )
    db.session.add(contact)
    db.session.commit()
    return True


def update_contact(record_id, form):
    """Update an existing contact record."""
    contact = db.session.get(Contact, record_id)
    if not contact:
        return False

    production_id = form.get("production_id") or None
    contact.prenom = form.get("prenom", "")
    contact.nom = form.get("nom", "")
    contact.telephone = form.get("telephone", "")
    contact.mail = form.get("mail", "")
    contact.production_id = int(production_id) if production_id else None
    contact.metier = form.get("metier", "")

    db.session.commit()
    return True


def get_contact_for_edit(record_id):
    """Fetch a contact record for editing."""
    contact = db.session.get(Contact, record_id)
    if not contact:
        return None

    return {
        "prenom": contact.prenom,
        "nom": contact.nom,
        "telephone": contact.telephone or "",
        "mail": contact.mail or "",
        "production_id": contact.production_id,
        "metier": contact.metier or "",
    }


def delete_contact(record_id):
    """Delete a contact record."""
    contact = db.session.get(Contact, record_id)
    if contact:
        db.session.delete(contact)
        db.session.commit()


def get_productions_for_select():
    """Return all productions for the contact form select."""
    return Production.query.order_by(Production.nom).all()
