"""
Tests unitaires pour l'architecture des Blueprints Publics Flask et l'aliasing d'URL.
Vérifie :
1. L'enregistrement complet de tous les Blueprints publics (web, inspections, waivers, incidents).
2. La résolution transparente des endpoints via url_for (alias sans préfixe vs nom qualifié de Blueprint).
3. L'idempotence des fonctions de compatibilité init_*_routes.
"""

import os
import unittest
from flask import Blueprint, url_for

os.environ["FLASK_ENV"] = "testing"
os.environ["TESTING"] = "True"
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
os.environ["USE_SSH_TUNNEL"] = "false"
os.environ["WTF_CSRF_ENABLED"] = "False"

from app import create_app
from routes.public.incidents import init_incident_public_routes, public_incidents_bp
from routes.public.inspections import public_inspections_bp
from routes.public.checkout import init_checkout_routes
from routes.public.checkin import init_checkin_routes
from routes.public.waivers import init_waiver_routes, public_waivers_bp
from routes.public.web import init_web_routes, public_web_bp


class PublicBlueprintsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def test_all_public_modules_are_blueprints(self):
        """Vérifie que chaque module public est une instance de Blueprint et bien enregistré sur l'application."""
        expected_bps = [
            public_web_bp,
            public_inspections_bp,
            public_waivers_bp,
            public_incidents_bp,
        ]
        for bp in expected_bps:
            self.assertIsInstance(
                bp, Blueprint, f"{bp} doit être une instance de Blueprint Flask"
            )
            self.assertIn(
                bp.name,
                self.app.blueprints,
                f"Blueprint {bp.name} non enregistré sur app",
            )

    def test_public_url_for_aliasing(self):
        """Vérifie que url_for fonctionne de manière transparente avec ou sans préfixe de Blueprint."""
        test_cases = [
            ("home", "public_web.home", {"lang": "en"}),
            ("vehicles", "public_web.vehicles", {"lang": "fr"}),
            ("heads", "public_web.heads", {"lang": "en"}),
            ("grips", "public_web.grips", {"lang": "fr"}),
            ("contact", "public_web.contact", {"lang": "en"}),
            ("about_us", "public_web.about_us", {"lang": "fr"}),
            ("launch", "public_web.launch", {}),
            (
                "checkout_verify",
                "public_inspections.checkout_verify",
                {"inspection_id": "BVCO-TEST1234", "version": 1, "t": "test_tok"},
            ),
            (
                "checkin_verify",
                "public_inspections.checkin_verify",
                {"inspection_id": "BVCI-TEST5678", "version": 1, "t": "test_tok"},
            ),
        ]

        with self.app.test_request_context():
            for legacy_ep, qualified_ep, kwargs in test_cases:
                url_legacy = url_for(legacy_ep, **kwargs)
                url_qualified = url_for(qualified_ep, **kwargs)
                self.assertEqual(
                    url_legacy,
                    url_qualified,
                    f"Incohérence entre {legacy_ep} ({url_legacy}) et {qualified_ep} ({url_qualified})",
                )

    def test_init_functions_idempotence(self):
        """Vérifie que réappeler les anciennes fonctions init_*_routes ne produit aucune erreur ni collision."""
        init_web_routes(self.app)
        init_checkout_routes(self.app)
        init_checkin_routes(self.app)
        init_waiver_routes(self.app)
        init_incident_public_routes(self.app)
        self.assertIn("public_web", self.app.blueprints)
        self.assertIn("public_inspections", self.app.blueprints)
        self.assertIn("public_waivers", self.app.blueprints)
        self.assertIn("public_incidents", self.app.blueprints)


if __name__ == "__main__":
    unittest.main()
