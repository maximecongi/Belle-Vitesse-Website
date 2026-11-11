"""Pages épinglées (favoris ⌘ + ;) : API /admin/api/pins et rendu sidebar."""
import unittest

from models import UserPin, db
from tests.base import BaseTestCase


class UserPinsApiTestCase(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.alice = self.create_user(firstname="Alice", mail="alice@bv.test", role="manager")
        self.bob = self.create_user(firstname="Bob", mail="bob@bv.test", role="manager")
        self.login(self.alice.id)

    def login(self, user_id):
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_role"] = "manager"
            sess["admin_user_id"] = user_id

    def pin(self, url, label="Favori"):
        return self.client.post("/admin/api/pins", json={"url": url, "label": label})

    def test_create_and_list(self):
        resp = self.pin("/admin/projects/12", "BVPR-2026-001 — Film")
        self.assertEqual(resp.status_code, 200)
        pins = resp.get_json()["pins"]
        self.assertEqual(len(pins), 1)
        self.assertEqual(pins[0]["url"], "/admin/projects/12")
        self.assertEqual(pins[0]["label"], "BVPR-2026-001 — Film")

        listed = self.client.get("/admin/api/pins").get_json()["pins"]
        self.assertEqual(listed, pins)

    def test_same_url_updates_label_and_strips_return_to(self):
        self.pin("/admin/incidents/3?return_to=/admin/dashboard", "Ancien")
        resp = self.pin("/admin/incidents/3", "  Nouveau   nom ")
        pins = resp.get_json()["pins"]
        self.assertEqual(len(pins), 1)
        self.assertEqual(pins[0]["url"], "/admin/incidents/3")
        self.assertEqual(pins[0]["label"], "Nouveau nom")

    def test_query_string_is_kept(self):
        pins = self.pin("/admin/projects?status=active&q=film").get_json()["pins"]
        self.assertEqual(pins[0]["url"], "/admin/projects?status=active&q=film")

    def test_rejects_external_or_invalid(self):
        for url in ("https://evil.com/admin", "//evil.com/admin", "/public/page", "", None):
            self.assertEqual(self.pin(url).status_code, 400, url)
        self.assertEqual(self.pin("/admin/fleet", "   ").status_code, 400)
        self.assertEqual(UserPin.query.count(), 0)

    def test_label_truncated(self):
        pins = self.pin("/admin/fleet", "x" * 300).get_json()["pins"]
        self.assertEqual(len(pins[0]["label"]), UserPin.LABEL_MAX)

    def test_rename_and_delete(self):
        pin_id = self.pin("/admin/fleet", "Flotte").get_json()["pin"]["id"]
        resp = self.client.patch(f"/admin/api/pins/{pin_id}", json={"label": "Véhicules"})
        self.assertEqual(resp.get_json()["pins"][0]["label"], "Véhicules")

        resp = self.client.delete(f"/admin/api/pins/{pin_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["pins"], [])

    def test_isolation_between_users(self):
        pin_id = self.pin("/admin/fleet", "Alice").get_json()["pin"]["id"]

        self.login(self.bob.id)
        self.assertEqual(self.client.get("/admin/api/pins").get_json()["pins"], [])
        self.assertEqual(self.client.patch(f"/admin/api/pins/{pin_id}", json={"label": "pirate"}).status_code, 404)
        self.assertEqual(self.client.delete(f"/admin/api/pins/{pin_id}").status_code, 404)
        self.client.post("/admin/api/pins/reorder", json={"ids": [pin_id]})

        pin = db.session.get(UserPin, pin_id)
        self.assertIsNotNone(pin)
        self.assertEqual(pin.label, "Alice")

    def test_reorder(self):
        a = self.pin("/admin/a", "A").get_json()["pin"]["id"]
        b = self.pin("/admin/b", "B").get_json()["pin"]["id"]
        c = self.pin("/admin/c", "C").get_json()["pin"]["id"]

        resp = self.client.post("/admin/api/pins/reorder", json={"ids": [c, a]})
        self.assertEqual([p["id"] for p in resp.get_json()["pins"]], [c, a, b])

        self.assertEqual(self.client.post("/admin/api/pins/reorder", json={"ids": "nope"}).status_code, 400)
        self.assertEqual(self.client.post("/admin/api/pins/reorder", json={"ids": ["x"]}).status_code, 400)

    def test_requires_authentication(self):
        with self.client.session_transaction() as sess:
            sess.clear()
        resp = self.pin("/admin/fleet")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(UserPin.query.count(), 0)

    def test_sidebar_renders_pins_above_dashboard(self):
        self.pin("/admin/projects", "Mes projets")
        html = self.client.get("/admin/dashboard").get_data(as_text=True)
        self.assertIn("Mes projets", html)
        self.assertIn('id="pinModal"', html)
        self.assertLess(html.index("admin-nav-pins"), html.index("Tableau de bord</span>"))


if __name__ == "__main__":
    unittest.main()
