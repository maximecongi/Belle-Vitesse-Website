"""Techniciens BV multiples par projet (remplace le Machiniste BV unique).

Crée la table d'association project_bv_technicians, y reporte les valeurs de
projects.bv_grip_user_id, puis supprime cette colonne.

Revision ID: j10d7fe3c496
Revises: i10d7fe3c495
Create Date: 2026-11-12 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "j10d7fe3c496"
down_revision = "i10d7fe3c495"
branch_labels = None
depends_on = None

_TABLE = "project_bv_technicians"
_OLD_COL = "bv_grip_user_id"


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _TABLE not in inspector.get_table_names():
        op.create_table(
            _TABLE,
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        )

    columns = {c["name"] for c in inspector.get_columns("projects")}
    if _OLD_COL not in columns:
        return

    # Reprise des machinistes BV existants
    bind.execute(sa.text(
        f"INSERT INTO {_TABLE} (project_id, user_id) "
        f"SELECT p.id, p.{_OLD_COL} FROM projects p "
        f"WHERE p.{_OLD_COL} IS NOT NULL "
        f"AND NOT EXISTS (SELECT 1 FROM {_TABLE} t WHERE t.project_id = p.id AND t.user_id = p.{_OLD_COL})"
    ))

    fks = inspector.get_foreign_keys("projects")
    indexes = inspector.get_indexes("projects")
    with op.batch_alter_table("projects") as batch:
        for fk in fks:
            if fk.get("constrained_columns") == [_OLD_COL] and fk.get("name"):
                batch.drop_constraint(fk["name"], type_="foreignkey")
        for ix in indexes:
            if ix.get("column_names") == [_OLD_COL] and ix.get("name"):
                batch.drop_index(ix["name"])
        batch.drop_column(_OLD_COL)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("projects")}
    if _OLD_COL not in columns:
        with op.batch_alter_table("projects") as batch:
            batch.add_column(sa.Column(_OLD_COL, sa.Integer(), nullable=True))
            batch.create_foreign_key(f"fk_projects_{_OLD_COL}", "users", [_OLD_COL], ["id"], ondelete="SET NULL")
            batch.create_index(f"ix_projects_{_OLD_COL}", [_OLD_COL], unique=False)

    if _TABLE in inspector.get_table_names():
        # Un seul technicien conservable : le premier (plus petit ID utilisateur)
        bind.execute(sa.text(
            f"UPDATE projects SET {_OLD_COL} = "
            f"(SELECT MIN(t.user_id) FROM {_TABLE} t WHERE t.project_id = projects.id)"
        ))
        op.drop_table(_TABLE)
