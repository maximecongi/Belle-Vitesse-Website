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
from models import CalendarSubscription, User, db


class CalendarPermissionsTestCase(unittest.TestCase):
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

            # Create test users with different roles
            self.user_regular = User(
                firstname="Regular",
                lastname="Technician",
                mail="tech@bellevitesse.com",
                role="user"
            )
            self.user_commercial = User(
                firstname="Alice",
                lastname="Commercial",
                mail="alice@bellevitesse.com",
                role="commercial"
            )
            self.user_manager = User(
                firstname="Bob",
                lastname="Manager",
                mail="bob@bellevitesse.com",
                role="manager"
            )
            self.user_admin = User(
                firstname="Charlie",
                lastname="Admin",
                mail="charlie@bellevitesse.com",
                role="administrator"
            )
            self.user_super_admin = User(
                firstname="Super",
                lastname="Admin",
                mail="super@bellevitesse.com",
                role="super administrator"
            )

            db.session.add_all([
                self.user_regular,
                self.user_commercial,
                self.user_manager,
                self.user_admin,
                self.user_super_admin
            ])
            db.session.commit()

            self.user_regular_id = self.user_regular.id
            self.user_commercial_id = self.user_commercial.id
            self.user_manager_id = self.user_manager.id
            self.user_admin_id = self.user_admin.id
            self.user_super_admin_id = self.user_super_admin.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _login_as(self, user):
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = user.id
            sess["admin_user_firstname"] = user.firstname
            sess["admin_user_lastname"] = user.lastname
            sess["admin_user_role"] = user.role

    def test_unauthenticated_access_redirects_to_login(self):
        """Unauthenticated user should be redirected to login page."""
        response = self.client.get("/admin/calendar")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login", response.location)

    def test_user_role_cannot_access_calendar(self):
        """User with role 'user' should be forbidden / redirected to dashboard."""
        self._login_as(self.user_regular)
        response = self.client.get("/admin/calendar", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/dashboard", response.location)

    def test_commercial_sees_only_own_calendar(self):
        """Commercial user should only see their own calendar entry."""
        self._login_as(self.user_commercial)
        response = self.client.get("/admin/calendar")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        self.assertIn("alice@bellevitesse.com", html)
        self.assertNotIn("bob@bellevitesse.com", html)
        self.assertNotIn("charlie@bellevitesse.com", html)
        self.assertNotIn("super@bellevitesse.com", html)
        self.assertNotIn("tech@bellevitesse.com", html)

    def test_manager_sees_only_own_calendar(self):
        """Manager user should only see their own calendar entry."""
        self._login_as(self.user_manager)
        response = self.client.get("/admin/calendar")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        self.assertIn("bob@bellevitesse.com", html)
        self.assertNotIn("alice@bellevitesse.com", html)
        self.assertNotIn("charlie@bellevitesse.com", html)
        self.assertNotIn("super@bellevitesse.com", html)

    def test_administrator_sees_only_own_calendar(self):
        """Administrator user should only see their own calendar entry."""
        self._login_as(self.user_admin)
        response = self.client.get("/admin/calendar")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        self.assertIn("charlie@bellevitesse.com", html)
        self.assertNotIn("alice@bellevitesse.com", html)
        self.assertNotIn("bob@bellevitesse.com", html)
        self.assertNotIn("super@bellevitesse.com", html)

    def test_super_administrator_sees_all_users(self):
        """Super Administrator user should see all users."""
        self._login_as(self.user_super_admin)
        response = self.client.get("/admin/calendar")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        self.assertIn("super@bellevitesse.com", html)
        self.assertIn("alice@bellevitesse.com", html)
        self.assertIn("bob@bellevitesse.com", html)
        self.assertIn("charlie@bellevitesse.com", html)
        self.assertIn("tech@bellevitesse.com", html)

    def test_non_super_admin_cannot_generate_for_other_user(self):
        """If a commercial tries to generate a subscription with another user_id, it is forced to their own."""
        self._login_as(self.user_commercial)
        # Attempt to post with user_admin_id
        response = self.client.post(
            "/admin/calendar/generate",
            data={"user_id": str(self.user_admin_id)},
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            # Check that subscription was created for commercial, NOT admin
            comm_sub = CalendarSubscription.query.filter_by(
                user_id=self.user_commercial_id, is_active=True
            ).first()
            admin_sub = CalendarSubscription.query.filter_by(
                user_id=self.user_admin_id, is_active=True
            ).first()

            self.assertIsNotNone(comm_sub)
            self.assertIsNone(admin_sub)

    def test_super_admin_can_generate_for_other_user(self):
        """Super admin can generate subscription for any user specified in form."""
        self._login_as(self.user_super_admin)
        response = self.client.post(
            "/admin/calendar/generate",
            data={"user_id": str(self.user_manager_id)},
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            manager_sub = CalendarSubscription.query.filter_by(
                user_id=self.user_manager_id, is_active=True
            ).first()
            self.assertIsNotNone(manager_sub)


if __name__ == "__main__":
    unittest.main()
