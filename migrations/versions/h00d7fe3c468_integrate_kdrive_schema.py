"""Integrate kDrive schema into Alembic

Revision ID: h00d7fe3c468
Revises: g00d7fe3c467
Create Date: 2026-09-26 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h00d7fe3c468'
down_revision = 'g00d7fe3c467'
branch_labels = None
depends_on = None


def upgrade():
    """Ajoute de façon idempotente la table kdrive_objects et les colonnes kdrive sur projects."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. Table kdrive_objects
    if "kdrive_objects" not in tables:
        op.create_table(
            "kdrive_objects",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("kdrive_id", sa.BigInteger(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("type", sa.String(length=20), nullable=False),
            sa.Column("path", sa.String(length=500), nullable=False),
            sa.Column("parent_id", sa.BigInteger(), nullable=True),
            sa.Column("size", sa.BigInteger(), nullable=True),
            sa.Column("last_modified", sa.DateTime(), nullable=True),
            sa.Column("sync_status", sa.String(length=20), nullable=False, server_default="synced"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("kdrive_id"),
        )
        op.create_index("idx_kdrive_path", "kdrive_objects", ["path"])
        op.create_index("idx_kdrive_parent", "kdrive_objects", ["parent_id"])
        op.create_index("idx_kdrive_sync", "kdrive_objects", ["sync_status"])

    # 2. Colonnes kdrive sur projects
    if "projects" in tables:
        project_cols = [c["name"] for c in inspector.get_columns("projects")]
        if "kdrive_folder_id" not in project_cols:
            op.add_column("projects", sa.Column("kdrive_folder_id", sa.BigInteger(), nullable=True))
        if "kdrive_path" not in project_cols:
            op.add_column("projects", sa.Column("kdrive_path", sa.String(length=500), nullable=True))
        if "kdrive_sync_status" not in project_cols:
            op.add_column("projects", sa.Column("kdrive_sync_status", sa.String(length=20), nullable=False, server_default="pending"))
        if "kdrive_last_error" not in project_cols:
            op.add_column("projects", sa.Column("kdrive_last_error", sa.Text(), nullable=True))
        if "kdrive_last_cancel_id" not in project_cols:
            op.add_column("projects", sa.Column("kdrive_last_cancel_id", sa.String(length=100), nullable=True))


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "projects" in tables:
        project_cols = [c["name"] for c in inspector.get_columns("projects")]
        for col in ["kdrive_last_cancel_id", "kdrive_last_error", "kdrive_sync_status", "kdrive_path", "kdrive_folder_id"]:
            if col in project_cols:
                op.drop_column("projects", col)

    if "kdrive_objects" in tables:
        op.drop_table("kdrive_objects")
