"""Add BV team roles to projects (commercial, machiniste BV, opérateur remote head).

Revision ID: e10d7fe3c491
Revises: d10d7fe3c490
Create Date: 2026-11-11 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "e10d7fe3c491"
down_revision = "d10d7fe3c490"
branch_labels = None
depends_on = None

_COLUMNS = (
    "commercial_user_id",
    "bv_grip_user_id",
    "remote_head_operator_user_id",
)


def upgrade():
    inspector = sa.inspect(op.get_bind())
    existing = {c["name"] for c in inspector.get_columns("projects")}
    for col in _COLUMNS:
        if col in existing:
            continue
        op.add_column("projects", sa.Column(col, sa.Integer(), nullable=True))
        op.create_foreign_key(
            f"fk_projects_{col}", "projects", "users", [col], ["id"], ondelete="SET NULL"
        )
        op.create_index(f"ix_projects_{col}", "projects", [col], unique=False)


def downgrade():
    inspector = sa.inspect(op.get_bind())
    existing = {c["name"] for c in inspector.get_columns("projects")}
    for col in _COLUMNS:
        if col not in existing:
            continue
        op.drop_index(f"ix_projects_{col}", table_name="projects")
        op.drop_constraint(f"fk_projects_{col}", "projects", type_="foreignkey")
        op.drop_column("projects", col)
