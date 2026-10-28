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
    Contact,
    Production,
    Project,
    PilotWaiver,
    WaiverSignedDocument,
    WaiverToken,
    Vehicle,
    User,
    db,
)
from services.admin.waivers import (
    create_pilot_waiver,
    delete_pilot_waiver,
    generate_pilot_waiver,
    get_or_create_waiver_signing_url,
    list_pilot_waivers,
    reset_pilot_waiver,
    send_pilot_waiver,
)
from utils.signature_storage import load_signature_data_uri


class PilotWaiverComprehensiveTest(unittest.TestCase):
    """Suite de tests unitaires et d'intégration pour l'Attestation Pilote (Annexe 3 aux CGL - BVPA)."""

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
        """Crée un jeu complet de données de test en mémoire (isolé)."""
        user = User(
            firstname="Admin",
            lastname="BV",
            mail="admin@bellevitesse.com",
            role="administrator"
        )
        db.session.add(user)

        prod = Production(name="Horizon Films Studio")
        db.session.add(prod)
        db.session.flush()

        prod_contact = Contact(
            first_name="Sophie",
            last_name="Directrice",
            mail="sophie@horizonfilms.com",
            phone="0611223344",
            job_title="Directrice de Production",
            production_id=prod.id
        )
        pilot_contact = Contact(
            first_name="Lucas",
            last_name="Cascadeur",
            mail="lucas@stuntpro.fr",
            phone="0699887766",
            job_title="Pilote de précision",
            production_id=prod.id
        )
        db.session.add_all([prod_contact, pilot_contact])
        db.session.flush()

        v1 = Vehicle(id="rec_v1", fields={"name": "e-Car High Speed", "unique_id": "ECAR-01", "slug": "ecar"})
        v2 = Vehicle(id="rec_v2", fields={"name": "Gyropode Segway X2", "unique_id": "SEG-02", "slug": "segway"})
        db.session.add_all([v1, v2])
        db.session.flush()

        proj = Project(
            name="Tournage Pub Sport Automobile",
            production_id=prod.id,
            production_contact_id=prod_contact.id,
            pilot_contact_id=pilot_contact.id,
            departure_date=date(2026, 9, 1),
            shoot_start_date=date(2026, 9, 2),
            shoot_end_date=date(2026, 9, 5),
            return_date=date(2026, 9, 6),
            vehicles_to_check=f"{v1.id}, {v2.id}"
        )
        db.session.add(proj)
        db.session.commit()
        return proj, prod, prod_contact, pilot_contact, [v1, v2]

    def test_01_pilot_waiver_model_and_id_generation(self):
        """Vérifie le modèle PilotWaiver, le préfixe BVPA, le polymorphisme et les labels."""
        with self.app.app_context():
            proj, prod, _, _, vehicles = self._create_mock_project()

            waiver = PilotWaiver(project_id=proj.id)
            db.session.add(waiver)
            db.session.commit()

            self.assertTrue(waiver.waiver_id.startswith("BVPA-"), f"L'ID doit débuter par BVPA-, reçu: {waiver.waiver_id}")
            self.assertEqual(waiver.waiver_type, "pilot_waiver")
            self.assertEqual(waiver.pilot_function_label, "Pilote")

            waiver.signer_role = "operator"
            self.assertEqual(waiver.pilot_function_label, "Opérateur gyropode")

            waiver.signer_role = "stunt_performer"
            self.assertEqual(waiver.pilot_function_label, "Cascadeur")

            waiver.signer_role = "other"
            waiver.signer_role_custom = "Conducteur de précision"
            self.assertEqual(waiver.pilot_function_label, "Conducteur de précision")

    def test_02_create_pilot_waiver_service_and_vehicle_selection(self):
        """Vérifie la création d'une attestation pilote avec sélection restreinte de véhicules."""
        with self.app.app_context():
            proj, prod, _, pilot_contact, vehicles = self._create_mock_project()

            # Création avec seulement le 1er véhicule sélectionné
            success, msg = create_pilot_waiver(
                project_id=proj.id,
                signer_role="pilot",
                selected_vehicles=["e-Car High Speed"],
            )
            self.assertTrue(success, msg)

            pw = PilotWaiver.query.filter_by(project_id=proj.id).first()
            self.assertIsNotNone(pw)
            self.assertEqual(pw.signer_first_name, pilot_contact.first_name)
            self.assertEqual(pw.signer_last_name, pilot_contact.last_name)
            self.assertEqual(pw.signer_email, pilot_contact.mail)
            self.assertEqual(pw.vehicles, "e-Car High Speed")

            # Vérifie le filtrage de vehicles_details
            details = pw.vehicles_details
            self.assertEqual(len(details), 1)
            self.assertEqual(details[0]["name"], "e-Car High Speed")

    def test_03_url_generation_and_token(self):
        """Vérifie la génération du jeton de session et de l'URL sécurisée de signature."""
        with self.app.app_context():
            proj, _, _, _, _ = self._create_mock_project()
            create_pilot_waiver(project_id=proj.id, signer_first_name="Jean", signer_last_name="Alesi", signer_email="jean@alesi.fr")
            pw = PilotWaiver.query.filter_by(project_id=proj.id).first()

            success, url = get_or_create_waiver_signing_url(pw.waiver_id, waiver_type="pilot_waiver")
            self.assertTrue(success, url)
            self.assertIn("/sign/pilot-attestation/", url)

            token_str = url.split("/sign/pilot-attestation/")[-1]
            token_rec = WaiverToken.query.filter_by(token=token_str).first()
            self.assertIsNotNone(token_rec)
            self.assertEqual(token_rec.waiver_id, pw.waiver_id)

    @patch("services.common.signatures.render_pdf_from_template")
    def test_04_public_signing_flow(self, mock_render_pdf):
        """Vérifie le parcours complet de signature publique (GET puis POST avec scellement eIDAS)."""
        mock_render_pdf.return_value = b"%PDF-1.4 Mocked Pilot Waiver PDF Content"

        with self.app.app_context():
            proj, _, _, _, _ = self._create_mock_project()
            create_pilot_waiver(project_id=proj.id, signer_first_name="Lucas", signer_last_name="Moreau", signer_email="lucas@stuntpro.fr")
            pw = PilotWaiver.query.filter_by(project_id=proj.id).first()

            _, url = get_or_create_waiver_signing_url(pw.waiver_id, waiver_type="pilot_waiver")
            token = url.split("/sign/pilot-attestation/")[-1]

            # 1. Requête GET : page publique
            res_get = self.client.get(f"/sign/pilot-attestation/{token}")
            self.assertEqual(res_get.status_code, 200)
            self.assertIn("Annexe 3 aux CGL", res_get.data.decode("utf-8"))
            self.assertIn("Lucas", res_get.data.decode("utf-8"))

            # 2. Requête POST sans acceptation de la case obligatoire : doit échouer
            fake_sig = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            res_post_fail = self.client.post(
                f"/sign/pilot-attestation/{token}",
                data={
                    "first_name": "Lucas",
                    "last_name": "Moreau",
                    "email": "lucas@stuntpro.fr",
                    "signature": fake_sig,
                    # ack_pilot_engagement manquant
                }
            )
            self.assertEqual(res_post_fail.status_code, 400)
            self.assertIn("obligatoire", res_post_fail.get_json().get("error", "").lower())

            # 3. Requête POST valide avec signature et consentement
            res_post_success = self.client.post(
                f"/sign/pilot-attestation/{token}",
                data={
                    "first_name": "Lucas",
                    "last_name": "Moreau",
                    "email": "lucas@stuntpro.fr",
                    "signer_role": "stunt_performer",
                    "ack_pilot_engagement": "1",
                    "signature_data": fake_sig,
                }
            )
            self.assertEqual(res_post_success.status_code, 200)
            json_data = res_post_success.get_json()
            self.assertTrue(json_data.get("success"))
            self.assertEqual(json_data.get("document_id"), pw.waiver_id)

            # Vérification de l'état en BDD
            signed_pw = PilotWaiver.query.filter_by(waiver_id=pw.waiver_id).first()
            self.assertEqual(signed_pw.status, "signed")
            self.assertIsNotNone(signed_pw.signed_at)
            self.assertIsNotNone(signed_pw.hash)
            self.assertIsNotNone(signed_pw.signed_pdf_path)

            # Vérification de l'archive WaiverSignedDocument
            signed_doc = WaiverSignedDocument.query.filter_by(waiver_id=pw.waiver_id).first()
            self.assertIsNotNone(signed_doc)
            self.assertIsNotNone(signed_doc.hash)
            self.assertEqual(signed_doc.version, 1)

    @patch("services.common.signatures.render_pdf_from_template")
    def test_05_public_verification_and_listing(self, mock_render_pdf):
        """Vérifie la route de vérification publique et les fonctions de listing/suppression."""
        mock_render_pdf.return_value = b"%PDF-1.4 Mocked Pilot Waiver PDF Content"

        with self.app.app_context():
            from utils.document_utils import generate_document_verification_token
            proj, _, _, _, _ = self._create_mock_project()
            create_pilot_waiver(project_id=proj.id, signer_first_name="Alain", signer_last_name="Prost", signer_email="alain@prost.fr")
            pw = PilotWaiver.query.filter_by(project_id=proj.id).first()

            # Listing
            items = list_pilot_waivers(project_id=proj.id)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["signer_name"], "Alain Prost")

            # Route de vérification sans token : doit retourner 404 (anti-énumération)
            res_verify_raw = self.client.get(f"/pilot-attestation/verify/{pw.waiver_id}")
            self.assertEqual(res_verify_raw.status_code, 404)

            # Signature du document pour créer l'archive scellée
            _, url = get_or_create_waiver_signing_url(pw.waiver_id, waiver_type="pilot_waiver")
            token = url.split("/sign/pilot-attestation/")[-1]
            fake_sig = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            self.client.post(
                f"/sign/pilot-attestation/{token}",
                data={
                    "first_name": "Alain",
                    "last_name": "Prost",
                    "email": "alain@prost.fr",
                    "signer_role": "pilot",
                    "ack_pilot_engagement": "1",
                    "signature_data": fake_sig,
                }
            )

            signed_doc = WaiverSignedDocument.query.filter_by(waiver_id=pw.waiver_id).first()
            self.assertIsNotNone(signed_doc)

            # Vérification avec token HMAC valide
            v_token = generate_document_verification_token("pilot_waiver", pw.waiver_id, 1, signed_doc.hash)
            res_verify = self.client.get(f"/pilot-attestation/verify/{pw.waiver_id}?version=1&t={v_token}")
            self.assertEqual(res_verify.status_code, 200)
            self.assertIn("Attestation Pilote Scellée", res_verify.get_data(as_text=True))

            # Suppression propre
            success_del, _ = delete_pilot_waiver(pw.waiver_id)
            self.assertTrue(success_del)
            self.assertEqual(len(list_pilot_waivers(project_id=proj.id)), 0)

    @patch("services.admin.project_reports.get_vehicles")
    def test_06_project_detail_modal_rendering(self, mock_get_vehicles):
        """Vérifie que la fiche projet admin rend correctement le modal d'invitation avec les classes d'overlay et les véhicules."""
        mock_get_vehicles.return_value = [
            {"id": "rec_v1", "fields": {"name": "e-Car High Speed", "unique_id": "ECAR-01"}},
            {"id": "rec_v2", "fields": {"name": "Gyropode Segway X2", "unique_id": "SEG-02"}},
        ]

        with self.app.app_context():
            proj, _, _, _, _ = self._create_mock_project()

            with self.client.session_transaction() as sess:
                sess["admin_authenticated"] = True
                sess["admin_user_id"] = 1
                sess["admin_user_role"] = "administrator"

            res = self.client.get(f"/admin/projects/{proj.id}")
            self.assertEqual(res.status_code, 200)
            html = res.get_data(as_text=True)

            # Vérification de l'overlay et des classes modales
            self.assertIn('id="addPilotSignerModal"', html)
            self.assertIn('class="admin-modal-overlay js-pilot-signer-modal u-d-none"', html)
            self.assertIn('js-open-add-pilot-signer-modal', html)

            # Vérification de l'action du formulaire et des cartes véhicules (style project_form)
            self.assertIn(f'/admin/projects/{proj.id}/pilot-waivers/create', html)
            self.assertIn('name="selected_vehicles"', html)
            self.assertIn('project-checkbox-card', html)
            self.assertIn('e-Car High Speed', html)
            self.assertIn('Gyropode Segway X2', html)
            self.assertIn('<input type="hidden" name="signer_role" value="pilot">', html)
            self.assertNotIn('id="new_pilot_signer_role"', html)


if __name__ == "__main__":
    unittest.main()
