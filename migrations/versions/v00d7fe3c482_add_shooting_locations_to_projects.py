"""Add shooting_locations to projects.

Revision ID: v00d7fe3c482
Revises: u00d7fe3c481
Create Date: 2026-10-30 10:45:00
"""
from alembic import op
import sqlalchemy as sa

revision = "v00d7fe3c482"
down_revision = "u00d7fe3c481"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns("projects")]
    if "shooting_locations" not in columns:
        op.add_column(
            "projects",
            sa.Column("shooting_locations", sa.JSON(), nullable=True),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns("projects")]
    if "shooting_locations" in columns:
        op.drop_column("projects", "shooting_locations")

