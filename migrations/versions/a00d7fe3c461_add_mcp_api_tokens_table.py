"""add mcp_api_tokens table

Revision ID: a00d7fe3c461
Revises: 900d7fe3c460
Create Date: 2026-08-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a00d7fe3c461'
down_revision = '900d7fe3c460'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'mcp_api_tokens' not in tables:
        op.create_table(
            'mcp_api_tokens',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('token_prefix', sa.String(length=30), nullable=False),
            sa.Column('token_hash', sa.String(length=64), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('last_used_at', sa.DateTime(), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_mcp_api_tokens_user_id', 'mcp_api_tokens', ['user_id'], unique=False)
        op.create_index('ix_mcp_api_tokens_token_hash', 'mcp_api_tokens', ['token_hash'], unique=True)
    else:
        op.alter_column('mcp_api_tokens', 'token_prefix', type_=sa.String(length=30), existing_nullable=False)


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'mcp_api_tokens' in tables:
        op.drop_table('mcp_api_tokens')
