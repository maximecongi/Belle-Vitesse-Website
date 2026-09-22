import os
import sys
import unittest
from datetime import date
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Isolation stricte de l'environnement de test avant tout import d'app
os.environ["FLASK_ENV"] = "testing"
os.environ["TESTING"] = "True"
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
os.environ["WTF_CSRF_ENABLED"] = "False"
os.environ["USE_SSH_TUNNEL"] = "false"

# Mock weasyprint
mock_weasyprint = MagicMock()
mock_weasyprint.HTML = MagicMock()
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint

from app import create_app
from models import db, Project, Production, User, PilotWaiver, ProductionWaiver
from services.admin.waivers import (
    create_pilot_waiver,
    create_production_waiver,
    list_pilot_waivers,
    list_production_waivers,
    generate_pilot_waiver,
    generate_production_waiver,
    reset_pilot_waiver,
    reset_production_waiver,
    delete_pilot_waiver_internal,
    delete_production_waiver_internal,
    delete_pilot_waiver,
    delete_production_waiver,
)

class WaiversTest(unittest.TestCase):
    def setUp(self):
        os.environ["FLASK_ENV"] = "testing"
        os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        os.environ["WTF_CSRF_ENABLED"] = "False"
        os.environ["USE_SSH_TUNNEL"] = "false"

        self.app = create_app()
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _create_mock_data(self):
        # Create user
        user = User(firstname="John", lastname="Doe", mail="john.doe@example.com", role="administrator")
        db.session.add(user)
        
        # Create production
        prod = Production(name="Test Prod")
        db.session.add(prod)
        db.session.flush()

        # Create project
        proj = Project(
            name="Test Project",
            production_id=prod.id,
            departure_date=date(2026, 6, 2),
            return_date=date(2026, 6, 5),
            vehicles_to_check="1"
        )
        db.session.add(proj)
        db.session.commit()

        return user, proj

    def test_create_and_list_waivers(self):
        with self.app.app_context():
            user, proj = self._create_mock_data()

            # Create waivers
            success, msg = create_pilot_waiver(proj.id)
            self.assertTrue(success)
            
            success, msg = create_production_waiver(proj.id)
            self.assertTrue(success)

            # List
            pilots = list_pilot_waivers()
            self.assertEqual(len(pilots), 1)
            self.assertEqual(pilots[0]["project_name"], "Test Project")

            productions = list_production_waivers()
            self.assertEqual(len(productions), 1)
            self.assertEqual(productions[0]["project_name"], "Test Project")

    def test_soft_delete_waivers(self):
        with self.app.app_context():
            user, proj = self._create_mock_data()

            # Create
            create_pilot_waiver(proj.id)
            create_production_waiver(proj.id)

            # Soft delete
            delete_pilot_waiver_internal(proj.id)
            delete_production_waiver_internal(proj.id)

            # List again - should be empty
            pilots = list_pilot_waivers()
            self.assertEqual(len(pilots), 0)

            productions = list_production_waivers()
            self.assertEqual(len(productions), 0)

            # Check DB directly
            pw = db.session.query(PilotWaiver).filter_by(project_id=proj.id).first()
            self.assertIsNotNone(pw)
            self.assertIsNotNone(pw.deleted_at)

            prw = db.session.query(ProductionWaiver).filter_by(project_id=proj.id).first()
            self.assertIsNotNone(prw)
            self.assertIsNotNone(prw.deleted_at)

    def test_explicit_delete_and_recreate(self):
        """Vérifie la suppression unitaire par ID et la capacité de recréer une décharge pour le même projet."""
        with self.app.app_context():
            user, proj = self._create_mock_data()

            # Création manuelle
            success, _ = create_pilot_waiver(proj.id)
            self.assertTrue(success)
            success, _ = create_production_waiver(proj.id)
            self.assertTrue(success)

            pw = PilotWaiver.query.filter_by(project_id=proj.id).first()
            prw = ProductionWaiver.query.filter_by(project_id=proj.id).first()

            # Suppression explicite (similaire au clic sur le bouton Supprimer)
            s_pw, _ = delete_pilot_waiver(pw.waiver_id)
            self.assertTrue(s_pw)
            s_prw, _ = delete_production_waiver(prw.waiver_id)
            self.assertTrue(s_prw)

            # Doivent avoir disparu des listes actives
            self.assertEqual(len(list_pilot_waivers()), 0)
            self.assertEqual(len(list_production_waivers()), 0)

            # Recréation manuelle sur demande pour le même projet -> doit réussir sans conflit SQL
            re_pw, msg_pw = create_pilot_waiver(proj.id)
            self.assertTrue(re_pw, msg_pw)
            re_prw, msg_prw = create_production_waiver(proj.id)
            self.assertTrue(re_prw, msg_prw)

            self.assertEqual(len(list_pilot_waivers()), 1)
            self.assertEqual(len(list_production_waivers()), 1)

    def test_no_automatic_waivers_on_project_create(self):
        """Vérifie qu'aucune décharge n'est créée automatiquement lors de la création d'un projet."""
        with self.app.app_context():
            from services.admin.projects import create_project

            prod = Production(name="Prod Sans Décharge Auto")
            db.session.add(prod)
            db.session.flush()

            class MockForm(dict):
                def getlist(self, name):
                    return []

            form_data = {
                "name": "Tournage Standalone",
                "production_id": str(prod.id),
                "departure_date": date(2026, 7, 1),
                "shoot_start": date(2026, 7, 2),
                "shoot_end": date(2026, 7, 5),
                "return_date": date(2026, 7, 6),
            }
            form = MockForm(form_data)
            created = create_project(form)
            self.assertTrue(created)

            new_proj = Project.query.filter_by(name="Tournage Standalone").first()
            self.assertIsNotNone(new_proj)

            # Aucune décharge ne doit exister pour ce projet
            self.assertIsNone(PilotWaiver.query.filter_by(project_id=new_proj.id).first())
            self.assertIsNone(ProductionWaiver.query.filter_by(project_id=new_proj.id).first())

    def test_waivers_created_directly_in_to_send_status(self):
        """Vérifie que la création d'une décharge la place directement au statut 'to_send' avec snapshot."""
        with self.app.app_context():
            user, proj = self._create_mock_data()

            s_pw, _ = create_pilot_waiver(proj.id)
            self.assertTrue(s_pw)
            s_prw, _ = create_production_waiver(proj.id)
            self.assertTrue(s_prw)

            pw = PilotWaiver.query.filter_by(project_id=proj.id).first()
            self.assertIsNotNone(pw)
            self.assertEqual(pw.status, "to_send")
            self.assertIsNotNone(pw.generated_at)
            self.assertEqual(pw.project_name, "Test Project")

            prw = ProductionWaiver.query.filter_by(project_id=proj.id).first()
            self.assertIsNotNone(prw)
            self.assertEqual(prw.status, "to_send")
            self.assertIsNotNone(prw.generated_at)
            self.assertEqual(prw.project_name, "Test Project")

    def test_waivers_search_and_project_links(self):
        """Vérifie le formatage des décharges dans list_projects et le filtre ?q=."""
        with self.app.app_context():
            from services.admin.projects import list_projects

            user, proj = self._create_mock_data()

            # Avant création des décharges : id et waiver_num sont vides
            projects = list_projects()
            p_data = next(p for p in projects if p["id"] == proj.id)
            self.assertIsNone(p_data["pilot_waiver"]["id"])
            self.assertEqual(p_data["pilot_waiver"]["waiver_num"], "")
            self.assertIsNone(p_data["production_waiver"]["id"])
            self.assertEqual(p_data["production_waiver"]["waiver_num"], "")

            # Après création : waiver_num est renseigné et status est 'to_send'
            create_pilot_waiver(proj.id)
            create_production_waiver(proj.id)

            projects = list_projects()
            p_data = next(p for p in projects if p["id"] == proj.id)
            self.assertIsNotNone(p_data["pilot_waiver"]["id"])
            self.assertTrue(p_data["pilot_waiver"]["waiver_num"].startswith("BVDW"))
            self.assertEqual(p_data["pilot_waiver"]["raw_status"], "to_send")
            self.assertIsNotNone(p_data["production_waiver"]["id"])
            self.assertTrue(p_data["production_waiver"]["waiver_num"].startswith("BVDW") or p_data["production_waiver"]["waiver_num"].startswith("BVPW"))
            self.assertEqual(p_data["production_waiver"]["raw_status"], "to_send")

    def test_verify_production_waiver_route(self):
        """Vérifie l'accès à la route de vérification pour une décharge production scellée."""
        with self.app.app_context():
            from models import ProductionWaiverSignedDocument
            from utils.document_utils import compute_hmac_seal

            user, proj = self._create_mock_data()
            create_production_waiver(proj.id)
            prw = ProductionWaiver.query.filter_by(project_id=proj.id).first()
            prw.status = "signed"
            prw.production_name = "Studio Test"
            prw.production_representative = "Jean Dupont"

            seal_args = ["Studio Test", "Jean Dupont"]
            sig_data = "data:image/png;base64,mock"
            iso_signed = "2026-09-22T20:00:00"
            h = compute_hmac_seal("WAIVER_PROD", prw.waiver_id, *seal_args, sig_data, iso_signed)

            signed_doc = ProductionWaiverSignedDocument(
                waiver_id=prw.waiver_id,
                hash=h,
                pdf_file_hash="mock-pdf-hash",
                data_snapshot={
                    "_seal_production_name": "Studio Test",
                    "_seal_representative": "Jean Dupont",
                    "production": "Studio Test",
                    "project": "Test Project",
                    "_seal_signed_at": iso_signed,
                },
                signature=sig_data,
                pdf_url=f"/production-waiver/document/{prw.waiver_id}.pdf"
            )
            db.session.add(signed_doc)
            db.session.commit()

            # Test route standard QR code: /production-waiver/verify/<waiver_id>
            resp = self.client.get(f"/production-waiver/verify/{prw.waiver_id}")
            self.assertEqual(resp.status_code, 200)
            self.assertIn("Données Certifiées &amp; Intactes".encode("utf-8"), resp.data)
            self.assertIn(prw.waiver_id.encode("utf-8"), resp.data)

            # Test route alias: /verify/production-waiver/<waiver_id>
            resp2 = self.client.get(f"/verify/production-waiver/{prw.waiver_id}")
            self.assertEqual(resp2.status_code, 200)

            # Test ID inexistant
            resp404 = self.client.get("/production-waiver/verify/BVPW-NONEXISTENT")
            self.assertEqual(resp404.status_code, 404)

    def test_verify_pilot_waiver_route(self):
        """Vérifie l'accès à la route de vérification pour une décharge pilote scellée."""
        with self.app.app_context():
            from models import PilotWaiverSignedDocument
            from utils.document_utils import compute_hmac_seal

            user, proj = self._create_mock_data()
            create_pilot_waiver(proj.id)
            pw = PilotWaiver.query.filter_by(project_id=proj.id).first()
            pw.status = "signed"
            pw.pilot_first_name = "Pierre"
            pw.pilot_last_name = "Martin"
            pw.pilot_license_number = "12345ABC"

            full_name = "Pierre Martin"
            seal_args = [full_name, "12345ABC"]
            sig_data = "data:image/png;base64,mock"
            iso_signed = "2026-09-22T20:00:00"
            h = compute_hmac_seal("WAIVER", pw.waiver_id, *seal_args, sig_data, iso_signed)

            signed_doc = PilotWaiverSignedDocument(
                waiver_id=pw.waiver_id,
                hash=h,
                pdf_file_hash="mock-pdf-hash",
                data_snapshot={
                    "_seal_pilot_name": full_name,
                    "_seal_license": "12345ABC",
                    "production": "Test Prod",
                    "project": "Test Project",
                    "_seal_signed_at": iso_signed,
                },
                signature=sig_data,
                pdf_url=f"/pilot-waiver/document/{pw.waiver_id}.pdf"
            )
            db.session.add(signed_doc)
            db.session.commit()

            # Test route standard QR code: /pilot-waiver/verify/<waiver_id>
            resp = self.client.get(f"/pilot-waiver/verify/{pw.waiver_id}")
            self.assertEqual(resp.status_code, 200)
            self.assertIn("Données Certifiées &amp; Intactes".encode("utf-8"), resp.data)
            self.assertIn(pw.waiver_id.encode("utf-8"), resp.data)

            # Test route alias: /waiver/verify/<waiver_id>
            resp2 = self.client.get(f"/waiver/verify/{pw.waiver_id}")
            self.assertEqual(resp2.status_code, 200)

            # Test route alias: /verify/waiver/<waiver_id>
            resp3 = self.client.get(f"/verify/waiver/{pw.waiver_id}")
            self.assertEqual(resp3.status_code, 200)

            # Test ID inexistant
            resp404 = self.client.get("/pilot-waiver/verify/BVDW-NONEXISTENT")
            self.assertEqual(resp404.status_code, 404)


if __name__ == "__main__":
    unittest.main()
