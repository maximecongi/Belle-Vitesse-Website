"""Add BV team roles to projects (commercial, machiniste BV, opérateur remote head).

Revision ID: e10d7fe3c491
Revises: d10d7fe3c490
Create Date: 2026-11-11 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "e10d7fe3c491"
down_revision = "d10d7fe3c490"
branch_labels = None
depends_on = None

_COLUMNS = (
    "commercial_user_id",
    "bv_grip_user_id",
    "remote_head_operator_user_id",
)


def upgrade():
    inspector = sa.inspect(op.get_bind())
    existing = {c["name"] for c in inspector.get_columns("projects")}
    to_add = [col for col in _COLUMNS if col not in existing]
    if not to_add:
        return
    # Mode batch : compatible SQLite (ALTER de contraintes non supporté)
    with op.batch_alter_table("projects") as batch:
        for col in to_add:
            batch.add_column(sa.Column(col, sa.Integer(), nullable=True))
            batch.create_foreign_key(f"fk_projects_{col}", "users", [col], ["id"], ondelete="SET NULL")
            batch.create_index(f"ix_projects_{col}", [col], unique=False)


def downgrade():
    inspector = sa.inspect(op.get_bind())
    existing = {c["name"] for c in inspector.get_columns("projects")}
    to_drop = [col for col in _COLUMNS if col in existing]
    if not to_drop:
        return
    # Contraintes/index réellement présents (noms possiblement absents si table créée par create_all)
    fks = inspector.get_foreign_keys("projects")
    indexes = inspector.get_indexes("projects")
    with op.batch_alter_table("projects") as batch:
        for col in to_drop:
            for fk in fks:
                if fk.get("constrained_columns") == [col] and fk.get("name"):
                    batch.drop_constraint(fk["name"], type_="foreignkey")
            for ix in indexes:
                if ix.get("column_names") == [col] and ix.get("name"):
                    batch.drop_index(ix["name"])
            batch.drop_column(col)
