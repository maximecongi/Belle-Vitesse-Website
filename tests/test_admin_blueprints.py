"""
Tests unitaires pour l'architecture des Blueprints Admin Flask et l'aliasing d'URL.
Vérifie :
1. L'enregistrement complet de tous les Blueprints d'administration.
2. La conformité des préfixes d'URL (/admin).
3. La résolution bidirectionnelle des endpoints via url_for (alias historiques vs nom qualifié de Blueprint).
4. L'idempotence des fonctions de compatibilité init_*_routes.
"""

import unittest
from flask import Blueprint, url_for
from app import create_app
from routes.admin import (
    ADMIN_BLUEPRINTS,
    admin_url_alias_handler,
    api_bp,
    auth_bp,
    booking_bp,
    calendar_bp,
    catalog_bp,
    checkins_bp,
    checkouts_bp,
    checkpoints_bp,
    contacts_bp,
    dashboard_bp,
    files_bp,
    fleet_bp,
    incidents_bp,
    mcp_tokens_bp,
    newsletter_bp,
    pricing_bp,
    productions_bp,
    projects_bp,
    settings_bp,
    tools_bp,
    users_bp,
    waivers_bp,
    init_auth_routes,
    init_projects_routes,
)


class AdminBlueprintsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def test_all_admin_modules_are_blueprints(self):
        """Vérifie que chaque module admin est bien une instance de Blueprint."""
        expected_bps = [
            api_bp,
            auth_bp,
            booking_bp,
            calendar_bp,
            catalog_bp,
            checkins_bp,
            checkouts_bp,
            checkpoints_bp,
            contacts_bp,
            dashboard_bp,
            files_bp,
            fleet_bp,
            incidents_bp,
            mcp_tokens_bp,
            newsletter_bp,
            pricing_bp,
            productions_bp,
            projects_bp,
            settings_bp,
            tools_bp,
            users_bp,
            waivers_bp,
        ]
        self.assertEqual(len(ADMIN_BLUEPRINTS), len(expected_bps))
        for bp in expected_bps:
            self.assertIsInstance(bp, Blueprint, f"{bp} doit être une instance de Blueprint Flask")
            self.assertIn(bp.name, self.app.blueprints, f"Blueprint {bp.name} non enregistré sur app")

    def test_admin_blueprints_url_prefix(self):
        """Vérifie que les Blueprints admin ont le préfixe /admin approprié."""
        for bp in ADMIN_BLUEPRINTS:
            if bp.name == "admin_files":
                # Le blueprint des fichiers privés gère /files/<path>
                continue
            self.assertTrue(
                bp.url_prefix.startswith("/admin"),
                f"Le Blueprint {bp.name} a un url_prefix non conforme : {bp.url_prefix}",
            )

    def test_url_for_aliasing_bidirectional(self):
        """Vérifie que url_for fonctionne identiquement avec l'alias historique ou le nom qualifié Blueprint."""
        test_cases = [
            ("admin_login", "admin_auth.admin_login", None),
            ("admin_dashboard", "admin_dashboard.admin_dashboard", None),
            ("admin_projects_list", "admin_projects.admin_projects_list", None),
            ("admin_project_new", "admin_projects.admin_project_new", None),
            ("admin_checkouts_list", "admin_checkouts.admin_checkouts_list", None),
            ("admin_checkins_list", "admin_checkins.admin_checkins_list", None),
            ("admin_incidents_list", "admin_incidents.admin_incidents_list", None),
            ("admin_contacts_list", "admin_contacts.admin_contacts_list", None),
            ("admin_newsletter_dashboard", "admin_newsletter.admin_newsletter_dashboard", None),
            ("admin_pricing", "admin_pricing.admin_pricing", None),
            ("admin_calendar", "admin_calendar.admin_calendar", None),
            ("admin_catalog_preview", "admin_catalog.admin_catalog_preview", None),
            ("admin_users_list", "admin_users.admin_users_list", None),
            ("admin_pilot_waivers_list", "admin_waivers.admin_pilot_waivers_list", None),
            ("admin_production_waivers_list", "admin_waivers.admin_production_waivers_list", None),
        ]

        with self.app.test_request_context():
            for legacy_ep, qualified_ep, params in test_cases:
                kwargs = params or {}
                url_legacy = url_for(legacy_ep, **kwargs)
                url_qualified = url_for(qualified_ep, **kwargs)
                self.assertEqual(
                    url_legacy,
                    url_qualified,
                    f"Incohérence entre {legacy_ep} ({url_legacy}) et {qualified_ep} ({url_qualified})",
                )
                self.assertTrue(
                    url_legacy.startswith("/admin"),
                    f"L'URL {url_legacy} pour {legacy_ep} doit commencer par /admin",
                )

    def test_init_functions_idempotence(self):
        """Vérifie que réappeler les anciennes fonctions init_*_routes ne produit aucune erreur ni collision."""
        init_auth_routes(self.app)
        init_projects_routes(self.app)
        self.assertIn("admin_auth", self.app.blueprints)
        self.assertIn("admin_projects", self.app.blueprints)


if __name__ == "__main__":
    unittest.main()
