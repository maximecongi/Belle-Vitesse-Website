"""
Tests unitaires pour vérifier l'accès complet du rôle Commercial aux Décharges & Documents Légaux (CGL et BVSR).
"""
import os
import unittest

os.environ["FLASK_ENV"] = "testing"
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
os.environ["WTF_CSRF_ENABLED"] = "False"
os.environ["USE_SSH_TUNNEL"] = "false"

from app import create_app
from models import db, User, Project, Production, CglWaiver, SafetyRulesWaiver
from utils.context_processors import get_user_permissions
from utils.jwt_auth import generate_token


class CommercialWaiversAccessTest(unittest.TestCase):

    def setUp(self):
        os.environ["FLASK_ENV"] = "testing"
        os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        os.environ["WTF_CSRF_ENABLED"] = "False"
        os.environ["USE_SSH_TUNNEL"] = "false"

        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _create_mock_data(self):
        user = User(
            firstname="Alice",
            lastname="Commerciale",
            mail="alice.commerciale@bellevitesse.com",
            role="Commercial",
        )
        db.session.add(user)

        production = Production(name="Production Test Accès")
        db.session.add(production)
        db.session.flush()

        project = Project(
            name="Projet Test Waivers Commercial",
            production_id=production.id,
        )
        db.session.add(project)
        db.session.commit()

        return user, project

    def test_permissions_dictionary_for_commercial(self):
        """Vérifie que la matrice des permissions inclut cgl et safety_rules pour Commercial."""
        perms = get_user_permissions("commercial")
        self.assertIn("departs", perms["sections"])
        self.assertIn("cgl", perms["nav"])
        self.assertIn("safety_rules", perms["nav"])
        # Checkouts ne doit PAS être visible pour Commercial
        self.assertNotIn("checkouts", perms["nav"])

    def test_commercial_can_access_cgl_list(self):
        """Vérifie que le rôle commercial peut afficher la liste des CGL sans redirection 403."""
        with self.app.app_context():
            user, proj = self._create_mock_data()
            user_id = user.id
            user_firstname = user.firstname

        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = user_id
            sess["admin_user_role"] = "Commercial"
            sess["admin_user_firstname"] = user_firstname

        response = self.client.get("/admin/cgl")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Conditions G", response.data)

    def test_commercial_can_access_cgl_new(self):
        """Vérifie que le rôle commercial peut afficher le formulaire de création des CGL."""
        with self.app.app_context():
            user, proj = self._create_mock_data()
            user_id = user.id
            user_firstname = user.firstname

        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = user_id
            sess["admin_user_role"] = "Commercial"
            sess["admin_user_firstname"] = user_firstname

        response = self.client.get("/admin/cgl/new")
        self.assertEqual(response.status_code, 200)

    def test_commercial_can_access_safety_rules_list(self):
        """Vérifie que le rôle commercial peut afficher la liste des règles de sécurité (BVSR)."""
        with self.app.app_context():
            user, proj = self._create_mock_data()
            user_id = user.id
            user_firstname = user.firstname

        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = user_id
            sess["admin_user_role"] = "Commercial"
            sess["admin_user_firstname"] = user_firstname

        response = self.client.get("/admin/safety-rules")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"R\xc3\xa8gles de S\xc3\xa9curit\xc3\xa9 Universelles", response.data)

    def test_commercial_can_quick_create_cgl(self):
        """Vérifie que le rôle commercial peut créer des CGL en un clic."""
        with self.app.app_context():
            user, proj = self._create_mock_data()
            user_id = user.id
            user_firstname = user.firstname
            proj_id = proj.id

        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = user_id
            sess["admin_user_role"] = "Commercial"
            sess["admin_user_firstname"] = user_firstname

        response = self.client.post(f"/admin/cgl/quick-create/{proj_id}")
        self.assertIn(response.status_code, (200, 302))

        # Vérification en base isolée
        with self.app.app_context():
            cgl = CglWaiver.query.filter_by(project_id=proj_id).first()
            self.assertIsNotNone(cgl)

    def test_commercial_api_v1_cgl_access(self):
        """Vérifie que le rôle commercial a accès à l'API v1 des CGL avec un JWT."""
        with self.app.app_context():
            user, proj = self._create_mock_data()
            token = generate_token(user)

        headers = {"Authorization": f"Bearer {token}"}

        # GET /api/v1/cgl
        res = self.client.get("/api/v1/cgl", headers=headers)
        self.assertEqual(res.status_code, 200)

        # GET /api/v1/safety-rules
        res_sr = self.client.get("/api/v1/safety-rules", headers=headers)
        self.assertEqual(res_sr.status_code, 200)


if __name__ == "__main__":
    unittest.main()
