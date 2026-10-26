import os
import tempfile
import unittest
from flask_migrate import upgrade, downgrade
import sqlalchemy as sa
from app import create_app
from models import db


class MigrationsTestCase(unittest.TestCase):
    """Tests automatisés pour la baseline et la chaîne de migrations Alembic."""

    def test_clean_database_upgrade_from_zero_to_head(self):
        """Vérifie qu'une base vierge s'initialise de 0 à HEAD via flask_migrate.upgrade()."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "clean_test.db")
            os.environ["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
            os.environ["FLASK_ENV"] = "testing"
            os.environ["TESTING"] = "True"
            os.environ["RUN_MIGRATIONS"] = "true"

            test_app = create_app()

            with test_app.app_context():
                # 1. Exécution de l'upgrade de bout en bout
                upgrade()

                # 2. Vérification que les tables sont créées
                inspector = sa.inspect(db.engine)
                tables = inspector.get_table_names()

                critical_tables = [
                    "users",
                    "productions",
                    "projects",
                    "contacts",
                    "waivers",
                    "waiver_tokens",
                    "waiver_signed_documents",
                    "incidents",
                    "kdrive_objects",
                    "sql_query_logs",
                    "mcp_api_tokens",
                    "mcp_audit_logs",
                    "inspection_checkpoints",
                    "signature_events",
                    "alembic_version",
                ]
                for tbl in critical_tables:
                    self.assertIn(tbl, tables, f"La table {tbl} doit être créée par les migrations")

                # 3. Vérification de la version finale dans alembic_version
                with db.engine.connect() as conn:
                    current_rev = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
                    self.assertEqual(current_rev, "r00d7fe3c478")

                # Vérification de la clé primaire composite réelle (waiver_id, version) sur waiver_signed_documents
                wsd_pk = inspector.get_pk_constraint("waiver_signed_documents")
                self.assertEqual(
                    set(wsd_pk.get("constrained_columns") or []),
                    {"waiver_id", "version"},
                    f"La clé primaire doit être composite (waiver_id, version), actuel : {wsd_pk}"
                )

                # Test réel d'insertion des deux versions 1 et 2 pour le même document
                with db.engine.connect() as conn:
                    conn.execute(sa.text("""
                        INSERT INTO waiver_signed_documents (
                            waiver_id, version, parent_hash, hash, pdf_file_hash, data_snapshot, signature, pdf_url
                        ) VALUES (
                            'BVSR-MIGRATION-TEST', 1, NULL, 'hash_v1_test', 'pdf_h1', '{"version": 1}', 'sig1.png', '/url/1'
                        )
                    """))
                    conn.execute(sa.text("""
                        INSERT INTO waiver_signed_documents (
                            waiver_id, version, parent_hash, hash, pdf_file_hash, data_snapshot, signature, pdf_url
                        ) VALUES (
                            'BVSR-MIGRATION-TEST', 2, 'hash_v1_test', 'hash_v2_test', 'pdf_h2', '{"version": 2}', 'sig2.png', '/url/2'
                        )
                    """))
                    conn.commit()

                    inserted_versions = conn.execute(sa.text("""
                        SELECT version, parent_hash FROM waiver_signed_documents WHERE waiver_id = 'BVSR-MIGRATION-TEST' ORDER BY version ASC
                    """)).fetchall()
                    self.assertEqual(len(inserted_versions), 2)
                    self.assertEqual(inserted_versions[0][0], 1)
                    self.assertIsNone(inserted_versions[0][1])
                    self.assertEqual(inserted_versions[1][0], 2)
                    self.assertEqual(inserted_versions[1][1], 'hash_v1_test')

                # Vérification des colonnes de versioning sur waiver_signed_documents
                wsd_cols = [c["name"] for c in inspector.get_columns("waiver_signed_documents")]
                self.assertIn("version", wsd_cols)
                self.assertIn("parent_hash", wsd_cols)

                # Vérification des colonnes de chaînage cryptographique sur signature_events
                sig_cols = [c["name"] for c in inspector.get_columns("signature_events")]
                self.assertIn("previous_event_hash", sig_cols)
                self.assertIn("event_hash", sig_cols)

                # 4. Vérification que les tables décommissionnées sont bien absentes
                self.assertNotIn("pre_quotes", tables)
                self.assertNotIn("pre_quote_versions", tables)
                self.assertNotIn("pilot_waivers", tables)
                self.assertNotIn("production_waivers", tables)

                # 5. Vérification que les anciennes colonnes statiques de checkout_vehicles sont purgées
                co_cols = [c["name"] for c in inspector.get_columns("checkout_vehicles")]
                self.assertNotIn("tire_status", co_cols)
                self.assertNotIn("brake_status", co_cols)

                # 5. Vérification des colonnes kDrive sur projects
                proj_cols = [c["name"] for c in inspector.get_columns("projects")]
                for kcol in ["kdrive_folder_id", "kdrive_path", "kdrive_sync_status"]:
                    self.assertIn(kcol, proj_cols, f"La colonne {kcol} doit être présente sur projects")

    def test_idempotent_upgrade(self):
        """Vérifie que l'exécution répétée de upgrade() ne provoque aucune erreur."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "idempotent_test.db")
            os.environ["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
            os.environ["FLASK_ENV"] = "testing"
            os.environ["TESTING"] = "True"
            os.environ["RUN_MIGRATIONS"] = "true"

            test_app = create_app()

            with test_app.app_context():
                upgrade()
                # Second passage immédiat
                upgrade()
                with db.engine.connect() as conn:
                    current_rev = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
                    self.assertEqual(current_rev, "r00d7fe3c478")


    def test_upgrade_from_previous_head_stamp(self):
        """Vérifie qu'une base déjà estampillée à g00d7fe3c467 migre vers i00d7fe3c469 et supprime pre_quotes."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "prod_simulation.db")
            os.environ["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
            os.environ["FLASK_ENV"] = "testing"
            os.environ["TESTING"] = "True"
            os.environ["RUN_MIGRATIONS"] = "false"

            test_app = create_app()

            with test_app.app_context():
                # Initialiser les tables via db.create_all (simulation base existante)
                db.create_all()

                # Simuler les tables historiques pre_quotes et pre_quote_versions
                with db.engine.connect() as conn:
                    conn.execute(sa.text(
                        "CREATE TABLE IF NOT EXISTS pre_quotes (id INTEGER PRIMARY KEY, reference VARCHAR(50))"
                    ))
                    conn.execute(sa.text(
                        "CREATE TABLE IF NOT EXISTS pre_quote_versions (id INTEGER PRIMARY KEY, pre_quote_id INTEGER)"
                    ))
                    conn.execute(sa.text(
                        "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL, CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
                    ))
                    conn.execute(sa.text("DELETE FROM alembic_version"))
                    conn.execute(sa.text("INSERT INTO alembic_version VALUES ('g00d7fe3c467')"))
                    conn.commit()

                # Lancer l'upgrade : doit appliquer h00d7fe3c468 puis i00d7fe3c469
                upgrade()

                inspector = sa.inspect(db.engine)
                tables = inspector.get_table_names()
                self.assertNotIn("pre_quotes", tables)
                self.assertNotIn("pre_quote_versions", tables)

                with db.engine.connect() as conn:
                    current_rev = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
                    self.assertEqual(current_rev, "r00d7fe3c478")

    def test_downgrade_safety_prevents_losing_version_2(self):
        """Vérifie qu'un downgrade refuse strictement de s'exécuter si des documents version > 1 existent."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "downgrade_test.db")
            os.environ["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
            os.environ["FLASK_ENV"] = "testing"
            os.environ["TESTING"] = "True"
            os.environ["RUN_MIGRATIONS"] = "true"

            test_app = create_app()

            with test_app.app_context():
                upgrade()

                # Insérer une version 1 et une version 2
                with db.engine.connect() as conn:
                    conn.execute(sa.text("""
                        INSERT INTO waiver_signed_documents (
                            waiver_id, version, parent_hash, hash, pdf_file_hash, data_snapshot, signature, pdf_url
                        ) VALUES (
                            'BVSR-DOWNGRADE-TEST', 1, NULL, 'hash_v1', 'pdf_h1', '{"v": 1}', 'sig1.png', '/url/1'
                        )
                    """))
                    conn.execute(sa.text("""
                        INSERT INTO waiver_signed_documents (
                            waiver_id, version, parent_hash, hash, pdf_file_hash, data_snapshot, signature, pdf_url
                        ) VALUES (
                            'BVSR-DOWNGRADE-TEST', 2, 'hash_v1', 'hash_v2', 'pdf_h2', '{"v": 2}', 'sig2.png', '/url/2'
                        )
                    """))
                    conn.commit()

                # Tentative de downgrade vers q00d7fe3c477 : doit lever une RuntimeError explicite
                from flask import current_app
                from alembic import command
                cfg = current_app.extensions['migrate'].migrate.get_config(None)

                with self.assertRaises(RuntimeError) as ctx:
                    command.downgrade(cfg, revision="q00d7fe3c477")
                self.assertIn("perte de données irréversible", str(ctx.exception))
                self.assertIn("version > 1", str(ctx.exception))

                # Si on supprime la version 2 (ne reste que la version 1), le downgrade doit réussir proprement
                with db.engine.connect() as conn:
                    conn.execute(sa.text("DELETE FROM waiver_signed_documents WHERE version > 1"))
                    conn.commit()

                command.downgrade(cfg, revision="q00d7fe3c477")

                inspector = sa.inspect(db.engine)
                wsd_pk = inspector.get_pk_constraint("waiver_signed_documents")
                self.assertEqual(
                    set(wsd_pk.get("constrained_columns") or []),
                    {"waiver_id"},
                    "Après downgrade, la clé primaire doit redevenir waiver_id seul"
                )

                with db.engine.connect() as conn:
                    current_rev = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
                    self.assertEqual(current_rev, "q00d7fe3c477")
                    rows = conn.execute(sa.text("SELECT waiver_id, hash FROM waiver_signed_documents")).fetchall()
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(rows[0][0], "BVSR-DOWNGRADE-TEST")
                    self.assertEqual(rows[0][1], "hash_v1")



if __name__ == "__main__":
    unittest.main()
