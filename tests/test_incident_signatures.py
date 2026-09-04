import os
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from unittest.mock import MagicMock, patch

# Mock Weasyprint avant l'import de Flask
mock_weasyprint = MagicMock()
mock_html_inst = MagicMock()
mock_html_inst.write_pdf.return_value = (
    b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
    b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n"
    b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"
)
mock_weasyprint.HTML.return_value = mock_html_inst
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint

from app import create_app  # noqa: E402
from models import db, Project, Production, User, Vehicle  # noqa: E402
from models.incident import Incident, IncidentToken, IncidentSignedDocument  # noqa: E402
from services.admin import incidents as incident_service  # noqa: E402


class IncidentSignaturesTestCase(unittest.TestCase):
    def setUp(self):
        os.environ["FLASK_ENV"] = "testing"
        os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        os.environ["WTF_CSRF_ENABLED"] = "False"
        os.environ["USE_SSH_TUNNEL"] = "false"

        self.app = create_app()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.client = self.app.test_client()

        # Données de test
        self.prod = Production(name="Studio Cinéma Test")
        db.session.add(self.prod)
        db.session.commit()

        self.user = User(
            firstname="Alexandre",
            lastname="Dubois",
            mail="alex@bellevitesse.com",
            role="administrator",
        )
        db.session.add(self.user)
        db.session.commit()

        self.project = Project(
            name="Tournage Pub Sport",
            production_id=self.prod.id,
            departure_date=date.today(),
            shoot_start_date=date.today(),
            shoot_end_date=date.today(),
        )
        db.session.add(self.project)

        self.vehicle = Vehicle(
            id="audi-rs6",
            daily_rate=1800,
            fields={"name": "Audi RS6 Avant", "unique_id": "BV-CAR-02"},
        )
        db.session.add(self.vehicle)
        db.session.commit()

        # Création de l'incident de test
        form_data = {
            "title": "Frottement splitter carbone",
            "project_id": self.project.id,
            "vehicle_id": self.vehicle.id,
            "equipment_name": "Camera Car",
            "reported_by_id": self.user.id,
            "incident_date": "2026-09-04",
            "incident_time": "14:00",
            "location": "Piste Est",
            "category": "carrosserie",
            "severity": "modere",
            "shooting_impact": "retard",
            "description": "Frottement lors du passage sur une bordure surélevée.",
            "immediate_actions": "Vérification des fixations sur place.",
        }
        self.incident = incident_service.create_incident(form_data)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_bv_signature(self):
        """Vérifie l'enregistrement du visa Belle Vitesse."""
        sig_data = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        res = incident_service.sign_incident_bv(
            incident_id=self.incident.id,
            signer_name="Alexandre Dubois",
            signer_role="Responsable Technique Belle Vitesse",
            signature_data=sig_data,
            ip_address="192.168.1.50",
        )
        self.assertTrue(res["success"])
        self.assertEqual(self.incident.signature_status, "signed_bv")
        self.assertTrue(self.incident.is_signed_bv)
        self.assertFalse(self.incident.is_signed_prod)
        self.assertFalse(self.incident.is_fully_signed)
        self.assertEqual(self.incident.bv_signer_name, "Alexandre Dubois")
        self.assertEqual(self.incident.bv_signer_ip, "192.168.1.50")

    def test_token_generation_and_validation(self):
        """Vérifie la génération d'un jeton 48h et sa validation."""
        token_res = incident_service.generate_incident_token(
            incident_id=self.incident.id,
            recipient_email="regie@studio-cinema.com",
        )
        token_str = token_res["token"]
        self.assertTrue(token_str)
        self.assertIn(token_str, token_res["signing_url"])
        self.assertEqual(self.incident.signature_status, "pending_prod")

        # Validation succès
        val_res, code = incident_service.validate_incident_token(token_str)
        self.assertEqual(code, 200)
        token_entry, inc = val_res
        self.assertEqual(inc.id, self.incident.id)

        # Test token inconnu
        invalid_res, invalid_code = incident_service.validate_incident_token("inexistant-token")
        self.assertEqual(invalid_code, 404)
        self.assertIsNone(invalid_res)

        # Test token expiré
        token_entry.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.session.commit()
        exp_res, exp_code = incident_service.validate_incident_token(token_str)
        self.assertEqual(exp_code, 410)
        self.assertIsNone(exp_res)

    def test_contradictory_double_signature_and_sealing(self):
        """Vérifie le cycle complet BV + Production menant au scellement contradictoire."""
        sig_bv = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        sig_prod = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        # 1. Visa BV
        incident_service.sign_incident_bv(
            incident_id=self.incident.id,
            signer_name="Alexandre Dubois",
            signer_role="Responsable Technique",
            signature_data=sig_bv,
        )

        # 2. Signature Production
        prod_res = incident_service.sign_incident_prod(
            incident_id=self.incident.id,
            signer_name="Marie Laurent",
            signer_role="Directrice de Production",
            signature_data=sig_prod,
            ip_address="82.65.12.34",
        )

        self.assertTrue(prod_res["success"])
        self.assertEqual(self.incident.signature_status, "signed")
        self.assertTrue(self.incident.is_fully_signed)
        self.assertTrue(self.incident.is_signed_bv)
        self.assertTrue(self.incident.is_signed_prod)
        self.assertTrue(self.incident.hash)
        self.assertTrue(self.incident.pdf_file_hash)
        self.assertTrue(self.incident.signed_pdf_path)

        # 3. Archive légale IncidentSignedDocument
        signed_doc = IncidentSignedDocument.query.filter_by(incident_number=self.incident.incident_number).first()
        self.assertIsNotNone(signed_doc)
        self.assertEqual(signed_doc.hash, self.incident.hash)
        self.assertEqual(signed_doc.pdf_file_hash, self.incident.pdf_file_hash)
        self.assertEqual(signed_doc.data_snapshot["incident_number"], self.incident.incident_number)
        self.assertEqual(signed_doc.data_snapshot["bv_signer_name"], "Alexandre Dubois")
        self.assertEqual(signed_doc.data_snapshot["prod_signer_name"], "Marie Laurent")

    def test_production_signs_first_no_sealing_until_bv_signs(self):
        """Vérifie que si la Production signe en premier, le document N'EST PAS scellé tant que BV n'a pas visé."""
        sig_bv = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        sig_prod = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        # 1. La Production signe en premier
        prod_res = incident_service.sign_incident_prod(
            incident_id=self.incident.id,
            signer_name="Marie Laurent",
            signer_role="Directrice de Production",
            signature_data=sig_prod,
        )

        self.assertTrue(prod_res["success"])
        self.assertEqual(self.incident.signature_status, "signed_prod")
        self.assertTrue(self.incident.is_signed_prod)
        self.assertFalse(self.incident.is_signed_bv)
        self.assertFalse(self.incident.is_fully_signed)
        self.assertIsNone(self.incident.signed_pdf_path)
        self.assertIsNone(self.incident.hash)

        # 2. Belle Vitesse signe ensuite -> Le document est alors scellé
        bv_res = incident_service.sign_incident_bv(
            incident_id=self.incident.id,
            signer_name="Alexandre Dubois",
            signer_role="Responsable Technique",
            signature_data=sig_bv,
        )

        self.assertTrue(bv_res["success"])
        self.assertEqual(self.incident.signature_status, "signed")
        self.assertTrue(self.incident.is_fully_signed)
        self.assertTrue(self.incident.is_signed_bv)
        self.assertTrue(self.incident.is_signed_prod)
        self.assertIsNotNone(self.incident.signed_pdf_path)
        self.assertIsNotNone(self.incident.hash)

    def test_public_routes_sign_and_verify(self):
        """Vérifie le fonctionnement des endpoints HTTP publics."""
        sig_bv = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        sig_prod = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        # Visa préalable BV
        incident_service.sign_incident_bv(
            incident_id=self.incident.id,
            signer_name="Alexandre Dubois",
            signer_role="Responsable Technique",
            signature_data=sig_bv,
        )

        # Génération du token
        token_res = incident_service.generate_incident_token(
            incident_id=self.incident.id,
            recipient_email="prod@cinema.com",
        )
        token_str = token_res["token"]

        # GET /incidents/sign/<token>
        get_res = self.client.get(f"/incidents/sign/{token_str}")
        self.assertEqual(get_res.status_code, 200)
        self.assertIn(self.incident.incident_number.encode(), get_res.data)

        # POST /incidents/sign/<token>
        post_res = self.client.post(
            f"/incidents/sign/{token_str}",
            json={
                "signer_name": "Marie Laurent",
                "signer_role": "Régisseur Général",
                "signature": sig_prod,
            },
        )
        self.assertEqual(post_res.status_code, 200)
        data = post_res.get_json()
        self.assertEqual(data["status"], "signed")
        self.assertTrue(data["success"])

        # GET /incidents/verify/<incident_number>
        verify_res = self.client.get(f"/incidents/verify/{self.incident.incident_number}")
        self.assertEqual(verify_res.status_code, 200)
        self.assertIn("Données Scellées".encode(), verify_res.data)

    def test_pdf_download_security(self):
        """Vérifie les permissions d'accès au PDF signé (Admin, Token public, et Rejet si non autorisé)."""
        from utils.document_utils import generate_pdf_access_token

        sig_bv = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        sig_prod = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        incident_service.sign_incident_bv(self.incident.id, "BV", "Resp", sig_bv)
        incident_service.sign_incident_prod(self.incident.id, "Prod", "Dir", sig_prod)

        pdf_rel_path = self.incident.signed_pdf_path
        self.assertTrue(pdf_rel_path)

        # 1. Accès refusé pour un utilisateur anonyme sans token (403 Forbidden)
        anon_res = self.client.get(f"/incidents/document/{pdf_rel_path}")
        self.assertEqual(anon_res.status_code, 403)

        # 2. Accès autorisé avec un jeton temporaire valide t (200 OK)
        token = generate_pdf_access_token(pdf_rel_path)
        token_res = self.client.get(f"/incidents/document/{pdf_rel_path}?t={token}")
        self.assertEqual(token_res.status_code, 200)
        self.assertEqual(token_res.mimetype, "application/pdf")

        # 3. Accès autorisé pour un administrateur connecté via sa session (200 OK sans token)
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_role"] = "super administrateur"

        admin_res = self.client.get(f"/incidents/document/{pdf_rel_path}")
        self.assertEqual(admin_res.status_code, 200)
        self.assertEqual(admin_res.mimetype, "application/pdf")

        # 4. Route admin directe /admin/incidents/<record_id>/pdf
        admin_pdf_route_res = self.client.get(f"/admin/incidents/{self.incident.id}/pdf")
        self.assertEqual(admin_pdf_route_res.status_code, 200)
        self.assertEqual(admin_pdf_route_res.mimetype, "application/pdf")

    @patch("utils.mailer.EmailService._send_smtp_message", return_value=True)
    def test_incident_emails_rendering(self, mock_smtp):
        """Vérifie le bon rendu des templates d'email d'invitation et de confirmation scellée avec la DA Belle Vitesse."""
        from utils.mailer import (
            send_incident_signature_request_email,
            send_incident_signed_confirmation_email,
        )

        # 1. Email d'invitation
        res_invite = send_incident_signature_request_email(
            incident=self.incident,
            to_email="test-prod@example.com",
            signing_url="https://bellevitesse.com/incidents/sign/token123",
        )
        self.assertTrue(res_invite)
        self.assertTrue(mock_smtp.called)

        # 2. Email de confirmation scellée
        mock_smtp.reset_mock()
        res_confirm = send_incident_signed_confirmation_email(
            incident=self.incident,
            to_email="test-prod@example.com",
            pdf_path=None,
        )
        self.assertTrue(res_confirm)
        self.assertTrue(mock_smtp.called)


if __name__ == "__main__":
    unittest.main()

