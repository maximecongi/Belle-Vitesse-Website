"""Add deleted_at for soft delete

Revision ID: 600d7fe3c457
Revises: 500d7fe3c456
Create Date: 2026-06-02 15:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '600d7fe3c457'
down_revision = '500d7fe3c456'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    tables_to_add_column = [
        'projects',
        'checkout_vehicles',
        'checkin_vehicles',
        'pilot_waivers',
        'production_waivers'
    ]
    
    for table_name in tables_to_add_column:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        if 'deleted_at' not in columns:
            op.add_column(table_name, sa.Column('deleted_at', sa.DateTime(), nullable=True))


def downgrade():
    tables_to_add_column = [
        'projects',
        'checkout_vehicles',
        'checkin_vehicles',
        'pilot_waivers',
        'production_waivers'
    ]
    for table_name in tables_to_add_column:
        op.drop_column(table_name, 'deleted_at')
