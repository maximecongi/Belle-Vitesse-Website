import json
from datetime import datetime, timedelta, timezone

from models.db import db, _utcnow


# Fenêtre pendant laquelle l'auteur d'un rapport peut encore le modifier.
REPORT_EDIT_WINDOW_SECONDS = 3 * 3600  # 3 heures

# Nombre maximal de photos jointes à un rapport.
REPORT_MAX_PHOTOS = 10

# Catégories de rapport : (clé, libellé, variante de badge)
REPORT_CATEGORIES = [
    ("note", "Note", "neutral"),
    ("debrief", "Débrief", "info"),
    ("technique", "Technique", "accent"),
    ("logistique", "Logistique", "warning"),
    ("securite", "Sécurité", "danger"),
    ("production", "Production", "success"),
]
REPORT_CATEGORY_LABELS = {key: label for key, label, _ in REPORT_CATEGORIES}
REPORT_CATEGORY_VARIANTS = {key: variant for key, _, variant in REPORT_CATEGORIES}
DEFAULT_REPORT_CATEGORY = "note"


def _as_utc(dt):
    """Normalise un datetime naïf (stocké en UTC) en datetime aware UTC."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


class ProjectReport(db.Model):
    """
    Modèle représentant un rapport ou commentaire d'équipe affilié à un projet (tournage).
    Permet à l'équipe (pilotes, techniciens, administrateurs) de consigner des observations,
    faits marquants et débriefs techniques au fil de l'eau.
    """
    __tablename__ = "project_reports"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer,
        db.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    author_name = db.Column(db.String(150), nullable=True)
    author_role = db.Column(db.String(100), nullable=True)
    title = db.Column(db.String(255), nullable=True)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(30), nullable=False, default=DEFAULT_REPORT_CATEGORY,
                         server_default=DEFAULT_REPORT_CATEGORY, index=True)
    shoot_day = db.Column(db.Date, nullable=True, index=True)  # Jour de tournage concerné
    photos = db.Column(db.Text, nullable=True)  # JSON : chemins relatifs à OUTPUT_FOLDER

    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)
    deleted_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL", name="fk_project_reports_deleted_by_id_users"),
        nullable=True,
    )

    # Relations
    project = db.relationship("Project", backref=db.backref("reports", cascade="all, delete-orphan", order_by="ProjectReport.created_at.asc()", lazy=True))
    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("project_reports", lazy=True))
    deleted_by = db.relationship("User", foreign_keys=[deleted_by_id])

    # ── Requêtes ───────────────────────────────────────────────

    @classmethod
    def active(cls):
        """Requête de base excluant les rapports supprimés (soft-delete)."""
        return cls.query.filter(cls.deleted_at.is_(None))

    # ── Affichage ──────────────────────────────────────────────

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    @property
    def display_author_name(self):
        """Nom de l'auteur (snapshot) avec repli sur l'utilisateur lié."""
        if self.author_name:
            return self.author_name
        if self.user:
            return f"{self.user.firstname} {self.user.lastname}".strip()
        return "Collaborateur"

    @property
    def display_author_role(self):
        """Rôle de l'auteur (snapshot) avec repli sur le rôle de l'utilisateur lié."""
        if self.author_role:
            return self.author_role
        return self.user.role_display if self.user else "Équipe"

    @property
    def author_job(self):
        """Retourne le job/poste de l'auteur dans l'équipe (ou repli sur le rôle)."""
        if self.user and self.user.job:
            return self.user.job
        return self.author_role or "Équipe"

    @property
    def category_key(self):
        return self.category if self.category in REPORT_CATEGORY_LABELS else DEFAULT_REPORT_CATEGORY

    @property
    def category_label(self):
        return REPORT_CATEGORY_LABELS[self.category_key]

    @property
    def category_variant(self):
        return REPORT_CATEGORY_VARIANTS[self.category_key]

    @property
    def photo_paths(self):
        """Liste des chemins relatifs des photos jointes."""
        if not self.photos:
            return []
        try:
            data = json.loads(self.photos)
            return [str(p) for p in data] if isinstance(data, list) else []
        except (ValueError, TypeError):
            return []

    @photo_paths.setter
    def photo_paths(self, paths):
        paths = [str(p) for p in (paths or []) if p]
        self.photos = json.dumps(paths) if paths else None

    @property
    def editable_until(self):
        """Fin de la fenêtre de modification de l'auteur (UTC aware)."""
        created = _as_utc(self.created_at)
        return created + timedelta(seconds=REPORT_EDIT_WINDOW_SECONDS) if created else None

    @property
    def is_edited(self):
        """Vrai si le rapport a été modifié après sa publication (tolérance de 2 s)."""
        created, updated = _as_utc(self.created_at), _as_utc(self.updated_at)
        if not created or not updated:
            return False
        return (updated - created).total_seconds() > 2

    # ── Permissions ────────────────────────────────────────────

    def is_authored_by(self, user_id):
        return user_id is not None and self.user_id == user_id

    def is_within_edit_window(self, now=None):
        created = _as_utc(self.created_at)
        if not created:
            return False
        now = now or datetime.now(timezone.utc)
        return (now - created).total_seconds() <= REPORT_EDIT_WINDOW_SECONDS

    def can_be_edited_by(self, user_id, is_admin=False, now=None):
        """Administrateur : toujours. Auteur : uniquement dans la fenêtre de 3 h."""
        if is_admin:
            return True
        return self.is_authored_by(user_id) and self.is_within_edit_window(now)

    def can_be_deleted_by(self, user_id, is_admin=False):
        """Administrateur ou auteur."""
        return is_admin or self.is_authored_by(user_id)

    def can_be_restored_by(self, user_id, is_super_admin=False):
        """
        Super administrateur : toujours. Sinon uniquement la personne qui a créé
        le rapport ET l'a elle-même supprimé.
        """
        if is_super_admin:
            return True
        return self.is_authored_by(user_id) and self.deleted_by_id == user_id

    # ── Sérialisation ──────────────────────────────────────────

    def to_dict(self):
        """Sérialise le rapport pour les réponses JSON / API."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "user_id": self.user_id,
            "title": self.title,
            "author_name": self.display_author_name,
            "author_role": self.display_author_role,
            "author_job": self.author_job,
            "content": self.content,
            "category": self.category_key,
            "category_label": self.category_label,
            "shoot_day": self.shoot_day.isoformat() if self.shoot_day else None,
            "photos": [f"/files/{p}" for p in self.photo_paths],
            "is_edited": self.is_edited,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<ProjectReport #{self.id} for Project {self.project_id} by {self.author_name}>"
