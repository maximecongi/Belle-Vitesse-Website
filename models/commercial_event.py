"""
Timeline commerciale d'un projet : chaque prise de contact (mail, appel, devis, facture,
abandon…) est un événement daté. Le statut commercial du projet en est déduit.
"""
from models.db import db, _utcnow


# ── Types d'événements ─────────────────────────────────────────
# (clé, libellé, icône Lucide, famille de couleur, statut commercial atteint ou None)
# La famille pilote la couleur de la puce (cf. admin-commercial-timeline.css).
COMMERCIAL_EVENT_TYPES = [
    ("first_request", "Première demande", "inbox", "project", "prospect"),
    ("email_in", "Mail reçu", "mail", "info", None),
    ("email_out", "Mail envoyé", "send", "neutral", None),
    ("call_in", "Appel reçu", "phone-incoming", "info", None),
    ("call_out", "Appel émis", "phone-outgoing", "neutral", None),
    ("meeting", "Rendez-vous / visio", "users", "neutral", None),
    ("quote_sent", "Devis envoyé", "file-text", "warning", "quote_sent"),
    ("quote_followup", "Relance devis", "bell-ring", "warning", None),
    ("confirmed", "Projet confirmé", "circle-check", "success", "confirmed"),
    ("invoice_sent", "Facture émise", "receipt", "info", "invoiced"),
    ("invoice_paid", "Facture payée", "badge-euro", "success", "paid"),
    ("lost", "Abandon du projet", "circle-x", "danger", "lost"),
]
EVENT_TYPE_KEYS = [t[0] for t in COMMERCIAL_EVENT_TYPES]
EVENT_TYPE_LABELS = {t[0]: t[1] for t in COMMERCIAL_EVENT_TYPES}
EVENT_TYPE_ICONS = {t[0]: t[2] for t in COMMERCIAL_EVENT_TYPES}
EVENT_TYPE_FAMILIES = {t[0]: t[3] for t in COMMERCIAL_EVENT_TYPES}
EVENT_TYPE_MILESTONES = {t[0]: t[4] for t in COMMERCIAL_EVENT_TYPES if t[4]}

# Regroupement dans le sélecteur du formulaire
EVENT_TYPE_GROUPS = [
    ("Échanges", ["first_request", "email_in", "email_out", "call_in", "call_out", "meeting"]),
    ("Devis & facturation", ["quote_sent", "quote_followup", "confirmed", "invoice_sent", "invoice_paid"]),
    ("Clôture", ["lost"]),
]

# Motifs d'abandon
LOST_REASONS = [
    ("price", "Prix"),
    ("dates", "Dates / disponibilité"),
    ("competitor", "Concurrent retenu"),
    ("no_answer", "Sans réponse du client"),
    ("cancelled", "Tournage annulé"),
    ("other", "Autre"),
]
LOST_REASON_LABELS = dict(LOST_REASONS)

# ── Statuts commerciaux du projet ──────────────────────────────
# (clé, libellé, variante de badge)
COMMERCIAL_STATUSES = [
    ("prospect", "Demande en cours", "project"),
    ("quote_sent", "Devis envoyé", "warning"),
    ("confirmed", "Confirmé", "success"),
    ("invoiced", "Facturé", "info"),
    ("paid", "Payé", "success"),
    ("lost", "Abandonné", "danger"),
]
COMMERCIAL_STATUS_LABELS = {k: label for k, label, _ in COMMERCIAL_STATUSES}
COMMERCIAL_STATUS_VARIANTS = {k: v for k, _, v in COMMERCIAL_STATUSES}
DEFAULT_COMMERCIAL_STATUS = "prospect"

# Statuts pour lesquels le dossier commercial est clos (pas de repère « aujourd'hui »)
CLOSED_COMMERCIAL_STATUSES = {"paid", "lost"}


class ProjectCommercialEvent(db.Model):
    """Prise de contact ou jalon commercial daté, rattaché à un projet."""
    __tablename__ = "project_commercial_events"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type = db.Column(db.String(30), nullable=False)
    # Heure murale saisie par l'utilisateur (heure de Paris), et non un horodatage système UTC
    occurred_at = db.Column(db.DateTime, nullable=False, index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True)
    summary = db.Column(db.String(500), nullable=True)
    lost_reason = db.Column(db.String(30), nullable=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    author_name = db.Column(db.String(150), nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)

    project = db.relationship(
        "Project",
        backref=db.backref(
            "commercial_events", cascade="all, delete-orphan", lazy=True,
            order_by="ProjectCommercialEvent.occurred_at.asc()",
        ),
    )
    contact = db.relationship("Contact")
    user = db.relationship("User")

    @property
    def type_label(self):
        return EVENT_TYPE_LABELS.get(self.event_type, self.event_type)

    @property
    def icon(self):
        return EVENT_TYPE_ICONS.get(self.event_type, "circle")

    @property
    def family(self):
        return EVENT_TYPE_FAMILIES.get(self.event_type, "neutral")

    @property
    def milestone_status(self):
        return EVENT_TYPE_MILESTONES.get(self.event_type)

    @property
    def lost_reason_label(self):
        return LOST_REASON_LABELS.get(self.lost_reason) if self.lost_reason else None

    @property
    def contact_name(self):
        if not self.contact:
            return None
        return f"{self.contact.first_name} {self.contact.last_name}".strip()

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "event_type": self.event_type,
            "type_label": self.type_label,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "contact_id": self.contact_id,
            "contact_name": self.contact_name,
            "summary": self.summary,
            "lost_reason": self.lost_reason,
            "lost_reason_label": self.lost_reason_label,
            "author_name": self.author_name,
        }

    def __repr__(self):
        return f"<ProjectCommercialEvent #{self.id} {self.event_type} project={self.project_id}>"
