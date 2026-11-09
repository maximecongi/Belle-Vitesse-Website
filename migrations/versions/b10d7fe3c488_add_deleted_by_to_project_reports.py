"""Add deleted_by_id to project_reports (restauration réservée à l'auteur-suppresseur ou au super admin).

Revision ID: b10d7fe3c488
Revises: a10d7fe3c487
Create Date: 2026-11-09 21:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "b10d7fe3c488"
down_revision = "a10d7fe3c487"
branch_labels = None
depends_on = None


def _columns():
    return [c["name"] for c in sa.inspect(op.get_bind()).get_columns("project_reports")]


def upgrade():
    if "deleted_by_id" not in _columns():
        with op.batch_alter_table("project_reports") as batch:
            batch.add_column(sa.Column("deleted_by_id", sa.Integer(), nullable=True))
            batch.create_foreign_key(
                "fk_project_reports_deleted_by_id_users", "users", ["deleted_by_id"], ["id"], ondelete="SET NULL"
            )


def downgrade():
    if "deleted_by_id" not in _columns():
        return
    # La contrainte peut être absente ou sans nom (table créée par db.create_all) : on ne supprime
    # que les contraintes nommées réellement présentes sur la colonne.
    fk_names = [
        fk["name"]
        for fk in sa.inspect(op.get_bind()).get_foreign_keys("project_reports")
        if fk.get("constrained_columns") == ["deleted_by_id"] and fk.get("name")
    ]
    with op.batch_alter_table("project_reports") as batch:
        for name in fk_names:
            batch.drop_constraint(name, type_="foreignkey")
        batch.drop_column("deleted_by_id")
