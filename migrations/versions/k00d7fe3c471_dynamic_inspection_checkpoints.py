"""migrate hardcoded inspection checkpoint columns to dynamic inspection_checkpoints table (fresh start)

Revision ID: k00d7fe3c471
Revises: j00d7fe3c470
Create Date: 2026-10-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'k00d7fe3c471'
down_revision = 'j00d7fe3c470'
branch_labels = None
depends_on = None

LEGACY_COLUMNS = [
    'tire_status',
    'brake_status',
    'exterior_lighting_status',
    'horn_status',
    'gearbox_status',
    'engine_assistance_status',
    'driving_test_status',
    'wheel_tightness_status',
    'chain_tension_status',
    'roll_bar_tightness_status',
    'seat_plate_tightness_status',
    'seat_belt_status',
    'passenger_helmets_status',
    'pilot_protections_status',
    'communication_system_status',
    'accessories_case_status',
]


def upgrade():
    """Crée la table d'association inspection_checkpoints et purge les 16 colonnes en dur (fresh start)."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. Création de la table inspection_checkpoints si elle n'existe pas
    if 'inspection_checkpoints' not in existing_tables:
        op.create_table(
            'inspection_checkpoints',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('checkout_id', sa.Integer(), sa.ForeignKey('checkout_vehicles.id', ondelete='CASCADE'), nullable=True, index=True),
            sa.Column('checkin_id', sa.Integer(), sa.ForeignKey('checkin_vehicles.id', ondelete='CASCADE'), nullable=True, index=True),
            sa.Column('checkpoint_key', sa.String(length=100), nullable=False, index=True),
            sa.Column('checkpoint_id', sa.Integer(), sa.ForeignKey('checkpoint_definitions.id', ondelete='SET NULL'), nullable=True),
            sa.Column('status', sa.String(length=50), nullable=True),
            sa.Column('value', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.UniqueConstraint('checkout_id', 'checkpoint_key', name='uq_checkout_checkpoint'),
            sa.UniqueConstraint('checkin_id', 'checkpoint_key', name='uq_checkin_checkpoint'),
        )

    # 2. Suppression directe des 16 colonnes obsolètes de checkout_vehicles
    if 'checkout_vehicles' in existing_tables:
        co_cols = {c['name'] for c in inspector.get_columns('checkout_vehicles')}
        cols_to_drop = [c for c in LEGACY_COLUMNS if c in co_cols]
        if cols_to_drop:
            with op.batch_alter_table('checkout_vehicles') as batch_op:
                for col_name in cols_to_drop:
                    batch_op.drop_column(col_name)

    # 3. Suppression directe des 16 colonnes obsolètes de checkin_vehicles
    if 'checkin_vehicles' in existing_tables:
        ci_cols = {c['name'] for c in inspector.get_columns('checkin_vehicles')}
        cols_to_drop = [c for c in LEGACY_COLUMNS if c in ci_cols]
        if cols_to_drop:
            with op.batch_alter_table('checkin_vehicles') as batch_op:
                for col_name in cols_to_drop:
                    batch_op.drop_column(col_name)


def downgrade():
    """Restaure les 16 colonnes statiques et supprime inspection_checkpoints."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'checkout_vehicles' in existing_tables:
        co_cols = {c['name'] for c in inspector.get_columns('checkout_vehicles')}
        with op.batch_alter_table('checkout_vehicles') as batch_op:
            for col_name in LEGACY_COLUMNS:
                if col_name not in co_cols:
                    batch_op.add_column(sa.Column(col_name, sa.String(length=50), nullable=True))

    if 'checkin_vehicles' in existing_tables:
        ci_cols = {c['name'] for c in inspector.get_columns('checkin_vehicles')}
        with op.batch_alter_table('checkin_vehicles') as batch_op:
            for col_name in LEGACY_COLUMNS:
                if col_name not in ci_cols:
                    batch_op.add_column(sa.Column(col_name, sa.String(length=50), nullable=True))

    if 'inspection_checkpoints' in existing_tables:
        op.drop_table('inspection_checkpoints')
