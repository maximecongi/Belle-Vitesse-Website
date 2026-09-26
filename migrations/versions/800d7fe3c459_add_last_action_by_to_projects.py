"""Add last_action_by_id to projects

Revision ID: 800d7fe3c459
Revises: 700d7fe3c458
Create Date: 2026-06-10 15:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '800d7fe3c459'
down_revision = '700d7fe3c458'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Update projects table
    columns = [col['name'] for col in inspector.get_columns('projects')]
    if 'last_action_by_id' not in columns:
        op.add_column('projects', sa.Column(
            'last_action_by_id', 
            sa.Integer(), 
            nullable=True
        ))
        
        # Create index
        op.create_index(
            op.f('ix_projects_last_action_by_id'), 
            'projects', 
            ['last_action_by_id'], 
            unique=False
        )
        
        # Create foreign key constraint
        op.create_foreign_key(
            'fk_projects_last_action_by_id_users',
            'projects',
            'users',
            ['last_action_by_id'],
            ['id']
        )


def downgrade():
    op.drop_constraint('fk_projects_last_action_by_id_users', 'projects', type_='foreignkey')
    op.drop_index(op.f('ix_projects_last_action_by_id'), table_name='projects')
    op.drop_column('projects', 'last_action_by_id')
