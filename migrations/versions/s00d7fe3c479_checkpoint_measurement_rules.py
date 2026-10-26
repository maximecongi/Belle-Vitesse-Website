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
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "checkpoint_definitions" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("checkpoint_definitions")}
        for col_name in ("minimum", "maximum", "goal", "tolerance"):
            if col_name not in existing_cols:
                op.add_column("checkpoint_definitions", sa.Column(col_name, sa.Numeric(18, 6), nullable=True))

    if "inspection_checkpoints" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("inspection_checkpoints")}
        if "config_snapshot" not in existing_cols:
            op.add_column("inspection_checkpoints", sa.Column("config_snapshot", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("inspection_checkpoints", "config_snapshot")
    op.drop_column("checkpoint_definitions", "tolerance")
    op.drop_column("checkpoint_definitions", "goal")
    op.drop_column("checkpoint_definitions", "maximum")
    op.drop_column("checkpoint_definitions", "minimum")
