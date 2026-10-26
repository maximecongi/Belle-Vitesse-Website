"""Add numeric rules and immutable snapshots for measured checkpoints.

Revision ID: s00d7fe3c479
Revises: r00d7fe3c478
Create Date: 2026-10-26 16:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = "s00d7fe3c479"
down_revision = "r00d7fe3c478"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("checkpoint_definitions", sa.Column("minimum", sa.Numeric(18, 6), nullable=True))
    op.add_column("checkpoint_definitions", sa.Column("maximum", sa.Numeric(18, 6), nullable=True))
    op.add_column("checkpoint_definitions", sa.Column("goal", sa.Numeric(18, 6), nullable=True))
    op.add_column("checkpoint_definitions", sa.Column("tolerance", sa.Numeric(18, 6), nullable=True))
    op.add_column("inspection_checkpoints", sa.Column("config_snapshot", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("inspection_checkpoints", "config_snapshot")
    op.drop_column("checkpoint_definitions", "tolerance")
    op.drop_column("checkpoint_definitions", "goal")
    op.drop_column("checkpoint_definitions", "maximum")
    op.drop_column("checkpoint_definitions", "minimum")
