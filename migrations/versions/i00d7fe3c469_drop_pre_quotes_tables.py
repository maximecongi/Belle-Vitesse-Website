"""drop pre_quotes and pre_quote_versions tables

Revision ID: i00d7fe3c469
Revises: h00d7fe3c468
Create Date: 2026-09-26 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'i00d7fe3c469'
down_revision = 'h00d7fe3c468'
branch_labels = None
depends_on = None


def upgrade():
    """Supprime définitivement et de façon ordonnée les tables obsolètes pre_quote_versions et pre_quotes."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. Supprimer d'abord la table fille (contraintes clés étrangères)
    if 'pre_quote_versions' in tables:
        op.drop_table('pre_quote_versions')

    # 2. Supprimer la table parente
    if 'pre_quotes' in tables:
        op.drop_table('pre_quotes')


def downgrade():
    """Rétrogradation protégée (les pré-devis étant décommissionnés)."""
    pass
