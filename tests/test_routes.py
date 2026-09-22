import os
import sys
import unittest
from unittest.mock import MagicMock

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Isolation stricte de l'environnement de test avant tout import d'app
os.environ["FLASK_ENV"] = "testing"
os.environ["TESTING"] = "True"
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
os.environ["WTF_CSRF_ENABLED"] = "False"
os.environ["USE_SSH_TUNNEL"] = "false"
os.environ["LAUNCH_MODE"] = "false"

# --- Mocking WeasyPrint to avoid OSError on environments without GObject ---
mock_weasyprint = MagicMock()
mock_weasyprint.HTML = MagicMock()
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint

from app import create_app  # noqa: E402
from models import db  # noqa: E402


class RouteSmokeTest(unittest.TestCase):
    def setUp(self):
        # Use a test config
        os.environ["FLASK_ENV"] = "testing"
        os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        os.environ["WTF_CSRF_ENABLED"] = "False"
        os.environ["LAUNCH_MODE"] = "false"

        # Prevent SSH tunnel or other prod-only things if possible
        os.environ["USE_SSH_TUNNEL"] = "false"

        self.app = create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_home_page(self):
        """Test that the home page is accessible."""
        response = self.client.get("/en/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Belle Vitesse", response.data)

    def test_about_us_page(self):
        """Test that the about us page is accessible."""
        response = self.client.get("/en/about-us")
        if response.status_code != 200:
            print(
                f"\nDEBUG: About Us fail: {response.data.decode('utf-8', 'ignore')[:1000]}")
        self.assertEqual(response.status_code, 200)

    def test_contact_page(self):
        """Test that the contact page is accessible."""
        response = self.client.get("/en/contact")
        if response.status_code != 200:
            print(
                f"\nDEBUG: Contact fail: {response.data.decode('utf-8', 'ignore')[:1000]}")
        self.assertEqual(response.status_code, 200)

    def test_admin_login_page(self):
        """Test that the admin login page is accessible."""
        response = self.client.get("/admin/login")
        self.assertEqual(response.status_code, 200)

    def test_public_checkout_view_404(self):
        """Test that public checkout view returns 404 for non-existent record."""
        # Requires CHECK_API_TOKEN
        os.environ["CHECK_API_TOKEN"] = "test-token"
        response = self.client.get("/checkout/non-existent", headers={"X-Check-Token": "test-token"})
        self.assertEqual(response.status_code, 404)

    def test_public_checkin_view_404(self):
        """Test that public checkin view returns 404 for non-existent record."""
        os.environ["CHECK_API_TOKEN"] = "test-token"
        response = self.client.get("/checkin/non-existent", headers={"X-Check-Token": "test-token"})
        self.assertEqual(response.status_code, 404)

    def test_public_waiver_sign_page_404(self):
        """Test that public waiver sign page returns 404 for invalid token."""
        response = self.client.get("/waiver/sign/invalid-token")
        self.assertEqual(response.status_code, 404)

    def test_unsubscribe_success(self):
        """Test that unsubscribing with a valid token works and does not 500."""
        from itsdangerous import URLSafeSerializer
        from models.newsletter import NewsletterSubscriber

        with self.app.app_context():
            sub = NewsletterSubscriber(email="test_unsub@example.com")
            db.session.add(sub)
            db.session.commit()

        secret_key = self.app.config.get("SECRET_KEY") or "bv_super_secret_key_2026"
        serializer = URLSafeSerializer(secret_key)
        token = serializer.dumps("test_unsub@example.com")

        response = self.client.get(f"/unsubscribe/{token}")
        self.assertEqual(response.status_code, 200)

    def test_quick_contact_creation(self):
        """Test the /admin/api/contacts/quick endpoint."""
        from models import User, Contact, Production
        with self.app.app_context():
            user = User(firstname="Admin", lastname="User", mail="admin@test.com", role="administrator")
            prod = Production(name="Prod Alpha")
            db.session.add_all([user, prod])
            db.session.commit()
            user_id = user.id
            prod_id = prod.id

        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = user_id
            sess["admin_user_role"] = "administrator"

        # Missing names validation
        resp = self.client.post("/admin/api/contacts/quick", json={"first_name": "", "last_name": ""})
        self.assertEqual(resp.status_code, 400)

        # Success creation
        resp = self.client.post("/admin/api/contacts/quick", json={
            "first_name": "Sophie",
            "last_name": "Lumière",
            "job_title": "Directeur.rice de la photographie",
            "mail": "sophie@example.com",
            "phone": "0601020304",
            "production_id": prod_id
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertIn("id", data)
        self.assertEqual(data["first_name"], "Sophie")
        self.assertEqual(data["last_name"], "Lumière")
        self.assertEqual(data["name"], "Sophie Lumière (Directeur.rice de la photographie)")
        self.assertEqual(data["mail"], "sophie@example.com")
        self.assertEqual(data["phone"], "0601020304")
        self.assertEqual(data["production_id"], str(prod_id))

        with self.app.app_context():
            c = db.session.get(Contact, int(data["id"]))
            self.assertIsNotNone(c)
            self.assertEqual(c.first_name, "Sophie")


    def test_public_checkout_endpoints(self):
        """Test public checkout routes behavior."""
        os.environ["CHECK_API_TOKEN"] = "test-token"
        # Generate requires record_id
        resp = self.client.post("/checkout/generate", json={}, headers={"X-Check-Token": "test-token"})
        self.assertEqual(resp.status_code, 400)

        # Invalid token signature page
        resp = self.client.get("/checkout/sign/invalid-token")
        self.assertEqual(resp.status_code, 404)

        # Invalid token signature submission
        resp = self.client.post("/checkout/sign/invalid-token", json={"signature": "data"})
        self.assertEqual(resp.status_code, 404)

        # Abandon & resume
        resp = self.client.post("/checkout/sign/invalid-token/abandon")
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post("/checkout/sign/invalid-token/resume")
        self.assertEqual(resp.status_code, 200)

        # Verify non-existent
        resp = self.client.get("/checkout/verify/BVCO-NONEXISTENT")
        self.assertEqual(resp.status_code, 404)

        # Document download without auth or token
        resp = self.client.get("/checkout/document/test.pdf")
        self.assertEqual(resp.status_code, 403)

    def test_public_checkin_endpoints(self):
        """Test public checkin routes behavior."""
        os.environ["CHECK_API_TOKEN"] = "test-token"
        # Generate requires record_id
        resp = self.client.post("/checkin/generate", json={}, headers={"X-Check-Token": "test-token"})
        self.assertEqual(resp.status_code, 400)

        # Invalid token signature page
        resp = self.client.get("/checkin/sign/invalid-token")
        self.assertEqual(resp.status_code, 404)

        # Invalid token signature submission
        resp = self.client.post("/checkin/sign/invalid-token", json={"signature": "data"})
        self.assertEqual(resp.status_code, 404)

        # Abandon & resume
        resp = self.client.post("/checkin/sign/invalid-token/abandon")
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post("/checkin/sign/invalid-token/resume")
        self.assertEqual(resp.status_code, 200)

        # Verify non-existent
        resp = self.client.get("/checkin/verify/BVCI-NONEXISTENT")
        self.assertEqual(resp.status_code, 404)

        # Document download without auth or token
        resp = self.client.get("/checkin/document/test.pdf")
        self.assertEqual(resp.status_code, 403)

    def test_serve_private_file_unauthenticated_forbidden(self):
        """Test that accessing /files/<path> without authentication or token returns 403."""
        resp = self.client.get("/files/2026/09/PROD/PROJECT/test.pdf")
        self.assertEqual(resp.status_code, 403)

    def test_serve_private_file_with_valid_hmac_token(self):
        """Test that accessing /files/<path> with a valid HMAC access token passes auth (returns 404 if file absent, not 403)."""
        from utils.document_utils import generate_pdf_access_token
        path = "2026/09/PROD/PROJECT/test.pdf"
        token = generate_pdf_access_token(path)
        resp = self.client.get(f"/files/{path}?t={token}")
        self.assertEqual(resp.status_code, 404)

    def test_serve_private_file_with_admin_session(self):
        """Test that logged-in admin can access /files/<path> (returns 404 if file absent, not 403)."""
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_role"] = "technicien"

        resp = self.client.get("/files/2026/09/PROD/PROJECT/test.pdf")
        self.assertEqual(resp.status_code, 404)

    def test_serve_private_file_with_jwt_token(self):
        """Test that API / iPad client with valid Bearer JWT can access /files/<path>."""
        from models import User
        from utils.jwt_auth import generate_token

        with self.app.app_context():
            user = User(firstname="Tech", lastname="BV", mail="tech@test.com", role="technicien")
            db.session.add(user)
            db.session.commit()
            token = generate_token(user)

        resp = self.client.get("/files/2026/09/PROD/PROJECT/test.pdf", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp.status_code, 404)

    def test_admin_docs_chapter_not_found_returns_404(self):
        """Test that accessing a non-existent technical docs chapter returns 404 instead of 500."""
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_role"] = "administrator"

        resp = self.client.get("/admin/docs/non_existent_chapter_xyz")
        self.assertEqual(resp.status_code, 404)


    def test_dashboard_agenda_today_checkout(self):
        """Test that a project with departure_date = today (Europe/Paris) is displayed in the dashboard checkout column."""
        from models import Project, Production
        from utils.formatting import get_today_paris

        today = get_today_paris()
        with self.app.app_context():
            prod = Production(name="Prod Test Dashboard")
            db.session.add(prod)
            db.session.commit()

            project = Project(
                name="Tournage Urgent Aujourd'hui",
                production_id=prod.id,
                departure_date=today,
                shoot_start_date=today
            )
            db.session.add(project)
            db.session.commit()

        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_role"] = "administrator"

        resp = self.client.get("/admin/dashboard")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Tournage Urgent Aujourd&#39;hui", resp.get_data(as_text=True))
        self.assertNotIn("Aucun départ ou retour prévu aujourd&#39;hui.", resp.get_data(as_text=True))

    def test_dashboard_agenda_shoot_start_fallback(self):
        """Test that a project without explicit departure_date falls back to shoot_start_date for checkout."""
        from models import Project, Production
        from utils.formatting import get_today_paris

        today = get_today_paris()
        with self.app.app_context():
            prod = Production(name="Prod Fallback Shoot")
            db.session.add(prod)
            db.session.commit()

            project = Project(
                name="Tournage Fallback Shoot Start",
                production_id=prod.id,
                departure_date=None,
                shoot_start_date=today
            )
            db.session.add(project)
            db.session.commit()

        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_role"] = "administrator"

        resp = self.client.get("/admin/dashboard")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Tournage Fallback Shoot Start", resp.get_data(as_text=True))

    def test_temp_email_preview_access_and_prod_guard(self):
        """Vérifie que la route temporaire est accessible en dev/test et bloquée (404) en production."""
        # 1. Accessible en dev/test
        resp = self.client.get("/temp-email-preview/waiver")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Décharge Signée", resp.get_data(as_text=True))

        resp_cron = self.client.get("/temp-email-preview/cron")
        self.assertEqual(resp_cron.status_code, 200)
        self.assertIn("Statut Quotidien", resp_cron.get_data(as_text=True))

        resp_badges = self.client.get("/badges-preview")
        self.assertEqual(resp_badges.status_code, 200)
        self.assertIn("Nuancier Complet", resp_badges.get_data(as_text=True))

        resp_all_badges = self.client.get("/temp-email-preview/all-badges")
        self.assertEqual(resp_all_badges.status_code, 200)
        self.assertIn("Nuancier Complet", resp_all_badges.get_data(as_text=True))

        # 2. Bloqué (404) en production
        prev_env = os.environ.get("FLASK_ENV")
        try:
            os.environ["FLASK_ENV"] = "production"
            resp_prod = self.client.get("/temp-email-preview/waiver")
            self.assertEqual(resp_prod.status_code, 404)

            resp_prod_badges = self.client.get("/badges-preview")
            self.assertEqual(resp_prod_badges.status_code, 404)
        finally:
            if prev_env is not None:
                os.environ["FLASK_ENV"] = prev_env
            else:
                os.environ.pop("FLASK_ENV", None)


if __name__ == "__main__":
    unittest.main()


