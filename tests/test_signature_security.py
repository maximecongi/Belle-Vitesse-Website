"""
Suite de tests de sécurité et de robustesse pour le système de signature électronique durci :
1. Immuabilité stricte de la table d'audit `signature_events` (append-only, interdiction UPDATE / DELETE).
2. Validation stricte du format binaire PNG de la signature (magic bytes, Pillow, limite de taille 500 KB).
3. Déterminisme du sceau canonique HMAC-SHA256 et détection de falsification.
4. Déclaration obligatoire de mandat social B2B et consentement contractuel.
5. Détection d'altération physique du fichier PNG lors de la vérification.
"""

import base64
import io
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date
from unittest.mock import MagicMock

from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Isolation stricte en mémoire
os.environ["FLASK_ENV"] = "testing"
os.environ["TESTING"] = "True"
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
os.environ["WTF_CSRF_ENABLED"] = "False"
os.environ["USE_SSH_TUNNEL"] = "false"
os.environ["HASH_SECRET_KEY"] = "test-secret-key-for-audit-security-tests-12345"

# Mock Weasyprint
mock_weasyprint = MagicMock()
mock_weasyprint.HTML = MagicMock()
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint

from app import create_app
from models import (
    CglWaiver,
    Contact,
    Production,
    Project,
    SafetyRulesWaiver,
    SignatureEvent,
    User,
    WaiverSignedDocument,
    WaiverToken,
    db,
)
from services.admin.waivers import (
    create_cgl,
    generate_cgl,
    create_safety_rules_waiver,
    generate_safety_rules_waiver,
    get_or_create_waiver_signing_url,
)

from utils.document_utils import (
    compute_canonical_seal,
    compute_file_sha256,
    verify_canonical_seal,
)
from utils.signature_storage import save_signature_image


def _generate_valid_png_base64() -> str:
    """Génère un véritable binaire PNG valide encodé en base64."""
    img = Image.new("RGBA", (120, 60), color=(0, 0, 0, 0))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64_str}"


