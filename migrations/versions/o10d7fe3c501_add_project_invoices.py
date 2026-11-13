"""Factures multiples par projet.

Crée la table project_invoices (une ligne par facture : n°, libellé, date d'émission, montant HT,
ventilation par matériel, statut payée) et supprime projects.billing_amount / projects.equipment_billing
(montant unique, repris de zéro : pas de conversion des montants existants).

Revision ID: o10d7fe3c501
Revises: n10d7fe3c500
Create Date: 2026-11-13 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "o10d7fe3c501"
down_revision = "n10d7fe3c500"
branch_labels = None
depends_on = None

_OLD_COLUMNS = (
    ("billing_amount", sa.Numeric(12, 2)),
    ("equipment_billing", sa.JSON()),
)


def upgrade():
    inspector = sa.inspect(op.get_bind())
    tables = inspector.get_table_names()
    if "project_invoices" not in tables:
        op.create_table(
            "project_invoices",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("number", sa.String(60), nullable=True),
            sa.Column("label", sa.String(150), nullable=True),
            sa.Column("issued_on", sa.Date(), nullable=False),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("equipment_billing", sa.JSON(), nullable=True),
            sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("paid_on", sa.Date(), nullable=True),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_project_invoices_project_id", "project_invoices", ["project_id"])
        op.create_index("ix_project_invoices_issued_on", "project_invoices", ["issued_on"])

    if "projects" in tables:
        existing = {c["name"] for c in inspector.get_columns("projects")}
        to_drop = [name for name, _ in _OLD_COLUMNS if name in existing]
        if to_drop:
            with op.batch_alter_table("projects") as batch:
                for name in to_drop:
                    batch.drop_column(name)


def downgrade():
    inspector = sa.inspect(op.get_bind())
    tables = inspector.get_table_names()
    if "projects" in tables:
        existing = {c["name"] for c in inspector.get_columns("projects")}
        with op.batch_alter_table("projects") as batch:
            for name, col_type in _OLD_COLUMNS:
                if name not in existing:
                    batch.add_column(sa.Column(name, col_type, nullable=True))
    if "project_invoices" in tables:
        op.drop_index("ix_project_invoices_issued_on", table_name="project_invoices")
        op.drop_index("ix_project_invoices_project_id", table_name="project_invoices")
        op.drop_table("project_invoices")
