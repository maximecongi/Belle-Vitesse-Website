"""Rôle « Associé » : périmètre de lecture de l'administrateur, aucune écriture."""
import unittest

from models import Contact, User, db
from tests.base import BaseTestCase
from utils.context_processors import get_user_permissions, resolve_user_role, role_can
from utils.decorators import is_read_only_request_blocked, normalize_role


class AssociateRoleHelpersTestCase(unittest.TestCase):
    def test_normalize_role_variants(self):
        for raw in ("Associé", "associé", "ASSOCIE", " associe ", "partner"):
            self.assertEqual(normalize_role(raw), "associé", raw)

    def test_resolve_user_role(self):
        self.assertEqual(resolve_user_role({"role_lower": "associé"}), "associé")
        self.assertEqual(resolve_user_role({}, "Associé"), "associé")

    def test_navigation_mirrors_admin_without_write_entries(self):
        perms = get_user_permissions("associé")
        admin_nav = get_user_permissions("administrateur")["nav"]
        self.assertIn("indicators", perms["nav"])
        self.assertIn("settings", perms["nav"])
        self.assertNotIn("catalog_update", perms["nav"])
        self.assertTrue(perms["nav"] <= admin_nav)

    def test_role_can_only_grants_read_actions(self):
        self.assertTrue(role_can("Associé", "project_commercial_timeline"))
        self.assertTrue(role_can("Associé", "equipment_usage_admin"))
        for action in ("project_edit", "project_delete", "pricing_edit", "fleet_checkpoints_config"):
            self.assertFalse(role_can("Associé", action), action)

    def test_blocked_request_matrix(self):
        self.assertTrue(is_read_only_request_blocked("admin_projects.admin_project_delete", "POST"))
        self.assertTrue(is_read_only_request_blocked("admin_projects.admin_project_new", "GET"))
        self.assertTrue(is_read_only_request_blocked("admin_projects.admin_project_edit", "GET"))
        self.assertTrue(is_read_only_request_blocked("admin_catalog.admin_catalog_update", "GET"))
        self.assertFalse(is_read_only_request_blocked("admin_projects.admin_project_detail", "GET"))
        self.assertFalse(is_read_only_request_blocked("admin_settings.admin_settings_edit", "GET"))
        self.assertTrue(is_read_only_request_blocked("admin_settings.admin_settings_edit", "POST"))
        self.assertFalse(is_read_only_request_blocked("admin_auth.admin_logout", "GET"))
        self.assertFalse(is_read_only_request_blocked("admin_api.admin_api_checkout_status", "GET"))
        self.assertTrue(is_read_only_request_blocked("admin_api.admin_api_checkout_status", "POST"))


class AssociateRoleRoutesTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.associate = User(firstname="Paul", lastname="Associe", mail="assoc@bellevitesse.com", role="Associé")
        self.contact = Contact(first_name="Jean", last_name="Témoin", mail="temoin@example.com")
        db.session.add_all([self.associate, self.contact])
        db.session.commit()
        self.associate_id = self.associate.id
        self.contact_id = self.contact.id
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = self.associate_id
            sess["admin_user_firstname"] = "Paul"
            sess["admin_user_lastname"] = "Associe"
            sess["admin_user_role"] = "Associé"

    def test_model_flags(self):
        user = db.session.get(User, self.associate_id)
        self.assertTrue(user.is_read_only)
        self.assertFalse(user.is_admin)
        self.assertEqual(user.role_display, "Associé")

    def test_can_read_admin_only_pages(self):
        for url in ("/admin/dashboard", "/admin/indicators", "/admin/users", "/admin/contacts",
                    "/admin/projects", "/admin/settings/", "/admin/pricing"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)

    def test_read_only_banner_rendered(self):
        response = self.client.get("/admin/dashboard")
        html = response.get_data(as_text=True)
        self.assertIn('class="is-read-only"', html)
        self.assertIn("admin-read-only-banner", html)

    def test_create_and_edit_pages_are_refused(self):
        for url in ("/admin/projects/new", "/admin/contacts/new",
                    f"/admin/contacts/{self.contact_id}/edit", "/admin/users/new"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)

    def test_form_writes_are_refused_and_data_untouched(self):
        response = self.client.post(f"/admin/contacts/{self.contact_id}/delete")
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(db.session.get(Contact, self.contact_id))

        response = self.client.post("/admin/settings/", data={"company_name": "Piraté"})
        self.assertEqual(response.status_code, 302)

    def test_json_writes_return_403(self):
        response = self.client.post("/admin/api/contacts/quick", json={"first_name": "X", "last_name": "Y"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.get_json()["success"])

    def test_personal_pins_remain_allowed(self):
        response = self.client.get("/admin/api/pins")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