class SignatureSecurityHardeningTest(unittest.TestCase):
    """Tests rigoureux de la chaîne de scellement et de la piste d'audit."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.app.config["OUTPUT_FOLDER"] = self.temp_dir
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_signature_events_immutability(self):
        """Vérifie que la table d'audit signature_events est en append-only strict."""
        with self.app.app_context():
            event = SignatureEvent(
                document_id="BVRA-2026-TEST1",
                mode="cgl",
                event_type="document_signed",
                ip="192.168.1.50",
                user_agent="Mozilla/5.0 Test",
                details={"signer": "Jean Dupont", "role": "Directeur"},
            )
            db.session.add(event)
            db.session.commit()
            self.assertIsNotNone(event.id)

            # 1. Tentative d'UPDATE interdite
            event.ip = "10.0.0.1"
            with self.assertRaises(RuntimeError) as ctx_update:
                db.session.commit()
            self.assertIn("Table immuable en écriture seule", str(ctx_update.exception))
            db.session.rollback()

            # 2. Tentative de DELETE interdite
            event_persisted = db.session.get(SignatureEvent, event.id)
            db.session.delete(event_persisted)
            with self.assertRaises(RuntimeError) as ctx_delete:
                db.session.commit()
            self.assertIn("Table immuable en écriture seule", str(ctx_delete.exception))
            db.session.rollback()

    def test_save_signature_image_strict_validation(self):
        """Vérifie la validation stricte des signatures (format PNG, magic bytes, Pillow, taille)."""
        valid_b64 = _generate_valid_png_base64()

        with self.app.app_context():
            # Succès avec un PNG valide
            rel_path = save_signature_image(valid_b64, "waivers", "BVRA-TEST-SEC-1")
            full_path = os.path.join(self.temp_dir, rel_path)
            self.assertTrue(os.path.exists(full_path))

            # Échec : Faux PNG (octets magiques non conformes)
            corrupted_b64 = "data:image/jpeg;base64," + base64.b64encode(b"NOT_A_PNG_HEADER_DATA").decode("utf-8")
            with self.assertRaises(ValueError) as ctx_svg:
                save_signature_image(corrupted_b64, "waivers", "BVRA-TEST-SEC-2")
            self.assertIn("format", str(ctx_svg.exception).lower())
            self.assertIn("invalide", str(ctx_svg.exception).lower())

            # Échec : Faux PNG (octets magiques non conformes)
            fake_png_bytes = b"NOT_A_PNG_HEADER_DATA"
            fake_b64 = f"data:image/png;base64,{base64.b64encode(fake_png_bytes).decode('utf-8')}"
            with self.assertRaises(ValueError) as ctx_fake:
                save_signature_image(fake_b64, "waivers", "BVRA-TEST-SEC-3")
            self.assertIn("format", str(ctx_fake.exception).lower())

            # Échec : Signature trop volumineuse (> 500 KB)
            large_bytes = b"\x89PNG\r\n\x1a\n" + (b"0" * (505 * 1024))
            large_b64 = f"data:image/png;base64,{base64.b64encode(large_bytes).decode('utf-8')}"
            with self.assertRaises(ValueError) as ctx_large:
                save_signature_image(large_b64, "waivers", "BVRA-TEST-SEC-4")
            self.assertIn("trop volumineuse", str(ctx_large.exception))

    def test_canonical_seal_determinism_and_tampering(self):
        """Vérifie le caractère déterministe du sceau canonique et la sensibilité aux modifications."""
        payload_1 = {
            "version": "2.0",
            "document_id": "BVRA-2026-999",
            "signer": "Jean Dupont",
            "role": "Directeur de Production",
            "details": {"amount": 5000, "currency": "EUR"},
        }
        # Même dictionnaire avec ordre des clés inversé
        payload_2 = {
            "details": {"currency": "EUR", "amount": 5000},
            "role": "Directeur de Production",
            "signer": "Jean Dupont",
            "document_id": "BVRA-2026-999",
            "version": "2.0",
        }

        seal_1 = compute_canonical_seal(payload_1)
        seal_2 = compute_canonical_seal(payload_2)
        self.assertEqual(seal_1, seal_2, "Le sceau canonique doit être indépendant de l'ordre des clés")
        self.assertTrue(verify_canonical_seal(seal_1, payload_1))

        # Falsification : altération d'une seule valeur
        tampered_payload = dict(payload_1)
        tampered_payload["role"] = "Gérant Fictif"
        self.assertFalse(verify_canonical_seal(seal_1, tampered_payload), "Une altération doit invalider le sceau")

    def test_b2b_signing_authority_and_consent_enforcement(self):
        """Vérifie que la signature CGL exige le mandat légal B2B et les cases de consentement."""
        with self.app.app_context():
            user = User(firstname="Admin", lastname="BV", mail="admin@bv.test", role="administrator")
            prod = Production(name="Studio Films 7")
            db.session.add_all([user, prod])
            db.session.flush()

            contact = Contact(first_name="Alice", last_name="Dubois", mail="alice@studio.com", production_id=prod.id)
            project = Project(name="Projet Hardening", production_id=prod.id, production_contact_id=contact.id)
            db.session.add_all([contact, project])
            db.session.flush()

            success, msg = create_cgl(project.id)
            self.assertTrue(success)
            cgl = CglWaiver.query.filter_by(project_id=project.id).first()
            generate_cgl(cgl.waiver_id)
            _, sign_url = get_or_create_waiver_signing_url(cgl.waiver_id, waiver_type="cgl")
            token = sign_url.split("/")[-1]

            valid_sig = _generate_valid_png_base64()

            # 1. Manque déclaration de pouvoir (signing authority)
            res1 = self.client.post(
                f"/sign/cgl/{token}",
                data={
                    "signature": valid_sig,
                    "representative": "Alice Dubois",
                    "representative_role": "Directrice",
                    "accepted_terms": "1",
                    # has_signing_authority omis
                },
            )
            self.assertEqual(res1.status_code, 400)
            self.assertIn("pouvoir", res1.get_json().get("error", "").lower())

            # 2. Manque acceptation des CGL
            res2 = self.client.post(
                f"/sign/cgl/{token}",
                data={
                    "signature": valid_sig,
                    "representative": "Alice Dubois",
                    "representative_role": "Directrice",
                    "has_signing_authority": "1",
                    # accepted_terms omis
                },
            )
            self.assertEqual(res2.status_code, 400)
            self.assertIn("acceptation", res2.get_json().get("error", "").lower())

            # 3. Manque le nom ou la qualité du représentant
            res3 = self.client.post(
                f"/sign/cgl/{token}",
                data={
                    "signature": valid_sig,
                    "representative": "",
                    "representative_role": "",
                    "accepted_terms": "1",
                    "has_signing_authority": "1",
                },
            )
            self.assertEqual(res3.status_code, 400)
            self.assertIn("fonction", res3.get_json().get("error", "").lower())

            # 4. Succès avec toutes les déclarations complètes
            res4 = self.client.post(
                f"/sign/cgl/{token}",
                data={
                    "signature": valid_sig,
                    "representative": "Alice Dubois",
                    "representative_role": "Présidente Directrice Générale",
                    "accepted_terms": "1",
                    "has_signing_authority": "1",
                    "authority_declaration_text": "Je certifie sur l'honneur être dûment habilitée.",
                },
            )
            self.assertEqual(res4.status_code, 200)
            data = res4.get_json()
            self.assertTrue(data.get("success"))

            # Vérifier l'invalidation du token à usage unique (consommé avec signature enregistrée)
            token_in_db = db.session.get(WaiverToken, token)
            self.assertIsNotNone(token_in_db)
            self.assertIsNotNone(token_in_db.signature, "Le token doit être marqué comme consommé avec sa signature")

            # Vérifier que le rechargement GET affiche bien la page de confirmation signée
            get_res = self.client.get(f"/sign/cgl/{token}")
            self.assertEqual(get_res.status_code, 200)
            self.assertIn("CGL Signées", get_res.get_data(as_text=True))

            # Vérifier qu'une tentative de rejeu POST est rejetée
            res_replay = self.client.post(
                f"/sign/cgl/{token}",
                data={
                    "signature": valid_sig,
                    "representative": "Alice Dubois",
                    "representative_role": "PDG",
                    "accepted_terms": "1",
                    "has_signing_authority": "1",
                },
            )
            self.assertEqual(res_replay.status_code, 400)
            self.assertIn("déjà été signé", res_replay.get_json().get("error", ""))

            # Vérifier la présence des événements d'audit
            events = SignatureEvent.query.filter_by(document_id=cgl.waiver_id).all()
            event_types = [e.event_type for e in events]
            self.assertIn("consent_recorded", event_types)
            self.assertIn("document_signed", event_types)

    def test_document_verification_png_tampering(self):
        """Vérifie que l'altération physique du PNG de signature sur disque invalide la vérification."""
        with self.app.app_context():
            user = User(firstname="Admin", lastname="BV", mail="admin2@bv.test", role="administrator")
            prod = Production(name="Alpha Cinema")
            db.session.add_all([user, prod])
            db.session.flush()

            contact = Contact(first_name="Bob", last_name="Martin", mail="bob@alpha.com", production_id=prod.id)
            project = Project(name="Film Verification", production_id=prod.id, production_contact_id=contact.id)
            db.session.add_all([contact, project])
            db.session.flush()

            success, msg = create_cgl(project.id)
            self.assertTrue(success)
            cgl = CglWaiver.query.filter_by(project_id=project.id).first()
            generate_cgl(cgl.waiver_id)
            waiver_id = str(cgl.waiver_id)
            _, sign_url = get_or_create_waiver_signing_url(cgl.waiver_id, waiver_type="cgl")
            token = sign_url.split("/")[-1]

            valid_sig = _generate_valid_png_base64()
            res = self.client.post(
                f"/sign/cgl/{token}",
                data={
                    "signature": valid_sig,
                    "representative": "Bob Martin",
                    "representative_role": "Gérant",
                    "accepted_terms": "1",
                    "has_signing_authority": "1",
                },
            )
            self.assertEqual(res.status_code, 200)

            # 1. Consultation de la page de vérification -> Sceau valide
            signed_doc = WaiverSignedDocument.query.filter_by(waiver_id=waiver_id).first()
            self.assertIsNotNone(signed_doc)

            verify_res1 = self.client.get(f"/cgl/verify/{waiver_id}")
            self.assertEqual(verify_res1.status_code, 200)
            self.assertIn("sceau cryptographique", verify_res1.get_data(as_text=True).lower())

            # 2. Altération malveillante du PNG sur disque
            sig_file_path = os.path.join(self.temp_dir, signed_doc.signature.lstrip("/"))
            self.assertTrue(os.path.exists(sig_file_path))
            with open(sig_file_path, "wb") as f:
                f.write(b"CORRUPTED_TAMPERED_SIGNATURE_CONTENT")

            # 3. La page de vérification doit maintenant détecter l'altération et afficher un sceau invalide
            verify_res2 = self.client.get(f"/cgl/verify/{waiver_id}")
            self.assertEqual(verify_res2.status_code, 200)
            verify_html = verify_res2.get_data(as_text=True)
            self.assertIn("sceau invalide", verify_html.lower())

    def test_verify_page_pdf_upload_authenticity_check(self):
        """Vérifie l'authentification physique d'un PDF téléversé sur la page /verify (valide vs falsifié)."""
        from utils.document_utils import compute_pdf_hash

        with self.app.app_context():
            prod = Production(name="Upload Prod")
            db.session.add(prod)
            db.session.flush()
            contact = Contact(first_name="Alice", last_name="Dupont", mail="alice@upload.com", production_id=prod.id)
            project = Project(name="Film Upload Verify", production_id=prod.id, production_contact_id=contact.id)
            db.session.add_all([contact, project])
            db.session.flush()

            success, msg = create_cgl(project.id)
            self.assertTrue(success)
            cgl = CglWaiver.query.filter_by(project_id=project.id).first()
            generate_cgl(cgl.waiver_id)
            waiver_id = str(cgl.waiver_id)
            _, sign_url = get_or_create_waiver_signing_url(cgl.waiver_id, waiver_type="cgl")
            token = sign_url.split("/")[-1]

            valid_sig = _generate_valid_png_base64()
            res = self.client.post(
                f"/sign/cgl/{token}",
                data={
                    "signature": valid_sig,
                    "representative": "Alice Dupont",
                    "representative_role": "Directrice",
                    "accepted_terms": "1",
                    "has_signing_authority": "1",
                },
            )
            self.assertEqual(res.status_code, 200)

            signed_doc = WaiverSignedDocument.query.filter_by(waiver_id=waiver_id).first()
            self.assertIsNotNone(signed_doc)

            # Attribution de l'empreinte d'un PDF de test authentique
            authentic_pdf_content = b"%PDF-1.4 authentic pdf content for unit test"
            signed_doc.pdf_file_hash = compute_pdf_hash(authentic_pdf_content)
            db.session.commit()

            # 1. Upload du PDF authentique -> Détection positive
            data_authentic = {
                "pdf": (io.BytesIO(authentic_pdf_content), "authentic_cgl.pdf")
            }
            res_post_auth = self.client.post(
                f"/cgl/verify/{waiver_id}",
                data=data_authentic,
                content_type="multipart/form-data"
            )
            self.assertEqual(res_post_auth.status_code, 200)
            html_auth = res_post_auth.get_data(as_text=True)
            self.assertIn("Fichier PDF authentique", html_auth)

            # 2. Upload d'un PDF altéré ou falsifié -> Détection négative
            tampered_pdf_content = b"%PDF-1.4 TAMPERED corrupted and modified pdf content"
            data_tampered = {
                "pdf": (io.BytesIO(tampered_pdf_content), "tampered_cgl.pdf")
            }
            res_post_tamp = self.client.post(
                f"/cgl/verify/{waiver_id}",
                data=data_tampered,
                content_type="multipart/form-data"
            )
            self.assertEqual(res_post_tamp.status_code, 200)
            html_tamp = res_post_tamp.get_data(as_text=True)
            self.assertIn("Fichier PDF non authentique", html_tamp)

    def test_link_opened_event_persisted_in_independent_session(self):
        """Vérifie que la consultation GET d'un lien de signature enregistre et persiste l'événement link_opened."""
        with self.app.app_context():
            prod = Production(name="Audit Link Prod")
            db.session.add(prod)
            db.session.flush()
            contact = Contact(first_name="Jean", last_name="Lien", mail="jean@lien.com", production_id=prod.id)
            project = Project(name="Projet Audit Lien", production_id=prod.id, production_contact_id=contact.id)
            db.session.add_all([contact, project])
            db.session.flush()

            success, msg = create_cgl(project.id)
            self.assertTrue(success)
            cgl = CglWaiver.query.filter_by(project_id=project.id).first()
            generate_cgl(cgl.waiver_id)
            _, sign_url = get_or_create_waiver_signing_url(cgl.waiver_id, waiver_type="cgl")
            token = sign_url.split("/")[-1]

            # GET sur le lien de signature
            res = self.client.get(f"/sign/cgl/{token}")
            self.assertEqual(res.status_code, 200)

            # Vérification de la persistance en base
            db.session.expire_all()
            opened_event = SignatureEvent.query.filter_by(
                document_id=cgl.waiver_id,
                event_type="link_opened"
            ).first()
            self.assertIsNotNone(opened_event, "L'événement link_opened doit être persisté en base après GET")
            self.assertEqual(opened_event.mode, "cgl")

    def test_signature_events_cryptographic_chaining(self):
        """Vérifie le chaînage cryptographique SHA-256 entre événements d'audit successifs."""
        with self.app.app_context():
            from services.common.signatures import log_signature_event
            doc_id = "BVRA-CHAIN-TEST-1"
            ev1 = log_signature_event(doc_id, "cgl", "link_generated", {"token": "tok1"})
            ev2 = log_signature_event(doc_id, "cgl", "link_opened", {"ip": "1.2.3.4"})
            ev3 = log_signature_event(doc_id, "cgl", "document_signed", {"signer": "Test Signer"})

            db.session.commit()
            self.assertIsNotNone(ev1.event_hash)
            self.assertIsNone(ev1.previous_event_hash)

            self.assertEqual(ev2.previous_event_hash, ev1.event_hash)
            self.assertIsNotNone(ev2.event_hash)

            self.assertEqual(ev3.previous_event_hash, ev2.event_hash)
            self.assertIsNotNone(ev3.event_hash)

    def test_bvsr_consent_validation(self):
        """Vérifie que la signature BVSR exige obligatoirement ack_rules et ack_authority."""
        with self.app.app_context():
            prod = Production(name="BVSR Consent Prod")
            db.session.add(prod)
            db.session.flush()
            contact = Contact(first_name="Paul", last_name="Secu", mail="paul@secu.com", production_id=prod.id)
            project = Project(name="Tournage Securite", production_id=prod.id, production_contact_id=contact.id)
            db.session.add_all([contact, project])
            db.session.flush()

            success, msg = create_safety_rules_waiver(project.id)
            self.assertTrue(success)
            sr = SafetyRulesWaiver.query.filter_by(project_id=project.id).first()
            generate_safety_rules_waiver(sr.waiver_id)
            _, sign_url = get_or_create_waiver_signing_url(sr.waiver_id, waiver_type="safety_rules")
            token = sign_url.split("/")[-1]

            valid_sig = _generate_valid_png_base64()

            # 1. Échec : manque ack_rules
            res1 = self.client.post(
                f"/sign/safety-rules/{token}",
                data={
                    "signature": valid_sig,
                    "first_name": "Paul",
                    "last_name": "Secu",
                    "ack_authority": "1",
                },
            )
            self.assertEqual(res1.status_code, 400)
            self.assertIn("règles de sécurité", res1.get_json().get("error", "").lower())

            # 2. Échec : manque ack_authority
            res2 = self.client.post(
                f"/sign/safety-rules/{token}",
                data={
                    "signature": valid_sig,
                    "first_name": "Paul",
                    "last_name": "Secu",
                    "ack_rules": "1",
                },
            )
            self.assertEqual(res2.status_code, 400)
            self.assertIn("interruption", res2.get_json().get("error", "").lower())

            # 3. Succès avec les deux consentements
            res3 = self.client.post(
                f"/sign/safety-rules/{token}",
                data={
                    "signature": valid_sig,
                    "first_name": "Paul",
                    "last_name": "Secu",
                    "ack_rules": "1",
                    "ack_authority": "1",
                },
            )
            self.assertEqual(res3.status_code, 200)

            # Vérification de l'événement consent_recorded pour BVSR
            consent_ev = SignatureEvent.query.filter_by(
                document_id=sr.waiver_id,
                event_type="consent_recorded"
            ).first()
            self.assertIsNotNone(consent_ev)
            self.assertTrue(consent_ev.details.get("ack_rules"))
            self.assertTrue(consent_ev.details.get("ack_authority"))

    def test_cgl_field_validations_siret_and_email(self):
        """Vérifie la validation stricte côté serveur du SIRET et du format d'email pour les CGL."""
        with self.app.app_context():
            prod = Production(name="Validation Fields Prod")
            db.session.add(prod)
            db.session.flush()
            contact = Contact(first_name="Eva", last_name="Val", mail="eva@fields.com", production_id=prod.id)
            project = Project(name="Projet Validation", production_id=prod.id, production_contact_id=contact.id)
            db.session.add_all([contact, project])
            db.session.flush()

            success, msg = create_cgl(project.id)
            self.assertTrue(success)
            cgl = CglWaiver.query.filter_by(project_id=project.id).first()
            generate_cgl(cgl.waiver_id)
            _, sign_url = get_or_create_waiver_signing_url(cgl.waiver_id, waiver_type="cgl")
            token = sign_url.split("/")[-1]

            valid_sig = _generate_valid_png_base64()

            # SIRET invalide (< 14 chiffres)
            res_bad_siret = self.client.post(
                f"/sign/cgl/{token}",
                data={
                    "signature": valid_sig,
                    "representative": "Eva Val",
                    "representative_role": "Directrice",
                    "accepted_terms": "1",
                    "has_signing_authority": "1",
                    "siret": "123456789",  # 9 chiffres au lieu de 14
                },
            )
            self.assertEqual(res_bad_siret.status_code, 400)
            self.assertIn("siret", res_bad_siret.get_json().get("error", "").lower())

            # Email invalide
            res_bad_email = self.client.post(
                f"/sign/cgl/{token}",
                data={
                    "signature": valid_sig,
                    "representative": "Eva Val",
                    "representative_role": "Directrice",
                    "accepted_terms": "1",
                    "has_signing_authority": "1",
                    "email": "not-an-email",
                },
            )
            self.assertEqual(res_bad_email.status_code, 400)
            self.assertIn("e-mail", res_bad_email.get_json().get("error", "").lower())

    def test_insurance_upload_magic_bytes_check(self):
        """Vérifie le filtrage strict des magic bytes lors du téléversement de l'attestation d'assurance."""
        with self.app.app_context():
            prod = Production(name="Insurance Upload Prod")
            db.session.add(prod)
            db.session.flush()
            contact = Contact(first_name="Luc", last_name="Assur", mail="luc@assur.com", production_id=prod.id)
            project = Project(name="Projet Assurance", production_id=prod.id, production_contact_id=contact.id)
            db.session.add_all([contact, project])
            db.session.flush()

            success, msg = create_cgl(project.id)
            self.assertTrue(success)
            cgl = CglWaiver.query.filter_by(project_id=project.id).first()
            generate_cgl(cgl.waiver_id)
            _, sign_url = get_or_create_waiver_signing_url(cgl.waiver_id, waiver_type="cgl")
            token = sign_url.split("/")[-1]

            valid_sig = _generate_valid_png_base64()

            # Faux PDF avec octets exécutables malveillants
            fake_pdf = (io.BytesIO(b"MZ\x90\x00\x03\x00fake_executable_disguised_as_pdf"), "attestation.pdf")
            res_fake = self.client.post(
                f"/sign/cgl/{token}",
                data={
                    "signature": valid_sig,
                    "representative": "Luc Assur",
                    "representative_role": "Directeur",
                    "accepted_terms": "1",
                    "has_signing_authority": "1",
                    "production_insurance": fake_pdf,
                },
                content_type="multipart/form-data"
            )
            self.assertEqual(res_fake.status_code, 400)
            self.assertIn("non reconnue", res_fake.get_json().get("error", "").lower())

            # Vrai PDF avec signature %PDF valide
            real_pdf = (io.BytesIO(b"%PDF-1.4\nvalid pdf content for insurance unit test\n%%EOF"), "attestation.pdf")
            res_real = self.client.post(
                f"/sign/cgl/{token}",
                data={
                    "signature": valid_sig,
                    "representative": "Luc Assur",
                    "representative_role": "Directeur",
                    "accepted_terms": "1",
                    "has_signing_authority": "1",
                    "production_insurance": real_pdf,
                },
                content_type="multipart/form-data"
            )
            self.assertEqual(res_real.status_code, 200)

    def test_sealed_document_overwrite_protection(self):
        """Vérifie que finalize_signed_document refuse d'écraser un document déjà scellé."""
        from services.common.signatures import finalize_signed_document
        with self.app.app_context():
            prod = Production(name="Overwrite Prod")
            db.session.add(prod)
            db.session.flush()
            contact = Contact(first_name="Max", last_name="Doc", mail="max@doc.com", production_id=prod.id)
            project = Project(name="Projet Overwrite", production_id=prod.id, production_contact_id=contact.id)
            db.session.add_all([contact, project])
            db.session.flush()

            success, msg = create_cgl(project.id)
            self.assertTrue(success)
            cgl = CglWaiver.query.filter_by(project_id=project.id).first()
            generate_cgl(cgl.waiver_id)

            sig1 = _generate_valid_png_base64()

            # Création du premier document signé scellé
            with self.app.test_request_context():
                res1 = finalize_signed_document(
                    mode="cgl",
                    record_id=cgl.id,
                    signature_data=sig1,
                    signed_ip="10.0.0.1",
                )
                self.assertIsNotNone(res1)
                self.assertIn("hash", res1)

                # Deuxième image de signature différente
                img2 = Image.new("RGBA", (150, 75), color=(255, 0, 0, 128))
                buf2 = io.BytesIO()
                img2.save(buf2, format="PNG")
                sig2 = f"data:image/png;base64,{base64.b64encode(buf2.getvalue()).decode('utf-8')}"

                # Tentative d'écrasement avec une signature différente sans contresignature BV -> doit lever ValueError
                with self.assertRaises(ValueError) as ctx:
                    finalize_signed_document(
                        mode="cgl",
                        record_id=cgl.id,
                        signature_data=sig2,
                        signed_ip="10.0.0.2",
                    )
                self.assertIn("écrasement de la signature d'origine est interdit", str(ctx.exception).lower())

    def test_download_security_headers_and_attachment(self):
        """Vérifie que le téléchargement de pièces jointes applique nosniff et Content-Disposition attachment."""
        from utils.document_utils import generate_pdf_access_token
        with self.app.app_context():
            # Créer un fichier de test dans OUTPUT_FOLDER
            att_dir = os.path.join(self.temp_dir, "waivers", "attachments")
            os.makedirs(att_dir, exist_ok=True)
            test_file_path = os.path.join(att_dir, "test_assurance.pdf")
            with open(test_file_path, "wb") as f:
                f.write(b"%PDF-1.4 test insurance content")

            rel_path = "waivers/attachments/test_assurance.pdf"
            token = generate_pdf_access_token(rel_path)

            res = self.client.get(f"/cgl/attachment/{rel_path}?t={token}")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
            disposition = res.headers.get("Content-Disposition", "")
            self.assertIn("attachment", disposition)
            self.assertIn("test_assurance.pdf", disposition)
            res.close()


    def test_production_hmac_secret_startup_check(self):
        """Vérifie que create_app lève une exception fatale en production si la clé HMAC est manquante."""
        orig_env = os.environ.get("FLASK_ENV")
        orig_hmac = os.environ.get("HASH_SECRET_KEY")
        orig_sec = os.environ.get("SECRET_KEY")

        try:
            os.environ["FLASK_ENV"] = "production"
            os.environ["HASH_SECRET_KEY"] = "dev-only-insecure-key-change-in-production"
            os.environ["SECRET_KEY"] = "dev-only-insecure-key-change-in-production"

            with self.assertRaises(RuntimeError) as ctx:
                create_app()
            self.assertIn("HASH_SECRET_KEY", str(ctx.exception))
        finally:
            if orig_env:
                os.environ["FLASK_ENV"] = orig_env
            else:
                os.environ.pop("FLASK_ENV", None)
            if orig_hmac:
                os.environ["HASH_SECRET_KEY"] = orig_hmac
            else:
                os.environ.pop("HASH_SECRET_KEY", None)
            if orig_sec:
                os.environ["SECRET_KEY"] = orig_sec
            else:
                os.environ.pop("SECRET_KEY", None)


if __name__ == "__main__":
    unittest.main()

