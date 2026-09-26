"""Add title to project_reports

Revision ID: f00d7fe3c466
Revises: e00d7fe3c465
Create Date: 2026-09-12 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f00d7fe3c466'
down_revision = 'e00d7fe3c465'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    report_cols = [col['name'] for col in inspector.get_columns('project_reports')]
    if 'title' not in report_cols:
        op.add_column('project_reports', sa.Column('title', sa.String(255), nullable=True))


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    report_cols = [col['name'] for col in inspector.get_columns('project_reports')]
    if 'title' in report_cols:
        op.drop_column('project_reports', 'title')
