"""unify waivers tables into waivers, waiver_tokens, waiver_signed_documents (fresh start)

Revision ID: n00d7fe3c474
Revises: m00d7fe3c473
Create Date: 2026-10-03 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'n00d7fe3c474'
down_revision = 'm00d7fe3c473'
branch_labels = None
depends_on = None


def upgrade():
    """Crée les tables unifiées waivers, waiver_tokens et waiver_signed_documents, puis supprime les anciennes tables."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. Création de la table unifiée waivers si elle n'existe pas
    if 'waivers' not in existing_tables:
        op.create_table(
            'waivers',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('waiver_type', sa.String(length=20), nullable=False, server_default='pilot', index=True),
            sa.Column('waiver_id', sa.String(length=50), nullable=False, unique=True, index=True),

            sa.Column('project_name', sa.String(length=255), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='to_generate'),
            sa.Column('generated_at', sa.DateTime(), nullable=True),
            sa.Column('sent_at', sa.DateTime(), nullable=True),
            sa.Column('signed_at', sa.DateTime(), nullable=True),

            # Données pilote
            sa.Column('pilot_first_name', sa.String(length=100), nullable=True),
            sa.Column('pilot_last_name', sa.String(length=100), nullable=True),
            sa.Column('pilot_dob', sa.Date(), nullable=True),
            sa.Column('pilot_license_number', sa.String(length=100), nullable=True),
            sa.Column('pilot_address', sa.Text(), nullable=True),
            sa.Column('pilot_insurance_company', sa.String(length=255), nullable=True),
            sa.Column('pilot_insurance_policy', sa.String(length=255), nullable=True),
            sa.Column('pilot_license_path', sa.String(length=500), nullable=True),
            sa.Column('pilot_insurance_path', sa.String(length=500), nullable=True),
            sa.Column('pilot_identity_path', sa.String(length=500), nullable=True),

            # Données production
            sa.Column('production_name', sa.String(length=255), nullable=True),
            sa.Column('production_representative', sa.String(length=255), nullable=True),
            sa.Column('production_address', sa.Text(), nullable=True),
            sa.Column('production_siret', sa.String(length=100), nullable=True),
            sa.Column('production_vat', sa.String(length=100), nullable=True),
            sa.Column('production_insurance_company', sa.String(length=255), nullable=True),
            sa.Column('production_insurance_policy', sa.String(length=255), nullable=True),
            sa.Column('production_insurance_validity', sa.String(length=100), nullable=True),
            sa.Column('location_of_use', sa.Text(), nullable=True),
            sa.Column('production_insurance_path', sa.String(length=500), nullable=True),

            # Données tournage & snapshot extensible
            sa.Column('vehicles', sa.Text(), nullable=True),
            sa.Column('shooting_dates', sa.String(length=255), nullable=True),
            sa.Column('sign_data', sa.JSON(), nullable=True),

            # Signature & fichiers
            sa.Column('signature_data', sa.String(length=255), nullable=True),
            sa.Column('signed_pdf_path', sa.String(length=500), nullable=True),
            sa.Column('signer_ip', sa.String(length=45), nullable=True),

            # Suivi & soft delete
            sa.Column('webhook_triggered_at', sa.DateTime(), nullable=True),
            sa.Column('last_reminded_at', sa.DateTime(), nullable=True),
            sa.Column('reminder_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),

            sa.UniqueConstraint('project_id', 'waiver_type', name='uq_project_waiver_type'),
        )

    # 2. Création de la table unifiée waiver_tokens si elle n'existe pas
    if 'waiver_tokens' not in existing_tables:
        op.create_table(
            'waiver_tokens',
            sa.Column('token', sa.String(length=36), nullable=False, primary_key=True),
            sa.Column('waiver_id', sa.String(length=255), nullable=False, index=True),
            sa.Column('signature', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
        )

    # 3. Création de la table unifiée waiver_signed_documents si elle n'existe pas
    if 'waiver_signed_documents' not in existing_tables:
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

    # 4. Suppression des anciennes tables miroirs si elles existent (fresh start)
    legacy_tables = [
        'pilot_waiver_signed_documents',
        'production_waiver_signed_documents',
        'pilot_waiver_tokens',
        'production_waiver_tokens',
        'pilot_waivers',
        'production_waivers',
    ]
    for table_name in legacy_tables:
        if table_name in existing_tables:
            op.drop_table(table_name)


def downgrade():
    """Supprime les tables unifiées."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    for table_name in ['waiver_signed_documents', 'waiver_tokens', 'waivers']:
        if table_name in existing_tables:
            op.drop_table(table_name)
