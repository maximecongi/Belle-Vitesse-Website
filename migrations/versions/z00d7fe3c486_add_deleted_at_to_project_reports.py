"""Add deleted_at (soft-delete) to project_reports.

Revision ID: z00d7fe3c486
Revises: y00d7fe3c485
Create Date: 2026-11-09 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "z00d7fe3c486"
down_revision = "y00d7fe3c485"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns("project_reports")]
    if "deleted_at" not in columns:
        op.add_column("project_reports", sa.Column("deleted_at", sa.DateTime(), nullable=True))
        op.create_index(
            "ix_project_reports_deleted_at", "project_reports", ["deleted_at"], unique=False
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns("project_reports")]
    if "deleted_at" in columns:
        op.drop_index("ix_project_reports_deleted_at", table_name="project_reports")
        op.drop_column("project_reports", "deleted_at")
