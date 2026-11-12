"""Opérateur Remote Head : rattaché à un contact (contacts) au lieu d'un utilisateur BV (users).

Remplace projects.remote_head_operator_user_id (FK users) par
projects.remote_head_operator_contact_id (FK contacts). Les affectations existantes
(utilisateurs) ne peuvent pas être converties en contacts et sont abandonnées.

Revision ID: g10d7fe3c493
Revises: f10d7fe3c492
Create Date: 2026-11-11 18:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "g10d7fe3c493"
down_revision = "f10d7fe3c492"
branch_labels = None
depends_on = None

_OLD = "remote_head_operator_user_id"
_NEW = "remote_head_operator_contact_id"


def _columns():
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("projects")}


def _swap(add_col, add_target, drop_col):
    """Ajoute add_col (FK vers add_target) et supprime drop_col (mode batch : compatible SQLite)."""
    existing = _columns()
    with op.batch_alter_table("projects") as batch:
        if add_col not in existing:
            batch.add_column(sa.Column(add_col, sa.Integer(), nullable=True))
            batch.create_foreign_key(
                f"fk_projects_{add_col}", add_target, [add_col], ["id"], ondelete="SET NULL"
            )
            batch.create_index(f"ix_projects_{add_col}", [add_col], unique=False)
        if drop_col in existing:
            # Contraintes/index réellement présents (noms possiblement absents si table créée par create_all)
            inspector = sa.inspect(op.get_bind())
            for fk in inspector.get_foreign_keys("projects"):
                if fk.get("constrained_columns") == [drop_col] and fk.get("name"):
                    batch.drop_constraint(fk["name"], type_="foreignkey")
            for ix in inspector.get_indexes("projects"):
                if ix.get("column_names") == [drop_col] and ix.get("name"):
                    batch.drop_index(ix["name"])
            batch.drop_column(drop_col)


def upgrade():
    _swap(_NEW, "contacts", _OLD)


def downgrade():
    _swap(_OLD, "users", _NEW)
