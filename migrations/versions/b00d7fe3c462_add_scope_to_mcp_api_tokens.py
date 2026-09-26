"""add scope column to mcp_api_tokens table

Revision ID: b00d7fe3c462
Revises: a00d7fe3c461
Create Date: 2026-08-07 18:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b00d7fe3c462'
down_revision = 'a00d7fe3c461'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'mcp_api_tokens' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('mcp_api_tokens')]
        if 'scope' not in columns:
            op.add_column(
                'mcp_api_tokens',
                sa.Column('scope', sa.String(length=20), nullable=False, server_default='read_only')
            )
        try:
            op.alter_column('mcp_api_tokens', 'token_prefix', type_=sa.String(length=30), existing_nullable=False)
        except Exception:
            pass


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'mcp_api_tokens' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('mcp_api_tokens')]
        if 'scope' in columns:
            op.drop_column('mcp_api_tokens', 'scope')
