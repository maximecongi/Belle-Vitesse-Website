"""
Suite de tests de sécurité et de robustesse pour le système de signature électronique durci :
1. Immuabilité stricte de la table d'audit `signature_events` (append-only, interdiction UPDATE / DELETE).
2. Validation stricte du format binaire PNG de la signature (magic bytes, Pillow, limite de taille 500 KB).
3. Déterminisme du sceau canonique HMAC-SHA256 et détection de falsification.
4. Déclaration obligatoire de mandat social B2B et consentement contractuel.
5. Détection d'altération physique du fichier PNG lors de la vérification.
"""

import base64
import hashlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

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
    generate_document_verification_token,
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
        self.app.config["SERVER_NAME"] = "localhost"
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _verification_url(self, route_base, mode, document_id, signed_doc):
        version = int(getattr(signed_doc, "version", 1))
        token = generate_document_verification_token(
            mode, str(document_id), version, signed_doc.hash
        )
        return f"/{route_base}/verify/{document_id}?version={version}&t={token}"

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

            verify_url = self._verification_url("cgl", "cgl", waiver_id, signed_doc)
            self.assertEqual(self.client.get(f"/cgl/verify/{waiver_id}").status_code, 404)
            verify_res1 = self.client.get(verify_url)
            self.assertEqual(verify_res1.status_code, 200)
            self.assertIn("sceau cryptographique", verify_res1.get_data(as_text=True).lower())

            # 2. Altération malveillante du PNG sur disque
            sig_file_path = os.path.join(self.temp_dir, signed_doc.signature.lstrip("/"))
            self.assertTrue(os.path.exists(sig_file_path))
            with open(sig_file_path, "wb") as f:
                f.write(b"CORRUPTED_TAMPERED_SIGNATURE_CONTENT")

            # 3. La page de vérification doit maintenant détecter l'altération et afficher un sceau invalide
            verify_res2 = self.client.get(verify_url)
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
            verify_url = self._verification_url("cgl", "cgl", waiver_id, signed_doc)
            res_post_auth = self.client.post(
                verify_url,
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
                verify_url,
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


    def test_concurrent_signing_lock_and_stale_recovery(self):
        """Vérifie le blocage 409 en cours de signature et la reprise automatique après expiration du verrou (>10 min)."""
        with self.app.app_context():
            prod = Production(name="Lock Prod")
            db.session.add(prod)
            db.session.flush()
            contact = Contact(first_name="Verrou", last_name="Test", mail="verrou@test.com", production_id=prod.id)
            project = Project(name="Projet Verrou", production_id=prod.id, production_contact_id=contact.id)
            db.session.add_all([contact, project])
            db.session.flush()

            success, msg = create_cgl(project.id)
            self.assertTrue(success)
            cgl = CglWaiver.query.filter_by(project_id=project.id).first()
            generate_cgl(cgl.waiver_id)
            _, sign_url = get_or_create_waiver_signing_url(cgl.waiver_id, waiver_type="cgl")
            token = sign_url.split("/")[-1]

            # 1. Simuler un verrou actif 'signing' posé il y a 1 minute
            cgl.status = "signing"
            cgl.sign_data = {"signing_started_at": datetime.now(timezone.utc).isoformat()}
            db.session.commit()

            res_locked = self.client.post(
                f"/sign/cgl/{token}",
                data={
                    "signature": _generate_valid_png_base64(),
                    "representative": "Verrou Test",
                    "representative_role": "Directeur",
                    "accepted_terms": "1",
                    "has_signing_authority": "1",
                }
            )
            self.assertEqual(res_locked.status_code, 409)
            self.assertIn("déjà en cours de traitement", res_locked.get_json().get("error", ""))

            # 2. Simuler un verrou périmé (> 10 minutes)
            old_dt = datetime.now(timezone.utc) - timedelta(minutes=15)
            cgl.sign_data = {"signing_started_at": old_dt.isoformat()}
            db.session.commit()

            with patch("services.common.pdf_tasks.render_pdf_from_template", return_value=b"%PDF-1.4 mock"):
                res_recovered = self.client.post(
                    f"/sign/cgl/{token}",
                    data={
                        "signature": _generate_valid_png_base64(),
                        "representative": "Verrou Test",
                        "representative_role": "Directeur",
                        "accepted_terms": "1",
                        "has_signing_authority": "1",
                    }
                )
            self.assertEqual(res_recovered.status_code, 200)
            db.session.refresh(cgl)
            self.assertEqual(cgl.status, "signed")

    def test_key_rotation_kid_support(self):
        """Vérifie le support de la rotation de clés cryptographiques via kid et HASH_SECRET_KEY_{KID}."""
        from utils.document_utils import compute_canonical_seal, verify_canonical_seal
        orig_v2 = os.environ.get("HASH_SECRET_KEY_V2")
        try:
            os.environ["HASH_SECRET_KEY_V2"] = "super-secret-rotation-key-v2-bellevitesse"
            payload_v1 = {"doc_id": "TEST-1", "value": 42}
            payload_v2 = {"_seal_kid": "v2", "doc_id": "TEST-1", "value": 42}

            seal_v1 = compute_canonical_seal(payload_v1)
            seal_v2 = compute_canonical_seal(payload_v2)

            self.assertNotEqual(seal_v1, seal_v2)
            self.assertTrue(verify_canonical_seal(seal_v1, payload_v1))
            self.assertTrue(verify_canonical_seal(seal_v2, payload_v2))
        finally:
            if orig_v2:
                os.environ["HASH_SECRET_KEY_V2"] = orig_v2
            else:
                os.environ.pop("HASH_SECRET_KEY_V2", None)

    def test_token_redaction_in_audit_events(self):
        """Vérifie que les jetons bruts sont masqués dans signature_events (token_preview + sha256)."""
        from models.signature_event import SignatureEvent
        with self.app.app_context():
            prod = Production(name="Token Redaction Prod")
            db.session.add(prod)
            db.session.flush()
            contact = Contact(first_name="Redact", last_name="Token", mail="redact@token.com", production_id=prod.id)
            project = Project(name="Projet Redaction", production_id=prod.id, production_contact_id=contact.id)
            db.session.add_all([contact, project])
            db.session.flush()

            success, msg = create_cgl(project.id)
            cgl = CglWaiver.query.filter_by(project_id=project.id).first()
            generate_cgl(cgl.waiver_id)
            _, sign_url = get_or_create_waiver_signing_url(cgl.waiver_id, waiver_type="cgl")
            raw_token = sign_url.split("/")[-1]

            ev = SignatureEvent.query.filter_by(document_id=cgl.waiver_id, event_type="link_generated").first()
            self.assertIsNotNone(ev)
            self.assertNotIn("token", ev.details)
            self.assertIn("token_preview", ev.details)
            self.assertIn("token_sha256", ev.details)
            self.assertEqual(ev.details["token_preview"], f"{raw_token[:8]}...")
            self.assertEqual(ev.details["token_sha256"], hashlib.sha256(raw_token.encode("utf-8")).hexdigest())

    def test_signature_events_chain_tamper_detection(self):
        """Vérifie que la falsification d'un événement d'audit fait échouer verify_signature_events_chain."""
        from services.common.signatures import verify_signature_events_chain, log_signature_event
        from models.signature_event import SignatureEvent
        with self.app.app_context():
            doc_id = "BVRA-CHAIN-TEST-001"
            log_signature_event(doc_id, "cgl", "link_generated", {"admin": "test"})
            log_signature_event(doc_id, "cgl", "link_opened", {})
            log_signature_event(doc_id, "cgl", "document_signed", {"hash": "abc"})
            db.session.commit()

            # La chaîne intacte est valide
            res_ok = verify_signature_events_chain(doc_id)
            self.assertTrue(res_ok["valid"])
            self.assertEqual(res_ok["count"], 3)

            # Altérer un événement directement en SQL (contourner l'event listener)
            db.session.execute(
                db.text("UPDATE signature_events SET ip = '1.2.3.4' WHERE document_id = :d AND event_type = 'link_opened'"),
                {"d": doc_id}
            )
            db.session.commit()

            res_tampered = verify_signature_events_chain(doc_id)
            self.assertFalse(res_tampered["valid"])
            self.assertIn("Empreinte falsifiée", res_tampered.get("error", ""))

    def test_manual_status_change_forbidden_on_inspections(self):
        """Vérifie que le passage manuel au statut 'signed' est rejeté avec HTTP 400."""
        from models import CheckoutVehicle, CheckinVehicle, User
        from utils.jwt_auth import generate_token
        with self.app.app_context():
            user = User(firstname="Admin", lastname="User", mail="admin@bv.com", role="administrator")
            db.session.add(user)
            db.session.commit()

            co = CheckoutVehicle(status="in_progress", vehicle_id="1", inspection_number="BVCO-TEST-STAT1")
            ci = CheckinVehicle(status="in_progress", vehicle_id="1", inspection_number="BVCI-TEST-STAT1")
            db.session.add_all([co, ci])
            db.session.commit()
            co_id = co.id
            ci_id = ci.id

            auth_token = generate_token(user)
            headers = {"Authorization": f"Bearer {auth_token}"}

            # 1. Tentative PATCH checkout status = 'signed'
            res_co = self.client.patch(f"/api/v1/checkouts/{co_id}/status", json={"status": "signed"}, headers=headers)
            self.assertEqual(res_co.status_code, 400)
            self.assertIn("ne peut être obtenu que par scellement cryptographique", res_co.get_json()["error"])

            # 2. Tentative PATCH checkin status = 'signé'
            res_ci = self.client.patch(f"/api/v1/checkins/{ci_id}/status", json={"status": "signé"}, headers=headers)
            self.assertEqual(res_ci.status_code, 400)
            self.assertIn("ne peut être obtenu que par scellement cryptographique", res_ci.get_json()["error"])

            # 3. Statut normal permis
            res_valid = self.client.patch(f"/api/v1/checkouts/{co_id}/status", json={"status": "pending"}, headers=headers)
            self.assertEqual(res_valid.status_code, 200)

    def test_api_finalize_inspection_token_required_and_checks(self):
        """Vérifie que l'API de finalisation exige un token, bloque les bypass et contrôle la préparation."""
        from models import CheckoutVehicle, User
        from services.common.signatures import generate_inspection_token
        from utils.jwt_auth import generate_token
        with self.app.app_context():
            user = User(firstname="Admin", lastname="User", mail="admin@bv.com", role="administrator")
            db.session.add(user)
            db.session.commit()

            co = CheckoutVehicle(
                status="pending",
                vehicle_id="1",
                inspection_number="BVCO-TEST-FIN1",
                battery_level=50,
                vehicle_ready=False
            )
            db.session.add(co)
            db.session.commit()
            co_id = co.id

            auth_token = generate_token(user)
            headers = {"Authorization": f"Bearer {auth_token}"}

            sig_png = _generate_valid_png_base64()

            mock_fleet = [
                {"id": "1", "fields": {"name": "Test Car 1"}},
                {"id": "2", "fields": {"name": "Test Car 2"}},
            ]
            with patch("utils.database.get_vehicles", return_value=mock_fleet):
                # 1. Finalisation sans token -> HTTP 400
                res_no_token = self.client.post(f"/api/v1/checkouts/{co_id}/finalize", json={"signature_data": sig_png}, headers=headers)
                self.assertEqual(res_no_token.status_code, 400)
                self.assertIn("jeton de validation", res_no_token.get_json()["error"])

                # 2. Tentative de génération d'un token sur un véhicule non prêt (batterie 50%) -> rejet précoce (ValueError)
                with self.assertRaises(ValueError) as ctx_err:
                    generate_inspection_token(co_id, "checkout")
                self.assertIn("le véhicule n'est pas prêt", str(ctx_err.exception))

                # 3. Rendre le véhicule prêt (batterie 100%, vehicle_ready True et checkpoints OK)
                co_record = db.session.get(CheckoutVehicle, co_id)
                co_record.battery_level = 100
                co_record.vehicle_ready = True
                from utils.checkpoints import get_checkpoints_for_vehicle
                for cp in get_checkpoints_for_vehicle(co_record.vehicle_id):
                    co_record.set_checkpoint_status(cp["key"], "ok")
                db.session.commit()

                # 4. Génération valide une fois le véhicule prêt
                tok_data = generate_inspection_token(co_id, "checkout")
                token_str = tok_data["token"]

                # 5. Tentative avec token appartenant à un autre enregistrement (mismatch)
                co2 = CheckoutVehicle(status="pending", vehicle_id="2", inspection_number="BVCO-TEST-FIN2")
                db.session.add(co2)
                db.session.commit()
                res_mismatch = self.client.post(f"/api/v1/checkouts/{co2.id}/finalize", json={
                    "signature_data": sig_png,
                    "token": token_str
                }, headers=headers)
                self.assertEqual(res_mismatch.status_code, 400)
                self.assertIn("ne correspond pas à l'enregistrement", res_mismatch.get_json()["error"])

                # 6. Finalisation réussie avec les bons paramètres
                res_ok = self.client.post(f"/api/v1/checkouts/{co_id}/finalize", json={
                    "signature_data": sig_png,
                    "token": token_str
                }, headers=headers)
                self.assertEqual(res_ok.status_code, 200)

                # 7. Réutilisation du même token (anti-rejeu) -> HTTP 400
                res_reused = self.client.post(f"/api/v1/checkouts/{co_id}/finalize", json={
                    "signature_data": sig_png,
                    "token": token_str
                }, headers=headers)
                self.assertEqual(res_reused.status_code, 400)
                self.assertIn("déjà été utilisé", res_reused.get_json()["error"])

    def test_is_ready_strict_battery_and_checkpoint_rules(self):
        """Vérifie la rigueur fail-closed de _is_ready sur la batterie (>= 100) et les points de contrôle."""
        from services.admin.utils import _is_ready, compute_inspection_readiness

        # Pour un départ (is_checkout=True)
        # Batterie manquante (None) -> False
        self.assertFalse(_is_ready({}, is_checkout=True, battery_val=None))
        # Batterie invalide non convertible -> False
        self.assertFalse(_is_ready({}, is_checkout=True, battery_val="invalid"))
        # Batterie < 100 -> False
        self.assertFalse(_is_ready({}, is_checkout=True, battery_val=99))
        self.assertFalse(_is_ready({"battery_level": "99.5"}, is_checkout=True))

        valid_statuses = {
            "tires": "ok", "brakes": "ok", "fluid_levels": "ok",
            "bodywork": "ok", "lights": "ok", "cleanliness": "ok"
        }

        # 1. Régression : Véhicule absent -> Checkout STRICTEMENT REFUSÉ (Fail-Closed)
        # même si un dictionnaire arbitraire contient uniquement des 'ok'
        self.assertFalse(_is_ready(valid_statuses, vehicle_id=None, is_checkout=True, battery_val=100))
        ready, fails = compute_inspection_readiness(valid_statuses, vehicle_id=None, is_checkout=True, battery_val=100)
        self.assertFalse(ready)
        self.assertIn("Véhicule non sélectionné", fails)

        # 2. Régression : Véhicule non reconnu -> Checkout STRICTEMENT REFUSÉ
        self.assertFalse(_is_ready(valid_statuses, vehicle_id="unknown_veh_999", is_checkout=True, battery_val=100))
        ready_unk, fails_unk = compute_inspection_readiness(valid_statuses, vehicle_id="unknown_veh_999", is_checkout=True, battery_val=100)
        self.assertFalse(ready_unk)
        self.assertIn("Véhicule non reconnu", fails_unk)

        # 2 bis. Véhicule reconnu mais profil de checkpoints vide -> Checkout STRICTEMENT REFUSÉ
        with patch("services.admin.utils.is_known_vehicle", return_value=True), \
             patch("services.admin.utils.get_checkpoints_for_vehicle", return_value=[]):
            self.assertFalse(_is_ready(valid_statuses, vehicle_id="known_veh_no_profile", is_checkout=True, battery_val=100))
            ready_no_prof, fails_no_prof = compute_inspection_readiness(valid_statuses, vehicle_id="known_veh_no_profile", is_checkout=True, battery_val=100)
            self.assertFalse(ready_no_prof)
            self.assertIn("Profil de points de contrôle introuvable", fails_no_prof)

        # 3. Profil valide avec points OK -> Checkout accepté
        mock_cps = [
            {"key": "tires", "type": "status", "label": "Pneus"},
            {"key": "brakes", "type": "status", "label": "Freins"},
            {"key": "lights", "type": "status", "label": "Feux"},
        ]
        with patch("services.admin.utils.is_known_vehicle", return_value=True), \
             patch("services.admin.utils.get_checkpoints_for_vehicle", return_value=mock_cps):
            cps_ok = {"tires": "ok", "brakes": "ok", "lights": "ok"}
            self.assertTrue(_is_ready(cps_ok, vehicle_id="veh_valid", is_checkout=True, battery_val=100))

            # Point de contrôle non conforme -> Checkout refusé
            cps_nok = dict(cps_ok)
            cps_nok["brakes"] = "action_requise"
            self.assertFalse(_is_ready(cps_nok, vehicle_id="veh_valid", is_checkout=True, battery_val=100))

        # 4. Régression : Fallback permissif autorisé UNIQUEMENT hors checkout (ex: check-in direct)
        self.assertTrue(_is_ready(valid_statuses, vehicle_id=None, is_checkout=False, battery_val=50))

    def test_save_signature_image_strict_base64_and_path_validation(self):
        """Vérifie la suppression du bypass par chemin de fichier et la fonction validate_stored_signature_file."""
        from utils.signature_storage import save_signature_image, validate_stored_signature_file

        with self.app.app_context():
            # 1. Tenter de passer un chemin pour contourner le Base64 doit échouer
            with self.assertRaises(ValueError):
                save_signature_image("signatures/waivers/malicious.png", "waivers", "BVRA-BYPASS")

            # 2. validate_stored_signature_file sur fichier inexistant
            with self.assertRaises(ValueError) as ctx_missing:
                validate_stored_signature_file("signatures/waivers/non_existent.png")
            self.assertIn("introuvable", str(ctx_missing.exception))

            # 3. validate_stored_signature_file sur tentative de traversée de répertoire
            with self.assertRaises(ValueError) as ctx_traversal:
                validate_stored_signature_file("signatures/../../etc/passwd.png")
            self.assertTrue("interdite" in str(ctx_traversal.exception) or "non conforme" in str(ctx_traversal.exception))

    def test_verify_signature_events_chain_require_events_for_signed_doc(self):
        """Vérifie que verify_signature_events_chain échoue si require_events=True et qu'aucun événement n'existe."""
        from services.common.signatures import verify_signature_events_chain

        with self.app.app_context():
            # Sans require_events: valide par défaut
            res_default = verify_signature_events_chain("BVRA-EMPTY-CHAIN", require_events=False)
            self.assertTrue(res_default["valid"])
            self.assertEqual(res_default["count"], 0)

            # Avec require_events=True: invalide car aucun audit pour document scellé
            res_strict = verify_signature_events_chain("BVRA-EMPTY-CHAIN", require_events=True)
            self.assertFalse(res_strict["valid"])
            self.assertIn("Aucun événement d'audit", res_strict["error"])

    def test_create_checkin_requires_signed_checkout_document_or_force(self):
        """Vérifie que la création d'un checkin exige CheckoutSignedDocument avec hash valide."""
        from models import CheckoutVehicle, CheckoutSignedDocument, CheckinVehicle, User, Project, Production
        from services.admin.checkins import create_checkin

        with self.app.app_context():
            user = User(firstname="Admin", lastname="User", mail="admin@bv.com", role="administrator")
            prod = Production(name="Prod Test")
            db.session.add_all([user, prod])
            db.session.commit()

            proj = Project(name="Project Test", production_id=prod.id, departure_date=date.today(), return_date=date.today())
            db.session.add(proj)
            db.session.commit()

            # Checkout avec status = 'signed' mais AUCUN CheckoutSignedDocument
            co = CheckoutVehicle(
                status="signed",
                vehicle_id="VEH-TEST-99",
                project_id=proj.id,
                controller_id=user.id,
                inspection_number="BVCO-TEST-ARCHIVE-99"
            )
            db.session.add(co)
            db.session.commit()

            # 1. create_checkin sans force_checkin échoue
            form_data = {
                "project_id": str(proj.id),
                "vehicle_id": "VEH-TEST-99",
                "controller_id": str(user.id),
                "notes": "Test without force",
            }
            with self.assertRaises(ValueError) as ctx_fail:
                create_checkin(form_data)
            self.assertIn("Le départ de ce véhicule n'a pas été validé par une signature", str(ctx_fail.exception))

            # 2. create_checkin avec force_checkin réussit
            form_force = dict(form_data)
            form_force["force_checkin"] = "1"
            res_force = create_checkin(form_force)
            self.assertTrue(res_force)

            ci_record = CheckinVehicle.query.filter_by(vehicle_id="VEH-TEST-99").first()
            self.assertIsNotNone(ci_record)
            self.assertIn("Retour exceptionnel", ci_record.notes)

            # Nettoyage
            db.session.delete(ci_record)
            db.session.commit()

            # 3. Créer le CheckoutSignedDocument avec hash
            signed_archive = CheckoutSignedDocument(
                inspection_id="BVCO-TEST-ARCHIVE-99",
                hash="canonical_seal_hash_12345",
                data_snapshot={"version": "2.0"},
                signed_at=datetime.now(timezone.utc)
            )
            db.session.add(signed_archive)
            db.session.commit()

            # 4. Maintenant create_checkin sans force_checkin réussit !
            res_success = create_checkin(form_data)
            self.assertTrue(res_success)

    def test_global_security_headers_present_on_all_responses(self):
        """Vérifie que X-Content-Type-Options et X-Frame-Options sont présents sur toutes les routes (admin et public)."""
        res_public = self.client.get("/")
        self.assertEqual(res_public.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res_public.headers.get("X-Frame-Options"), "SAMEORIGIN")

        res_sign = self.client.get("/checkout/sign/nonexistent-token-xyz")
        self.assertEqual(res_sign.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res_sign.headers.get("X-Frame-Options"), "SAMEORIGIN")

    def test_cgl_verify_fails_when_insurance_file_is_tampered_or_missing(self):
        """Vérifie que handle_document_verify invalide le sceau si le fichier d'assurance est manquant ou altéré sur disque."""
        from models import CglWaiver, WaiverSignedDocument, Production, Project
        from routes.public.shared_docs import handle_document_verify

        with self.app.app_context():
            prod = Production(name="Prod Insurance Test")
            db.session.add(prod)
            db.session.commit()
            proj = Project(name="Project Insurance Test", production_id=prod.id, departure_date=date.today(), return_date=date.today())
            db.session.add(proj)
            db.session.commit()

            output_dir = self.temp_dir
            ins_rel_path = "attachments/cgl/test_insurance.pdf"
            full_ins_path = os.path.join(output_dir, ins_rel_path)
            os.makedirs(os.path.dirname(full_ins_path), exist_ok=True)
            with open(full_ins_path, "wb") as f:
                f.write(b"%PDF-1.4 original insurance content")

            expected_sha = compute_file_sha256(full_ins_path)
            sig_png = _generate_valid_png_base64()
            sig_rel_path = save_signature_image(sig_png, "waivers", "BVRA-INS-TEST")
            sig_full = os.path.join(output_dir, sig_rel_path)
            sig_sha = compute_file_sha256(sig_full)

            doc_id = "BVRA-INS-TEST"
            snapshot = {
                "insurance_file_sha256": expected_sha,
                "production_insurance_path": ins_rel_path,
                "project_name": "Test Insurance Project",
            }
            canonical_payload = {
                "version": "2.0",
                "_seal_kid": "v1",
                "mode": "cgl",
                "document_id": doc_id,
                "signed_at": datetime.now(timezone.utc).isoformat(),
                "signer_ip": "127.0.0.1",
                "signature_sha256": sig_sha,
                "insurance_file_sha256": expected_sha,
                "snapshot": snapshot,
            }
            seal_hash = compute_canonical_seal(canonical_payload)

            waiver = CglWaiver(
                waiver_id=doc_id,
                project_id=proj.id,
                status="signed",
                production_insurance_path=ins_rel_path,
                sign_data={"insurance_file_sha256": expected_sha}
            )
            signed_doc = WaiverSignedDocument(
                waiver_id=doc_id,
                hash=seal_hash,
                data_snapshot=canonical_payload,
                signature=sig_rel_path,
                signed_at=datetime.now(timezone.utc)
            )
            db.session.add_all([waiver, signed_doc])
            db.session.commit()

            from services.common.signatures import log_signature_event
            log_signature_event(doc_id, "cgl", "document_signed", {"hash": seal_hash})
            db.session.commit()

            config = {
                "mode": "cgl",
                "model": CglWaiver,
                "signed_model": WaiverSignedDocument,
                "template_verify": "public/cgl/cgl_verify.html",
                "route_base": "cgl",
                "seal_prefix": "BVRA",
                "get_seal_args": lambda data, doc: []
            }
            verification_token = generate_document_verification_token(
                "cgl", doc_id, 1, signed_doc.hash
            )
            verify_path = f"/cgl/verify/{doc_id}?version=1&t={verification_token}"

            # 1. Intact -> Sceau valide
            with self.app.test_request_context(verify_path):
                resp = handle_document_verify(config, doc_id)
                self.assertIn("CGL Scellées &amp; Intactes", resp.get_data(as_text=True))

            # 2. Altération physique -> Sceau invalide
            with open(full_ins_path, "wb") as f:
                f.write(b"%PDF-1.4 tampered insurance content")

            with self.app.test_request_context(verify_path):
                resp_tampered = handle_document_verify(config, doc_id)
                self.assertIn("Sceau Invalide", resp_tampered.get_data(as_text=True))

            # 3. Disparition physique -> Sceau invalide
            os.remove(full_ins_path)
            with self.app.test_request_context(verify_path):
                resp_missing = handle_document_verify(config, doc_id)
                self.assertIn("Sceau Invalide", resp_missing.get_data(as_text=True))

    def test_generate_inspection_token_guards(self):
        """Vérifie le durcissement de generate_inspection_token (refus sur statut signé, scellé existant ou non prêt)."""
        with self.app.app_context():
            from models import CheckoutVehicle, CheckoutSignedDocument
            from services.common.signatures import generate_inspection_token

            co = CheckoutVehicle(
                status="signed",
                vehicle_id="1",
                inspection_number="BVCO-TEST-GUARD1",
                battery_level=100,
                vehicle_ready=True,
            )
            db.session.add(co)
            db.session.commit()

            # 1. Refus car déjà signé
            with self.assertRaises(ValueError) as ctx:
                generate_inspection_token(co.id, "checkout")
            self.assertIn("déjà été signé", str(ctx.exception))

            # 2. Refus si archive scellée existante
            co2 = CheckoutVehicle(
                status="pending",
                vehicle_id="1",
                inspection_number="BVCO-TEST-GUARD2",
                battery_level=100,
                vehicle_ready=True,
            )
            doc = CheckoutSignedDocument(
                inspection_id=co2.inspection_number,
                hash="fakehash",
                pdf_file_hash="",
                data_snapshot={},
                signature="signatures/fake.png",
                pdf_url="/fake.pdf",
                signed_at=datetime.now(timezone.utc),
            )
            db.session.add_all([co2, doc])
            db.session.commit()

            with self.assertRaises(ValueError) as ctx:
                generate_inspection_token(co2.id, "checkout")
            self.assertIn("archive scellée immuable existe déjà", str(ctx.exception))

            # 3. Refus car non prêt (batterie < 100 sur checkout)
            co3 = CheckoutVehicle(
                status="pending",
                vehicle_id="1",
                inspection_number="BVCO-TEST-GUARD3",
                battery_level=80,
                vehicle_ready=False,
            )
            db.session.add(co3)
            db.session.commit()

            with self.assertRaises(ValueError) as ctx:
                generate_inspection_token(co3.id, "checkout")
            self.assertIn("le véhicule n'est pas prêt", str(ctx.exception))

    def test_waiver_reset_forbidden_when_signed(self):
        """Vérifie le blocage absolu de réinitialisation (reset_waiver) sur document signé ou scellé."""
        with self.app.app_context():
            from services.admin.waivers.core import reset_waiver

            prod = Production(name="Prod Signed Test")
            db.session.add(prod)
            db.session.commit()
            proj = Project(name="Project Signed Test", production_id=prod.id)
            db.session.add(proj)
            db.session.commit()

            cgl = CglWaiver(
                waiver_id="BVRA-CGL-RESET-TEST",
                project_id=proj.id,
                status="signed",
            )
            signed_doc = WaiverSignedDocument(
                waiver_id="BVRA-CGL-RESET-TEST",
                hash="seal_reset_hash",
                pdf_file_hash="",
                data_snapshot={},
                signature="signatures/cgl.png",
                pdf_url="/cgl.pdf",
                signed_at=datetime.now(timezone.utc),
            )
            db.session.add_all([cgl, signed_doc])
            db.session.commit()

            success, msg = reset_waiver("BVRA-CGL-RESET-TEST", waiver_type="cgl")
            self.assertFalse(success)
            self.assertIn("Impossible de réinitialiser un document déjà signé", msg)

    def test_waiver_delete_preserves_signed_pdf_and_signed_doc(self):
        """Vérifie que la suppression d'un waiver signé préserve le PDF et WaiverSignedDocument (soft delete + révocation token)."""
        with self.app.app_context():
            from services.admin.waivers.core import delete_waiver

            prod = Production(name="Prod Del Test")
            db.session.add(prod)
            db.session.commit()
            proj = Project(name="Project Del Test", production_id=prod.id)
            db.session.add(proj)
            db.session.commit()

            cgl = CglWaiver(
                waiver_id="BVRA-CGL-DEL-TEST",
                project_id=proj.id,
                status="signed",
            )
            signed_doc = WaiverSignedDocument(
                waiver_id="BVRA-CGL-DEL-TEST",
                hash="seal_del_hash",
                pdf_file_hash="pdf_del_hash",
                data_snapshot={},
                signature="signatures/cgl_del.png",
                pdf_url="/cgl_del.pdf",
                signed_at=datetime.now(timezone.utc),
            )
            token = WaiverToken(
                token="active-token-to-revoke",
                waiver_id="BVRA-CGL-DEL-TEST",
            )
            db.session.add_all([cgl, signed_doc, token])
            db.session.commit()

            success, msg = delete_waiver("BVRA-CGL-DEL-TEST", waiver_type="cgl")
            self.assertTrue(success)

            # 1. Vérifier soft-delete
            reloaded_cgl = CglWaiver.query.filter_by(waiver_id="BVRA-CGL-DEL-TEST").first()
            self.assertIsNotNone(reloaded_cgl.deleted_at)

            # 2. Vérifier préservation absolue de l'archive WaiverSignedDocument
            reloaded_doc = WaiverSignedDocument.query.filter_by(waiver_id="BVRA-CGL-DEL-TEST").first()
            self.assertIsNotNone(reloaded_doc)
            self.assertEqual(reloaded_doc.hash, "seal_del_hash")

            # 3. Vérifier révocation / suppression des jetons actifs
            tokens_left = WaiverToken.query.filter_by(waiver_id="BVRA-CGL-DEL-TEST").all()
            self.assertEqual(len(tokens_left), 0)

            # 4. Vérifier journal d'audit
            events = SignatureEvent.query.filter_by(
                document_id="BVRA-CGL-DEL-TEST",
                event_type="waiver_archived_or_retired"
            ).all()
            self.assertGreaterEqual(len(events), 1)

    def test_bvsr_countersign_security(self):
        """Vérifie la sécurité de la contre-signature BVSR (unicité, validation Base64, audit log)."""
        with self.app.app_context():
            from services.admin.waivers.safety_rules import countersign_safety_rules

            prod = Production(name="Prod BVSR Test")
            db.session.add(prod)
            db.session.commit()
            proj = Project(name="Project BVSR Test", production_id=prod.id)
            db.session.add(proj)
            db.session.commit()

            waiver = SafetyRulesWaiver(
                waiver_id="BVSR-TEST-CS",
                project_id=proj.id,
                status="signed",
                signature_data=_generate_valid_png_base64(),
            )
            db.session.add(waiver)
            db.session.commit()

            # 1. Échec si signature invalide (pas une image valide)
            invalid_sig = "data:image/png;base64,bm90YW5pbWFnZQ=="
            ok_inv, err_inv = countersign_safety_rules("BVSR-TEST-CS", invalid_sig)
            self.assertFalse(ok_inv)
            self.assertIn("invalide", err_inv.lower())

            # 2. Succès première contre-signature
            valid_sig = _generate_valid_png_base64()
            ok, msg = countersign_safety_rules(
                "BVSR-TEST-CS",
                valid_sig,
                signer_name="Jean Dupont (Superviseur BV)",
                signer_ip="10.0.0.1"
            )
            self.assertTrue(ok)

            reloaded = SafetyRulesWaiver.query.filter_by(waiver_id="BVSR-TEST-CS").first()
            self.assertIsNotNone(reloaded.bv_signed_at)
            self.assertEqual(reloaded.bv_signer_name, "Jean Dupont (Superviseur BV)")

            # 3. Refus deuxième contre-signature
            ok_again, msg_again = countersign_safety_rules("BVSR-TEST-CS", valid_sig)
            self.assertFalse(ok_again)
            self.assertIn("déjà été contre-signé", msg_again)

            # 4. Événement d'audit présent
            events = SignatureEvent.query.filter_by(
                document_id="BVSR-TEST-CS",
                event_type="bvsr_countersigned"
            ).all()
            self.assertGreaterEqual(len(events), 1)

    def test_compute_inspection_readiness_strictness(self):
        """Vérifie la robustesse mathématique et métier de compute_inspection_readiness."""
        from services.admin.utils import compute_inspection_readiness

        # 1. NaN ou Infini
        ready_nan, fails_nan = compute_inspection_readiness({}, is_checkout=True, battery_val=float("nan"))
        self.assertFalse(ready_nan)
        self.assertTrue(any("non numérique ou infini" in f for f in fails_nan))

        ready_inf, fails_inf = compute_inspection_readiness({}, is_checkout=True, battery_val=float("inf"))
        self.assertFalse(ready_inf)
        self.assertTrue(any("non numérique ou infini" in f for f in fails_inf))

        # 2. Hors bornes 0-100
        ready_neg, fails_neg = compute_inspection_readiness({}, is_checkout=False, battery_val=-10)
        self.assertFalse(ready_neg)
        self.assertTrue(any("hors limites" in f for f in fails_neg))

        ready_over, fails_over = compute_inspection_readiness({}, is_checkout=False, battery_val=105)
        self.assertFalse(ready_over)
        self.assertTrue(any("hors limites" in f for f in fails_over))

        # 3. Checkout < 100%
        ready_under, fails_under = compute_inspection_readiness({}, is_checkout=True, battery_val=99)
        self.assertFalse(ready_under)
        self.assertTrue(any("< 100%" in f for f in fails_under))

    def test_seal_secret_key_production_requirement(self):
        """Vérifie que _get_hmac_secret lève une RuntimeError en production si aucun secret dédié n'est fourni."""
        from utils.document_utils import _get_hmac_secret

        with patch.dict(os.environ, {"FLASK_ENV": "production", "SEAL_SECRET_KEY": "", "HASH_SECRET_KEY": ""}):
            with self.assertRaises(RuntimeError) as ctx:
                _get_hmac_secret()
            self.assertIn("SEAL_SECRET_KEY ou HASH_SECRET_KEY doit impérativement être définie", str(ctx.exception))

    def test_cgl_field_length_validation_rejection(self):
        """Vérifie que la soumission de champs dépassant les limites est rejetée avec HTTP 400."""
        with self.app.app_context():
            prod = Production(name="Prod Field Test")
            db.session.add(prod)
            db.session.commit()
            proj = Project(name="Project Field Test", production_id=prod.id)
            db.session.add(proj)
            db.session.commit()

            cgl = CglWaiver(
                waiver_id="BVRA-CGL-FIELD-TEST",
                project_id=proj.id,
                status="to_sign",
            )
            tok = WaiverToken(
                token="tok-field-len-test",
                waiver_id="BVRA-CGL-FIELD-TEST",
            )
            db.session.add_all([cgl, tok])
            db.session.commit()

            # Trop long nom de représentant (> 150 caractères)
            long_name = "X" * 160
            res = self.client.post(
                "/sign/cgl/tok-field-len-test",
                data={
                    "signature": _generate_valid_png_base64(),
                    "accepted_terms": "1",
                    "has_signing_authority": "1",
                    "production_name": "BV Production",
                    "representative": long_name,
                    "representative_role": "Directeur",
                }
            )
            self.assertEqual(res.status_code, 400)
            self.assertIn("ne peut dépasser 150 caractères", res.get_json()["error"])

            # Trop long numéro de téléphone (> 50 caractères)
            res_phone = self.client.post(
                "/sign/cgl/tok-field-len-test",
                data={
                    "signature": _generate_valid_png_base64(),
                    "accepted_terms": "1",
                    "has_signing_authority": "1",
                    "production_name": "BV Production",
                    "representative": "Jean Dupont",
                    "representative_role": "Directeur",
                    "phone": "0" * 60,
                }
            )
            self.assertEqual(res_phone.status_code, 400)
            self.assertIn("téléphone ne peut dépasser 50 caractères", res_phone.get_json()["error"])

    def test_checkout_token_and_signature_fail_closed_validation(self):
        """
        Vérifie que la génération de jeton et la signature check-out refusent strictement :
        - un véhicule absent,
        - un véhicule inventé / non reconnu (même si utils/checkpoints retourne des checkpoints génériques tous 'ok'),
        et autorisent un véhicule reconnu et prêt (par ID ou nom).
        Utilise le vrai chemin de résolution des checkpoints (utils/checkpoints.py) et simule uniquement get_vehicles à sa frontière.
        """
        from models import CheckoutVehicle, Project, CheckoutToken, Production
        from services.common.signatures import generate_inspection_token, process_inspection_signature
        from utils.checkpoints import get_checkpoints_for_vehicle

        mock_fleet = [
            {"id": "rec_known_car_1", "fields": {"name": "Porsche Panamera Turbo"}},
            {"id": "rec_known_car_2", "fields": {"name": "Ferrari 488 GTB"}},
        ]

        with self.app.app_context():
            prod = Production(name="Prod FailClosed Real")
            db.session.add(prod)
            db.session.flush()
            p = Project(name="Project FailClosed Real", production_id=prod.id)
            db.session.add(p)
            db.session.flush()

            with patch("utils.database.get_vehicles", return_value=mock_fleet):
                # 1. Cas Véhicule absent (vehicle_id=None), batterie=100 et checkpoints "ok"
                cv_absent = CheckoutVehicle(
                    project_id=p.id,
                    vehicle_id=None,
                    battery_level=100,
                    vehicle_ready=True,
                )
                cv_absent.set_checkpoint_status("tires", "ok")
                cv_absent.set_checkpoint_status("brakes", "ok")
                db.session.add(cv_absent)
                db.session.commit()

                with self.assertRaises(ValueError) as ctx_absent_tok:
                    generate_inspection_token(cv_absent.id, "checkout")
                self.assertIn("le véhicule n'est pas prêt", str(ctx_absent_tok.exception))
                self.assertIn("Véhicule non sélectionné", str(ctx_absent_tok.exception))

                tok_absent = CheckoutToken(
                    token="tok-absent-test",
                    record_id=str(cv_absent.id),
                    inspection_id=cv_absent.inspection_number,
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
                )
                db.session.add(tok_absent)
                db.session.commit()

                with self.assertRaises(ValueError) as ctx_absent_sign:
                    process_inspection_signature(
                        "tok-absent-test",
                        "checkout",
                        _generate_valid_png_base64(),
                        "127.0.0.1",
                        expected_record_id=cv_absent.id
                    )
                self.assertIn("le véhicule n'est pas prêt", str(ctx_absent_sign.exception))
                self.assertIn("Véhicule non sélectionné", str(ctx_absent_sign.exception))

                # 2. Cas Véhicule inventé / absent de get_vehicles (ex: "fake_invented_vehicle_999")
                # Même si get_checkpoints_for_vehicle réel lui attribue les checkpoints génériques de sécurité
                # et que toutes les valeurs sont "ok" avec batterie=100% :
                fake_veh_id = "fake_invented_vehicle_999"
                real_cps_for_fake = get_checkpoints_for_vehicle(fake_veh_id)
                self.assertTrue(len(real_cps_for_fake) > 0, "Le chemin réel doit renvoyer des checkpoints génériques")

                cv_fake = CheckoutVehicle(
                    project_id=p.id,
                    vehicle_id=fake_veh_id,
                    battery_level=100,
                    vehicle_ready=True,
                )
                for cp in real_cps_for_fake:
                    cv_fake.set_checkpoint_status(cp["key"], "ok")
                db.session.add(cv_fake)
                db.session.commit()

                # Refus à la génération du jeton
                with self.assertRaises(ValueError) as ctx_fake_tok:
                    generate_inspection_token(cv_fake.id, "checkout")
                self.assertIn("le véhicule n'est pas prêt", str(ctx_fake_tok.exception))
                self.assertIn("Véhicule non reconnu", str(ctx_fake_tok.exception))

                # Refus à la signature
                tok_fake = CheckoutToken(
                    token="tok-fake-test",
                    record_id=str(cv_fake.id),
                    inspection_id=cv_fake.inspection_number,
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
                )
                db.session.add(tok_fake)
                db.session.commit()

                with self.assertRaises(ValueError) as ctx_fake_sign:
                    process_inspection_signature(
                        "tok-fake-test",
                        "checkout",
                        _generate_valid_png_base64(),
                        "127.0.0.1",
                        expected_record_id=cv_fake.id
                    )
                self.assertIn("le véhicule n'est pas prêt", str(ctx_fake_sign.exception))
                self.assertIn("Véhicule non reconnu", str(ctx_fake_sign.exception))

                # 3. Cas Véhicule reconnu et prêt (rec_known_car_1)
                known_veh_id = "rec_known_car_1"
                real_cps_for_known = get_checkpoints_for_vehicle(known_veh_id)
                self.assertTrue(len(real_cps_for_known) > 0)

                cv_ready = CheckoutVehicle(
                    project_id=p.id,
                    vehicle_id=known_veh_id,
                    battery_level=100,
                )
                for cp in real_cps_for_known:
                    cv_ready.set_checkpoint_status(cp["key"], "ok")
                db.session.add(cv_ready)
                db.session.commit()

                # Succès génération de jeton
                res_tok = generate_inspection_token(cv_ready.id, "checkout")
                self.assertIsNotNone(res_tok)
                self.assertIn("token", res_tok)
                gen_token = res_tok["token"]

                # Succès signature
                res_sign = process_inspection_signature(
                    gen_token,
                    "checkout",
                    _generate_valid_png_base64(),
                    "127.0.0.1",
                    expected_record_id=cv_ready.id
                )
                self.assertIsNotNone(res_sign)
                self.assertEqual(res_sign["document_id"], cv_ready.inspection_number)

                # Nettoyage
                CheckoutToken.query.filter(CheckoutToken.token.in_(["tok-absent-test", "tok-fake-test", gen_token])).delete()
                db.session.delete(cv_absent)
                db.session.delete(cv_fake)
                db.session.delete(cv_ready)
                db.session.delete(p)
                db.session.delete(prod)
                db.session.commit()

    def test_bvsr_versioned_countersignature_preserves_initial_proof(self):
        """Vérifie la conservation de la version 1 client (archive + PDF) lors de la contre-signature BVSR (version 2)."""
        from models import SafetyRulesWaiver, WaiverSignedDocument, Project, Production
        from services.admin.waivers.safety_rules import countersign_safety_rules
        from services.common.signatures import finalize_signed_document

        with self.app.app_context():
            prod = Production(name="Prod BVSR Versioning")
            db.session.add(prod)
            db.session.flush()
            p = Project(name="Project BVSR Versioning", production_id=prod.id)
            db.session.add(p)
            db.session.flush()

            waiver = SafetyRulesWaiver(
                project_id=p.id,
                waiver_id="BVSR-VERS-TEST01",
                signer_first_name="Pilote",
                signer_last_name="Test",
                signer_email="pilote@test.com",
                status="signed",
                signature_data=_generate_valid_png_base64(),
                signer_ip="192.168.1.50"
            )
            db.session.add(waiver)
            db.session.commit()

            # 1. Scellement initial du client (Version 1)
            res_v1 = finalize_signed_document(
                "safety_rules",
                waiver.id,
                waiver.signature_data,
                waiver.signer_ip
            )
            v1_hash = res_v1["hash"]
            v1_pdf_url = res_v1["pdf_url"]

            doc_v1 = WaiverSignedDocument.query.filter_by(waiver_id="BVSR-VERS-TEST01", version=1).first()
            self.assertIsNotNone(doc_v1)
            self.assertEqual(doc_v1.version, 1)
            self.assertIsNone(doc_v1.parent_hash)
            self.assertEqual(doc_v1.hash, v1_hash)

            # 2. Contre-signature par Belle Vitesse (Version 2)
            bv_sig = _generate_valid_png_base64()
            ok, msg = countersign_safety_rules(
                "BVSR-VERS-TEST01",
                bv_sig,
                signer_name="Superviseur BV",
                signer_ip="10.0.0.1"
            )
            self.assertTrue(ok, f"La contre-signature a échoué: {msg}")

            # Vérifier que Version 1 est TOUJOURS PRÉSENTE et INTACTE
            doc_v1_after = WaiverSignedDocument.query.filter_by(waiver_id="BVSR-VERS-TEST01", version=1).first()
            self.assertIsNotNone(doc_v1_after)
            self.assertEqual(doc_v1_after.hash, v1_hash)
            self.assertEqual(doc_v1_after.pdf_url, v1_pdf_url)

            # Vérifier que Version 2 a été créée avec parent_hash lié à Version 1
            doc_v2 = WaiverSignedDocument.query.filter_by(waiver_id="BVSR-VERS-TEST01", version=2).first()
            self.assertIsNotNone(doc_v2)
            self.assertEqual(doc_v2.version, 2)
            self.assertEqual(doc_v2.parent_hash, v1_hash)
            self.assertNotEqual(doc_v2.hash, v1_hash)
            self.assertNotEqual(doc_v2.pdf_url, v1_pdf_url)

            # Le QR et les liens de vérification sont liés à une version précise.
            self.assertIn("version=1&t=", res_v1["verification_url"])
            v1_verify_url = self._verification_url(
                "safety-rules", "safety_rules", "BVSR-VERS-TEST01", doc_v1
            )
            self.assertEqual(self.client.get("/safety-rules/verify/BVSR-VERS-TEST01").status_code, 404)
            v1_verify = self.client.get(v1_verify_url)
            self.assertEqual(v1_verify.status_code, 200)
            self.assertIn("Version 1", v1_verify.get_data(as_text=True))

            v2_verify_url = self._verification_url(
                "safety-rules", "safety_rules", "BVSR-VERS-TEST01", doc_v2
            )
            v2_verify = self.client.get(v2_verify_url)
            self.assertEqual(v2_verify.status_code, 200)
            v2_html = v2_verify.get_data(as_text=True)
            self.assertIn("Version 2", v2_html)
            self.assertIn("Voir la version 1", v2_html)

            # Le lien parent fait partie du sceau : sa modification invalide la version 2.
            tampered_snapshot = dict(doc_v2.data_snapshot)
            tampered_snapshot["parent_hash"] = "hash-parent-altéré"
            doc_v2.data_snapshot = tampered_snapshot
            db.session.commit()
            tampered_verify = self.client.get(v2_verify_url)
            self.assertIn("Sceau Invalide", tampered_verify.get_data(as_text=True))

            # Vérifier que la liste des versions contient les 2 versions
            all_versions = WaiverSignedDocument.query.filter_by(waiver_id="BVSR-VERS-TEST01").order_by(WaiverSignedDocument.version.asc()).all()
            self.assertEqual(len(all_versions), 2)
            self.assertEqual(all_versions[0].version, 1)
            self.assertEqual(all_versions[1].version, 2)

            # 3. Tentative de seconde contre-signature -> STRICTEMENT INTERDITE
            ok_re, msg_re = countersign_safety_rules("BVSR-VERS-TEST01", bv_sig)
            self.assertFalse(ok_re)
            self.assertIn("déjà été contre-signé", msg_re)

            # Nettoyage
            WaiverSignedDocument.query.filter_by(waiver_id="BVSR-VERS-TEST01").delete()
            db.session.delete(waiver)
            db.session.delete(p)
            db.session.delete(prod)
            db.session.commit()

    def test_bvsr_countersignature_transaction_sql_failure_is_atomic(self):
        """Vérifie qu'une vraie erreur SQL/commit lors du scellement de la contre-signature BVSR annule tout et permet de réessayer."""
        from models import SafetyRulesWaiver, WaiverSignedDocument, Project, Production
        from services.admin.waivers.safety_rules import countersign_safety_rules
        from services.common.signatures import finalize_signed_document
        from sqlalchemy.exc import OperationalError

        with self.app.app_context():
            prod = Production(name="Prod Atomic Rollback")
            db.session.add(prod)
            db.session.flush()
            p = Project(name="Project Atomic Rollback", production_id=prod.id)
            db.session.add(p)
            db.session.flush()

            waiver = SafetyRulesWaiver(
                project_id=p.id,
                waiver_id="BVSR-ATOMIC-TEST",
                signer_first_name="Intervenant",
                signer_last_name="Test",
                status="signed",
                signature_data=_generate_valid_png_base64(),
                signer_ip="192.168.1.100"
            )
            db.session.add(waiver)
            db.session.commit()

            # Sceller version 1 avec le vrai finaliseur
            finalize_signed_document("safety_rules", waiver.id, waiver.signature_data, waiver.signer_ip)

            # Simuler une vraie erreur SQL/commit avant validation de la contre-signature (ex: base verrouillée)
            with patch.object(db.session, "commit", side_effect=OperationalError("simulate commit error", None, Exception("database locked"))):
                ok, msg = countersign_safety_rules("BVSR-ATOMIC-TEST", _generate_valid_png_base64())
                self.assertFalse(ok)
                self.assertIn("database locked", msg.lower())

            # Recharger depuis la base et vérifier l'absence d'état partiel bloquant
            reloaded = SafetyRulesWaiver.query.filter_by(waiver_id="BVSR-ATOMIC-TEST").first()
            self.assertIsNone(reloaded.bv_signed_at)
            self.assertIsNone(reloaded.bv_signature_data)
            self.assertIsNone(reloaded.bv_signer_name)

            # Version 2 ne doit pas exister, version 1 doit subsister intacte
            v2_doc = WaiverSignedDocument.query.filter_by(waiver_id="BVSR-ATOMIC-TEST", version=2).first()
            self.assertIsNone(v2_doc)
            v1_doc = WaiverSignedDocument.query.filter_by(waiver_id="BVSR-ATOMIC-TEST", version=1).first()
            self.assertIsNotNone(v1_doc)

            # Une nouvelle tentative immédiate doit pouvoir réussir sans être bloquée
            ok_retry, msg_retry = countersign_safety_rules("BVSR-ATOMIC-TEST", _generate_valid_png_base64())
            self.assertTrue(ok_retry, f"Le réessai a échoué : {msg_retry}")

            reloaded_success = SafetyRulesWaiver.query.filter_by(waiver_id="BVSR-ATOMIC-TEST").first()
            self.assertIsNotNone(reloaded_success.bv_signed_at)
            v2_doc_success = WaiverSignedDocument.query.filter_by(waiver_id="BVSR-ATOMIC-TEST", version=2).first()
            self.assertIsNotNone(v2_doc_success)
            self.assertEqual(v2_doc_success.version, 2)

            # Nettoyage
            WaiverSignedDocument.query.filter_by(waiver_id="BVSR-ATOMIC-TEST").delete()
            db.session.delete(reloaded_success)
            db.session.delete(p)
            db.session.delete(prod)
            db.session.commit()

    def test_bvsr_countersignature_post_commit_pdf_queue_failure_preserves_proof(self):
        """Vérifie qu'un échec de mise en file du PDF après commit préserve la preuve DB et ne déclare pas d'échec de contre-signature."""
        from models import SafetyRulesWaiver, WaiverSignedDocument, Project, Production
        from services.admin.waivers.safety_rules import countersign_safety_rules
        from services.common.signatures import finalize_signed_document

        with self.app.app_context():
            prod = Production(name="Prod PostCommit Queue")
            db.session.add(prod)
            db.session.flush()
            p = Project(name="Project PostCommit Queue", production_id=prod.id)
            db.session.add(p)
            db.session.flush()

            waiver = SafetyRulesWaiver(
                project_id=p.id,
                waiver_id="BVSR-POSTCOMMIT-TEST",
                signer_first_name="Pilote",
                signer_last_name="PostCommit",
                status="signed",
                signature_data=_generate_valid_png_base64(),
                signer_ip="192.168.1.101"
            )
            db.session.add(waiver)
            db.session.commit()

            # Sceller version 1
            finalize_signed_document("safety_rules", waiver.id, waiver.signature_data, waiver.signer_ip)

            # Simuler un échec de la file RQ lors de la contre-signature (après le commit DB)
            with patch("services.common.pdf_tasks.dispatch_pdf_generation", side_effect=RuntimeError("Redis queue offline")):
                ok, msg = countersign_safety_rules("BVSR-POSTCOMMIT-TEST", _generate_valid_png_base64())
                self.assertTrue(ok, f"La contre-signature doit réussir même si la file PDF est inaccessible : {msg}")
                self.assertIn("avec succès", msg)

            # Vérifier que le scellement DB est complet
            reloaded = SafetyRulesWaiver.query.filter_by(waiver_id="BVSR-POSTCOMMIT-TEST").first()
            self.assertIsNotNone(reloaded.bv_signed_at)
            self.assertIsNotNone(reloaded.bv_signature_data)
            v2_doc = WaiverSignedDocument.query.filter_by(waiver_id="BVSR-POSTCOMMIT-TEST", version=2).first()
            self.assertIsNotNone(v2_doc)
            self.assertEqual(v2_doc.version, 2)

            # Interdire toute rejoue : le document est bien scellé
            ok_re, msg_re = countersign_safety_rules("BVSR-POSTCOMMIT-TEST", _generate_valid_png_base64())
            self.assertFalse(ok_re)
            self.assertIn("déjà été contre-signé", msg_re)

            # Sur la route de vérification, le sceau de données est valide et le PDF est marqué en attente
            verify_url = self._verification_url("safety-rules", "safety_rules", "BVSR-POSTCOMMIT-TEST", v2_doc)
            res_verify = self.client.get(verify_url)
            self.assertEqual(res_verify.status_code, 200)
            html = res_verify.get_data(as_text=True)
            self.assertIn("Scellées &amp; Intactes", html)
            self.assertIn("en attente / non vérifiable", html)
            self.assertNotIn("Exemplaire PDF original certifié intact", html)

            # Nettoyage
            WaiverSignedDocument.query.filter_by(waiver_id="BVSR-POSTCOMMIT-TEST").delete()
            db.session.delete(reloaded)
            db.session.delete(p)
            db.session.delete(prod)
            db.session.commit()

    def test_pdf_storage_status_without_hash_is_pending_not_intact(self):
        """Vérifie qu'un PDF sans hash n'est jamais marqué 'intact', mais 'en attente' sans invalider le sceau."""
        from models import CglWaiver, WaiverSignedDocument, Project, Production
        from services.common.signatures import compute_canonical_seal, compute_file_sha256, log_signature_event

        with self.app.app_context():
            prod = Production(name="Prod PDF No Hash")
            db.session.add(prod)
            db.session.flush()
            p = Project(name="Project PDF No Hash", production_id=prod.id)
            db.session.add(p)
            db.session.flush()

            out_folder = self.app.config.get("OUTPUT_FOLDER")

            # Créer un PNG valide sur disque pour la signature
            sig_rel = "signatures/waivers/mock_nohash.png"
            full_sig_path = os.path.join(out_folder, sig_rel)
            os.makedirs(os.path.dirname(full_sig_path), exist_ok=True)
            img = Image.new("RGBA", (120, 60), color=(0, 0, 0, 0))
            img.save(full_sig_path, format="PNG")
            sig_sha256 = compute_file_sha256(full_sig_path)

            waiver = CglWaiver(
                project_id=p.id,
                waiver_id="BVRA-NOHASH-TEST",
                status="signed",
                signature_data=sig_rel,
                signer_ip="127.0.0.1"
            )
            db.session.add(waiver)
            db.session.flush()

            # Enregistrer l'événement d'audit requis pour la chaîne v2
            log_signature_event("BVRA-NOHASH-TEST", "cgl", "document_signed", {"signer": "Test"})

            # Créer un faux PDF physique sur disque
            pdf_rel = "documents/cgl/test_nohash.pdf"
            full_pdf_path = os.path.join(out_folder, pdf_rel)
            os.makedirs(os.path.dirname(full_pdf_path), exist_ok=True)
            with open(full_pdf_path, "wb") as f:
                f.write(b"%PDF-1.4 Mock PDF Content")

            canonical_payload = {
                "version": "2.0",
                "_seal_kid": "v1",
                "mode": "cgl",
                "document_id": "BVRA-NOHASH-TEST",
                "signed_at": datetime.now(timezone.utc).isoformat(),
                "signer_ip": "127.0.0.1",
                "signature_sha256": sig_sha256,
                "snapshot": {"mode": "cgl", "waiver_id": "BVRA-NOHASH-TEST", "representative_name": "Test Representative"}
            }
            seal_hash = compute_canonical_seal(canonical_payload)

            signed_doc = WaiverSignedDocument(
                waiver_id="BVRA-NOHASH-TEST",
                version=1,
                hash=seal_hash,
                pdf_file_hash="",  # ABSENT !
                data_snapshot=canonical_payload,
                signature=sig_rel,
                pdf_url=f"/cgl/document/{pdf_rel}",
                signed_at=datetime.now(timezone.utc)
            )
            db.session.add(signed_doc)
            db.session.commit()

            # Appel de la route de vérification
            verify_url = self._verification_url("cgl", "cgl", "BVRA-NOHASH-TEST", signed_doc)
            res = self.client.get(verify_url)
            self.assertEqual(res.status_code, 200)
            html = res.get_data(as_text=True)

            # Le PDF doit afficher 'en attente / non vérifiable', et JAMAIS 'certifié intact'
            self.assertIn("en attente / non vérifiable", html)
            self.assertNotIn("Exemplaire PDF original certifié intact", html)

            # Le sceau des données doit être valide (non invalidé par l'absence d'empreinte PDF)
            self.assertIn("verify-badge--ok", html)
            self.assertIn("Scellées &amp; Intactes", html)

            # Nettoyage
            if os.path.exists(full_pdf_path):
                os.remove(full_pdf_path)
            if os.path.exists(full_sig_path):
                os.remove(full_sig_path)
            WaiverSignedDocument.query.filter_by(waiver_id="BVRA-NOHASH-TEST").delete()
            db.session.delete(waiver)
            db.session.delete(p)
            db.session.delete(prod)
            db.session.commit()

    def test_pdf_storage_status_corrupted_on_missing_or_altered_file(self):
        """Vérifie qu'un PDF avec hash attendu passe à 'altéré' si manquant ou corrompu."""
        from models import CglWaiver, WaiverSignedDocument, Project, Production
        from services.common.signatures import compute_canonical_seal, compute_file_sha256, log_signature_event

        with self.app.app_context():
            prod = Production(name="Prod PDF Corrupted")
            db.session.add(prod)
            db.session.flush()
            p = Project(name="Project PDF Corrupted", production_id=prod.id)
            db.session.add(p)
            db.session.flush()

            out_folder = self.app.config.get("OUTPUT_FOLDER")

            # Créer un PNG valide sur disque pour la signature
            sig_rel = "signatures/waivers/mock_corrupt.png"
            full_sig_path = os.path.join(out_folder, sig_rel)
            os.makedirs(os.path.dirname(full_sig_path), exist_ok=True)
            img = Image.new("RGBA", (120, 60), color=(0, 0, 0, 0))
            img.save(full_sig_path, format="PNG")
            sig_sha256 = compute_file_sha256(full_sig_path)

            waiver = CglWaiver(
                project_id=p.id,
                waiver_id="BVRA-CORRUPT-TEST",
                status="signed",
                signature_data=sig_rel,
                signer_ip="127.0.0.1"
            )
            db.session.add(waiver)
            db.session.flush()

            # Enregistrer l'événement d'audit requis pour la chaîne v2
            log_signature_event("BVRA-CORRUPT-TEST", "cgl", "document_signed", {"signer": "Test"})

            pdf_rel = "documents/cgl/test_corrupt.pdf"
            full_pdf_path = os.path.join(out_folder, pdf_rel)
            os.makedirs(os.path.dirname(full_pdf_path), exist_ok=True)
            with open(full_pdf_path, "wb") as f:
                f.write(b"%PDF-1.4 Original Content")

            pdf_hash = compute_file_sha256(full_pdf_path)

            canonical_payload = {
                "version": "2.0",
                "_seal_kid": "v1",
                "mode": "cgl",
                "document_id": "BVRA-CORRUPT-TEST",
                "signed_at": datetime.now(timezone.utc).isoformat(),
                "signer_ip": "127.0.0.1",
                "signature_sha256": sig_sha256,
                "snapshot": {"mode": "cgl", "waiver_id": "BVRA-CORRUPT-TEST", "representative_name": "Test Representative"}
            }
            seal_hash = compute_canonical_seal(canonical_payload)

            signed_doc = WaiverSignedDocument(
                waiver_id="BVRA-CORRUPT-TEST",
                version=1,
                hash=seal_hash,
                pdf_file_hash=pdf_hash,
                data_snapshot=canonical_payload,
                signature=sig_rel,
                pdf_url=f"/cgl/document/{pdf_rel}",
                signed_at=datetime.now(timezone.utc)
            )
            db.session.add(signed_doc)
            db.session.commit()

            # Cas 1 : PDF intact
            verify_url = self._verification_url("cgl", "cgl", "BVRA-CORRUPT-TEST", signed_doc)
            res_intact = self.client.get(verify_url)
            self.assertEqual(res_intact.status_code, 200)
            html_intact = res_intact.get_data(as_text=True)
            self.assertIn("Exemplaire PDF original certifié intact", html_intact)
            self.assertIn("verify-badge--ok", html_intact)

            # Cas 2 : PDF altéré (contenu modifié)
            with open(full_pdf_path, "wb") as f:
                f.write(b"%PDF-1.4 TAMPERED Content")
            res_tampered = self.client.get(verify_url)
            html_tampered = res_tampered.get_data(as_text=True)
            self.assertIn("Exemplaire PDF altéré ou manquant sur disque", html_tampered)
            self.assertIn("verify-badge--critical", html_tampered)

            # Cas 3 : PDF manquant (supprimé du disque)
            os.remove(full_pdf_path)
            res_missing = self.client.get(verify_url)
            html_missing = res_missing.get_data(as_text=True)
            self.assertIn("Exemplaire PDF altéré ou manquant sur disque", html_missing)
            self.assertIn("verify-badge--critical", html_missing)

            # Nettoyage
            if os.path.exists(full_sig_path):
                os.remove(full_sig_path)
            WaiverSignedDocument.query.filter_by(waiver_id="BVRA-CORRUPT-TEST").delete()
            db.session.delete(waiver)
            db.session.delete(p)
            db.session.delete(prod)
            db.session.commit()


if __name__ == "__main__":
    unittest.main()

