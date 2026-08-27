"""
Suite de tests unitaires et d'intégration PyTest pour le serveur MCP (BV-MCP).
Vérifie la conformité de tous les outils MCP, la sécurité par scopes et les garde-fous.
"""
import os
import sys
import unittest
from unittest.mock import MagicMock

# Mock Weasyprint
mock_weasyprint = MagicMock()
mock_html_inst = MagicMock()
mock_html_inst.write_pdf.return_value = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"
mock_weasyprint.HTML.return_value = mock_html_inst
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint

from mcp_server.core import flask_app
from mcp_server.context import CURRENT_MCP_USER, CURRENT_MCP_IP
from mcp_auth.auth import McpUserContext
from models import db, McpAuditLog, McpApiToken, Production, Vehicle
from mcp_server.tools import (
    calendars,
    contacts,
    documents,
    inspections,
    pre_quotes,
    pricing,
    productions,
    projects,
    system,
    users,
    vehicles,
)


class MCPServerFullTestSuite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = flask_app
        cls.app_context = cls.app.app_context()
        cls.app_context.push()

    @classmethod
    def tearDownClass(cls):
        cls.app_context.pop()

    def setUp(self):
        token = McpApiToken.query.filter_by(is_active=True).first()
        token_id = token.id if token else None
        self.admin_user = McpUserContext(
            user_id=1,
            mail="test_runner@bellevitesse.com",
            firstname="Antigravity",
            lastname="TestRunner",
            role="super administrator",
            scope="admin",
            token_id=token_id,
        )
        CURRENT_MCP_USER.set(self.admin_user)
        CURRENT_MCP_IP.set("127.0.0.1")

    # ── 1. SYSTÈME ───────────────────────────────────────────────
    def test_system_status(self):
        res = system.get_system_status()
        self.assertIsInstance(res, dict)
        self.assertIn("mysql", res)
        self.assertEqual(res.get("mysql"), "connected")

    def test_newsletter_subscribers(self):
        res = system.get_newsletter_subscribers()
        self.assertIsInstance(res, list)

    def test_purge_system_cache(self):
        guard = system.purge_system_cache(confirm=False)
        self.assertEqual(guard.get("status"), "requires_confirmation")
        purged = system.purge_system_cache(confirm=True)
        self.assertTrue(purged.get("success"))

    # ── 2. PRODUCTIONS ───────────────────────────────────────────
    def test_productions_lifecycle(self):
        # List & Form Context
        self.assertIsInstance(productions.list_productions(), list)
        self.assertIn("fields", productions.get_production_form_context())

        # Create
        res_c = productions.create_production(
            name="PyTest Studio Production",
            address="123 rue du Test",
            email="pytest.prod@example.com",
            phone="0102030405"
        )
        self.assertTrue(res_c.get("success"))

        # Find created
        all_p = productions.list_productions()
        prod = next((p for p in all_p if p.get("name") == "PyTest Studio Production"), None)
        self.assertIsNotNone(prod)
        prod_id = prod["id"]

        # Get & Update
        det = productions.get_production(prod_id)
        self.assertEqual(det.get("name"), "PyTest Studio Production")

        res_u = productions.update_production(prod_id, name="PyTest Studio Production V2")
        self.assertTrue(res_u.get("success"))

        # Delete Guard & Confirm
        guard = productions.delete_production(prod_id, confirm=False)
        self.assertEqual(guard.get("status"), "requires_confirmation")

        deleted = productions.delete_production(prod_id, confirm=True)
        self.assertTrue(deleted.get("success"))

    # ── 3. CONTACTS ──────────────────────────────────────────────
    def test_contacts_lifecycle(self):
        self.assertIsInstance(contacts.list_contacts(), list)
        self.assertIn("productions", contacts.get_contact_form_context())

        res_c = contacts.create_contact(
            first_name="PyTest",
            last_name="ContactMCP",
            job="Assistant Caméra",
            email="pytest.contact@example.com",
            phone="0600000000"
        )
        self.assertTrue(res_c.get("success"))

        all_c = contacts.list_contacts()
        cnt = next((c for c in all_c if c.get("first_name") == "PyTest" and c.get("last_name") == "ContactMCP"), None)
        self.assertIsNotNone(cnt)
        cnt_id = cnt["id"]

        det = contacts.get_contact(cnt_id)
        self.assertEqual(det.get("first_name"), "PyTest")

        res_u = contacts.update_contact(cnt_id, first_name="PyTestUpdated", last_name="ContactMCP")
        self.assertTrue(res_u.get("success"))

        guard = contacts.delete_contact(cnt_id, confirm=False)
        self.assertEqual(guard.get("status"), "requires_confirmation")

        deleted = contacts.delete_contact(cnt_id, confirm=True)
        self.assertTrue(deleted.get("success"))

    # ── 4. PROJETS ───────────────────────────────────────────────
    def test_projects_lifecycle(self):
        self.assertIsInstance(projects.list_projects(), list)
        self.assertIsInstance(projects.get_project_form_context(), dict)

        first_prod = Production.query.first()
        prod_id = first_prod.id if first_prod else 1

        res_c = projects.create_project(
            name="PyTest Tournage MCP",
            production_id=prod_id,
            notes="Projet test PyTest"
        )
        self.assertTrue(res_c.get("success"))

        all_pr = projects.list_projects()
        proj = next((p for p in all_pr if p.get("name") == "PyTest Tournage MCP"), None)
        self.assertIsNotNone(proj)
        proj_id = proj["id"]

        det = projects.get_project(proj_id)
        self.assertEqual(det.get("name"), "PyTest Tournage MCP")

        res_u = projects.update_project(proj_id, name="PyTest Tournage MCP V2")
        self.assertTrue(res_u.get("success"))

        # Delete Guard & Confirm
        guard = projects.delete_project(proj_id, confirm=False)
        self.assertEqual(guard.get("status"), "requires_confirmation")

        deleted = projects.delete_project(proj_id, confirm=True)
        self.assertTrue(deleted.get("success"))

    # ── 5. PRÉ-DEVIS ─────────────────────────────────────────────
    def test_pre_quotes_lifecycle(self):
        self.assertIsInstance(pre_quotes.list_pre_quotes(), list)
        self.assertIn("delivery_config", pre_quotes.get_pre_quote_form_context())

        first_prod = Production.query.first()
        prod_id = first_prod.id if first_prod else 1

        res_c = pre_quotes.create_pre_quote(
            production_id=prod_id,
            version_label="V1",
            notes="Pré-devis PyTest",
            items=[{
                "category": "equipment",
                "description": "Véhicule travelling",
                "quantity": 1,
                "unit": "jour",
                "unit_price": 1000.0,
                "discount_rate": 0.0,
                "total": 1000.0
            }]
        )
        self.assertTrue(res_c.get("success"))
        pq_id = res_c.get("pre_quote_id")

        det = pre_quotes.get_pre_quote(pq_id)
        self.assertEqual(det.get("id"), pq_id)

        res_u = pre_quotes.update_pre_quote(pq_id, notes="Pré-devis actualisé")
        self.assertTrue(res_u.get("success"))

        res_v = pre_quotes.create_pre_quote_version(pq_id, "V2")
        self.assertTrue(res_v.get("success"))

        guard = pre_quotes.delete_pre_quote(pq_id, confirm=False)
        self.assertEqual(guard.get("status"), "requires_confirmation")

        deleted = pre_quotes.delete_pre_quote(pq_id, confirm=True)
        self.assertTrue(deleted.get("success"))

    # ── 6. INSPECTIONS ───────────────────────────────────────────
    def test_inspections(self):
        self.assertIsInstance(inspections.list_checkouts(), dict)
        self.assertIsInstance(inspections.list_checkins(), dict)
        self.assertIsInstance(inspections.get_inspection_form_context("checkout"), dict)
        guard = inspections.delete_inspection("checkout", 999999, confirm=False)
        self.assertEqual(guard.get("status"), "requires_confirmation")

    # ── 7. TARIFICATION ──────────────────────────────────────────
    def test_pricing(self):
        self.assertIsInstance(pricing.get_equipment_rates(), dict)
        self.assertIsInstance(pricing.get_salary_rates(), list)
        self.assertIsInstance(pricing.get_logistics_rates(), list)

        first_v = Vehicle.query.first()
        if first_v:
            res_u = pricing.update_equipment_daily_rate("vehicles", first_v.id, float(first_v.daily_rate or 800.0))
            self.assertTrue(res_u.get("success"))

        sal_rates = pricing.get_salary_rates()
        if sal_rates:
            res_s = pricing.update_salary_rate(sal_rates[0]["id"], "notes", "Note PyTest")
            self.assertTrue(res_s.get("success"))

        guard = pricing.delete_salary_rate(999999, confirm=False)
        self.assertEqual(guard.get("status"), "requires_confirmation")

    # ── 8. UTILISATEURS ──────────────────────────────────────────
    def test_users_lifecycle(self):
        self.assertIsInstance(users.list_users(), list)

        res_c = users.create_user(
            firstname="PyTestUser",
            lastname="MCP",
            mail="pytest_temp_user@bellevitesse.com",
            role="user",
            phone="0611223344",
            job="Technicien"
        )
        self.assertTrue(res_c.get("success"))
        u_id = res_c["user"]["id"]

        det = users.get_user(u_id)
        self.assertEqual(det.get("firstname"), "PyTestUser")

        res_u = users.update_user(u_id, firstname="PyTestUserUpdated")
        self.assertTrue(res_u.get("success"))

        guard = users.delete_user(u_id, confirm=False)
        self.assertEqual(guard.get("status"), "requires_confirmation")

        deleted = users.delete_user(u_id, confirm=True)
        self.assertTrue(deleted.get("success"))

    # ── 9. CALENDRIERS ───────────────────────────────────────────
    def test_calendars_lifecycle(self):
        self.assertIsInstance(calendars.list_calendar_subscriptions(), list)
        res_c = calendars.create_calendar_subscription(user_id=1, label="PyTest iCal")
        self.assertTrue(res_c.get("success"))
        token_id = res_c.get("token_id")

        guard = calendars.revoke_calendar_subscription(token_id, confirm=False)
        self.assertEqual(guard.get("status"), "requires_confirmation")

        revoked = calendars.revoke_calendar_subscription(token_id, confirm=True)
        self.assertTrue(revoked.get("success"))

    # ── 10. DOCUMENTS & VÉHICULES ────────────────────────────────
    def test_documents_and_vehicles(self):
        first_v = Vehicle.query.first()
        v_id = first_v.id if first_v else "mercedes-c63"

        sheet = documents.get_vehicle_sheet_data(v_id)
        self.assertIsNotNone(sheet)

        catalog_up = documents.update_catalog_pdf(with_prices=True)
        self.assertTrue(catalog_up.get("success"))

        self.assertIsInstance(vehicles.get_vehicles_with_config(), list)
        self.assertIsInstance(vehicles.get_checkpoints_for_vehicle(v_id), list)

        save_chk = vehicles.save_vehicle_checkpoint_config(v_id, ["exterior_cleanliness"])
        self.assertTrue(save_chk.get("success"))

    # ── 11. SÉCURITÉ & AUDIT ─────────────────────────────────────
    def test_security_scopes_and_audit(self):
        # Read-only scope blocks write
        read_only_user = McpUserContext(1, "ro@test.com", "RO", "User", "user", scope="read_only")
        CURRENT_MCP_USER.set(read_only_user)
        blocked = contacts.create_contact(first_name="Illegal", last_name="Write")
        self.assertEqual(blocked.get("status"), "error")
        self.assertEqual(blocked.get("error_code"), 403)

        # Write scope blocks admin
        write_user = McpUserContext(1, "w@test.com", "W", "User", "user", scope="write")
        CURRENT_MCP_USER.set(write_user)
        blocked_admin = users.delete_user(1, confirm=True)
        self.assertEqual(blocked_admin.get("status"), "error")
        self.assertEqual(blocked_admin.get("error_code"), 403)

        # Audit logs recorded in database
        logs = McpAuditLog.query.order_by(McpAuditLog.created_at.desc()).limit(5).all()
        self.assertGreater(len(logs), 0)


if __name__ == "__main__":
    unittest.main()
