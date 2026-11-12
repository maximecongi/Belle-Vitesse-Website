"""Timeline commerciale : événements à venir (planifiés).

Ajoute project_commercial_events.is_planned (faux pour les prises de contact existantes).

Revision ID: l10d7fe3c498
Revises: k10d7fe3c497
Create Date: 2026-11-12 19:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "l10d7fe3c498"
down_revision = "k10d7fe3c497"
branch_labels = None
depends_on = None

_TABLE = "project_commercial_events"
_COL = "is_planned"


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if _TABLE not in inspector.get_table_names():
        return
    if _COL not in {c["name"] for c in inspector.get_columns(_TABLE)}:
        with op.batch_alter_table(_TABLE) as batch:
            batch.add_column(sa.Column(_COL, sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if _TABLE in inspector.get_table_names() and _COL in {c["name"] for c in inspector.get_columns(_TABLE)}:
        with op.batch_alter_table(_TABLE) as batch:
            batch.drop_column(_COL)
