"""
Suite de tests unitaires et d'intégration PyTest pour le serveur MCP (BV-MCP).
Vérifie la conformité de tous les outils MCP, la sécurité par scopes et les garde-fous.
"""
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

from mcp_server.core import flask_app  # noqa: E402
from mcp_server.context import CURRENT_MCP_USER, CURRENT_MCP_IP  # noqa: E402
from mcp_auth.auth import McpUserContext  # noqa: E402
from models import db, McpAuditLog, McpApiToken, Production, Vehicle, Contact  # noqa: E402
from mcp_server.tools import (  # noqa: E402
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
    incidents,
    waivers,
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
        db.create_all()
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

        if not Vehicle.query.filter_by(id="test-veh-01").first():
            test_v = Vehicle(
                id="test-veh-01",
                daily_rate=1500,
                fields={
                    "name": "Mercedes C63 AMG Test",
                    "max_speed": "250 km/h",
                    "passengers": "4",
                    "setups": "Standard",
                    "power": "510 ch",
                    "weight": "1800 kg",
                }
            )
            db.session.add(test_v)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

    # ── 1. SYSTÈME ───────────────────────────────────────────────
    def test_system_status(self):
        res = system.get_system_status()
        self.assertIsInstance(res, dict)
        self.assertIn("mysql", res)
        self.assertEqual(res.get("mysql"), "connected")

    def test_newsletter_subscribers(self):
        from models import NewsletterSubscriber
        # Insérer un abonné de test si non présent
        sub = NewsletterSubscriber.query.filter_by(email="test_sub_mcp@bellevitesse.com").first()
        if not sub:
            sub = NewsletterSubscriber(email="test_sub_mcp@bellevitesse.com")
            db.session.add(sub)
            db.session.commit()

        res = system.get_newsletter_subscribers()
        self.assertIsInstance(res, dict)
        self.assertIn("subscribers", res)
        self.assertIn("total", res)
        self.assertGreaterEqual(res["total"], 1)

        found = next((s for s in res["subscribers"] if s["email"] == "test_sub_mcp@bellevitesse.com"), None)
        self.assertIsNotNone(found)
        self.assertTrue(bool(found.get("created_at")), "created_at ne doit pas être vide")
        self.assertTrue(bool(found.get("subscribed_at")), "subscribed_at ne doit pas être vide")
        self.assertEqual(found["created_at"], found["subscribed_at"])

        # Nettoyage
        db.session.delete(sub)
        db.session.commit()


    def test_purge_system_cache(self):
        guard = system.purge_system_cache(confirm=False)
        self.assertEqual(guard.get("status"), "requires_confirmation")
        purged = system.purge_system_cache(confirm=True)
        self.assertTrue(purged.get("success"))

    # ── 2. PRODUCTIONS ───────────────────────────────────────────
    def test_productions_lifecycle(self):
        # List & Form Context
        res_list = productions.list_productions()
        self.assertIsInstance(res_list, dict)
        self.assertIn("productions", res_list)
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
        all_p = productions.list_productions().get("productions", [])
        prod = next((p for p in all_p if p.get("name") == "PyTest Studio Production"), None)
        self.assertIsNotNone(prod)
        prod_id = prod["id"]

        # Get & Update (Test Patch mode: only updating phone preserves name and address)
        det = productions.get_production(prod_id)
        self.assertEqual(det.get("name"), "PyTest Studio Production")

        res_u = productions.update_production(prod_id, phone="0699999999")
        self.assertTrue(res_u.get("success"))
        det_after = productions.get_production(prod_id)
        self.assertEqual(det_after.get("name"), "PyTest Studio Production")
        self.assertEqual(det_after.get("phone"), "0699999999")

        # Delete Guard & Confirm
        guard = productions.delete_production(prod_id, confirm=False)
        self.assertEqual(guard.get("status"), "requires_confirmation")

        deleted = productions.delete_production(prod_id, confirm=True)
        self.assertTrue(deleted.get("success"))

    # ── 3. CONTACTS ──────────────────────────────────────────────
    def test_contacts_lifecycle(self):
        res_c_list = contacts.list_contacts()
        self.assertIsInstance(res_c_list, dict)
        self.assertIn("contacts", res_c_list)
        self.assertIn("productions", contacts.get_contact_form_context())

        res_c = contacts.create_contact(
            first_name="PyTest",
            last_name="ContactMCP",
            job="Assistant Caméra",
            email="pytest.contact@example.com",
            phone="0600000000"
        )
        self.assertTrue(res_c.get("success"))

        all_c = contacts.list_contacts().get("contacts", [])
        cnt = next((c for c in all_c if c.get("first_name") == "PyTest" and c.get("last_name") == "ContactMCP"), None)
        self.assertIsNotNone(cnt)
        cnt_id = cnt["id"]

        det = contacts.get_contact(cnt_id)
        self.assertEqual(det.get("first_name"), "PyTest")

        # Test Patch mode: only update job without passing first_name/last_name
        res_u = contacts.update_contact(cnt_id, job="Chef Opérateur")
        self.assertTrue(res_u.get("success"))
        det_after = contacts.get_contact(cnt_id)
        self.assertEqual(det_after.get("first_name"), "PyTest")
        self.assertEqual(det_after.get("last_name"), "ContactMCP")
        self.assertEqual(det_after.get("job"), "Chef Opérateur")

        guard = contacts.delete_contact(cnt_id, confirm=False)
        self.assertEqual(guard.get("status"), "requires_confirmation")

        deleted = contacts.delete_contact(cnt_id, confirm=True)
        self.assertTrue(deleted.get("success"))

    # ── 4. PROJETS ───────────────────────────────────────────────
    def test_projects_lifecycle(self):
        res_p_list = projects.list_projects()
        self.assertIsInstance(res_p_list, dict)
        self.assertIn("projects", res_p_list)
        self.assertIsInstance(projects.get_project_form_context(), dict)

        first_prod = Production.query.first()
        prod_id = first_prod.id if first_prod else 1

        first_contact = Contact.query.first()
        contact_id = first_contact.id if first_contact else None

        res_c = projects.create_project(
            name="PyTest Tournage MCP",
            production_id=prod_id,
            first_ac_contact_id=contact_id,
            key_grip_contact_id=contact_id,
            notes="Projet test PyTest"
        )
        self.assertTrue(res_c.get("success"))

        all_pr = projects.list_projects().get("projects", [])
        proj = next((p for p in all_pr if p.get("name") == "PyTest Tournage MCP"), None)
        self.assertIsNotNone(proj)
        proj_id = proj["id"]

        det = projects.get_project(proj_id)
        self.assertEqual(det.get("name"), "PyTest Tournage MCP")
        if contact_id:
            self.assertEqual(det.get("first_ac_contact_id"), str(contact_id))
            self.assertEqual(det.get("key_grip_contact_id"), str(contact_id))

        # Test Patch mode: only updating notes without passing name or contacts
        res_u = projects.update_project(
            proj_id,
            notes="Notes patchées uniquement"
        )
        self.assertTrue(res_u.get("success"))
        det_after = projects.get_project(proj_id)
        self.assertEqual(det_after.get("name"), "PyTest Tournage MCP")
        self.assertEqual(det_after.get("notes"), "Notes patchées uniquement")
        if contact_id:
            self.assertEqual(det_after.get("first_ac_contact_id"), str(contact_id))
            self.assertEqual(det_after.get("key_grip_contact_id"), str(contact_id))

        # Delete Guard & Confirm
        guard = projects.delete_project(proj_id, confirm=False)
        self.assertEqual(guard.get("status"), "requires_confirmation")

        deleted = projects.delete_project(proj_id, confirm=True)
        self.assertTrue(deleted.get("success"))

    # ── 5. PRÉ-DEVIS ─────────────────────────────────────────────
    def test_pre_quotes_lifecycle(self):
        res_pq_list = pre_quotes.list_pre_quotes()
        self.assertIsInstance(res_pq_list, dict)
        self.assertIn("pre_quotes", res_pq_list)
        self.assertIn("delivery_config", pre_quotes.get_pre_quote_form_context())

        first_prod = Production.query.first()
        if not first_prod:
            first_prod = Production(name="Production Test Pré-Devis")
            db.session.add(first_prod)
            db.session.commit()
        prod_id = first_prod.id

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
        self.assertEqual(len(det.get("prestations", [])), 1)

        # Test Patch mode: only update project_name without passing items, prestations should be preserved
        res_u = pre_quotes.update_pre_quote(pq_id, project_name="Projet PyTest Patché")
        self.assertTrue(res_u.get("success"))
        det_after = pre_quotes.get_pre_quote(pq_id)
        self.assertEqual(det_after.get("project_name"), "Projet PyTest Patché")
        self.assertEqual(len(det_after.get("prestations", [])), 1)

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
        self.assertIsInstance(pricing.get_salary_rates(), dict)
        self.assertIsInstance(pricing.get_logistics_rates(), dict)

        first_v = Vehicle.query.first()
        if first_v:
            res_u = pricing.update_equipment_daily_rate("vehicles", first_v.id, float(first_v.daily_rate or 800.0))
            self.assertTrue(res_u.get("success"))

        sal_rates = pricing.get_salary_rates().get("rates", [])
        if sal_rates:
            res_s = pricing.update_salary_rate(sal_rates[0]["id"], "notes", "Note PyTest")
            self.assertTrue(res_s.get("success"))

        guard = pricing.delete_salary_rate(999999, confirm=False)
        self.assertEqual(guard.get("status"), "requires_confirmation")

    # ── 8. UTILISATEURS ──────────────────────────────────────────
    def test_users_lifecycle(self):
        res_u = users.list_users()
        self.assertIsInstance(res_u, dict)
        self.assertIn("users", res_u)

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
        res_cal = calendars.list_calendar_subscriptions()
        self.assertIsInstance(res_cal, dict)
        self.assertIn("subscriptions", res_cal)
        res_c = calendars.create_calendar_subscription(user_id=1, label="PyTest iCal")
        self.assertTrue(res_c.get("success"))
        token_id = res_c.get("token_id")

        guard = calendars.revoke_calendar_subscription(token_id, confirm=False)
        self.assertEqual(guard.get("status"), "requires_confirmation")

        revoked = calendars.revoke_calendar_subscription(token_id, confirm=True)
        self.assertTrue(revoked.get("success"))

        from models import CalendarSubscription
        test_sub = db.session.get(CalendarSubscription, token_id)
        if test_sub:
            db.session.delete(test_sub)
            db.session.commit()

    # ── 10. DOCUMENTS & VÉHICULES ────────────────────────────────
    def test_documents_and_vehicles(self):
        first_v = Vehicle.query.first()
        v_id = first_v.id if first_v else "mercedes-c63"

        sheet = documents.get_vehicle_sheet_data(v_id)
        self.assertIsNotNone(sheet)

        catalog_up = documents.update_catalog_pdf(with_prices=True)
        self.assertTrue(catalog_up.get("success"))

        self.assertIsInstance(vehicles.get_vehicles_with_config(), dict)
        self.assertIsInstance(vehicles.get_checkpoints_for_vehicle(v_id), dict)

        save_chk = vehicles.save_vehicle_checkpoint_config(v_id, ["exterior_cleanliness"])
        self.assertTrue(save_chk.get("success"))

        # Test véhicule invalide : renvoie [] proprement
        invalid_cps = vehicles.get_checkpoints_for_vehicle("recINVALIDE999")
        self.assertEqual(invalid_cps.get("checkpoints"), [])

    # ── 11. SÉCURITÉ & AUDIT ─────────────────────────────────────
    def test_security_scopes_and_audit(self):
        # 1. Rôle Technicien / User : aucun accès MCP autorisé (bloqué 403 même avec scope admin)
        tech_user = McpUserContext(1, "tech@test.com", "Tech", "User", "technicien", scope="admin")
        CURRENT_MCP_USER.set(tech_user)
        blocked_tech = projects.list_projects()
        self.assertEqual(blocked_tech.get("status"), "error")
        self.assertEqual(blocked_tech.get("error_code"), 403)

        # 2. Rôle Commercial : plafonné à read_only (écriture bloquée 403 même avec token write/admin)
        com_user = McpUserContext(1, "com@test.com", "Com", "User", "commercial", scope="write")
        CURRENT_MCP_USER.set(com_user)
        allowed_read = projects.list_projects()
        self.assertIn("projects", allowed_read)
        blocked_write = contacts.create_contact(first_name="Illegal", last_name="Write")
        self.assertEqual(blocked_write.get("status"), "error")
        self.assertEqual(blocked_write.get("error_code"), 403)

        # 3. Rôle Manager : plafonné à write (actions admin/destructives bloquées 403 même avec token admin)
        mgr_user = McpUserContext(1, "mgr@test.com", "Mgr", "User", "manager", scope="admin")
        CURRENT_MCP_USER.set(mgr_user)
        blocked_admin = users.delete_user(1, confirm=True)
        self.assertEqual(blocked_admin.get("status"), "error")
        self.assertEqual(blocked_admin.get("error_code"), 403)

        # 4. Rôle Super Admin : tous les droits
        CURRENT_MCP_USER.set(self.admin_user)
        admin_read = projects.list_projects()
        self.assertIn("projects", admin_read)

        # Audit logs enregistrés en base
        logs = McpAuditLog.query.order_by(McpAuditLog.created_at.desc()).limit(5).all()
        self.assertGreater(len(logs), 0)

        # Réinitialiser le contexte utilisateur sur admin
        CURRENT_MCP_USER.set(self.admin_user)


    # ── 12. PARSING DE DATES, FILTRES, PAGINATION & ENRICHISSEMENT ──
    def test_flexible_date_parsing(self):
        from mcp_server.utils import parse_flexible_date
        self.assertEqual(parse_flexible_date("15/09/2026"), "2026-09-15")
        self.assertEqual(parse_flexible_date("2026-09-15"), "2026-09-15")
        self.assertEqual(parse_flexible_date("15-09-2026"), "2026-09-15")
        self.assertEqual(parse_flexible_date("2026/09/15"), "2026-09-15")
        self.assertEqual(parse_flexible_date("2026-09-15T10:30:00"), "2026-09-15")
        self.assertIsNone(parse_flexible_date(""))
        self.assertIsNone(parse_flexible_date(None))

    def test_search_filters_and_pagination(self):
        # 1. Contacts
        c_list = contacts.list_contacts(limit=5, offset=0)
        self.assertLessEqual(c_list.get("count", 0), 5)
        c_search = contacts.list_contacts(query="NonExistentContactName999")
        self.assertEqual(c_search.get("total", 0), 0)

        # 2. Productions
        p_list = productions.list_productions(limit=3, offset=0)
        self.assertLessEqual(p_list.get("count", 0), 3)
        p_search = productions.list_productions(query="NonExistentProdName999")
        self.assertEqual(p_search.get("total", 0), 0)

        # 3. Projets
        pr_list = projects.list_projects(limit=5, offset=0)
        self.assertLessEqual(pr_list.get("count", 0), 5)
        pr_search = projects.list_projects(query="NonExistentProjectName999")
        self.assertEqual(pr_search.get("total", 0), 0)

        # 4. Devis
        q_list = pre_quotes.list_pre_quotes(limit=5, offset=0)
        self.assertLessEqual(q_list.get("count", 0), 5)

    def test_enriched_details(self):
        # Production enrichie
        first_p = productions.list_productions(limit=1).get("productions", [])
        if first_p:
            p_id = first_p[0]["id"]
            p_det = productions.get_production(p_id)
            self.assertIsNotNone(p_det)
            self.assertIn("contacts", p_det)
            self.assertIn("recent_projects", p_det)
            self.assertIsInstance(p_det["contacts"], list)
            self.assertIsInstance(p_det["recent_projects"], list)

        # Projet enrichi
        first_proj = projects.list_projects(limit=1).get("projects", [])
        if first_proj:
            proj_id = first_proj[0]["id"]
            proj_det = projects.get_project(proj_id)
            self.assertIsNotNone(proj_det)
            self.assertIn("assigned_contacts", proj_det)
            self.assertIn("vehicles", proj_det)
            self.assertIn("heads", proj_det)
            self.assertIn("waivers", proj_det)

    def test_vehicle_availability(self):
        first_v = Vehicle.query.first()
        v_id = first_v.id if first_v else "mercedes-c63"

        # Période valide
        res = vehicles.check_vehicle_availability(v_id, "2030-01-01", "2030-01-05")
        self.assertTrue(res.get("success"))
        self.assertTrue(res.get("available"))

        # Dates françaises
        res_fr = vehicles.check_vehicle_availability(v_id, "01/01/2030", "05/01/2030")
        self.assertTrue(res_fr.get("success"))
        self.assertTrue(res_fr.get("available"))

        # Date de fin antérieure
        res_err = vehicles.check_vehicle_availability(v_id, "2030-01-10", "2030-01-05")
        self.assertFalse(res_err.get("success"))

        # Véhicule inexistant
        res_inv = vehicles.check_vehicle_availability("recINVALIDE999", "2030-01-01", "2030-01-05")
        self.assertFalse(res_inv.get("success"))
        self.assertFalse(res_inv.get("available"))

    def test_dashboard_summary_and_pre_quote_duplicate(self):
        # Dashboard summary
        dash = projects.get_dashboard_summary()
        self.assertIsInstance(dash, dict)
        self.assertIn("active_shoots", dash)
        self.assertIn("upcoming_shoots_15d", dash)
        self.assertIn("pending_waivers", dash)

        # Pre-quote duplicate
        first_pq = pre_quotes.list_pre_quotes(limit=1).get("pre_quotes", [])
        if first_pq:
            orig_id = first_pq[0]["id"]
            res_dup = pre_quotes.duplicate_pre_quote(orig_id, new_project_name="Duplicated Project Test")
            self.assertTrue(res_dup.get("success"))
            dup_id = res_dup.get("new_pre_quote_id")
            self.assertIsNotNone(dup_id)

            # Cleanup duplicated pre-quote
            pre_quotes.delete_pre_quote(dup_id, confirm=True)

    def test_mcp_resources_and_prompts(self):
        from mcp_server import resources, prompts

        # Resources
        rates_json = resources.resource_pricing_rates()
        self.assertIn("equipment", rates_json)
        self.assertIn("salaries", rates_json)

        dash_json = resources.resource_dashboard_summary()
        self.assertIn("active_shoots", dash_json)

        veh_json = resources.resource_vehicles_catalog()
        self.assertIsInstance(veh_json, str)

        # Prompts
        p_tournage = prompts.prompt_nouveau_tournage("Projet Test", "Prod Test")
        self.assertIn("Projet Test", p_tournage)

        p_devis = prompts.prompt_chiffrer_devis("Projet Test", 3, "Mercedes Travelling")
        self.assertIn("Projet Test", p_devis)

        p_audit = prompts.prompt_audit_tournage(123)
        self.assertIn("123", p_audit)

    def test_mcp_waivers_tools(self):
        # 1. Listing des décharges
        res = waivers.list_waivers(mode="all")
        self.assertIsInstance(res, dict)
        self.assertIn("mode", res)
        self.assertIn("total", res)
        self.assertIn("pending_count", res)
        self.assertIn("pilot_waivers", res)
        self.assertIn("production_waivers", res)

        # 2. Test auto remind
        remind_res = waivers.auto_remind_waivers(days_before=2)
        self.assertTrue(remind_res.get("success"))
        self.assertIn("production_reminders_sent", remind_res)

        # 3. Test reset confirmation guard
        reset_res = waivers.reset_waiver(mode="pilot", waiver_id="test-uuid", confirm=False)
        self.assertFalse(reset_res.get("success"))
        self.assertEqual(reset_res.get("status"), "requires_confirmation")

    def test_mcp_fleet_360_and_conflicts_tools(self):
        # 1. Vue d'ensemble de la flotte
        fleet = vehicles.get_fleet_overview()
        self.assertIsInstance(fleet, dict)
        self.assertIn("vehicles", fleet)
        self.assertIn("stats", fleet)

        # 2. Détection unifiée des conflits (ciblé)
        conflicts = vehicles.check_booking_conflicts(
            start_date="2026-11-01",
            end_date="2026-11-05",
            vehicle_ids=["rec_dummy"],
        )
        self.assertIsInstance(conflicts, dict)
        self.assertIn("has_conflicts", conflicts)
        self.assertIn("conflicts_list", conflicts)
        self.assertFalse(conflicts.get("scanned_all_equipment"))

        # 2b. Détection globale de la flotte (sans vehicle_ids ni head_ids)
        global_conflicts = vehicles.check_booking_conflicts(
            start_date="2026-11-01",
            end_date="2026-11-05",
        )
        self.assertIsInstance(global_conflicts, dict)
        self.assertIn("has_conflicts", global_conflicts)
        self.assertTrue(global_conflicts.get("scanned_all_equipment"))
        self.assertIn("scan_summary", global_conflicts)

        # 3. Disponibilité d'un véhicule
        avail = vehicles.check_vehicle_availability(
            vehicle_id="dummy_id",
            start_date="2026-11-01",
            end_date="2026-11-05",
        )
        self.assertIsInstance(avail, dict)
        self.assertIn("available", avail)

    def test_mcp_incidents_tools_checkpoints(self):
        # Listing des incidents
        inc_res = incidents.list_incidents(limit=5)
        self.assertIsInstance(inc_res, dict)
        self.assertIn("incidents", inc_res)
        self.assertIn("stats", inc_res)

    def test_mcp_connector_routes_access_and_scoping(self):
        """Vérifie le contrôle d'accès aux routes web /admin/mcp-connector et la limitation de création de scope selon le rôle."""
        client = self.app.test_client()
        prev_csrf = self.app.config.get("WTF_CSRF_ENABLED", True)
        self.app.config["WTF_CSRF_ENABLED"] = False
        try:
            # 1. Technicien : accès refusé à la page (redirect 302)
            with client.session_transaction() as sess:
                sess["admin_authenticated"] = True
                sess["admin_user_id"] = 901
                sess["admin_user_role"] = "technicien"
            res = client.get("/admin/mcp-connector")
            self.assertEqual(res.status_code, 302)

            # 2. Commercial : accès GET 200, bloqué 403 sur scope 'admin' et 'write', autorisé 201 sur 'read_only'
            with client.session_transaction() as sess:
                sess["admin_authenticated"] = True
                sess["admin_user_id"] = 902
                sess["admin_user_role"] = "commercial"
            res_com_get = client.get("/admin/mcp-connector")
            self.assertEqual(res_com_get.status_code, 200)

            res_com_admin = client.post(
                "/admin/mcp-connector/generate",
                json={"name": "Com Admin", "scope": "admin"},
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            self.assertEqual(res_com_admin.status_code, 403)

            res_com_write = client.post(
                "/admin/mcp-connector/generate",
                json={"name": "Com Write", "scope": "write"},
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            self.assertEqual(res_com_write.status_code, 403)

            res_com_ro = client.post(
                "/admin/mcp-connector/generate",
                json={"name": "Com ReadOnly", "scope": "read_only"},
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            self.assertEqual(res_com_ro.status_code, 201)

            # 3. Manager : bloqué 403 sur 'admin', autorisé 201 sur 'write'
            with client.session_transaction() as sess:
                sess["admin_authenticated"] = True
                sess["admin_user_id"] = 903
                sess["admin_user_role"] = "manager"

            res_mgr_admin = client.post(
                "/admin/mcp-connector/generate",
                json={"name": "Mgr Admin", "scope": "admin"},
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            self.assertEqual(res_mgr_admin.status_code, 403)

            res_mgr_write = client.post(
                "/admin/mcp-connector/generate",
                json={"name": "Mgr Write", "scope": "write"},
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            self.assertEqual(res_mgr_write.status_code, 201)

            # 4. Administrateur : autorisé 201 sur 'admin'
            with client.session_transaction() as sess:
                sess["admin_authenticated"] = True
                sess["admin_user_id"] = 904
                sess["admin_user_role"] = "administrateur"

            res_adm_admin = client.post(
                "/admin/mcp-connector/generate",
                json={"name": "Adm Full", "scope": "admin"},
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            self.assertEqual(res_adm_admin.status_code, 201)
        finally:
            self.app.config["WTF_CSRF_ENABLED"] = prev_csrf


if __name__ == "__main__":
    unittest.main()

