"""add bvsr fields to waivers and drop uq_project_waiver_type

Revision ID: o00d7fe3c475
Revises: n00d7fe3c474
Create Date: 2026-10-18 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'o00d7fe3c475'
down_revision = 'n00d7fe3c474'
branch_labels = None
depends_on = None


def upgrade():
    """Ajoute les champs requis pour le protocole BVSR et supprime la contrainte unique sur type de décharge."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'waivers' not in existing_tables:
        return

    existing_columns = {c['name'] for c in inspector.get_columns('waivers')}

    columns_to_add = [
        ('signer_role', sa.Column('signer_role', sa.String(length=50), nullable=True)),
        ('signer_role_custom', sa.Column('signer_role_custom', sa.String(length=100), nullable=True)),
        ('signer_first_name', sa.Column('signer_first_name', sa.String(length=100), nullable=True)),
        ('signer_last_name', sa.Column('signer_last_name', sa.String(length=100), nullable=True)),
        ('signer_email', sa.Column('signer_email', sa.String(length=120), nullable=True)),
        ('signer_phone', sa.Column('signer_phone', sa.String(length=50), nullable=True)),
        ('signer_company', sa.Column('signer_company', sa.String(length=255), nullable=True)),
        ('safety_technicians', sa.Column('safety_technicians', sa.Text(), nullable=True)),
        ('helmets_inventory', sa.Column('helmets_inventory', sa.JSON(), nullable=True)),
        ('custom_rules_snapshot', sa.Column('custom_rules_snapshot', sa.JSON(), nullable=True)),
        ('bv_signature_data', sa.Column('bv_signature_data', sa.String(length=255), nullable=True)),
        ('bv_signed_at', sa.Column('bv_signed_at', sa.DateTime(), nullable=True)),
        ('bv_signer_name', sa.Column('bv_signer_name', sa.String(length=100), nullable=True)),
    ]

    with op.batch_alter_table('waivers', schema=None) as batch_op:
        for col_name, col_obj in columns_to_add:
            if col_name not in existing_columns:
                batch_op.add_column(col_obj)

        # Suppression de la contrainte unique (project_id, waiver_type) pour permettre plusieurs BVSR par projet
        try:
            uqs = inspector.get_unique_constraints('waivers')
            uq_names = {u['name'] for u in uqs if u.get('name')}
            if 'uq_project_waiver_type' in uq_names:
                batch_op.drop_constraint('uq_project_waiver_type', type_='unique')
        except Exception:
            pass


def downgrade():
    """Supprime les champs ajoutés pour BVSR."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'waivers' not in existing_tables:
        return

    existing_columns = {c['name'] for c in inspector.get_columns('waivers')}
    columns_to_drop = [
        'signer_role', 'signer_role_custom', 'signer_first_name', 'signer_last_name',
        'signer_email', 'signer_phone', 'signer_company', 'safety_technicians',
        'helmets_inventory', 'custom_rules_snapshot', 'bv_signature_data',
        'bv_signed_at', 'bv_signer_name'
    ]

    with op.batch_alter_table('waivers', schema=None) as batch_op:
        for col_name in columns_to_drop:
            if col_name in existing_columns:
                batch_op.drop_column(col_name)
