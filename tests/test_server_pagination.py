import os
import unittest
from datetime import date, timedelta

# Isolation de l'environnement de test (SQLite in-memory, aucun tunnel SSH/MySQL)
os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("TESTING", "True")
os.environ.setdefault("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")
os.environ.setdefault("USE_SSH_TUNNEL", "false")
os.environ.setdefault("WTF_CSRF_ENABLED", "False")

from app import create_app
from models import Project, Production, Incident, CheckoutVehicle, CheckinVehicle, db
from services.admin.projects import list_projects
from services.admin.incidents import list_incidents
from services.admin.checkouts import list_checkouts
from services.admin.checkins import list_checkins
from utils.pagination import Pagination


class TestServerPagination(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.rollback()
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_list_projects_backward_compatibility(self):
        """Vérifie que list_projects sans page retourne toujours une liste standard."""
        with self.app.app_context():
            res = list_projects()
            self.assertIsInstance(res, list)

    def test_list_projects_pagination_instance(self):
        """Vérifie que list_projects avec page retourne un objet Pagination."""
        with self.app.app_context():
            p = list_projects(page=1, per_page=5)
            self.assertIsInstance(p, Pagination)
            self.assertLessEqual(len(p.items), 5)
            self.assertGreaterEqual(p.total, 0)
            self.assertGreaterEqual(p.pages, 1)

    def test_list_projects_search_filter(self):
        """Vérifie que le filtre de recherche q fonctionne avec la pagination."""
        with self.app.app_context():
            # Créer un projet de test avec un nom unique si besoin
            prod = Production.query.first()
            if not prod:
                prod = Production(name="Prod Pagination Test")
                db.session.add(prod)
                db.session.commit()

            test_project = Project(
                name="Tournage Super Unique Pagination 2026",
                production_id=prod.id,
                departure_date=date.today() + timedelta(days=10),
                return_date=date.today() + timedelta(days=20),
            )
            db.session.add(test_project)
            db.session.commit()

            p = list_projects(is_archive=False, q="Super Unique Pagination", page=1, per_page=10)
            self.assertIsInstance(p, Pagination)
            self.assertGreaterEqual(p.total, 1)
            self.assertTrue(any("Super Unique Pagination" in proj["name"] for proj in p.items))

            # Nettoyage
            db.session.delete(test_project)
            db.session.commit()

    def test_list_incidents_pagination(self):
        """Vérifie que list_incidents retourne un conteneur paginé avec stats."""
        with self.app.app_context():
            res = list_incidents(page=1, per_page=10)
            self.assertIn("pagination", res)
            self.assertIn("incidents", res)
            self.assertIn("stats", res)
            self.assertIsInstance(res["pagination"], Pagination)
            self.assertEqual(len(res["incidents"]), len(res["pagination"].items))

    def test_list_checkouts_and_checkins_pagination(self):
        """Vérifie que list_checkouts et list_checkins retournent un conteneur paginé."""
        with self.app.app_context():
            co = list_checkouts(page=1, per_page=10)
            self.assertIn("pagination", co)
            self.assertIn("checkouts", co)
            self.assertIn("stats", co)
            self.assertIsInstance(co["pagination"], Pagination)

            ci = list_checkins(page=1, per_page=10)
            self.assertIn("pagination", ci)
            self.assertIn("checkins", ci)
            self.assertIn("stats", ci)
            self.assertIsInstance(ci["pagination"], Pagination)

    def test_admin_routes_with_pagination_query_params(self):
        """Vérifie que les routes admin acceptent les paramètres ?page= et ?q= sans erreur 500."""
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_role"] = "administrateur"
            sess["admin_user_id"] = 1

        for route in [
            "/admin/projects?page=1&per_page=5",
            "/admin/projects/archives?page=1&per_page=5",
            "/admin/incidents?page=1&per_page=5",
            "/admin/checkouts?page=1&per_page=5",
            "/admin/checkins?page=1&per_page=5",
        ]:
            response = self.client.get(route)
            self.assertEqual(
                response.status_code,
                200,
                f"La route {route} a retourné le code {response.status_code}",
            )


if __name__ == "__main__":
    unittest.main()
