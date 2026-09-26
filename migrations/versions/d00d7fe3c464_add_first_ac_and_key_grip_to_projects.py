"""Add first_ac_contact_id and key_grip_contact_id to projects

Revision ID: d00d7fe3c464
Revises: c00d7fe3c463
Create Date: 2026-08-28 00:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd00d7fe3c464'
down_revision = 'c00d7fe3c463'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Update projects table
    columns = [col['name'] for col in inspector.get_columns('projects')]
    
    if 'first_ac_contact_id' not in columns:
        op.add_column('projects', sa.Column(
            'first_ac_contact_id',
            sa.Integer(),
            nullable=True
        ))
        op.create_index(
            op.f('ix_projects_first_ac_contact_id'),
            'projects',
            ['first_ac_contact_id'],
            unique=False
        )
        op.create_foreign_key(
            'fk_projects_first_ac_contact_id_contacts',
            'projects',
            'contacts',
            ['first_ac_contact_id'],
            ['id']
        )

    if 'key_grip_contact_id' not in columns:
        op.add_column('projects', sa.Column(
            'key_grip_contact_id',
            sa.Integer(),
            nullable=True
        ))
        op.create_index(
            op.f('ix_projects_key_grip_contact_id'),
            'projects',
            ['key_grip_contact_id'],
            unique=False
        )
        op.create_foreign_key(
            'fk_projects_key_grip_contact_id_contacts',
            'projects',
            'contacts',
            ['key_grip_contact_id'],
            ['id']
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('projects')]

    if 'key_grip_contact_id' in columns:
        op.drop_constraint('fk_projects_key_grip_contact_id_contacts', 'projects', type_='foreignkey')
        op.drop_index(op.f('ix_projects_key_grip_contact_id'), table_name='projects')
        op.drop_column('projects', 'key_grip_contact_id')

    if 'first_ac_contact_id' in columns:
        op.drop_constraint('fk_projects_first_ac_contact_id_contacts', 'projects', type_='foreignkey')
        op.drop_index(op.f('ix_projects_first_ac_contact_id'), table_name='projects')
        op.drop_column('projects', 'first_ac_contact_id')
