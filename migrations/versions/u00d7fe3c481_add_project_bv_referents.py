"""Add project_bv_referents association table.

Revision ID: u00d7fe3c481
Revises: t00d7fe3c480
Create Date: 2026-10-27 10:52:00
"""
from alembic import op
import sqlalchemy as sa

revision = "u00d7fe3c481"
down_revision = "t00d7fe3c480"
branch_labels = None
depends_on = None


def upgrade():
    # Vérifie si la table existe déjà pour idempotence
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if "project_bv_referents" not in tables:
        op.create_table(
            "project_bv_referents",
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if "project_bv_referents" in tables:
        op.drop_table("project_bv_referents")
