"""change sql query logs index

Revision ID: 900d7fe3c460
Revises: 800d7fe3c459
Create Date: 2026-07-02 09:25:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '900d7fe3c460'
down_revision = '800d7fe3c459'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Check if index exists on sql_query_logs before dropping
    indexes = [idx['name'] for idx in inspector.get_indexes('sql_query_logs')]
    
    if 'idx_user_ts' in indexes:
        op.drop_index('idx_user_ts', table_name='sql_query_logs')
        
    if 'idx_timestamp_user' not in indexes:
        op.create_index(
            'idx_timestamp_user',
            'sql_query_logs',
            ['timestamp', 'user'],
            unique=False
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    indexes = [idx['name'] for idx in inspector.get_indexes('sql_query_logs')]
    
    if 'idx_timestamp_user' in indexes:
        op.drop_index('idx_timestamp_user', table_name='sql_query_logs')
        
    if 'idx_user_ts' not in indexes:
        op.create_index(
            'idx_user_ts',
            'sql_query_logs',
            ['user', 'timestamp'],
            unique=False
        )
