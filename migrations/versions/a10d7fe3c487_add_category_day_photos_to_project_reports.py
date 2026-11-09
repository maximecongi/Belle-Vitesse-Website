"""Add category, shoot_day and photos to project_reports.

Revision ID: a10d7fe3c487
Revises: z00d7fe3c486
Create Date: 2026-11-09 14:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "a10d7fe3c487"
down_revision = "z00d7fe3c486"
branch_labels = None
depends_on = None


def _columns():
    return [c["name"] for c in sa.inspect(op.get_bind()).get_columns("project_reports")]


def upgrade():
    cols = _columns()
    if "category" not in cols:
        op.add_column(
            "project_reports",
            sa.Column("category", sa.String(30), nullable=False, server_default="note"),
        )
        op.create_index("ix_project_reports_category", "project_reports", ["category"], unique=False)
    if "shoot_day" not in cols:
        op.add_column("project_reports", sa.Column("shoot_day", sa.Date(), nullable=True))
        op.create_index("ix_project_reports_shoot_day", "project_reports", ["shoot_day"], unique=False)
    if "photos" not in cols:
        op.add_column("project_reports", sa.Column("photos", sa.Text(), nullable=True))


def downgrade():
    cols = _columns()
    if "photos" in cols:
        op.drop_column("project_reports", "photos")
    if "shoot_day" in cols:
        op.drop_index("ix_project_reports_shoot_day", table_name="project_reports")
        op.drop_column("project_reports", "shoot_day")
    if "category" in cols:
        op.drop_index("ix_project_reports_category", table_name="project_reports")
        op.drop_column("project_reports", "category")
