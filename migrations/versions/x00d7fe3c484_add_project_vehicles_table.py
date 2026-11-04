"""Add project_vehicles association table.

Revision ID: x00d7fe3c484
Revises: w00d7fe3c483
Create Date: 2026-11-04 13:20:00
"""
from alembic import op
import sqlalchemy as sa

revision = "x00d7fe3c484"
down_revision = "w00d7fe3c483"
branch_labels = None
depends_on = None


def upgrade():
    # Vérifie si la table existe déjà pour idempotence
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if "project_vehicles" not in tables:
        op.create_table(
            "project_vehicles",
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("vehicle_id", sa.String(length=100), primary_key=True),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if "project_vehicles" in tables:
        op.drop_table("project_vehicles")

