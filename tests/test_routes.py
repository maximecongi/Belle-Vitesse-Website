import unittest
import os
import sys
from unittest.mock import MagicMock

# --- Mocking WeasyPrint to avoid OSError on environments without GObject ---
mock_weasyprint = MagicMock()
mock_weasyprint.HTML = MagicMock()
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from app import create_app
from models import db

class RouteSmokeTest(unittest.TestCase):
    def setUp(self):
        # Use a test config
        os.environ["FLASK_ENV"] = "testing"
        os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        os.environ["WTF_CSRF_ENABLED"] = "False"
        
        # Prevent SSH tunnel or other prod-only things if possible
        os.environ["USE_SSH_TUNNEL"] = "false"
        
        self.app = create_app()
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
            print(f"\nDEBUG: About Us fail: {response.data.decode('utf-8', 'ignore')[:1000]}")
        self.assertEqual(response.status_code, 200)

    def test_contact_page(self):
        """Test that the contact page is accessible."""
        response = self.client.get("/en/contact")
        if response.status_code != 200:
            print(f"\nDEBUG: Contact fail: {response.data.decode('utf-8', 'ignore')[:1000]}")
        self.assertEqual(response.status_code, 200)

    def test_admin_login_page(self):
        """Test that the admin login page is accessible."""
        response = self.client.get("/admin/login")
        if response.status_code != 200:
            print(f"\nDEBUG: Admin Login fail: {response.data.decode('utf-8', 'ignore')[:1000]}")
        self.assertEqual(response.status_code, 200)

if __name__ == "__main__":
    unittest.main()
