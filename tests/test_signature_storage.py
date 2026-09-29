import base64
import os
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

# Isolation stricte de l'environnement de test avant tout import d'app
os.environ["FLASK_ENV"] = "testing"
os.environ["TESTING"] = "True"
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
os.environ["WTF_CSRF_ENABLED"] = "False"
os.environ["USE_SSH_TUNNEL"] = "false"

# Mock weasyprint si nécessaire
mock_weasyprint = MagicMock()
mock_weasyprint.HTML = MagicMock()
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint

from app import create_app
from models.db import db
from models.incident import Incident
from models.project import Project, Production
from models.user import User
from models.waiver import PilotWaiver, ProductionWaiver, PilotWaiverSignedDocument
from services.admin.incidents import create_incident, sign_incident_bv, sign_incident_prod
from services.common.signatures import finalize_signed_document
from utils.signature_storage import (
    delete_signature_file,
    get_signatures_base_dir,
    load_signature_data_uri,
    save_signature_image,
)

SAMPLE_BASE64_PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


class TestSignatureStorage(unittest.TestCase):
    def setUp(self):
        os.environ["FLASK_ENV"] = "testing"
        os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        os.environ["WTF_CSRF_ENABLED"] = "False"
        os.environ["USE_SSH_TUNNEL"] = "false"

        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["SERVER_NAME"] = "localhost"
        self.app.config["WTF_CSRF_ENABLED"] = False

        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_save_and_load_signature_image(self):
        """Vérifie la sauvegarde d'un Base64 en PNG physique et sa relecture en Data URI."""
        rel_path = save_signature_image(
            base64_data=SAMPLE_BASE64_PNG,
            entity_type="waivers",
            record_id="TEST_UNIT_W1",
            suffix="_sign"
        )
        self.assertTrue(rel_path.startswith("signatures/waivers/TEST_UNIT_W1_sign.png"))

        # Vérification physique sur disque
        output_base = Path(self.app.root_path) / "output"
        full_path = output_base / rel_path
        self.assertTrue(full_path.exists())
        self.assertGreater(full_path.stat().st_size, 0)

        # Relecture Data URI
        data_uri = load_signature_data_uri(rel_path)
        self.assertIsNotNone(data_uri)
        self.assertTrue(data_uri.startswith("data:image/png;base64,"))

        # Nettoyage
        deleted = delete_signature_file(rel_path)
        self.assertTrue(deleted)
        self.assertFalse(full_path.exists())

    def test_finalize_waiver_stores_relative_path(self):
        """Vérifie qu'une décharge finalisée persiste le chemin relatif PNG et non le Base64 brut."""
        # Création des entités parentes nécessaires (Projet et Production)
        prod = Production(name="Prod Test Unit")
        db.session.add(prod)
        db.session.flush()

        project = Project(
            name="Projet Test Unit",
            production_id=prod.id,
            departure_date=date.today(),
            return_date=date.today(),
            vehicles_to_check="1",
        )
        db.session.add(project)
        db.session.flush()

        waiver = PilotWaiver(
            waiver_id="BVDW-TESTUNIT99",
            pilot_first_name="Jean",
            pilot_last_name="Testeur",
            status="to_sign",
            project_id=project.id,
        )
        db.session.add(waiver)
        db.session.commit()

        # Finalisation de la signature
        res = finalize_signed_document(
            mode="pilot",
            record_id=waiver.id,
            signature_data=SAMPLE_BASE64_PNG,
            signed_ip="127.0.0.1",
        )

        db.session.refresh(waiver)
        # La colonne en BDD doit être un chemin relatif
        self.assertTrue(waiver.signature_data.startswith("signatures/waivers/BVDW-TESTUNIT99"))
        self.assertFalse(waiver.signature_data.startswith("data:image/"))

        # La property signature_data_uri doit charger le Base64
        self.assertTrue(waiver.signature_data_uri.startswith("data:image/png;base64,"))

        # Nettoyage fichier créé
        delete_signature_file(waiver.signature_data)

    def test_incident_double_signatures_storage(self):
        """Vérifie que les signatures BV et Prod d'un incident sont enregistrées sous forme de fichiers PNG distincts."""
        user = User(firstname="Admin", lastname="BV", mail="admin.bv@test.com", role="administrator")
        db.session.add(user)
        db.session.flush()

        inc_data = {
            "title": "Incident Test Storage Signatures",
            "incident_date": "2026-09-29",
            "category": "vehicule",
            "severity": "mineur",
            "shooting_impact": "aucun",
            "reporter_id": user.id,
            "description": "Test unitaire déport des signatures",
        }
        incident = create_incident(inc_data)
        self.assertIsNotNone(incident)

        # 1. Signature BV
        res_bv = sign_incident_bv(
            incident_id=incident.id,
            signer_name="Marc BV",
            signer_role="Responsable Technique",
            signature_data=SAMPLE_BASE64_PNG,
            ip_address="127.0.0.1"
        )
        self.assertTrue(res_bv.get("success"))
        db.session.refresh(incident)
        self.assertTrue(incident.bv_signature_data.startswith("signatures/incidents/"))
        self.assertTrue(incident.bv_signature_data.endswith("_bv.png"))
        self.assertTrue(incident.bv_signature_data_uri.startswith("data:image/png;base64,"))

        # 2. Signature Prod
        res_prod = sign_incident_prod(
            incident_id=incident.id,
            signer_name="Alice Prod",
            signer_role="Directrice de Production",
            signature_data=SAMPLE_BASE64_PNG,
            ip_address="127.0.0.1"
        )
        self.assertTrue(res_prod.get("success"))
        db.session.refresh(incident)
        self.assertTrue(incident.prod_signature_data.startswith("signatures/incidents/"))
        self.assertTrue(incident.prod_signature_data.endswith("_prod.png"))
        self.assertTrue(incident.prod_signature_data_uri.startswith("data:image/png;base64,"))
        self.assertTrue(incident.is_fully_signed)

        # Nettoyage fichiers créés
        delete_signature_file(incident.bv_signature_data)
        delete_signature_file(incident.prod_signature_data)

    def test_migration_script_dry_run_and_execution(self):
        """Vérifie le bon fonctionnement du script de migration des signatures."""
        from scripts.migrate_signatures_to_files import migrate_signatures

        # Création d'une décharge avec Base64 brut
        prod = Production(name="Prod Migration Test")
        db.session.add(prod)
        db.session.flush()

        project = Project(
            name="Projet Migration Test",
            production_id=prod.id,
            departure_date=date.today(),
            return_date=date.today(),
            vehicles_to_check="1",
        )
        db.session.add(project)
        db.session.flush()

        pw = PilotWaiver(
            waiver_id="BVDW-MIGRATE-01",
            pilot_first_name="Paul",
            pilot_last_name="Volant",
            project_id=project.id,
            signature_data=SAMPLE_BASE64_PNG,
        )
        db.session.add(pw)
        db.session.commit()

        # 1. Dry run ne doit pas modifier la BDD
        migrate_signatures(dry_run=True, app=self.app)
        db.session.refresh(pw)
        self.assertEqual(pw.signature_data, SAMPLE_BASE64_PNG)

        # 2. Exécution réelle
        migrate_signatures(dry_run=False, app=self.app)
        db.session.refresh(pw)
        self.assertTrue(pw.signature_data.startswith("signatures/waivers/BVDW-MIGRATE-01"))

        # Nettoyage
        delete_signature_file(pw.signature_data)


if __name__ == "__main__":
    unittest.main()
