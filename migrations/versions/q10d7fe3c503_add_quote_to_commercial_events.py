"""Timeline commerciale : devis joint aux événements « Devis envoyé ».

Ajoute project_commercial_events.quote_amount (montant total HT), file_path / file_name (copie locale
du devis, également envoyée dans 1_DEVIS sur kDrive).

Revision ID: q10d7fe3c503
Revises: p10d7fe3c502
Create Date: 2026-11-13 15:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "q10d7fe3c503"
down_revision = "p10d7fe3c502"
branch_labels = None
depends_on = None

_TABLE = "project_commercial_events"
_COLUMNS = (
    ("quote_amount", sa.Numeric(12, 2)),
    ("file_path", sa.String(500)),
    ("file_name", sa.String(255)),
)


def _existing(inspector):
    return {c["name"] for c in inspector.get_columns(_TABLE)}


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if _TABLE not in inspector.get_table_names():
        return
    existing = _existing(inspector)
    with op.batch_alter_table(_TABLE) as batch:
        for name, col_type in _COLUMNS:
            if name not in existing:
                batch.add_column(sa.Column(name, col_type, nullable=True))


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if _TABLE not in inspector.get_table_names():
        return
    existing = _existing(inspector)
    with op.batch_alter_table(_TABLE) as batch:
        for name, _ in _COLUMNS:
            if name in existing:
                batch.drop_column(name)
