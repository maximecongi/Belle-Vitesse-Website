"""Add signer_contact_id (lien vers le contact ERP signataire) to waivers.

Revision ID: c10d7fe3c489
Revises: b10d7fe3c488
Create Date: 2026-11-10 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "c10d7fe3c489"
down_revision = "b10d7fe3c488"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns("waivers")]
    if "signer_contact_id" not in columns:
        with op.batch_alter_table("waivers") as batch_op:
            batch_op.add_column(sa.Column("signer_contact_id", sa.Integer(), nullable=True))
            batch_op.create_index("ix_waivers_signer_contact_id", ["signer_contact_id"], unique=False)
            batch_op.create_foreign_key(
                "fk_waivers_signer_contact_id", "contacts", ["signer_contact_id"], ["id"], ondelete="SET NULL"
            )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if "signer_contact_id" not in [c["name"] for c in inspector.get_columns("waivers")]:
        return
    # La contrainte peut être absente ou sans nom (table créée par db.create_all) : on ne supprime
    # que les contraintes et index nommés réellement présents sur la colonne.
    fk_names = [
        fk["name"]
        for fk in inspector.get_foreign_keys("waivers")
        if fk.get("constrained_columns") == ["signer_contact_id"] and fk.get("name")
    ]
    index_names = [
        ix["name"]
        for ix in inspector.get_indexes("waivers")
        if ix.get("column_names") == ["signer_contact_id"] and ix.get("name")
    ]
    with op.batch_alter_table("waivers") as batch_op:
        for name in fk_names:
            batch_op.drop_constraint(name, type_="foreignkey")
        for name in index_names:
            batch_op.drop_index(name)
        batch_op.drop_column("signer_contact_id")
