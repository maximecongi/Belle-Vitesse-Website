"""Add indexes to projects and incidents

Revision ID: g00d7fe3c467
Revises: f00d7fe3c466
Create Date: 2026-09-21 00:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g00d7fe3c467'
down_revision = 'f00d7fe3c466'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # 1. Index sur projects
    existing_project_indexes = [idx['name'] for idx in inspector.get_indexes('projects')]
    if 'ix_projects_departure_date' not in existing_project_indexes:
        op.create_index('ix_projects_departure_date', 'projects', ['departure_date'])
    if 'ix_projects_shoot_start_date' not in existing_project_indexes:
        op.create_index('ix_projects_shoot_start_date', 'projects', ['shoot_start_date'])

    # 2. Index sur incidents
    existing_incident_indexes = [idx['name'] for idx in inspector.get_indexes('incidents')]
    if 'ix_incidents_incident_date' not in existing_incident_indexes:
        op.create_index('ix_incidents_incident_date', 'incidents', ['incident_date'])
    if 'ix_incidents_status' not in existing_incident_indexes:
        op.create_index('ix_incidents_status', 'incidents', ['status'])


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    existing_project_indexes = [idx['name'] for idx in inspector.get_indexes('projects')]
    if 'ix_projects_departure_date' in existing_project_indexes:
        op.drop_index('ix_projects_departure_date', table_name='projects')
    if 'ix_projects_shoot_start_date' in existing_project_indexes:
        op.drop_index('ix_projects_shoot_start_date', table_name='projects')

    existing_incident_indexes = [idx['name'] for idx in inspector.get_indexes('incidents')]
    if 'ix_incidents_incident_date' in existing_incident_indexes:
        op.drop_index('ix_incidents_incident_date', table_name='incidents')
    if 'ix_incidents_status' in existing_incident_indexes:
        op.drop_index('ix_incidents_status', table_name='incidents')
