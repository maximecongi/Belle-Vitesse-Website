#!/usr/bin/env python3
"""
scripts/migrate_kdrive_schema.py
Applique les modifications de schéma SQL pour l'intégration kDrive (Project columns + kdrive_objects table).
Compatible SQLite et MySQL via SQLAlchemy inspect.
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root))

from app import create_app
from models.db import db
from models.kdrive import KDriveObject
from sqlalchemy import inspect, text


def migrate():
    app = create_app()
    with app.app_context():
        inspector = inspect(db.engine)
        print("🔍 Inspection du schéma de la base de données...")

        # 1. Vérification / Création de la table kdrive_objects
        tables = inspector.get_table_names()
        if "kdrive_objects" not in tables:
            print("📦 Création de la table 'kdrive_objects'...")
            KDriveObject.__table__.create(db.engine)
            print("✅ Table 'kdrive_objects' créée.")
        else:
            print("✓ Table 'kdrive_objects' déjà existante.")

        # 2. Vérification / Ajout des colonnes sur projects
        project_cols = [c["name"] for c in inspector.get_columns("projects")]

        cols_to_add = [
            ("kdrive_folder_id", "BIGINT NULL"),
            ("kdrive_path", "VARCHAR(500) NULL"),
            ("kdrive_sync_status", "VARCHAR(20) NOT NULL DEFAULT 'pending'"),
            ("kdrive_last_error", "TEXT NULL"),
            ("kdrive_last_cancel_id", "VARCHAR(100) NULL"),
        ]

        # Détecter dialecte (sqlite vs mysql)
        is_sqlite = db.engine.dialect.name == "sqlite"

        for col_name, col_type in cols_to_add:
            if col_name not in project_cols:
                print(f"➕ Ajout de la colonne '{col_name}' sur 'projects'...")
                if is_sqlite and "DEFAULT" in col_type:
                    # SQLite supporte ALTER TABLE ADD COLUMN
                    sql = f"ALTER TABLE projects ADD COLUMN {col_name} {col_type}"
                elif is_sqlite:
                    sql = f"ALTER TABLE projects ADD COLUMN {col_name} {col_type.split()[0]}"
                else:
                    sql = f"ALTER TABLE projects ADD COLUMN {col_name} {col_type}"

                db.session.execute(text(sql))
                db.session.commit()
                print(f"✅ Colonne '{col_name}' ajoutée.")
            else:
                print(f"✓ Colonne '{col_name}' déjà présente sur 'projects'.")

        print("🎉 Migration kDrive terminée avec succès !")


if __name__ == "__main__":
    migrate()
