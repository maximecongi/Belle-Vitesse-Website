"""Change app_settings value column from varchar(500) to text.

Revision ID: w00d7fe3c483
Revises: v00d7fe3c482
Create Date: 2026-11-03 14:58:00
"""
from alembic import op
import sqlalchemy as sa

revision = "w00d7fe3c483"
down_revision = "v00d7fe3c482"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("app_settings", schema=None) as batch_op:
        batch_op.alter_column(
            "value",
            existing_type=sa.String(length=500),
            type_=sa.Text(),
            existing_nullable=False,
        )


def downgrade():
    with op.batch_alter_table("app_settings", schema=None) as batch_op:
        batch_op.alter_column(
            "value",
            existing_type=sa.Text(),
            type_=sa.String(length=500),
            existing_nullable=False,
        )

