"""add signature_events table

Revision ID: p00d7fe3c476
Revises: o00d7fe3c475
Create Date: 2026-10-25 18:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'p00d7fe3c476'
down_revision = 'o00d7fe3c475'
branch_labels = None
depends_on = None


def upgrade():
    """Crée la table d'audit immuable signature_events."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'signature_events' not in existing_tables:
        op.create_table(
            'signature_events',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('document_id', sa.String(length=100), nullable=False),
            sa.Column('mode', sa.String(length=30), nullable=False),
            sa.Column('event_type', sa.String(length=50), nullable=False),
            sa.Column('ip', sa.String(length=45), nullable=True),
            sa.Column('user_agent', sa.String(length=255), nullable=True),
            sa.Column('details', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_signature_events_document_id'), 'signature_events', ['document_id'], unique=False)
        op.create_index(op.f('ix_signature_events_mode'), 'signature_events', ['mode'], unique=False)
        op.create_index(op.f('ix_signature_events_event_type'), 'signature_events', ['event_type'], unique=False)


def downgrade():
    """Supprime la table signature_events."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'signature_events' in existing_tables:
        op.drop_index(op.f('ix_signature_events_event_type'), table_name='signature_events')
        op.drop_index(op.f('ix_signature_events_mode'), table_name='signature_events')
        op.drop_index(op.f('ix_signature_events_document_id'), table_name='signature_events')
        op.drop_table('signature_events')
