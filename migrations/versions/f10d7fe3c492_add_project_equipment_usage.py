"""Add project_equipment_usage table (pointage journalier du matériel par jour de tournage).

Revision ID: f10d7fe3c492
Revises: e10d7fe3c491
Create Date: 2026-11-11 16:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "f10d7fe3c492"
down_revision = "e10d7fe3c491"
branch_labels = None
depends_on = None

_TABLE = "project_equipment_usage"


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if _TABLE in inspector.get_table_names():
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("equipment_type", sa.String(length=20), nullable=False),
        sa.Column("equipment_id", sa.String(length=100), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "project_id", "equipment_type", "equipment_id", "usage_date",
            name="uq_project_equipment_usage_day",
        ),
    )
    op.create_index("ix_project_equipment_usage_project_id", _TABLE, ["project_id"], unique=False)
    op.create_index(
        "ix_project_equipment_usage_equipment", _TABLE,
        ["equipment_type", "equipment_id", "usage_date"], unique=False,
    )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if _TABLE not in inspector.get_table_names():
        return
    op.drop_index("ix_project_equipment_usage_equipment", table_name=_TABLE)
    op.drop_index("ix_project_equipment_usage_project_id", table_name=_TABLE)
    op.drop_table(_TABLE)
