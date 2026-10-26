"""versioned waiver signed documents with composite primary key (waiver_id, version)

Revision ID: r00d7fe3c478
Revises: q00d7fe3c477
Create Date: 2026-10-26 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'r00d7fe3c478'
down_revision = 'q00d7fe3c477'
branch_labels = None
depends_on = None


def upgrade():
    """Ajoute les colonnes version et parent_hash et établit la clé primaire composite (waiver_id, version)."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'waiver_signed_documents' in existing_tables:
        pk_info = inspector.get_pk_constraint('waiver_signed_documents')
        pk_cols = set(pk_info.get('constrained_columns') or [])
        if pk_cols != {'waiver_id', 'version'}:
            existing_cols = {c['name'] for c in inspector.get_columns('waiver_signed_documents')}
            has_version = 'version' in existing_cols
            has_parent_hash = 'parent_hash' in existing_cols

            # Recréation propre pour garantir la contrainte de clé primaire composite (waiver_id, version)
            op.rename_table('waiver_signed_documents', '_old_waiver_signed_documents')
            op.create_table(
                'waiver_signed_documents',
                sa.Column('waiver_id', sa.String(length=50), nullable=False),
                sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
                sa.Column('parent_hash', sa.String(length=255), nullable=True),
                sa.Column('hash', sa.String(length=255), nullable=False),
                sa.Column('pdf_file_hash', sa.String(length=64), nullable=True),
                sa.Column('data_snapshot', sa.JSON(), nullable=False),
                sa.Column('signature', sa.String(length=255), nullable=True),
                sa.Column('pdf_url', sa.Text(), nullable=True),
                sa.Column('signed_at', sa.DateTime(), nullable=True),
                sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.current_timestamp()),
                sa.PrimaryKeyConstraint('waiver_id', 'version', name='pk_waiver_signed_documents')
            )

            # Copier les données existantes en préservant explicitement toutes les lignes sans perte
            col_version_src = 'version' if has_version else '1 AS version'
            col_parent_hash_src = 'parent_hash' if has_parent_hash else 'NULL AS parent_hash'

            conn.execute(sa.text(f"""
                INSERT INTO waiver_signed_documents (
                    waiver_id, version, parent_hash, hash, pdf_file_hash, data_snapshot, signature, pdf_url, signed_at, created_at
                )
                SELECT waiver_id, {col_version_src}, {col_parent_hash_src}, hash, pdf_file_hash, data_snapshot, signature, pdf_url, signed_at, created_at
                FROM _old_waiver_signed_documents
            """))

            op.drop_table('_old_waiver_signed_documents')


def downgrade():
    """Supprime les colonnes de versionnement et rétablit la clé primaire waiver_id seule."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'waiver_signed_documents' in existing_tables:
        existing_cols = {c['name'] for c in inspector.get_columns('waiver_signed_documents')}
        if 'version' in existing_cols:
            # Vérifier qu'aucune version > 1 n'existe pour ne pas perdre silencieusement des données
            v2_count = conn.execute(sa.text("SELECT COUNT(*) FROM waiver_signed_documents WHERE version > 1")).scalar()
            if v2_count and v2_count > 0:
                raise RuntimeError(
                    f"Impossible de rétrograder la migration : {v2_count} document(s) avec version > 1 existent en base de données. "
                    "Le downgrade entraînerait une perte de données irréversible."
                )

            op.rename_table('waiver_signed_documents', '_old_waiver_signed_documents')
            op.create_table(
                'waiver_signed_documents',
                sa.Column('waiver_id', sa.String(length=50), nullable=False, primary_key=True),
                sa.Column('hash', sa.String(length=255), nullable=False),
                sa.Column('pdf_file_hash', sa.String(length=64), nullable=True),
                sa.Column('data_snapshot', sa.JSON(), nullable=False),
                sa.Column('signature', sa.String(length=255), nullable=True),
                sa.Column('pdf_url', sa.Text(), nullable=True),
                sa.Column('signed_at', sa.DateTime(), nullable=True),
                sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.current_timestamp()),
            )

            conn.execute(sa.text("""
                INSERT INTO waiver_signed_documents (
                    waiver_id, hash, pdf_file_hash, data_snapshot, signature, pdf_url, signed_at, created_at
                )
                SELECT waiver_id, hash, pdf_file_hash, data_snapshot, signature, pdf_url, signed_at, created_at
                FROM _old_waiver_signed_documents
            """))

            op.drop_table('_old_waiver_signed_documents')
