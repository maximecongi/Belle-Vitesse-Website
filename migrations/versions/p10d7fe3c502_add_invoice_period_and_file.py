"""Factures : fichier joint.

Ajoute project_invoices.file_path / file_name (copie locale du fichier de facture, également envoyée
dans 2_FACTURES sur kDrive).

Revision ID: p10d7fe3c502
Revises: o10d7fe3c501
Create Date: 2026-11-13 11:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "p10d7fe3c502"
down_revision = "o10d7fe3c501"
branch_labels = None
depends_on = None

_TABLE = "project_invoices"
_COLUMNS = (
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
