"""Sync models

Revision ID: 500d7fe3c456
Revises: 
Create Date: 2026-06-02 15:19:38.904255

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '500d7fe3c456'
down_revision = '000000000000'
branch_labels = None
depends_on = None


def upgrade():
    # Check if table exists before creating (to handle dev vs prod environments)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'pre_quotes' in tables and 'pre_quote_versions' not in tables:
        op.create_table(
            'pre_quote_versions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('pre_quote_id', sa.Integer(), nullable=False),
            sa.Column('version_number', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('prestations', sa.JSON(), nullable=False),
            sa.Column('total_ht', sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column('total_ttc', sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column('insurance_rate', sa.Numeric(precision=5, scale=2), nullable=True),
            sa.Column('insurance_amount', sa.Numeric(precision=10, scale=2), nullable=True),
            sa.Column('tva_rate', sa.Numeric(precision=5, scale=2), nullable=True),
            sa.Column('tva_amount', sa.Numeric(precision=10, scale=2), nullable=True),
            sa.Column('pdf_path', sa.String(length=500), nullable=True),
            sa.Column('version_note', sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(['pre_quote_id'], ['pre_quotes.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )


def downgrade():
    op.drop_table('pre_quote_versions')
