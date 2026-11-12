"""Add project_equipment_usage_logs (historique des pointages du matériel).

Revision ID: i10d7fe3c495
Revises: h10d7fe3c494
Create Date: 2026-11-12 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "i10d7fe3c495"
down_revision = "h10d7fe3c494"
branch_labels = None
depends_on = None

_TABLE = "project_equipment_usage_logs"


def upgrade():
    if _TABLE in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("equipment_type", sa.String(length=20), nullable=False),
        sa.Column("equipment_id", sa.String(length=100), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("old_state", sa.String(length=10), nullable=False),
        sa.Column("new_state", sa.String(length=10), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_project_equipment_usage_logs_project_id", _TABLE, ["project_id"], unique=False)


def downgrade():
    if _TABLE not in sa.inspect(op.get_bind()).get_table_names():
        return
    op.drop_index("ix_project_equipment_usage_logs_project_id", table_name=_TABLE)
    op.drop_table(_TABLE)
