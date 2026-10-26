"""Limit measured checkpoint rules to one decimal place.

Revision ID: t00d7fe3c480
Revises: s00d7fe3c479
Create Date: 2026-10-26 17:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = "t00d7fe3c480"
down_revision = "s00d7fe3c479"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("checkpoint_definitions") as batch_op:
        for column in ("minimum", "maximum", "goal", "tolerance"):
            batch_op.alter_column(
                column,
                existing_type=sa.Numeric(18, 6),
                type_=sa.Numeric(18, 1),
                existing_nullable=True,
            )


def downgrade():
    with op.batch_alter_table("checkpoint_definitions") as batch_op:
        for column in ("minimum", "maximum", "goal", "tolerance"):
            batch_op.alter_column(
                column,
                existing_type=sa.Numeric(18, 1),
                type_=sa.Numeric(18, 6),
                existing_nullable=True,
            )
