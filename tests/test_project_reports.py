import os
import sys
import unittest
from datetime import date
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock weasyprint
mock_weasyprint = MagicMock()
mock_weasyprint.HTML = MagicMock()
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint

from app import create_app
from models import db, Project, Production, User, ProjectReport
from services.admin.project_reports import (
    add_project_report,
    delete_project_report,
    list_project_reports,
    get_project_detail_context,
)
from mcp_server.tools.projects import get_project_reports, add_project_report as mcp_add_project_report


class ProjectReportsTest(unittest.TestCase):
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

            # Create test production
            prod = Production(name="Studio 2026")
            db.session.add(prod)
            db.session.commit()

            # Create test users
            admin_user = User(
                firstname="Maxime",
                lastname="Admin",
                mail="admin@bellevitesse.com",
                role="administrateur"
            )
            tech_user = User(
                firstname="Lucas",
                lastname="Technicien",
                mail="tech@bellevitesse.com",
                role="technicien"
            )
            db.session.add_all([admin_user, tech_user])
            db.session.commit()

            # Create test project
            project = Project(
                name="Tournage Pub Sport",
                production_id=prod.id,
                departure_date=date(2026, 9, 10),
                shoot_start_date=date(2026, 9, 11),
                shoot_end_date=date(2026, 9, 12),
                return_date=date(2026, 9, 13),
                notes="Besoins caméra spéciaux"
            )
            db.session.add(project)
            db.session.commit()

            self.project_id = project.id
            self.admin_id = admin_user.id
            self.tech_id = tech_user.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_add_and_list_reports(self):
        with self.app.app_context():
            # Ajout d'un premier rapport par le technicien
            report1 = add_project_report(
                self.project_id,
                user_id=self.tech_id,
                content="Essai carmount validé à 110 km/h."
            )
            self.assertIsNotNone(report1.id)
            self.assertEqual(report1.author_name, "Lucas Technicien")
            self.assertEqual(report1.author_role, "Technicien")

            # Ajout d'un second rapport par l'administrateur
            report2 = add_project_report(
                self.project_id,
                user_id=self.admin_id,
                content="Prévoir jeu de pneus pluie supplémentaire pour demain."
            )
            self.assertEqual(report2.author_name, "Maxime Admin")

            # Récupération de la liste
            reports = list_project_reports(self.project_id)
            self.assertEqual(len(reports), 2)
            self.assertEqual(reports[0]["content"], "Essai carmount validé à 110 km/h.")
            self.assertEqual(reports[1]["content"], "Prévoir jeu de pneus pluie supplémentaire pour demain.")
            self.assertTrue("created_at_fr" in reports[0])

    def test_empty_content_validation(self):
        with self.app.app_context():
            with self.assertRaises(ValueError):
                add_project_report(self.project_id, user_id=self.tech_id, content="   ")

    def test_delete_permissions(self):
        with self.app.app_context():
            report = add_project_report(
                self.project_id,
                user_id=self.tech_id,
                content="Note temporaire du technicien"
            )

            # Un autre utilisateur non admin ne peut pas supprimer
            with self.assertRaises(PermissionError):
                delete_project_report(report.id, current_user_id=999, is_admin=False)

            # L'administrateur peut supprimer
            success = delete_project_report(report.id, current_user_id=self.admin_id, is_admin=True)
            self.assertTrue(success)

            # Vérification de suppression
            remaining = list_project_reports(self.project_id)
            self.assertEqual(len(remaining), 0)

    def test_cascade_delete_with_project(self):
        with self.app.app_context():
            add_project_report(
                self.project_id,
                user_id=self.tech_id,
                content="Rapport lié au projet"
            )
            self.assertEqual(ProjectReport.query.filter_by(project_id=self.project_id).count(), 1)

            # Suppression du projet
            p = db.session.get(Project, self.project_id)
            db.session.delete(p)
            db.session.commit()

            # Les rapports associés doivent être supprimés en cascade
            self.assertEqual(ProjectReport.query.filter_by(project_id=self.project_id).count(), 0)

    def test_project_detail_context(self):
        with self.app.app_context():
            add_project_report(
                self.project_id,
                user_id=self.tech_id,
                content="Débriefing fin de journée."
            )
            ctx = get_project_detail_context(self.project_id, current_user_id=self.tech_id, is_admin=False)
            self.assertIsNotNone(ctx)
            self.assertEqual(ctx["reports_count"], 1)
            self.assertEqual(ctx["project"].name, "Tournage Pub Sport")
            self.assertTrue(ctx["reports"][0]["can_delete"])

    def test_http_routes(self):
        # 1. Accès fiche projet
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = self.tech_id
            sess["admin_user_role"] = "technicien"

        resp = self.client.get(f"/admin/projects/{self.project_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Hub Projet", resp.data)
        self.assertIn(b"Journal de Bord", resp.data)

        # 2. Ajout rapport via POST JSON
        resp_add = self.client.post(
            f"/admin/projects/{self.project_id}/reports",
            json={"content": "Rapport test via API HTTP"},
            headers={"X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(resp_add.status_code, 201)
        data = resp_add.get_json()
        self.assertEqual(data["status"], "success")
        report_id = data["report"]["id"]

        # 3. Suppression rapport
        resp_del = self.client.post(
            f"/admin/projects/{self.project_id}/reports/{report_id}/delete",
            headers={"X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(resp_del.status_code, 200)

    def test_mcp_tools(self):
        with self.app.app_context():
            from mcp_server.context import CURRENT_MCP_USER
            from mcp_auth.auth import McpUserContext
            admin_context = McpUserContext(
                user_id=self.admin_id,
                mail="admin@bellevitesse.com",
                firstname="Maxime",
                lastname="Admin",
                role="super administrator",
                scope="admin",
                token_id=1,
            )
            CURRENT_MCP_USER.set(admin_context)

            # Ajout via outil MCP
            res = mcp_add_project_report(
                project_id=self.project_id,
                content="Note ajoutée par subagent IA",
                author_name="Claude Antigravity"
            )
            self.assertEqual(res.get("status"), "success")

            # Récupération via outil MCP
            rep_res = get_project_reports(project_id=self.project_id)
            self.assertEqual(rep_res.get("reports_count"), 1)
            self.assertEqual(rep_res["reports"][0]["content"], "Note ajoutée par subagent IA")
            self.assertEqual(rep_res["reports"][0]["author_name"], "Claude Antigravity")

    def test_author_job_display(self):
        with self.app.app_context():
            # Création d'un utilisateur avec un job spécifique dans l'équipe
            user_pilot = User(
                firstname="Romain",
                lastname="Grosjean",
                mail="romain@bellevitesse.com",
                role="technicien",
                job="Pilote Précision"
            )
            db.session.add(user_pilot)
            db.session.commit()

            report = add_project_report(
                self.project_id,
                user_id=user_pilot.id,
                content="Passage sur circuit validé."
            )
            self.assertEqual(report.author_job, "Pilote Précision")

            # Vérification dans list_project_reports
            reports = list_project_reports(self.project_id)
            pilot_report = next((r for r in reports if r["id"] == report.id), None)
            self.assertIsNotNone(pilot_report)
            self.assertEqual(pilot_report["author_job"], "Pilote Précision")

            # Vérification dans get_project_detail_context
            ctx = get_project_detail_context(self.project_id)
            ctx_report = next((r for r in ctx["reports"] if r["id"] == report.id), None)
            self.assertIsNotNone(ctx_report)
            self.assertEqual(ctx_report["author_job"], "Pilote Précision")


if __name__ == '__main__':
    unittest.main()
