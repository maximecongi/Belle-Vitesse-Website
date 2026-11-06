"""Add vehicle_road_legal_statuses to projects.

Revision ID: y00d7fe3c485
Revises: x00d7fe3c484
Create Date: 2026-11-06 18:20:00
"""
from alembic import op
import sqlalchemy as sa

revision = "y00d7fe3c485"
down_revision = "x00d7fe3c484"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns("projects")]
    if "vehicle_road_legal_statuses" not in columns:
        op.add_column(
            "projects",
            sa.Column("vehicle_road_legal_statuses", sa.JSON(), nullable=True),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns("projects")]
    if "vehicle_road_legal_statuses" in columns:
        op.drop_column("projects", "vehicle_road_legal_statuses")

