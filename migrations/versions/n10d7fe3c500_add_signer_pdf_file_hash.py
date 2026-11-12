"""Empreinte de la copie signataire des documents scellés.

Chaque document signé est désormais compilé en deux PDF : l'archive Belle Vitesse
(filigrane « Belle Vitesse », empreinte dans pdf_file_hash) et la copie remise au
signataire (filigrane à son nom). signer_pdf_file_hash conserve le SHA-256 de cette
copie pour que la page de vérification publique l'accepte aussi. Colonne facultative,
vide pour les documents existants et pour ceux sans copie signataire (check-in/out).

Revision ID: n10d7fe3c500
Revises: m10d7fe3c499
Create Date: 2026-11-12 22:40:00
"""
from alembic import op
import sqlalchemy as sa

revision = "n10d7fe3c500"
down_revision = "m10d7fe3c499"
branch_labels = None
depends_on = None

_TABLES = (
    "waiver_signed_documents",
    "incident_signed_documents",
    "checkout_signed_documents",
    "checkin_signed_documents",
)
_COLUMN = "signer_pdf_file_hash"


def upgrade():
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    for table in _TABLES:
        if table not in tables:
            continue
        if _COLUMN in {c["name"] for c in inspector.get_columns(table)}:
            continue
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column(_COLUMN, sa.String(64), nullable=True))


def downgrade():
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    for table in _TABLES:
        if table not in tables:
            continue
        if _COLUMN not in {c["name"] for c in inspector.get_columns(table)}:
            continue
        with op.batch_alter_table(table) as batch:
            batch.drop_column(_COLUMN)
