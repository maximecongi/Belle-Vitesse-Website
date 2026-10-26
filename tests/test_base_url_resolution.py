"""
Tests unitaires pour la résolution robuste des URLs de base et des liens absolus (QR codes PDF, signatures, etc.).
Vérifie qu'en environnement de développement (ou sur 127.0.0.1 / localhost), le protocole est strictement 'http://' et non 'https://'.
"""

import os
import unittest
from unittest.mock import patch

# Forcer l'environnement de test mémoire avant create_app
os.environ["FLASK_ENV"] = "testing"
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
os.environ["WTF_CSRF_ENABLED"] = "False"
os.environ["USE_SSH_TUNNEL"] = "false"

from app import create_app
from models.db import db
from utils.request_utils import resolve_base_url


class BaseUrlResolutionTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.app.config["SERVER_NAME"] = "127.0.0.1:5001"
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_local_hosts_force_http_scheme(self):
        """Vérifie que pour 127.0.0.1 et localhost, https:// est automatiquement converti en http://."""
        test_cases = [
            ("https://127.0.0.1:5001", "http://127.0.0.1:5001"),
            ("https://127.0.0.1:5001/", "http://127.0.0.1:5001"),
            ("127.0.0.1:5001", "http://127.0.0.1:5001"),
            ("http://127.0.0.1:5001", "http://127.0.0.1:5001"),
            ("https://localhost:5001", "http://localhost:5001"),
            ("localhost:5001", "http://localhost:5001"),
            ("http://localhost:5001", "http://localhost:5001"),
            ("https://http://127.0.0.1:5001", "http://127.0.0.1:5001"),
        ]
        for input_url, expected in test_cases:
            with self.subTest(input_url=input_url):
                self.assertEqual(resolve_base_url(input_url), expected)

    def test_production_hosts_preserve_or_add_https(self):
        """Vérifie que pour les domaines externes/production, https:// est préservé ou ajouté."""
        test_cases = [
            ("https://bellevitesse.com", "https://bellevitesse.com"),
            ("https://team.bellevitesse.com/", "https://team.bellevitesse.com"),
            ("bellevitesse.com", "https://bellevitesse.com"),
        ]
        for input_url, expected in test_cases:
            with self.subTest(input_url=input_url):
                self.assertEqual(resolve_base_url(input_url), expected)

    def test_resolve_from_request_context_in_dev(self):
        """Vérifie la résolution dynamique depuis le contexte de requête en développement."""
        with self.app.test_request_context("http://127.0.0.1:5001/cgl/test"):
            self.assertEqual(resolve_base_url(), "http://127.0.0.1:5001")

        # Même si pour une raison quelconque request.host_url avait du https sur 127.0.0.1
        with self.app.test_request_context(
            "https://127.0.0.1:5001/cgl/test",
            environ_base={"wsgi.url_scheme": "https", "HTTP_HOST": "127.0.0.1:5001"}
        ):
            self.assertEqual(resolve_base_url(), "http://127.0.0.1:5001")

    def test_verification_url_in_pdf_rendering_in_dev(self):
        """Vérifie que le QR code et l'URL de vérification scellés dans le PDF utilisent http:// en dev."""
        from datetime import date
        from models import CglWaiver, Production, Project, WaiverSignedDocument
        from services.common.signatures import finalize_signed_document

        with self.app.test_request_context("http://127.0.0.1:5001/"):
            prod = Production(name="Prod BaseURL Test")
            db.session.add(prod)
            db.session.flush()

            project = Project(
                name="Projet Test BaseURL",
                project_id="BVPR-BASEURL",
                production_id=prod.id,
                departure_date=date(2026, 9, 1),
            )
            db.session.add(project)
            db.session.flush()

            cgl = CglWaiver(
                waiver_id="BVRA-BASEURL-TEST",
                project_id=project.id,
                project_name="Projet Test BaseURL",
                production_name="Prod BaseURL Test",
            )
            db.session.add(cgl)
            db.session.commit()

            dummy_sig = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

            # Forcer APP_BASE_URL="http://127.0.0.1:5001"
            with patch.dict(os.environ, {"APP_BASE_URL": "http://127.0.0.1:5001", "FLASK_ENV": "development"}):
                self.app.config["APP_BASE_URL"] = "http://127.0.0.1:5001"
                self.app.config["FLASK_ENV"] = "development"

                with patch("services.common.pdf_tasks.render_pdf_from_template", return_value=b"%PDF-mock"):
                    res = finalize_signed_document(
                        mode="cgl",
                        record_id=cgl.id,
                        signature_data=dummy_sig,
                        signed_ip="127.0.0.1",
                    )

                    self.assertIn("verification_url", res)
                    # L'URL de vérification DOIT commencer par http://127.0.0.1:5001/ et PAS https://
                    self.assertTrue(
                        res["verification_url"].startswith("http://127.0.0.1:5001/"),
                        f"L'URL de vérification devrait commencer par http://127.0.0.1:5001/ mais est : {res['verification_url']}"
                    )
                    self.assertFalse(res["verification_url"].startswith("https://127.0.0.1:5001/"))


if __name__ == "__main__":
    unittest.main()
