"""migrate signature columns from mediumtext to varchar for file storage

Revision ID: j00d7fe3c470
Revises: i00d7fe3c469
Create Date: 2026-09-29 23:25:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'j00d7fe3c470'
down_revision = 'i00d7fe3c469'
branch_labels = None
depends_on = None


def upgrade():
    """Modifie le type des colonnes de signature pour stocker des chemins relatifs VARCHAR(255)."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    columns_to_alter = [
        ('pilot_waivers', 'signature_data'),
        ('production_waivers', 'signature_data'),
        ('incidents', 'bv_signature_data'),
        ('incidents', 'prod_signature_data'),
        ('pilot_waiver_signed_documents', 'signature'),
        ('production_waiver_signed_documents', 'signature'),
        ('checkout_signed_documents', 'signature'),
        ('checkin_signed_documents', 'signature'),
        ('incident_signed_documents', 'signature'),
        ('checkout_tokens', 'signature'),
        ('checkin_tokens', 'signature'),
        ('incident_tokens', 'signature'),
    ]

    for table_name, column_name in columns_to_alter:
        if table_name in tables:
            cols = [c['name'] for c in inspector.get_columns(table_name)]
            if column_name in cols:
                try:
                    with op.batch_alter_table(table_name) as batch_op:
                        batch_op.alter_column(
                            column_name,
                            existing_type=sa.Text(),
                            type_=sa.String(length=255),
                            nullable=True
                        )
                except Exception as err:
                    print(f"⚠️ Note: alter_column {table_name}.{column_name} : {err}")


def downgrade():
    """Restaure les colonnes en type Text."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    columns_to_alter = [
        ('pilot_waivers', 'signature_data'),
        ('production_waivers', 'signature_data'),
        ('incidents', 'bv_signature_data'),
        ('incidents', 'prod_signature_data'),
        ('pilot_waiver_signed_documents', 'signature'),
        ('production_waiver_signed_documents', 'signature'),
        ('checkout_signed_documents', 'signature'),
        ('checkin_signed_documents', 'signature'),
        ('incident_signed_documents', 'signature'),
        ('checkout_tokens', 'signature'),
        ('checkin_tokens', 'signature'),
        ('incident_tokens', 'signature'),
    ]

    for table_name, column_name in columns_to_alter:
        if table_name in tables:
            cols = [c['name'] for c in inspector.get_columns(table_name)]
            if column_name in cols:
                try:
                    with op.batch_alter_table(table_name) as batch_op:
                        batch_op.alter_column(
                            column_name,
                            existing_type=sa.String(length=255),
                            type_=sa.Text(),
                            nullable=True
                        )
                except Exception as err:
                    print(f"⚠️ Note: downgrade {table_name}.{column_name} : {err}")
