"""Add fixed identification color to vehicles and heads (attribution initiale dans l'ordre du catalogue).

Revision ID: h10d7fe3c494
Revises: g10d7fe3c493
Create Date: 2026-11-11 18:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "h10d7fe3c494"
down_revision = "g10d7fe3c493"
branch_labels = None
depends_on = None

_TABLES = ("vehicles", "heads")

# Copie figée de la palette (services/admin/equipment_colors.py) au moment de la migration
# (coloris du gaffer Cinéboutique)
_PALETTE = ["red", "blue", "yellow", "green", "orange", "purple", "pink", "neon_yellow", "neon_green", "neon_pink", "neon_orange", "neon_blue", "brown", "dark_blue", "dark_green", "cream"]


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    for table in _TABLES:
        if table not in tables:
            continue
        if "color" not in {c["name"] for c in inspector.get_columns(table)}:
            op.add_column(table, sa.Column("color", sa.String(length=20), nullable=True))

    # Attribution initiale : véhicules puis têtes, dans l'ordre du catalogue, en parcourant la palette
    index = 0
    for table in _TABLES:
        if table not in tables:
            continue
        columns = {c["name"] for c in sa.inspect(bind).get_columns(table)}
        order = "display_order, id" if "display_order" in columns else "id"
        rows = bind.execute(sa.text(
            f"SELECT id FROM {table} WHERE color IS NULL ORDER BY {order}"
        )).fetchall()
        for (row_id,) in rows:
            bind.execute(
                sa.text(f"UPDATE {table} SET color = :color WHERE id = :id"),
                {"color": _PALETTE[index % len(_PALETTE)], "id": row_id},
            )
            index += 1


def downgrade():
    inspector = sa.inspect(op.get_bind())
    tables = inspector.get_table_names()
    for table in _TABLES:
        if table in tables and "color" in {c["name"] for c in inspector.get_columns(table)}:
            op.drop_column(table, "color")
