"""Baseline schema

Revision ID: 000000000000
Revises: 
Create Date: 2026-06-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from flask import current_app


# revision identifiers, used by Alembic.
revision = '000000000000'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Initialise l'ensemble des tables de base dans l'ordre topologique si elles n'existent pas encore."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    app_db = current_app.extensions['migrate'].db
    import models  # noqa: F401 - assure le chargement de tous les modèles dans app_db.metadata

    # Tables créées par des migrations ultérieures spécifiques
    later_tables = {"pre_quote_versions", "mcp_api_tokens", "mcp_audit_logs", "kdrive_objects"}

    for table in app_db.metadata.sorted_tables:
        if table.name not in existing_tables and table.name not in later_tables:
            table.create(bind=conn, checkfirst=True)
            existing_tables.add(table.name)


def downgrade():
    """Pour la baseline initiale, la rétrogradation est protégée."""
    pass
