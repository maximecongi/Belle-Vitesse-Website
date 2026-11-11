from tests.base import BaseTestCase
from services.admin.projects import (
    create_project,
    update_project,
    get_project_for_edit,
    get_project_for_duplicate,
)
from models import db, Project, Production, User


class _Form(dict):
    """Imite un MultiDict : getlist() pour les listes (véhicules, têtes, référents)."""

    def __init__(self, data, lists=None):
        super().__init__(data)
        self._lists = lists or {}

    def getlist(self, name):
        return list(self._lists.get(name, []))


class ProjectBvRolesTest(BaseTestCase):

    def _setup(self):
        commercial = User(firstname="Chloé", lastname="Vente", mail="commercial.roles@example.com",
                          role="commercial", phone="0600000001")
        grip = User(firstname="Hugo", lastname="Machino", mail="grip.roles@example.com", role="technicien")
        operator = User(firstname="Inès", lastname="Remote", mail="operator.roles@example.com", role="technicien")
        prod = Production(name="Production Rôles BV")
        db.session.add_all([commercial, grip, operator, prod])
        db.session.commit()
        return commercial, grip, operator, prod

    def _base_form(self, prod, commercial, grip, operator):
        return {
            "name": "Projet Rôles BV",
            "production_id": str(prod.id),
            "commercial_user_id": str(commercial.id),
            "bv_grip_user_id": str(grip.id),
            "remote_head_operator_user_id": str(operator.id),
            "shoot_start": "2026-12-01",
            "shoot_end": "2026-12-03",
        }

    def test_roles_saved_with_head(self):
        with self.app.app_context():
            commercial, grip, operator, prod = self._setup()
            form = _Form(self._base_form(prod, commercial, grip, operator), {"head_ids": ["rec_head_1"]})
            project = create_project(form)

            project = db.session.get(Project, project.id)
            self.assertEqual(project.commercial_user_id, commercial.id)
            self.assertEqual(project.bv_grip_user_id, grip.id)
            self.assertEqual(project.remote_head_operator_user_id, operator.id)
            self.assertEqual(
                [label for label, _ in project.bv_team_roles],
                ["Commercial", "Machiniste BV", "Opérateur Remote Head"],
            )

            edit = get_project_for_edit(project.id)
            self.assertEqual(edit["commercial_user_id"], str(commercial.id))
            self.assertEqual(edit["bv_grip_user_id"], str(grip.id))
            self.assertEqual(edit["remote_head_operator_user_id"], str(operator.id))

            dup = get_project_for_duplicate(project.id)
            self.assertEqual(dup["remote_head_operator_user_id"], str(operator.id))

    def test_operator_ignored_without_head(self):
        with self.app.app_context():
            commercial, grip, operator, prod = self._setup()
            form = _Form(self._base_form(prod, commercial, grip, operator))
            project = create_project(form)

            project = db.session.get(Project, project.id)
            self.assertEqual(project.commercial_user_id, commercial.id)
            self.assertIsNone(project.remote_head_operator_user_id)

    def test_operator_cleared_when_heads_removed(self):
        with self.app.app_context():
            commercial, grip, operator, prod = self._setup()
            data = self._base_form(prod, commercial, grip, operator)
            project = create_project(_Form(data, {"head_ids": ["rec_head_1"]}))
            self.assertEqual(project.remote_head_operator_user_id, operator.id)

            data["commercial_user_id"] = ""
            self.assertTrue(update_project(project.id, _Form(data)))

            project = db.session.get(Project, project.id)
            self.assertIsNone(project.commercial_user_id)
            self.assertEqual(project.bv_grip_user_id, grip.id)
            self.assertIsNone(project.remote_head_operator_user_id)

    def test_form_and_detail_pages_render_roles(self):
        with self.app.app_context():
            commercial, grip, operator, prod = self._setup()
            admin = User(firstname="Admin", lastname="Roles", mail="admin.roles@example.com", role="administrator")
            db.session.add(admin)
            db.session.commit()
            project = create_project(_Form(self._base_form(prod, commercial, grip, operator),
                                           {"head_ids": ["rec_head_1"]}))

            with self.client.session_transaction() as sess:
                sess["admin_authenticated"] = True
                sess["admin_user_id"] = admin.id
                sess["admin_user_role"] = admin.role
                sess["admin_user_email"] = admin.mail

            res = self.client.get("/admin/projects/new")
            self.assertEqual(res.status_code, 200)
            html = res.get_data(as_text=True)
            self.assertIn('name="commercial_user_id"', html)
            self.assertIn('name="bv_grip_user_id"', html)
            self.assertIn('id="remoteHeadOperatorGroup"', html)

            res = self.client.get(f"/admin/projects/{project.id}")
            self.assertEqual(res.status_code, 200)
            html = res.get_data(as_text=True)
            self.assertIn("Équipe Belle Vitesse", html)
            self.assertIn("Chloé Vente", html)
            self.assertIn("Machiniste BV", html)
            self.assertIn("Opérateur Remote Head", html)
