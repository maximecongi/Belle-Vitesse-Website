"""Facturation des projets : montant global HT et montants par matériel.

Ajoute projects.billing_amount (Numeric 12,2) et projects.equipment_billing (JSON
{"vehicle:<id>" | "head:<id>": montant}). Colonnes facultatives, vides pour les projets existants.

Revision ID: m10d7fe3c499
Revises: l10d7fe3c498
Create Date: 2026-11-12 21:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "m10d7fe3c499"
down_revision = "l10d7fe3c498"
branch_labels = None
depends_on = None

_TABLE = "projects"
_COLUMNS = (
    ("billing_amount", sa.Numeric(12, 2)),
    ("equipment_billing", sa.JSON()),
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
