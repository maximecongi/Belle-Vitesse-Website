"""add event_hash and previous_event_hash to signature_events

Revision ID: q00d7fe3c477
Revises: p00d7fe3c476
Create Date: 2026-10-26 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'q00d7fe3c477'
down_revision = 'p00d7fe3c476'
branch_labels = None
depends_on = None


def upgrade():
    """Ajoute les colonnes event_hash et previous_event_hash à signature_events."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'signature_events' in existing_tables:
        existing_cols = {c['name'] for c in inspector.get_columns('signature_events')}
        if 'previous_event_hash' not in existing_cols:
            op.add_column(
                'signature_events',
                sa.Column('previous_event_hash', sa.String(length=64), nullable=True)
            )
        if 'event_hash' not in existing_cols:
            op.add_column(
                'signature_events',
                sa.Column('event_hash', sa.String(length=64), nullable=True)
            )


def downgrade():
    """Supprime les colonnes de chaînage cryptographique."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'signature_events' in existing_tables:
        existing_cols = {c['name'] for c in inspector.get_columns('signature_events')}
        if 'event_hash' in existing_cols:
            op.drop_column('signature_events', 'event_hash')
        if 'previous_event_hash' in existing_cols:
            op.drop_column('signature_events', 'previous_event_hash')
