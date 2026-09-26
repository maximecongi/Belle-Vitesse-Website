"""Add insurance_based_on_undiscounted to pre_quotes and pre_quote_versions

Revision ID: 700d7fe3c458
Revises: 600d7fe3c457
Create Date: 2026-06-06 16:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '700d7fe3c458'
down_revision = '600d7fe3c457'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # Update pre_quotes table
    if 'pre_quotes' in tables:
        columns_pq = [col['name'] for col in inspector.get_columns('pre_quotes')]
        if 'insurance_based_on_undiscounted' not in columns_pq:
            op.add_column('pre_quotes', sa.Column(
                'insurance_based_on_undiscounted', 
                sa.Boolean(), 
                nullable=False, 
                server_default=sa.text('0')
            ))

    # Update pre_quote_versions table
    if 'pre_quote_versions' in tables:
        columns_pqv = [col['name'] for col in inspector.get_columns('pre_quote_versions')]
        if 'insurance_based_on_undiscounted' not in columns_pqv:
            op.add_column('pre_quote_versions', sa.Column(
                'insurance_based_on_undiscounted', 
                sa.Boolean(), 
                nullable=False, 
                server_default=sa.text('0')
            ))


def downgrade():
    op.drop_column('pre_quotes', 'insurance_based_on_undiscounted')
    op.drop_column('pre_quote_versions', 'insurance_based_on_undiscounted')
