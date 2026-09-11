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
from mcp_server.tools.projects import (
    get_project_reports,
    add_project_report as mcp_add_project_report,
    get_project_hub,
    delete_project_report as mcp_delete_project_report,
    search_project_reports,
)


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
            # Ajout d'un premier rapport par le technicien avec titre
            report1 = add_project_report(
                self.project_id,
                user_id=self.tech_id,
                title="Débriefing Tournage J1",
                content="Essai carmount validé à 110 km/h."
            )
            self.assertIsNotNone(report1.id)
            self.assertEqual(report1.title, "Débriefing Tournage J1")
            self.assertEqual(report1.author_name, "Lucas Technicien")
            self.assertEqual(report1.author_role, "Technicien")

            # Ajout d'un second rapport par l'administrateur (sans titre)
            report2 = add_project_report(
                self.project_id,
                user_id=self.admin_id,
                content="Prévoir jeu de pneus pluie supplémentaire pour demain."
            )
            self.assertEqual(report2.author_name, "Maxime Admin")
            self.assertIsNone(report2.title)

            # Récupération de la liste
            reports = list_project_reports(self.project_id)
            self.assertEqual(len(reports), 2)
            self.assertEqual(reports[0]["title"], "Débriefing Tournage J1")
            self.assertEqual(reports[0]["content"], "Essai carmount validé à 110 km/h.")
            self.assertIsNone(reports[1]["title"])
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
            from models import Project
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

            proj = db.session.get(Project, self.project_id)
            bvpr_code = proj.project_id

            # 1. Ajout via outil MCP avec nom et poste
            res = mcp_add_project_report(
                project_id=bvpr_code,  # Test avec le code BVPR en chaîne !
                content="Note d'essai ajoutée par subagent IA sur caméra",
                author_name="Claude Antigravity",
                author_job="Ingénieur Caméra",
            )
            self.assertEqual(res.get("status"), "success")
            report_id = res["report"]["id"]

            # 2. Récupération via outil MCP get_project_reports avec code BVPR
            rep_res = get_project_reports(project_id=bvpr_code)
            self.assertEqual(rep_res.get("reports_count"), 1)
            self.assertEqual(rep_res["reports"][0]["content"], "Note d'essai ajoutée par subagent IA sur caméra")
            self.assertEqual(rep_res["reports"][0]["author_name"], "Claude Antigravity")

            # 3. Test de get_project_hub
            hub = get_project_hub(project_id=bvpr_code)
            self.assertNotIn("error", hub)
            self.assertEqual(hub["id"], self.project_id)
            self.assertEqual(hub["project_id"], bvpr_code)
            self.assertIn("status", hub)
            self.assertIn("equipment", hub)
            self.assertIn("waivers", hub)
            self.assertIn("reports", hub)
            self.assertEqual(hub["reports_count"], 1)

            # 4. Test de search_project_reports
            search_res = search_project_reports(query="caméra", project_id=self.project_id)
            self.assertEqual(search_res.get("total"), 1)
            self.assertIn("caméra", search_res["results"][0]["content"])

            # 5. Test de delete_project_report avec simulation puis confirmation
            del_sim = mcp_delete_project_report(report_id=report_id, confirm=False)
            self.assertEqual(del_sim.get("status"), "requires_confirmation")

            del_ok = mcp_delete_project_report(report_id=report_id, confirm=True)
            self.assertEqual(del_ok.get("status"), "success")

            # Vérifier que le rapport a bien disparu
            rep_after = get_project_reports(project_id=self.project_id)
            self.assertEqual(rep_after.get("reports_count"), 0)

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

    def test_render_markdown_filter(self):
        with self.app.app_context():
            from utils.formatting import render_markdown
            md_input = (
                "## Titre Test\n"
                "- Puce de test 1\n"
                "- Puce de test 2\n"
                "**Important** : *observation*\n"
                "> Citation d'équipe\n"
                "<script>alert('xss')</script>"
            )
            html = render_markdown(md_input)
            self.assertIn("<h2>Titre Test</h2>", html)
            self.assertIn("<li>Puce de test 1</li>", html)
            self.assertIn("<strong>Important</strong>", html)
            self.assertIn("<em>observation</em>", html)
            self.assertIn("<blockquote>", html)
            self.assertNotIn("<script>", html)
            self.assertNotIn("alert('xss')", html)

    def test_truncate_report(self):
        with self.app.app_context():
            from utils.formatting import truncate_report

            # Texte court (< 200 caractères) : non tronqué
            short_text = "Rapport bref de tournage."
            self.assertEqual(truncate_report(short_text, 200), short_text)

            # Texte exactement égal à 200 caractères : non tronqué
            exact_text = "A" * 200
            self.assertEqual(truncate_report(exact_text, 200), exact_text)

            # Texte long (> 200 caractères) avec des espaces : tronqué au mot avec points de suspension
            long_text = "Ceci est un compte-rendu très détaillé du tournage sur le circuit du Mans avec plusieurs équipes et véhicules engagés. " * 3
            truncated = truncate_report(long_text, 200)
            self.assertTrue(len(truncated) <= 204)  # 200 max + ...
            self.assertTrue(truncated.endswith("..."))
            self.assertFalse(truncated.endswith(" ..."))

            # Test de nettoyage des marqueurs orphelins
            md_trailing = "Texte avec marqueur gras **" + " mot" * 40
            truncated_md = truncate_report(md_trailing, 30)
            self.assertNotIn("**...", truncated_md)

            # Test présence du filtre Jinja dans l'environnement Flask
            self.assertIn("truncate_report", self.app.jinja_env.filters)


if __name__ == '__main__':
    unittest.main()
