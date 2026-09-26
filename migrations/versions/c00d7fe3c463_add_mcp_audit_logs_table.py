"""add mcp_audit_logs table

Revision ID: c00d7fe3c463
Revises: b00d7fe3c462
Create Date: 2026-08-08 10:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c00d7fe3c463'
down_revision = 'b00d7fe3c462'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if 'mcp_audit_logs' not in inspector.get_table_names():
        op.create_table(
            'mcp_audit_logs',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('token_id', sa.Integer(), sa.ForeignKey('mcp_api_tokens.id', ondelete='SET NULL'), nullable=True),
            sa.Column('tool_name', sa.String(length=100), nullable=False),
            sa.Column('arguments_json', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=30), nullable=False, server_default='success'),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('ip_address', sa.String(length=45), nullable=True),
            sa.Column('execution_time_ms', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        )
        op.create_index('ix_mcp_audit_logs_user_id', 'mcp_audit_logs', ['user_id'], unique=False)
        op.create_index('ix_mcp_audit_logs_token_id', 'mcp_audit_logs', ['token_id'], unique=False)
        op.create_index('ix_mcp_audit_logs_tool_name', 'mcp_audit_logs', ['tool_name'], unique=False)
        op.create_index('ix_mcp_audit_logs_created_at', 'mcp_audit_logs', ['created_at'], unique=False)


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if 'mcp_audit_logs' in inspector.get_table_names():
        op.drop_table('mcp_audit_logs')
