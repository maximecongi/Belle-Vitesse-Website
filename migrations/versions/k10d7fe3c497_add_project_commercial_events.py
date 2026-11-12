"""Timeline commerciale des projets (prises de contact) et statut commercial.

Crée la table project_commercial_events et ajoute projects.commercial_status.
Les projets existants restent à NULL (antérieurs au suivi commercial, aucun badge affiché).

Revision ID: k10d7fe3c497
Revises: j10d7fe3c496
Create Date: 2026-11-12 18:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "k10d7fe3c497"
down_revision = "j10d7fe3c496"
branch_labels = None
depends_on = None

_TABLE = "project_commercial_events"
_COL = "commercial_status"


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _TABLE not in inspector.get_table_names():
        op.create_table(
            _TABLE,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("event_type", sa.String(30), nullable=False),
            sa.Column("occurred_at", sa.DateTime(), nullable=False),
            sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True),
            sa.Column("summary", sa.String(500), nullable=True),
            sa.Column("lost_reason", sa.String(30), nullable=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("author_name", sa.String(150), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index(f"ix_{_TABLE}_project_id", _TABLE, ["project_id"], unique=False)
        op.create_index(f"ix_{_TABLE}_occurred_at", _TABLE, ["occurred_at"], unique=False)

    columns = {c["name"] for c in inspector.get_columns("projects")}
    if _COL not in columns:
        with op.batch_alter_table("projects") as batch:
            batch.add_column(sa.Column(_COL, sa.String(20), nullable=True))
            batch.create_index(f"ix_projects_{_COL}", [_COL], unique=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {c["name"] for c in inspector.get_columns("projects")}
    if _COL in columns:
        indexes = {ix["name"] for ix in inspector.get_indexes("projects")}
        with op.batch_alter_table("projects") as batch:
            if f"ix_projects_{_COL}" in indexes:
                batch.drop_index(f"ix_projects_{_COL}")
            batch.drop_column(_COL)

    if _TABLE in inspector.get_table_names():
        op.drop_table(_TABLE)
