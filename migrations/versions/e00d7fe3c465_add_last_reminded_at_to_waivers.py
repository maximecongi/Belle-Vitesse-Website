"""Add last_reminded_at and reminder_count to waivers

Revision ID: e00d7fe3c465
Revises: d00d7fe3c464
Create Date: 2026-09-06 22:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e00d7fe3c465'
down_revision = 'd00d7fe3c464'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # 1. Update pilot_waivers table
    pilot_cols = [col['name'] for col in inspector.get_columns('pilot_waivers')]
    if 'last_reminded_at' not in pilot_cols:
        op.add_column('pilot_waivers', sa.Column('last_reminded_at', sa.DateTime(), nullable=True))
    if 'reminder_count' not in pilot_cols:
        op.add_column('pilot_waivers', sa.Column('reminder_count', sa.Integer(), server_default='0', nullable=False))

    # 2. Update production_waivers table
    prod_cols = [col['name'] for col in inspector.get_columns('production_waivers')]
    if 'last_reminded_at' not in prod_cols:
        op.add_column('production_waivers', sa.Column('last_reminded_at', sa.DateTime(), nullable=True))
    if 'reminder_count' not in prod_cols:
        op.add_column('production_waivers', sa.Column('reminder_count', sa.Integer(), server_default='0', nullable=False))


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    pilot_cols = [col['name'] for col in inspector.get_columns('pilot_waivers')]
    if 'reminder_count' in pilot_cols:
        op.drop_column('pilot_waivers', 'reminder_count')
    if 'last_reminded_at' in pilot_cols:
        op.drop_column('pilot_waivers', 'last_reminded_at')

    prod_cols = [col['name'] for col in inspector.get_columns('production_waivers')]
    if 'reminder_count' in prod_cols:
        op.drop_column('production_waivers', 'reminder_count')
    if 'last_reminded_at' in prod_cols:
        op.drop_column('production_waivers', 'last_reminded_at')
