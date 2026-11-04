import unittest
import uuid

from tests.base import BaseTestCase
from models import User, db
from utils.jwt_auth import generate_token


class APIRouteSmokeTest(BaseTestCase):
    """Smoke tests pour les routes de l'API v1."""

    def test_api_login_no_email(self):
        """POST /api/v1/auth/login without email returns 400."""
        resp = self.client.post("/api/v1/auth/login",
                                json={},
                                content_type="application/json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.get_json())

    def test_api_checkouts_no_auth(self):
        """GET /api/v1/checkouts without JWT returns 401."""
        resp = self.client.get("/api/v1/checkouts")
        self.assertEqual(resp.status_code, 401)

    def test_api_checkins_no_auth(self):
        """GET /api/v1/checkins without JWT returns 401."""
        resp = self.client.get("/api/v1/checkins")
        self.assertEqual(resp.status_code, 401)

    def test_api_projects_no_auth(self):
        """GET /api/v1/projects without JWT returns 401."""
        resp = self.client.get("/api/v1/projects")
        self.assertEqual(resp.status_code, 401)

    def test_api_productions_no_auth(self):
        """GET /api/v1/productions without JWT returns 401."""
        resp = self.client.get("/api/v1/productions")
        self.assertEqual(resp.status_code, 401)

    def test_api_contacts_no_auth(self):
        """GET /api/v1/contacts without JWT returns 401."""
        resp = self.client.get("/api/v1/contacts")
        self.assertEqual(resp.status_code, 401)

    def test_api_calendar_no_auth(self):
        """GET /api/v1/calendar/events without JWT returns 401."""
        resp = self.client.get("/api/v1/calendar/events")
        self.assertEqual(resp.status_code, 401)

    def test_api_me_no_auth(self):
        """GET /api/v1/auth/me without JWT returns 401."""
        resp = self.client.get("/api/v1/auth/me")
        self.assertEqual(resp.status_code, 401)

    def test_api_with_invalid_token(self):
        """GET /api/v1/checkouts with invalid token returns 401."""
        resp = self.client.get("/api/v1/checkouts",
                                headers={"Authorization": "Bearer invalid-token"})
        self.assertEqual(resp.status_code, 401)

    def test_api_with_valid_jwt(self):
        """GET /api/v1/checkouts with valid JWT returns 200."""
        unique_mail = f"test-{uuid.uuid4().hex[:8]}@bellevitesse.com"
        user = User(firstname="Test", lastname="User",
                    mail=unique_mail, role="Administrator")
        db.session.add(user)
        db.session.commit()

        token = generate_token(user)

        resp = self.client.get("/api/v1/checkouts",
                               headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("checkouts", data)

    def test_api_me_with_valid_jwt(self):
        """GET /api/v1/auth/me with valid JWT returns user profile."""
        unique_mail = f"me-{uuid.uuid4().hex[:8]}@bellevitesse.com"
        user = User(firstname="Simon", lastname="Maignan",
                    mail=unique_mail, role="Administrateur")
        db.session.add(user)
        db.session.commit()

        token = generate_token(user)

        resp = self.client.get("/api/v1/auth/me",
                               headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["firstname"], "Simon")
        self.assertEqual(data["role"], "Administrateur")


if __name__ == "__main__":
    unittest.main()
