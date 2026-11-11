"""Add user_pins (pages épinglées de l'ERP, par utilisateur).

Revision ID: d10d7fe3c490
Revises: c10d7fe3c489
Create Date: 2026-11-11 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "d10d7fe3c490"
down_revision = "c10d7fe3c489"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if "user_pins" in inspector.get_table_names():
        return
    op.create_table(
        "user_pins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_user_pins_user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("url", sa.String(512), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "url", name="uq_user_pins_user_url"),
    )
    op.create_index("ix_user_pins_user_id", "user_pins", ["user_id"], unique=False)


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if "user_pins" not in inspector.get_table_names():
        return
    op.drop_table("user_pins")
