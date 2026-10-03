"""add date_mode, is_immobilized_between and shoot_dates to projects

Revision ID: l00d7fe3c472
Revises: k00d7fe3c471
Create Date: 2026-10-03 13:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'l00d7fe3c472'
down_revision = 'k00d7fe3c471'
branch_labels = None
depends_on = None


def upgrade():
    """Ajoute les colonnes de dates ponctuelles et d'immobilisation à la table projects."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'projects' in existing_tables:
        existing_cols = {c['name'] for c in inspector.get_columns('projects')}
        with op.batch_alter_table('projects') as batch_op:
            if 'date_mode' not in existing_cols:
                batch_op.add_column(
                    sa.Column('date_mode', sa.String(length=20), nullable=False, server_default='continuous')
                )
            if 'is_immobilized_between' not in existing_cols:
                batch_op.add_column(
                    sa.Column('is_immobilized_between', sa.Boolean(), nullable=False, server_default=sa.true())
                )
            if 'shoot_dates' not in existing_cols:
                batch_op.add_column(
                    sa.Column('shoot_dates', sa.JSON(), nullable=True)
                )


def downgrade():
    """Supprime les colonnes ajoutées pour les dates ponctuelles."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'projects' in existing_tables:
        existing_cols = {c['name'] for c in inspector.get_columns('projects')}
        with op.batch_alter_table('projects') as batch_op:
            if 'shoot_dates' in existing_cols:
                batch_op.drop_column('shoot_dates')
            if 'is_immobilized_between' in existing_cols:
                batch_op.drop_column('is_immobilized_between')
            if 'date_mode' in existing_cols:
                batch_op.drop_column('date_mode')
