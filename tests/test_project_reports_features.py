"""
Rapports d'équipe — catégories, jour de tournage, photos, restauration, recherche, export PDF,
réponses AJAX (partial HTML) et navigation.
"""
import io
import json
import os
import shutil
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone

from PIL import Image

from models import Production, Project, ProjectReport, User, db
from services.admin.project_reports import (
    ReportNotFoundError,
    add_project_report,
    build_reports_export_context,
    delete_project_report,
    get_project_detail_context,
    project_shoot_days,
    restore_project_report,
    search_reports,
    shoot_day_choices,
    update_project_report,
)
from tests.base import BaseTestCase

XHR = {"X-Requested-With": "XMLHttpRequest"}


def _png_bytes(color=(200, 30, 30)):
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), color).save(buf, format="PNG")
    buf.seek(0)
    return buf


class ProjectReportsFeaturesTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self._output_dir = tempfile.mkdtemp(prefix="bv-reports-")
        self._previous_output = os.environ.get("OUTPUT_FOLDER")
        os.environ["OUTPUT_FOLDER"] = self._output_dir

        prod = Production(name="Studio Nord")
        db.session.add(prod)
        db.session.commit()
        admin = User(firstname="Ada", lastname="Admin", mail="ada@bv.fr", role="administrateur")
        tech = User(firstname="Tom", lastname="Tech", mail="tom@bv.fr", role="technicien")
        other = User(firstname="Oli", lastname="Autre", mail="oli@bv.fr", role="technicien")
        boss = User(firstname="Sam", lastname="Super", mail="sam@bv.fr", role="super administrateur")
        db.session.add_all([admin, tech, other, boss])
        db.session.commit()
        project = Project(
            name="Pub Voiture",
            production_id=prod.id,
            departure_date=date(2026, 9, 9),
            shoot_start_date=date(2026, 9, 10),
            shoot_end_date=date(2026, 9, 12),
            return_date=date(2026, 9, 13),
        )
        # Techniciens rattachés à l'équipe BV du projet (périmètre d'accès)
        project.bv_technicians = [tech, other]
        db.session.add(project)
        db.session.commit()
        self.project_id = project.id
        self.admin_id, self.tech_id, self.other_id, self.super_id = admin.id, tech.id, other.id, boss.id

    def tearDown(self):
        if self._previous_output is None:
            os.environ.pop("OUTPUT_FOLDER", None)
        else:
            os.environ["OUTPUT_FOLDER"] = self._previous_output
        shutil.rmtree(self._output_dir, ignore_errors=True)
        super().tearDown()

    def _login(self, user_id, role):
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = user_id
            sess["admin_user_role"] = role

    # ── Catégorie & jour ────────────────────────────────────────

    def test_category_defaults_and_validation(self):
        with self.app.app_context():
            r = add_project_report(self.project_id, self.tech_id, "Contenu", title="T")
            self.assertEqual(r.category, "note")
            r2 = add_project_report(self.project_id, self.tech_id, "Contenu", title="T", category="SECURITE")
            self.assertEqual(r2.category, "securite")
            r3 = add_project_report(self.project_id, self.tech_id, "Contenu", title="T", category="inconnue")
            self.assertEqual(r3.category, "note")

    def test_shoot_days_continuous_and_punctual(self):
        with self.app.app_context():
            p = db.session.get(Project, self.project_id)
            self.assertEqual(project_shoot_days(p), [date(2026, 9, 10), date(2026, 9, 11), date(2026, 9, 12)])
            self.assertEqual(shoot_day_choices(p)[0][0], "2026-09-10")
            self.assertTrue(shoot_day_choices(p)[0][1].startswith("J1 · jeu. 10 sept."))

            p.date_mode = "punctual"
            p.shoot_dates = ["2026-09-14", "2026-09-10"]
            db.session.commit()
            self.assertEqual(project_shoot_days(p), [date(2026, 9, 10), date(2026, 9, 14)])

    def test_shoot_day_stored_and_invalid_rejected(self):
        with self.app.app_context():
            r = add_project_report(self.project_id, self.tech_id, "C", title="T", shoot_day="2026-09-11")
            self.assertEqual(r.shoot_day, date(2026, 9, 11))
            with self.assertRaises(ValueError):
                add_project_report(self.project_id, self.tech_id, "C", title="T", shoot_day="11/09/2026")
            ctx = get_project_detail_context(self.project_id, current_user_id=self.tech_id)
            self.assertTrue(ctx["reports"][0]["shoot_day_label"].startswith("J2 ·"))
            self.assertEqual(len(ctx["report_days"]), 3)

    def test_update_keeps_category_when_not_provided(self):
        with self.app.app_context():
            r = add_project_report(self.project_id, self.tech_id, "C", title="T", category="technique",
                                   shoot_day="2026-09-10")
            update_project_report(r.id, self.tech_id, "C2", title="T2")
            self.assertEqual(r.category, "technique")
            self.assertEqual(r.shoot_day, date(2026, 9, 10))
            update_project_report(r.id, self.tech_id, "C3", title="T3", category="debrief", shoot_day=None)
            self.assertEqual(r.category, "debrief")
            self.assertIsNone(r.shoot_day)

    # ── Photos ──────────────────────────────────────────────────

    def test_photos_upload_remove_and_limit_via_routes(self):
        self._login(self.tech_id, "technicien")
        resp = self.client.post(
            f"/admin/projects/{self.project_id}/reports",
            data={
                "title": "Avec photos", "content": "Voir photos", "category": "logistique",
                "shoot_day": "2026-09-12",
                "photos": [(_png_bytes(), "a.png"), (_png_bytes((0, 0, 255)), "b.png")],
            },
            content_type="multipart/form-data", headers=XHR,
        )
        self.assertEqual(resp.status_code, 201, resp.get_json())
        data = resp.get_json()
        report_id = data["report"]["id"]
        self.assertEqual(len(data["report"]["photos"]), 2)
        self.assertEqual(data["count"], 1)
        # Le partial HTML renvoyé contient la carte complète
        self.assertIn(f'id="report-{report_id}"', data["html"])
        self.assertIn('data-category="logistique"', data["html"])
        self.assertIn("report-photos-grid", data["html"])

        with self.app.app_context():
            paths = db.session.get(ProjectReport, report_id).photo_paths
        for rel in paths:
            self.assertTrue(rel.startswith("reports/photos/"))
            self.assertTrue(os.path.exists(os.path.join(self._output_dir, rel)))

        # Retrait d'une photo + ajout d'une autre
        resp = self.client.post(
            f"/admin/projects/{self.project_id}/reports/{report_id}/edit",
            data={"title": "Avec photos", "content": "Voir photos", "remove_photos": [paths[0]],
                  "photos": [(_png_bytes((0, 255, 0)), "c.png")]},
            content_type="multipart/form-data", headers=XHR,
        )
        self.assertEqual(resp.status_code, 200, resp.get_json())
        with self.app.app_context():
            new_paths = db.session.get(ProjectReport, report_id).photo_paths
        self.assertEqual(len(new_paths), 2)
        self.assertNotIn(paths[0], new_paths)
        self.assertFalse(os.path.exists(os.path.join(self._output_dir, paths[0])), "Photo retirée supprimée du disque")

        # Un chemin étranger au rapport est ignoré (pas de suppression arbitraire)
        outsider = os.path.join(self._output_dir, "incidents", "keep.txt")
        os.makedirs(os.path.dirname(outsider), exist_ok=True)
        open(outsider, "w").close()
        self.client.post(
            f"/admin/projects/{self.project_id}/reports/{report_id}/edit",
            data={"title": "x", "content": "y", "remove_photos": ["incidents/keep.txt", "../../etc/passwd"]},
            content_type="multipart/form-data", headers=XHR,
        )
        self.assertTrue(os.path.exists(outsider))

        # Limite de 10 photos
        too_many = [(_png_bytes(), f"p{i}.png") for i in range(9)]
        resp = self.client.post(
            f"/admin/projects/{self.project_id}/reports/{report_id}/edit",
            data={"title": "x", "content": "y", "photos": too_many},
            content_type="multipart/form-data", headers=XHR,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("10 photos", resp.get_json()["message"])

    # ── Suppression / restauration ──────────────────────────────

    def test_restore_permissions(self):
        with self.app.app_context():
            # Auteur qui supprime lui-même : il peut restaurer
            r = add_project_report(self.project_id, self.tech_id, "C", title="T")
            delete_project_report(r.id, self.tech_id)
            self.assertEqual(r.deleted_by_id, self.tech_id)
            with self.assertRaises(PermissionError):
                restore_project_report(r.id, self.other_id)
            with self.assertRaises(PermissionError):
                restore_project_report(r.id, self.admin_id)  # administrateur simple : refusé
            restored = restore_project_report(r.id, self.tech_id, project_id=self.project_id)
            self.assertIsNone(restored.deleted_at)
            self.assertIsNone(restored.deleted_by_id)
            with self.assertRaises(ReportNotFoundError):
                restore_project_report(r.id, self.tech_id)  # déjà actif

            # Rapport de l'auteur supprimé par un administrateur : l'auteur ne peut pas le restaurer
            r2 = add_project_report(self.project_id, self.tech_id, "C", title="T2")
            delete_project_report(r2.id, self.admin_id, is_admin=True)
            with self.assertRaises(PermissionError):
                restore_project_report(r2.id, self.tech_id)
            with self.assertRaises(PermissionError):
                restore_project_report(r2.id, self.admin_id)  # ni l'administrateur qui l'a supprimé
            self.assertIsNone(restore_project_report(r2.id, self.super_id, is_super_admin=True).deleted_at)

            # Rapport d'un admin supprimé par lui-même : il le restaure (auteur + suppresseur)
            r3 = add_project_report(self.project_id, self.admin_id, "C", title="T3")
            delete_project_report(r3.id, self.admin_id, is_admin=True)
            self.assertIsNone(restore_project_report(r3.id, self.admin_id).deleted_at)

    def test_delete_returns_restore_url_and_undo_works(self):
        with self.app.app_context():
            r = add_project_report(self.project_id, self.tech_id, "C", title="T")
            rid = r.id
        self._login(self.tech_id, "technicien")
        resp = self.client.post(f"/admin/projects/{self.project_id}/reports/{rid}/delete", headers=XHR)
        data = resp.get_json()
        self.assertEqual(data["count"], 0)
        self.assertTrue(data["restore_url"].endswith(f"/reports/{rid}/restore"))
        resp = self.client.post(data["restore_url"], headers=XHR)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["count"], 1)
        self.assertIn(f'id="report-{rid}"', resp.get_json()["html"])

    def test_admin_deleting_others_report_gets_no_undo(self):
        with self.app.app_context():
            rid = add_project_report(self.project_id, self.tech_id, "C", title="T").id
        self._login(self.admin_id, "administrateur")
        data = self.client.post(f"/admin/projects/{self.project_id}/reports/{rid}/delete", headers=XHR).get_json()
        self.assertIsNone(data["restore_url"])
        resp = self.client.post(f"/admin/projects/{self.project_id}/reports/{rid}/restore", headers=XHR)
        self.assertEqual(resp.status_code, 403)
        # L'auteur non plus
        self._login(self.tech_id, "technicien")
        resp = self.client.post(f"/admin/projects/{self.project_id}/reports/{rid}/restore", headers=XHR)
        self.assertEqual(resp.status_code, 403)
        # Le super administrateur, oui
        self._login(self.super_id, "Super Administrator")
        resp = self.client.post(f"/admin/projects/{self.project_id}/reports/{rid}/restore", headers=XHR)
        self.assertEqual(resp.status_code, 200)

    def test_trash_lists_only_restorable_reports(self):
        with self.app.app_context():
            own = add_project_report(self.project_id, self.tech_id, "C", title="Supprimé par Tom")
            delete_project_report(own.id, self.tech_id)
            by_admin = add_project_report(self.project_id, self.tech_id, "C", title="Supprimé par Ada")
            delete_project_report(by_admin.id, self.admin_id, is_admin=True)

            titles = lambda ctx: [r["title"] for r in ctx["deleted_reports"]]
            self.assertEqual(titles(get_project_detail_context(self.project_id, self.tech_id)), ["Supprimé par Tom"])
            self.assertEqual(titles(get_project_detail_context(self.project_id, self.admin_id, True)), [])
            self.assertEqual(titles(get_project_detail_context(self.project_id, self.other_id)), [])
            self.assertEqual(
                sorted(titles(get_project_detail_context(self.project_id, self.super_id, True, is_super_admin=True))),
                ["Supprimé par Ada", "Supprimé par Tom"],
            )
            ctx = get_project_detail_context(self.project_id, self.super_id, True, is_super_admin=True)
            by = {r["title"]: r["deleted_by_name"] for r in ctx["deleted_reports"]}
            self.assertEqual(by["Supprimé par Ada"], "Ada Admin")

        self._login(self.admin_id, "administrateur")
        html = self.client.get(f"/admin/projects/{self.project_id}").get_data(as_text=True)
        self.assertNotIn("data-reports-trash", html)
        self._login(self.super_id, "super administrateur")
        html = self.client.get(f"/admin/projects/{self.project_id}").get_data(as_text=True)
        self.assertIn("data-reports-trash", html)
        self.assertIn("par Ada Admin", html)

    # ── Compte à rebours ────────────────────────────────────────

    def test_editable_until_only_for_author(self):
        with self.app.app_context():
            r = add_project_report(self.project_id, self.tech_id, "C", title="T")
            ctx = get_project_detail_context(self.project_id, self.tech_id, False)
            until = datetime.fromisoformat(ctx["reports"][0]["editable_until"])
            self.assertAlmostEqual((until - datetime.now(timezone.utc)).total_seconds(), 3 * 3600, delta=120)
            ctx_admin = get_project_detail_context(self.project_id, self.admin_id, True)
            self.assertEqual(ctx_admin["reports"][0]["editable_until"], "")
            r.created_at = datetime.now(timezone.utc) - timedelta(hours=4)
            db.session.commit()
            ctx = get_project_detail_context(self.project_id, self.tech_id, False)
            self.assertFalse(ctx["reports"][0]["can_edit"])
            self.assertEqual(ctx["reports"][0]["editable_until"], "")

    # ── Recherche ───────────────────────────────────────────────

    def test_search_reports_filters_and_snippet(self):
        with self.app.app_context():
            add_project_report(self.project_id, self.tech_id, "## Pneus\nUsure **avancée** du pneu avant gauche.",
                               title="Point pneus", category="technique")
            add_project_report(self.project_id, self.tech_id, "Rien à signaler", title="RAS", category="note")
            gone = add_project_report(self.project_id, self.tech_id, "pneu supprimé", title="Ancien")
            delete_project_report(gone.id, self.tech_id)

            res = search_reports(query="pneu")
            self.assertEqual(res.total, 1)
            self.assertEqual(res.items[0]["project_name"], "Pub Voiture")
            self.assertNotIn("**", res.items[0]["snippet"])
            self.assertNotIn("#", res.items[0]["snippet"])
            self.assertEqual(search_reports(category="note").total, 1)
            self.assertEqual(search_reports(query="Pub Voiture").total, 2)  # nom du projet

    def test_search_page_and_nav(self):
        with self.app.app_context():
            add_project_report(self.project_id, self.tech_id, "Embrayage à surveiller", title="Embrayage",
                               category="technique")
        self._login(self.tech_id, "technicien")
        resp = self.client.get("/admin/reports?q=embrayage")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("Embrayage", html)
        self.assertIn(f"/admin/projects/{self.project_id}#report-", html)
        self.assertIn("Rapports d&#39;équipe", html)  # entrée de navigation visible pour un technicien
        resp = self.client.get("/admin/reports?category=securite")
        self.assertIn("Aucun rapport trouvé", resp.get_data(as_text=True))

    # ── Export PDF ──────────────────────────────────────────────

    def test_export_context_filters_and_order(self):
        with self.app.app_context():
            first = add_project_report(self.project_id, self.tech_id, "A", title="Premier", category="debrief",
                                       shoot_day="2026-09-10")
            first.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
            db.session.commit()
            add_project_report(self.project_id, self.tech_id, "B", title="Second", category="technique",
                               shoot_day="2026-09-11")
            ctx = build_reports_export_context(self.project_id)
            self.assertEqual([r["title"] for r in ctx["reports"]], ["Premier", "Second"])  # chronologique
            ctx = build_reports_export_context(self.project_id, category="technique")
            self.assertEqual([r["title"] for r in ctx["reports"]], ["Second"])
            self.assertIn("Technique", ctx["filters_label"])
            ctx = build_reports_export_context(self.project_id, shoot_day="2026-09-10")
            self.assertEqual([r["title"] for r in ctx["reports"]], ["Premier"])
            self.assertIn("J1", ctx["filters_label"])

    def test_export_route_returns_pdf(self):
        with self.app.app_context():
            add_project_report(self.project_id, self.tech_id, "Contenu", title="T")
        self._login(self.tech_id, "technicien")
        resp = self.client.get(f"/admin/projects/{self.project_id}/reports/export?category=note")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "application/pdf")
        self.assertIn("Journal-", resp.headers["Content-Disposition"])
        self.assertEqual(self.client.get("/admin/projects/999999/reports/export").status_code, 404)

    def test_export_template_renders(self):
        with self.app.app_context(), self.app.test_request_context():
            from flask import render_template
            add_project_report(self.project_id, self.tech_id, "**Gras** et [lien](https://x.fr)", title="Rendu",
                               category="securite", shoot_day="2026-09-10")
            ctx = build_reports_export_context(self.project_id)
            html = render_template("pdf/project_reports.html", company_name="BV", doc_id="X", is_preview=False, **ctx)
            self.assertIn("Journal de Bord", html)
            self.assertIn("<strong>Gras</strong>", html)
            self.assertIn("reports-pdf-entry--securite", html)
            self.assertIn("Sécurité", html)

    # ── Page projet ─────────────────────────────────────────────

    def test_project_page_renders_new_fields(self):
        with self.app.app_context():
            add_project_report(self.project_id, self.tech_id, "Contenu", title="Visible", category="production",
                               shoot_day="2026-09-11")
        self._login(self.tech_id, "technicien")
        html = self.client.get(f"/admin/projects/{self.project_id}").get_data(as_text=True)
        for marker in ('data-report-form="create"', 'name="category"', 'name="shoot_day"', 'name="photos"',
                       "data-reports-filter", "data-reports-export", 'data-category="production"',
                       'data-day="2026-09-11"', "data-editable-until", 'enctype="multipart/form-data"',
                       'data-mine="1"', "project-report-avatar is-mine"):
            self.assertIn(marker, html, marker)

    def test_timeline_grouped_by_day(self):
        with self.app.app_context():
            a = add_project_report(self.project_id, self.tech_id, "A", title="Jour 1 tôt", shoot_day="2026-09-10")
            a.created_at = datetime.now(timezone.utc) - timedelta(hours=5)
            db.session.commit()
            add_project_report(self.project_id, self.tech_id, "B", title="Jour 1 tard", shoot_day="2026-09-10")
            add_project_report(self.project_id, self.tech_id, "C", title="Sans jour")
            add_project_report(self.project_id, self.tech_id, "D", title="Jour 3", shoot_day="2026-09-12")
            ctx = get_project_detail_context(self.project_id, self.tech_id)
            groups = [(g["day"], g["heading"], [r["title"] for r in g["reports"]]) for g in ctx["report_groups"]]
            self.assertEqual(groups[0][0], "2026-09-12")
            self.assertTrue(groups[0][1].startswith("J3 · sam. 12 septembre 2026"))
            self.assertEqual(groups[1][2], ["Jour 1 tard", "Jour 1 tôt"])
            self.assertEqual(groups[2][:2], ("", "Général"))
        self._login(self.tech_id, "technicien")
        html = self.client.get(f"/admin/projects/{self.project_id}").get_data(as_text=True)
        for marker in ('data-action="open-report-form"', 'id="addReportForm"', 'data-reports-category="securite"',
                       'data-group-day="2026-09-12"', "report-day-title", 'data-day-heading="Général"'):
            self.assertIn(marker, html, marker)
        self.assertRegex(html, r'id="addReportForm"[^>]*hidden')

    def test_mcp_tools_category_and_search(self):
        with self.app.app_context():
            from mcp_auth.auth import McpUserContext
            from mcp_server.context import CURRENT_MCP_USER
            from mcp_server.tools.projects import add_project_report as mcp_add
            from mcp_server.tools.projects import search_project_reports as mcp_search
            CURRENT_MCP_USER.set(McpUserContext(
                user_id=self.admin_id, mail="ada@bv.fr", firstname="Ada", lastname="Admin",
                role="super administrator", scope="admin", token_id=1,
            ))
            res = mcp_add(project_id=self.project_id, title="Sécu", content="Zone balisée",
                          category="securite", shoot_day="2026-09-10")
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["report"]["category"], "securite")
            self.assertEqual(res["report"]["shoot_day"], "2026-09-10")
            found = mcp_search(query="balisée", category="securite")
            self.assertEqual(found["total"], 1)
            self.assertEqual(found["results"][0]["category"], "securite")
            self.assertEqual(mcp_search(query="balisée", category="note")["total"], 0)
            json.dumps(found)  # sérialisable


if __name__ == "__main__":
    unittest.main()
