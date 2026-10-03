"""add inter_shoot_statuses to projects

Revision ID: m00d7fe3c473
Revises: l00d7fe3c472
Create Date: 2026-10-03 13:56:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'm00d7fe3c473'
down_revision = 'l00d7fe3c472'
branch_labels = None
depends_on = None


def upgrade():
    """Ajoute la colonne inter_shoot_statuses à la table projects."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'projects' in existing_tables:
        existing_cols = {c['name'] for c in inspector.get_columns('projects')}
        with op.batch_alter_table('projects') as batch_op:
            if 'inter_shoot_statuses' not in existing_cols:
                batch_op.add_column(
                    sa.Column('inter_shoot_statuses', sa.JSON(), nullable=True)
                )


def downgrade():
    """Supprime la colonne inter_shoot_statuses."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'projects' in existing_tables:
        existing_cols = {c['name'] for c in inspector.get_columns('projects')}
        with op.batch_alter_table('projects') as batch_op:
            if 'inter_shoot_statuses' in existing_cols:
                batch_op.drop_column('inter_shoot_statuses')
