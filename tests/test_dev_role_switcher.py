import os
import sys
import unittest
from unittest.mock import MagicMock

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock WeasyPrint
mock_weasyprint = MagicMock()
mock_weasyprint.HTML = MagicMock()
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint

from app import create_app
from models import User, db


class DevRoleSwitcherTestCase(unittest.TestCase):
    def setUp(self):
        os.environ["FLASK_ENV"] = "testing"
        os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        os.environ["WTF_CSRF_ENABLED"] = "False"
        os.environ["LAUNCH_MODE"] = "false"
        os.environ["USE_SSH_TUNNEL"] = "false"

        self.app = create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

            # Create a user with database role Super Administrator
            self.user = User(
                firstname="Maxime",
                lastname="Admin",
                mail="maxime@bellevitesse.com",
                role="Super Administrator"
            )
            db.session.add(self.user)
            db.session.commit()
            self.user_id = self.user.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _login(self):
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = self.user_id
            sess["admin_user_firstname"] = self.user.firstname
            sess["admin_user_lastname"] = self.user.lastname
            sess["admin_user_role"] = self.user.role

    def test_switch_role_unauthenticated(self):
        """Unauthenticated call to switch role redirects to login."""
        response = self.client.post("/admin/dev/switch-role", data={"role": "Manager"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login", response.location)

    def test_switch_role_in_production_blocked(self):
        """In production environment, role switching is forbidden."""
        self._login()
        self.app.config["FLASK_ENV"] = "production"

        response = self.client.post("/admin/dev/switch-role", data={"role": "Manager"})
        self.assertEqual(response.status_code, 302)

        # Ensure session role was NOT modified
        with self.client.session_transaction() as sess:
            self.assertEqual(sess["admin_user_role"], "Super Administrator")

    def test_switch_role_in_dev_updates_session_only(self):
        """Switching role updates session role without altering the database."""
        self._login()
        self.app.config["FLASK_ENV"] = "development"

        # Switch to Commercial
        response = self.client.post(
            "/admin/dev/switch-role",
            data={"role": "Commercial", "next": "/admin/dashboard"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/dashboard", response.location)

        # Check session role is Commercial
        with self.client.session_transaction() as sess:
            self.assertEqual(sess["admin_user_role"], "Commercial")

        # Check DB role remains untouched (Super Administrator)
        with self.app.app_context():
            db_user = db.session.get(User, self.user_id)
            self.assertEqual(db_user.role, "Super Administrator")

    def test_switch_role_affects_template_context_and_permissions(self):
        """After switching to User, accessing restricted pages like calendar is blocked by require_roles."""
        self._login()
        self.app.config["FLASK_ENV"] = "development"

        # 1. Initially Super Admin can access /admin/calendar
        resp1 = self.client.get("/admin/calendar")
        self.assertEqual(resp1.status_code, 200)

        # 2. Switch role to User
        self.client.post("/admin/dev/switch-role", data={"role": "User"})

        # 3. Accessing /admin/calendar is now redirected to dashboard (forbidden for role 'user')
        resp2 = self.client.get("/admin/calendar", follow_redirects=False)
        self.assertEqual(resp2.status_code, 302)
        self.assertIn("/admin/dashboard", resp2.location)

        # 4. Switch back to Manager -> /admin/calendar is accessible and shows only own calendar
        self.client.post("/admin/dev/switch-role", data={"role": "Manager"})
        resp3 = self.client.get("/admin/calendar")
        self.assertEqual(resp3.status_code, 200)

    def test_reset_role_restores_db_role(self):
        """Resetting role restores the original role from the database."""
        self._login()
        self.app.config["FLASK_ENV"] = "development"

        # Switch to User
        self.client.post("/admin/dev/switch-role", data={"role": "User"})
        with self.client.session_transaction() as sess:
            self.assertEqual(sess["admin_user_role"], "User")

        # Reset role
        self.client.post("/admin/dev/switch-role", data={"role": "reset"})
        with self.client.session_transaction() as sess:
            self.assertEqual(sess["admin_user_role"], "Super Administrator")

    def test_user_cannot_access_or_see_catalog_update(self):
        """User role should not see catalog_update in sidebar nav and should be forbidden on catalog preview/update."""
        self._login()
        self.app.config["FLASK_ENV"] = "development"

        # Switch to User
        self.client.post("/admin/dev/switch-role", data={"role": "User"})

        # Dashboard sidebar check: 'Mise à jour du catalogue' should NOT be present
        resp_dash = self.client.get("/admin/dashboard")
        self.assertEqual(resp_dash.status_code, 200)
        self.assertNotIn("Mise à jour du catalogue", resp_dash.data.decode("utf-8"))

        # Accessing /admin/catalog/preview directly should redirect to dashboard
        resp_prev = self.client.get("/admin/catalog/preview", follow_redirects=False)
        self.assertEqual(resp_prev.status_code, 302)
        self.assertIn("/admin/dashboard", resp_prev.location)

        # Accessing /admin/catalog/update directly should redirect to dashboard
        resp_up = self.client.get("/admin/catalog/update", follow_redirects=False)
        self.assertEqual(resp_up.status_code, 302)
        self.assertIn("/admin/dashboard", resp_up.location)

    def test_docs_restricted_to_admin_and_super_admin(self):
        """Technical and API docs should only be accessible/visible to Administrator and Super Administrator."""
        self._login()
        self.app.config["FLASK_ENV"] = "development"

        # 1. Super Administrator has access
        resp_sa_docs = self.client.get("/admin/docs")
        self.assertEqual(resp_sa_docs.status_code, 200)
        resp_sa_api = self.client.get("/admin/api-docs")
        self.assertEqual(resp_sa_api.status_code, 200)

        # 2. Administrator has access
        self.client.post("/admin/dev/switch-role", data={"role": "Administrator"})
        resp_admin_docs = self.client.get("/admin/docs")
        self.assertEqual(resp_admin_docs.status_code, 200)
        resp_admin_api = self.client.get("/admin/api-docs")
        self.assertEqual(resp_admin_api.status_code, 200)

        # 3. Manager is blocked and does not see docs in sidebar
        self.client.post("/admin/dev/switch-role", data={"role": "Manager"})
        resp_mgr_dash = self.client.get("/admin/dashboard")
        self.assertNotIn("Documentation technique", resp_mgr_dash.data.decode("utf-8"))
        self.assertNotIn("Documentation API", resp_mgr_dash.data.decode("utf-8"))

        resp_mgr_docs = self.client.get("/admin/docs", follow_redirects=False)
        self.assertEqual(resp_mgr_docs.status_code, 302)
        self.assertIn("/admin/dashboard", resp_mgr_docs.location)

        resp_mgr_api = self.client.get("/admin/api-docs", follow_redirects=False)
        self.assertEqual(resp_mgr_api.status_code, 302)
        self.assertIn("/admin/dashboard", resp_mgr_api.location)

        # 4. Commercial is blocked and does not see docs in sidebar
        self.client.post("/admin/dev/switch-role", data={"role": "Commercial"})
        resp_comm_dash = self.client.get("/admin/dashboard")
        self.assertNotIn("Documentation technique", resp_comm_dash.data.decode("utf-8"))
        self.assertNotIn("Documentation API", resp_comm_dash.data.decode("utf-8"))

        resp_comm_docs = self.client.get("/admin/docs", follow_redirects=False)
        self.assertEqual(resp_comm_docs.status_code, 302)
        self.assertIn("/admin/dashboard", resp_comm_docs.location)

        resp_comm_api = self.client.get("/admin/api-docs", follow_redirects=False)
        self.assertEqual(resp_comm_api.status_code, 302)
        self.assertIn("/admin/dashboard", resp_comm_api.location)

    def test_manager_can_modify_only_users_and_commercials(self):
        """Manager can only edit users with role User or Commercial, and cannot edit other Managers or Admins."""
        self._login()
        self.app.config["FLASK_ENV"] = "development"

        with self.app.app_context():
            u_user = User(firstname="Tech", lastname="User", mail="tech@test.com", role="User")
            u_comm = User(firstname="Sales", lastname="Commercial", mail="sales@test.com", role="Commercial")
            u_other_mgr = User(firstname="Other", lastname="Manager", mail="mgr@test.com", role="Manager")
            u_admin = User(firstname="Big", lastname="Admin", mail="admin@test.com", role="Administrator")
            db.session.add_all([u_user, u_comm, u_other_mgr, u_admin])
            db.session.commit()
            u_user_id = u_user.id
            u_comm_id = u_comm.id
            u_other_mgr_id = u_other_mgr.id
            u_admin_id = u_admin.id

        # Switch to Manager
        self.client.post("/admin/dev/switch-role", data={"role": "Manager"})

        # 1. Can access edit page for User
        resp = self.client.get(f"/admin/users/{u_user_id}/edit")
        self.assertEqual(resp.status_code, 200)

        # 2. Can access edit page for Commercial
        resp = self.client.get(f"/admin/users/{u_comm_id}/edit")
        self.assertEqual(resp.status_code, 200)

        # 3. CANNOT access edit page for another Manager
        resp = self.client.get(f"/admin/users/{u_other_mgr_id}/edit", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/admin/users", resp.location)

        # 4. CANNOT access edit page for Administrator
        resp = self.client.get(f"/admin/users/{u_admin_id}/edit", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/admin/users", resp.location)

        # 5. CANNOT delete another Manager or Admin
        resp = self.client.post(f"/admin/users/{u_other_mgr_id}/delete", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)

        resp = self.client.post(f"/admin/users/{u_admin_id}/delete", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)

        # 6. CANNOT edit own Super Admin account when simulated role is Manager
        resp_self_edit = self.client.get(f"/admin/users/{self.user_id}/edit", follow_redirects=False)
        self.assertEqual(resp_self_edit.status_code, 302)
        self.assertIn("/admin/users", resp_self_edit.location)

        # In users list HTML, Super Admin row should show '—' and NOT 'Modifier'
        resp_list = self.client.get("/admin/users")
        self.assertEqual(resp_list.status_code, 200)
        # Should not have edit link for self.user_id
        self.assertNotIn(f"/admin/users/{self.user_id}/edit", resp_list.data.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
