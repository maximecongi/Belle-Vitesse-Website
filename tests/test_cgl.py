import os
import sys
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Isolation stricte en mémoire
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
from models import (
    WaiverSignedDocument,
    CglWaiver,
    Contact,
    Production,
    Project,
    User,
    WaiverToken,
    db,
)
from services.admin.waivers import (
    create_cgl,
    delete_cgl,
    delete_cgl_internal,
    generate_cgl,
    get_or_create_waiver_signing_url,
    list_cgl,
    reset_cgl,
    send_cgl,
)


class CglComprehensiveTest(unittest.TestCase):
    """Suite de tests unitaires et d'intégration pour les Conditions Générales de Location (CGL)."""

    def setUp(self):
        os.environ["FLASK_ENV"] = "testing"
        os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        os.environ["WTF_CSRF_ENABLED"] = "False"
        os.environ["USE_SSH_TUNNEL"] = "false"

        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _create_mock_project(self):
        """Crée un jeu complet de données de test en mémoire."""
        user = User(
            firstname="Admin",
            lastname="BV",
            mail="admin@bellevitesse.com",
            role="administrator"
        )
        db.session.add(user)

        prod = Production(name="Production Cinéma SAS")
        db.session.add(prod)
        db.session.flush()

        contact = Contact(
            first_name="Jean",
            last_name="Dupont",
            mail="jean.dupont@cinema.fr",
            phone="0612345678",
            job_title="Directeur de Production",
            production_id=prod.id
        )
        db.session.add(contact)
        db.session.flush()

        proj = Project(
            name="Tournage Long Métrage Alpha",
            production_id=prod.id,
            production_contact_id=contact.id,
            departure_date=date(2026, 7, 10),
            shoot_start_date=date(2026, 7, 11),
            shoot_end_date=date(2026, 7, 15),
            return_date=date(2026, 7, 16),
            vehicles_to_check="1, 2",
            shooting_locations=[{"name": "Circuit Paul Ricard", "address": "Le Castellet"}]
        )
        db.session.add(proj)
        db.session.commit()
        return proj, prod, contact

    def test_01_create_cgl_success(self):
        """Vérifie la création d'un enregistrement CGL avec préfixe BVCGL et liaison projet."""
        with self.app.app_context():
            proj, _, _ = self._create_mock_project()

            success, msg = create_cgl(proj.id)
            self.assertTrue(success, f"La création de CGL a échoué: {msg}")

            cgl = CglWaiver.query.filter_by(project_id=proj.id).first()
            self.assertIsNotNone(cgl)
            self.assertTrue(cgl.waiver_id.startswith("BVRA-"))
            self.assertEqual(cgl.waiver_type, "cgl")
            self.assertEqual(cgl.status, "to_send")
            self.assertEqual(proj.cgl.id, cgl.id)
            self.assertEqual(proj.active_cgl.id, cgl.id)

    def test_02_create_cgl_duplicate_rejected(self):
        """Vérifie qu'il est impossible de créer deux CGL actives pour le même projet."""
        with self.app.app_context():
            proj, _, _ = self._create_mock_project()

            success1, _ = create_cgl(proj.id)
            self.assertTrue(success1)

            success2, msg = create_cgl(proj.id)
            self.assertFalse(success2)
            self.assertIn("existent déjà", msg)

    def test_02b_recreate_cgl_after_deletion_resolves_active_cgl(self):
        """Vérifie que la recréation de CGL après suppression résout correctement la nouvelle CGL active sur le projet."""
        with self.app.app_context():
            proj, _, _ = self._create_mock_project()
            proj_id = proj.id

            success1, _ = create_cgl(proj_id)
            self.assertTrue(success1)
            cgl1 = CglWaiver.query.filter_by(project_id=proj_id, deleted_at=None).first()
            delete_cgl(cgl1.waiver_id)

            # Recréation via create_cgl (quick create)
            success2, _ = create_cgl(proj_id)
            self.assertTrue(success2)

            db.session.expire_all()
            reloaded_proj = db.session.get(Project, proj_id)
            self.assertIsNotNone(reloaded_proj.cgl)
            self.assertIsNotNone(reloaded_proj.active_cgl)
            self.assertIsNone(reloaded_proj.active_cgl.deleted_at)
            self.assertNotEqual(reloaded_proj.active_cgl.waiver_id, cgl1.waiver_id)
            self.assertEqual(reloaded_proj.active_cgl.status, "to_send")

    def test_03_generate_cgl(self):
        """Vérifie que la génération des CGL capture les métadonnées du projet et passe en to_send."""
        with self.app.app_context():
            proj, prod, _ = self._create_mock_project()
            create_cgl(proj.id)
            cgl = CglWaiver.query.filter_by(project_id=proj.id).first()
            cgl.status = "to_generate"
            db.session.commit()

            success, msg = generate_cgl(cgl.waiver_id)
            self.assertTrue(success, f"La génération a échoué: {msg}")

            db.session.refresh(cgl)
            self.assertEqual(cgl.status, "to_send")
            self.assertEqual(cgl.production_name, prod.name)
            self.assertIn("11/07/2026", cgl.shooting_dates)

    def test_04_get_or_create_signing_url(self):
        """Vérifie la création d'un jeton de signature 24h et de l'URL publique /sign/cgl/<token>."""
        with self.app.app_context():
            proj, _, _ = self._create_mock_project()
            create_cgl(proj.id)
            cgl = CglWaiver.query.filter_by(project_id=proj.id).first()

            success, sign_url = get_or_create_waiver_signing_url(cgl.waiver_id, waiver_type="cgl")
            self.assertTrue(success)
            self.assertIn("/sign/cgl/", sign_url)

            # Vérifie le jeton en BDD
            token_val = sign_url.split("/sign/cgl/")[-1]
            token_rec = WaiverToken.query.filter_by(token=token_val).first()
            self.assertIsNotNone(token_rec)
            self.assertEqual(token_rec.waiver_id, cgl.waiver_id)

    @patch("services.common.pdf_tasks.render_pdf_from_template", return_value=b"%PDF-1.4 mock cgl content")
    def test_05_public_signing_flow(self, mock_render_pdf):
        """Vérifie le cycle complet de signature publique par le locataire et le scellement HMAC."""
        with self.app.app_context():
            proj, prod, _ = self._create_mock_project()
            create_cgl(proj.id)
            cgl = CglWaiver.query.filter_by(project_id=proj.id).first()
            _, sign_url = get_or_create_waiver_signing_url(cgl.waiver_id, waiver_type="cgl")
            self.assertEqual(cgl.display_order_ref, "")
            token_val = sign_url.split("/sign/cgl/")[-1]
            proj_id = proj.id
            waiver_id = cgl.waiver_id

        # 1. GET sur la page de signature
        resp_get = self.client.get(f"/sign/cgl/{token_val}")
        self.assertEqual(resp_get.status_code, 200)
        html_sign = resp_get.get_data(as_text=True)
        self.assertIn("Conditions Générales de Location", html_sign)
        self.assertIn('id="cgl_legal_country"', html_sign)
        self.assertIn('<option value="FR"', html_sign)
        self.assertIn('France</option>', html_sign)
        self.assertIn('<option value="ES"', html_sign)
        self.assertIn('Espagne</option>', html_sign)

        # 2. Rejet si accepted_terms ou has_signing_authority absent
        payload_invalid = {
            "production_name": "Société Production Réelle SAS",
            "representative": "Alice Martin",
            "representative_role": "Gérante",
            "signature_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        }
        resp_invalid = self.client.post(f"/sign/cgl/{token_val}", data=payload_invalid)
        self.assertEqual(resp_invalid.status_code, 400)
        self.assertIn("Conditions Générales", resp_invalid.get_json().get("error", ""))

        # 3. POST valide avec signature, consentement et déclaration de pouvoir
        payload = {
            "production_name": "Société Production Réelle SAS",
            "representative": "Alice Martin",
            "representative_role": "Gérante",
            "siret": "12345678900012",
            "address": "15 Avenue des Champs-Élysées, 75008 Paris",
            "vat_number": "FR12345678900",
            "legal_form": "SAS",
            "legal_country": "France",
            "order_ref": "BVPR-TEST-1234",
            "city": "Paris",
            "location_of_use": "Studio Bry-sur-Marne",
            "accepted_terms": "1",
            "has_signing_authority": "1",
            "signature_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        }
        resp_post = self.client.post(f"/sign/cgl/{token_val}", data=payload)
        self.assertEqual(resp_post.status_code, 200)
        json_data = resp_post.get_json()
        self.assertTrue(json_data.get("success"))

        with self.app.app_context():
            cgl_signed = CglWaiver.query.filter_by(project_id=proj_id).first()
            self.assertEqual(cgl_signed.status, "signed")
            self.assertEqual(cgl_signed.production_name, "Société Production Réelle SAS")
            self.assertEqual(cgl_signed.production_representative, "Alice Martin")
            self.assertEqual(cgl_signed.display_order_ref, "BVPR-TEST-1234")
            self.assertEqual(cgl_signed.display_legal_form_only, "SAS")
            self.assertEqual(cgl_signed.display_legal_country, "France")
            self.assertEqual(cgl_signed.display_legal_form, "SAS (France)")
            self.assertEqual(cgl_signed.display_signature_city, "Paris")
            self.assertIsNotNone(cgl_signed.signed_at)

            # Vérifie l'archive signée WaiverSignedDocument avec Sceau Canonique v2
            signed_doc = WaiverSignedDocument.query.filter_by(waiver_id=waiver_id).first()
            self.assertIsNotNone(signed_doc)
            self.assertIsNotNone(signed_doc.hash)
            self.assertEqual(signed_doc.data_snapshot.get("version"), "2.0")
            self.assertIn("127.0.0.1", signed_doc.data_snapshot.get("signer_ip", ""))
            self.assertTrue(signed_doc.data_snapshot.get("snapshot", {}).get("has_signing_authority"))

    @patch("services.common.pdf_tasks.render_pdf_from_template", return_value=b"%PDF-1.4 mock cgl content")
    def test_06_verification_flow(self, mock_render_pdf):
        """Vérifie la page de vérification publique et la validation du sceau cryptographique."""
        with self.app.app_context():
            proj, _, _ = self._create_mock_project()
            create_cgl(proj.id)
            cgl = CglWaiver.query.filter_by(project_id=proj.id).first()
            _, sign_url = get_or_create_waiver_signing_url(cgl.waiver_id, waiver_type="cgl")
            token_val = sign_url.split("/sign/cgl/")[-1]

            payload = {
                "production_name": "Prod Authentique",
                "representative": "Directeur Juridique",
                "representative_role": "Directeur Juridique",
                "siret": "B66123456",
                "address": "10 Boulevard Haussmann, Paris",
                "legal_country": "ES",
                "accepted_terms": "1",
                "has_signing_authority": "1",
                "signature_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            }
            resp_sign = self.client.post(f"/sign/cgl/{token_val}", data=payload)
            self.assertEqual(resp_sign.status_code, 200)
            self.assertEqual(cgl.display_legal_country, "Espagne")
            self.assertEqual(cgl.production_siret, "B66123456")
            self.assertEqual(cgl.display_legal_identifier_label, "N° d’immatriculation")
            waiver_id = cgl.waiver_id
            signed_doc = WaiverSignedDocument.query.filter_by(waiver_id=waiver_id).first()
            from utils.document_utils import generate_document_verification_token
            verify_token = generate_document_verification_token("cgl", waiver_id, 1, signed_doc.hash)
            verify_url = f"/cgl/verify/{waiver_id}?version=1&t={verify_token}"

        # Vérification du HTML du PDF : le QR code doit être cliquable vers la page de vérification
        pdf_html = mock_render_pdf.call_args[1]["html_content"]
        self.assertIn('class="cgl-qr-link"', pdf_html)
        self.assertIn(f"/cgl/verify/{waiver_id}?version=1&amp;t=", pdf_html)
        resp_verify = self.client.get(verify_url)
        self.assertEqual(resp_verify.status_code, 200)
        html = resp_verify.get_data(as_text=True)
        self.assertIn("Vérification CGL Locataire", html)
        self.assertIn("CGL Scellées &amp; Intactes", html)
        self.assertIn("Prod Authentique", html)

    def test_foreign_company_can_sign_without_registration_number(self):
        with self.app.app_context():
            proj, _, _ = self._create_mock_project()
            project_id = proj.id
            create_cgl(proj.id)
            cgl = CglWaiver.query.filter_by(project_id=proj.id).first()
            generate_cgl(cgl.waiver_id)
            _, sign_url = get_or_create_waiver_signing_url(cgl.waiver_id, waiver_type="cgl")
            token_val = sign_url.split("/sign/cgl/")[-1]

        response = self.client.post(f"/sign/cgl/{token_val}", data={
            "production_name": "Production étrangère GmbH",
            "representative": "Alice Martin",
            "representative_role": "Directrice",
            "legal_form": "GmbH",
            "legal_country": "DE",
            "siret": "",
            "accepted_terms": "1",
            "has_signing_authority": "1",
            "signature_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json().get("success"))
        with self.app.app_context():
            signed = CglWaiver.query.filter_by(project_id=project_id).first()
            self.assertEqual(signed.production_siret, "")
            self.assertEqual(signed.display_legal_identifier_label, "N° d’immatriculation")

    def test_07_list_and_delete_cgl(self):
        """Vérifie le listing et la suppression d'un contrat CGL."""
        with self.app.app_context():
            proj, _, _ = self._create_mock_project()
            create_cgl(proj.id)
            cgl = CglWaiver.query.filter_by(project_id=proj.id).first()

            items = list_cgl()
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["waiver_id"], cgl.waiver_id)

            # Suppression
            success, msg = delete_cgl(cgl.waiver_id)
            self.assertTrue(success)

            # Doit être soft-deleted
            items_after = list_cgl()
            self.assertEqual(len(items_after), 0)

    def test_08_delete_cgl_internal_cascade(self):
        """Vérifie la suppression interne des CGL lors de la suppression d'un projet."""
        with self.app.app_context():
            proj, _, _ = self._create_mock_project()
            create_cgl(proj.id)
            cgl = CglWaiver.query.filter_by(project_id=proj.id).first()
            self.assertIsNotNone(cgl)

            delete_cgl_internal(proj.id)
            db.session.refresh(cgl)
            self.assertIsNotNone(cgl.deleted_at)

    @patch("services.common.pdf_tasks.render_pdf_from_template", return_value=b"%PDF-1.4 mock cgl content")
    def test_09_cgl_additional_fields_signing_and_properties(self, mock_render_pdf):
        """Vérifie l'enregistrement et les propriétés des champs complémentaires CGL (forme juridique, rôle, assurance, ville)."""
        with self.app.app_context():
            proj, prod, contact = self._create_mock_project()
            create_cgl(proj.id)
            cgl = CglWaiver.query.filter_by(project_id=proj.id).first()

            # Vérifie le pré-remplissage depuis le contact de production
            self.assertEqual(cgl.production_representative, "Jean Dupont")
            self.assertEqual(cgl.signer_phone, "0612345678")
            self.assertEqual(cgl.signer_email, "jean.dupont@cinema.fr")
            self.assertEqual(cgl.signer_role_custom, "Directeur de Production")

            _, sign_url = get_or_create_waiver_signing_url(cgl.waiver_id, waiver_type="cgl")
            token_val = sign_url.split("/sign/cgl/")[-1]
            proj_id = proj.id

        payload = {
            "production_name": "Studio Lumière SAS",
            "legal_form": "SAS au capital de 50 000 €",
            "legal_country": "France",
            "representative": "Claire Delon",
            "representative_role": "Directrice Générale",
            "phone": "0789101112",
            "email": "claire.delon@studiolumiere.fr",
            "siret": "55566677700018",
            "address": "42 Rue du Faubourg Saint-Honoré, 75008 Paris",
            "vat_number": "FR55566677700",
            "city": "Paris",
            "insurance_company": "Allianz Cinéma & Audiovisuel",
            "insurance_policy": "POL-ALLIANZ-88291",
            "location_of_use": "Studios de Bry-sur-Marne",
            "accepted_terms": "1",
            "has_signing_authority": "1",
            "signature_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        }

        resp_post = self.client.post(f"/sign/cgl/{token_val}", data=payload)
        self.assertEqual(resp_post.status_code, 200)
        self.assertTrue(resp_post.get_json().get("success"))

        with self.app.app_context():
            signed_cgl = CglWaiver.query.filter_by(project_id=proj_id).first()
            self.assertEqual(signed_cgl.status, "signed")
            self.assertEqual(signed_cgl.display_legal_form_only, "SAS au capital de 50 000 €")
            self.assertEqual(signed_cgl.display_legal_country, "France")
            self.assertEqual(signed_cgl.display_legal_form, "SAS au capital de 50 000 € (France)")
            self.assertEqual(signed_cgl.display_representative_role, "Directrice Générale")
            self.assertEqual(signed_cgl.display_signature_city, "Paris")
            self.assertEqual(signed_cgl.signer_phone, "0789101112")
            self.assertEqual(signed_cgl.signer_email, "claire.delon@studiolumiere.fr")
            self.assertEqual(signed_cgl.production_insurance_company, "Allianz Cinéma & Audiovisuel")
            self.assertEqual(signed_cgl.production_insurance_policy, "POL-ALLIANZ-88291")
            self.assertEqual(signed_cgl.location_of_use, "Studios de Bry-sur-Marne")

    def test_10_pdf_preview_endpoints(self):
        """Vérifie le bon fonctionnement des endpoints de prévisualisation directe HTML des templates PDF."""
        # 1. Prévisualisation directe CGL (mock)
        resp_cgl_admin = self.client.get("/admin/cgl/preview")
        self.assertEqual(resp_cgl_admin.status_code, 200)
        cgl_html = resp_cgl_admin.get_data(as_text=True)
        self.assertIn("Conditions Générales de Location", cgl_html)
        self.assertIn("Antiestático Barcelona SL", cgl_html)
        self.assertIn("pdf-preview-toolbar", cgl_html)
        self.assertIn("Format A4 (210 × 297 mm)", cgl_html)
        self.assertIn("cgl-screen-footer", cgl_html)

        resp_cgl_alias = self.client.get("/admin/preview/pdf/cgl")
        self.assertEqual(resp_cgl_alias.status_code, 200)

        resp_cgl_direct = self.client.get("/preview/pdf/cgl")
        self.assertEqual(resp_cgl_direct.status_code, 200)

        # 2. Prévisualisation directe Règles de Sécurité BVSR (mock)
        resp_safety_admin = self.client.get("/admin/safety-rules/preview")
        self.assertEqual(resp_safety_admin.status_code, 200)
        safety_html = resp_safety_admin.get_data(as_text=True)
        self.assertIn("Règles de Sécurité Universelles", safety_html)
        self.assertIn("Alexandre Mercier", safety_html)
        self.assertIn("pdf-preview-toolbar", safety_html)
        self.assertIn("Format A4 (210 × 297 mm)", safety_html)
        self.assertIn("bvsr-screen-footer", safety_html)

        resp_safety_alias = self.client.get("/admin/preview/pdf/safety-rules")
        self.assertEqual(resp_safety_alias.status_code, 200)

        resp_safety_direct = self.client.get("/preview/pdf/safety-rules")
        self.assertEqual(resp_safety_direct.status_code, 200)


if __name__ == "__main__":
    unittest.main()

