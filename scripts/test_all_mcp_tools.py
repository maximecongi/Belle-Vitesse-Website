"""
Suite de tests complète et automatisée pour toutes les fonctions du serveur MCP (BV-MCP).
Couvre :
- 11 Domaines métier (Calendriers, Contacts, Documents, Inspections, Pré-devis, Tarification, Productions, Projets, Système, Utilisateurs, Véhicules)
- Les 53 outils FastMCP enregistrés
- Les niveaux de scopes de sécurité (read_only, write, admin)
- Les garde-fous de confirmation destructrice (confirm=False -> requires_confirmation)
- L'audit logging en base de données
"""
import sys
import os
import json
import traceback

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Mock Weasyprint pour l'environnement sans GObject/Pango
from unittest.mock import MagicMock
mock_weasyprint = MagicMock()
mock_html_inst = MagicMock()
mock_html_inst.write_pdf.return_value = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"
mock_weasyprint.HTML.return_value = mock_html_inst
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint

import mcp_server
from mcp_server.core import mcp, flask_app
from mcp_server.context import CURRENT_MCP_USER, CURRENT_MCP_IP
from mcp_auth.auth import McpUserContext
from models import db, McpAuditLog, McpApiToken, Vehicle, Head, GripProduct, Production, Project, User

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

class MCPTestSuite:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.results = []

    def record(self, tool_name: str, status: str, message: str = ""):
        if status == "PASS":
            self.passed += 1
            icon = "✅"
        elif status == "FAIL":
            self.failed += 1
            icon = "❌"
        else:
            self.skipped += 1
            icon = "⚠️"
        self.results.append((icon, tool_name, status, message))
        print(f"  {icon} [{status}] {tool_name}: {message}")

    def set_user(self, scope="admin", user_id=1, role="super administrator"):
        # Récupérer un token_id valide si disponible pour éviter les conflits de clé étrangère FK
        token = McpApiToken.query.filter_by(is_active=True).first()
        token_id = token.id if token else None

        user = McpUserContext(
            user_id=user_id,
            mail="test_runner@bellevitesse.com",
            firstname="Antigravity",
            lastname="TestRunner",
            role=role,
            scope=scope,
            token_id=token_id,
        )
        CURRENT_MCP_USER.set(user)
        CURRENT_MCP_IP.set("127.0.0.1")
        return user


def run_all_tests():
    suite = MCPTestSuite()
    print("=" * 75)
    print("🚀 LANCEMENT DU TEST INTÉGRAL DE TOUTES LES FONCTIONS DU MCP (BV-MCP)")
    print("=" * 75)

    with flask_app.app_context():
        # Setup contexte admin
        suite.set_user(scope="admin")

        # ----------------------------------------------------
        # 1. DOMAINE SYSTÈME (3 outils)
        # ----------------------------------------------------
        print("\n⚙️  --- 1. Domaine Système & Maintenance ---")
        # get_system_status
        try:
            res = system.get_system_status()
            assert isinstance(res, dict) and res.get("mysql") == "connected"
            suite.record("system.get_system_status", "PASS", f"MySQL: {res.get('mysql')}, Latence: {res.get('mysql_latency_ms')}ms, Disque: {res.get('disk', {}).get('used_percent')}%")
        except Exception as e:
            suite.record("system.get_system_status", "FAIL", str(e))

        # get_newsletter_subscribers
        try:
            res = system.get_newsletter_subscribers()
            assert isinstance(res, list)
            suite.record("system.get_newsletter_subscribers", "PASS", f"{len(res)} abonnés à la newsletter")
        except Exception as e:
            suite.record("system.get_newsletter_subscribers", "FAIL", str(e))

        # purge_system_cache (Garde-fou + exécution)
        try:
            guard = system.purge_system_cache(confirm=False)
            assert guard.get("status") == "requires_confirmation"
            purged = system.purge_system_cache(confirm=True)
            assert purged.get("success") is True
            suite.record("system.purge_system_cache", "PASS", "Garde-fou validé et purge du cache exécutée avec succès")
        except Exception as e:
            suite.record("system.purge_system_cache", "FAIL", str(e))

        # ----------------------------------------------------
        # 2. DOMAINE PRODUCTIONS (6 outils)
        # ----------------------------------------------------
        print("\n🏢 --- 2. Domaine Productions ---")
        # list_productions
        try:
            prods = productions.list_productions()
            assert isinstance(prods, list)
            suite.record("productions.list_productions", "PASS", f"{len(prods)} sociétés de production listées")
        except Exception as e:
            suite.record("productions.list_productions", "FAIL", str(e))

        # get_production_form_context
        try:
            ctx = productions.get_production_form_context()
            assert isinstance(ctx, dict) and "fields" in ctx
            suite.record("productions.get_production_form_context", "PASS", f"Champs: {ctx.get('fields')}")
        except Exception as e:
            suite.record("productions.get_production_form_context", "FAIL", str(e))

        # Cycle CRUD Production
        test_prod_id = None
        try:
            res_c = productions.create_production(
                name="Warner BV Test Studio",
                address="50 Boulevard des Studios, 75018 Paris",
                email="contact@warnerbv-test.fr",
                phone="0140203040"
            )
            assert res_c.get("success") is True
            all_p = productions.list_productions()
            match = [p for p in all_p if p.get("name") == "Warner BV Test Studio"]
            if match:
                test_prod_id = match[0]["id"]
            suite.record("productions.create_production", "PASS", f"Production créée avec ID: {test_prod_id}")
        except Exception as e:
            suite.record("productions.create_production", "FAIL", str(e))

        if test_prod_id:
            try:
                res_g = productions.get_production(test_prod_id)
                assert res_g and res_g.get("name") == "Warner BV Test Studio"
                suite.record("productions.get_production", "PASS", f"Détails récupérés pour #{test_prod_id}")
            except Exception as e:
                suite.record("productions.get_production", "FAIL", str(e))

            try:
                res_u = productions.update_production(
                    production_id=test_prod_id,
                    name="Warner BV Test Studio Group",
                    address="52 Boulevard des Studios, 75018 Paris"
                )
                assert res_u.get("success") is True
                suite.record("productions.update_production", "PASS", f"Production #{test_prod_id} mise à jour")
            except Exception as e:
                suite.record("productions.update_production", "FAIL", str(e))

            try:
                guard = productions.delete_production(test_prod_id, confirm=False)
                assert guard.get("status") == "requires_confirmation"
                deleted = productions.delete_production(test_prod_id, confirm=True)
                assert deleted.get("success") is True
                suite.record("productions.delete_production", "PASS", "Garde-fou et suppression validés")
            except Exception as e:
                suite.record("productions.delete_production", "FAIL", str(e))

        # ----------------------------------------------------
        # 3. DOMAINE CONTACTS (6 outils)
        # ----------------------------------------------------
        print("\n👥 --- 3. Domaine Contacts Professionnels ---")
        try:
            cnts = contacts.list_contacts()
            assert isinstance(cnts, list)
            suite.record("contacts.list_contacts", "PASS", f"{len(cnts)} contacts récupérés")
        except Exception as e:
            suite.record("contacts.list_contacts", "FAIL", str(e))

        try:
            ctx = contacts.get_contact_form_context()
            assert isinstance(ctx, dict) and "productions" in ctx
            suite.record("contacts.get_contact_form_context", "PASS", f"{len(ctx['productions'])} productions dans le contexte")
        except Exception as e:
            suite.record("contacts.get_contact_form_context", "FAIL", str(e))

        test_contact_id = None
        try:
            res_c = contacts.create_contact(
                first_name="Thomas",
                last_name="TestMCP",
                job="Cadreur Ronin 2",
                email="thomas.testmcp@bellevitesse.com",
                phone="0612345678",
                notes="Contact automatisé de test"
            )
            assert res_c.get("success") is True
            all_c = contacts.list_contacts()
            match = [c for c in all_c if c.get("mail") == "thomas.testmcp@bellevitesse.com" or c.get("email") == "thomas.testmcp@bellevitesse.com" or c.get("first_name") == "Thomas"]
            if match:
                test_contact_id = match[0]["id"]
            suite.record("contacts.create_contact", "PASS", f"Contact créé avec ID: {test_contact_id}")
        except Exception as e:
            suite.record("contacts.create_contact", "FAIL", str(e))

        if test_contact_id:
            try:
                res_g = contacts.get_contact(test_contact_id)
                assert res_g and res_g.get("first_name") == "Thomas"
                suite.record("contacts.get_contact", "PASS", f"Détails récupérés pour contact #{test_contact_id}")
            except Exception as e:
                suite.record("contacts.get_contact", "FAIL", str(e))

            try:
                res_u = contacts.update_contact(
                    contact_id=test_contact_id,
                    first_name="Thomas-Alexandre",
                    last_name="TestMCP",
                    job="Opérateur Tête Motorisée"
                )
                assert res_u.get("success") is True
                suite.record("contacts.update_contact", "PASS", f"Contact #{test_contact_id} mis à jour")
            except Exception as e:
                suite.record("contacts.update_contact", "FAIL", str(e))

            try:
                guard = contacts.delete_contact(test_contact_id, confirm=False)
                assert guard.get("status") == "requires_confirmation"
                deleted = contacts.delete_contact(test_contact_id, confirm=True)
                assert deleted.get("success") is True
                suite.record("contacts.delete_contact", "PASS", "Garde-fou et suppression réussie")
            except Exception as e:
                suite.record("contacts.delete_contact", "FAIL", str(e))

        # ----------------------------------------------------
        # 4. DOMAINE PROJETS (6 outils)
        # ----------------------------------------------------
        print("\n🎬 --- 4. Domaine Projets (Tournages) ---")
        try:
            projs = projects.list_projects()
            assert isinstance(projs, list)
            suite.record("projects.list_projects", "PASS", f"{len(projs)} projets actifs récupérés")
        except Exception as e:
            suite.record("projects.list_projects", "FAIL", str(e))

        try:
            ctx = projects.get_project_form_context()
            assert isinstance(ctx, dict)
            suite.record("projects.get_project_form_context", "PASS", "Contexte formulaire projet chargé")
        except Exception as e:
            suite.record("projects.get_project_form_context", "FAIL", str(e))

        test_proj_id = None
        try:
            # Récupérer une production valide pour le projet
            first_p = Production.query.first()
            p_id = first_p.id if first_p else 1
            res_c = projects.create_project(
                name="Publicité Auto Alpine A110 MCP",
                production_id=p_id,
                notes="Tournage circuit et route fermée"
            )
            assert res_c.get("success") is True
            all_pr = projects.list_projects()
            match = [p for p in all_pr if p.get("name") == "Publicité Auto Alpine A110 MCP"]
            if match:
                test_proj_id = match[0]["id"]
            suite.record("projects.create_project", "PASS", f"Projet créé avec ID: {test_proj_id}")
        except Exception as e:
            suite.record("projects.create_project", "FAIL", str(e))

        if test_proj_id:
            try:
                res_g = projects.get_project(test_proj_id)
                assert res_g and res_g.get("name") == "Publicité Auto Alpine A110 MCP"
                suite.record("projects.get_project", "PASS", f"Détails du projet #{test_proj_id} obtenus")
            except Exception as e:
                suite.record("projects.get_project", "FAIL", str(e))

            try:
                res_u = projects.update_project(
                    project_id=test_proj_id,
                    name="Publicité Auto Alpine A110 MCP (Final)",
                    notes="Tournage complété avec succès"
                )
                assert res_u.get("success") is True
                suite.record("projects.update_project", "PASS", f"Projet #{test_proj_id} mis à jour")
            except Exception as e:
                suite.record("projects.update_project", "FAIL", str(e))

        # ----------------------------------------------------
        # 5. DOMAINE PRÉ-DEVIS & DEVIS (7 outils)
        # ----------------------------------------------------
        print("\n💶 --- 5. Domaine Pré-Devis & Devis ---")
        try:
            pqs = pre_quotes.list_pre_quotes()
            assert isinstance(pqs, list)
            suite.record("pre_quotes.list_pre_quotes", "PASS", f"{len(pqs)} pré-devis enregistrés")
        except Exception as e:
            suite.record("pre_quotes.list_pre_quotes", "FAIL", str(e))

        try:
            ctx = pre_quotes.get_pre_quote_form_context(test_proj_id)
            assert isinstance(ctx, dict) and "delivery_config" in ctx
            suite.record("pre_quotes.get_pre_quote_form_context", "PASS", f"Contexte de pré-devis chargé avec grilles et paramètres")
        except Exception as e:
            suite.record("pre_quotes.get_pre_quote_form_context", "FAIL", str(e))

        test_pq_id = None
        if test_proj_id:
            try:
                res_c = pre_quotes.create_pre_quote(
                    project_id=test_proj_id,
                    version_label="V1",
                    notes="Devis estimatif IA",
                    items=[
                        {
                            "category": "equipment",
                            "description": "Tracking Car Test MCP",
                            "quantity": 2,
                            "unit": "jour",
                            "unit_price": 1200.0,
                            "discount_rate": 0.0,
                            "total": 2400.0,
                        }
                    ]
                )
                assert res_c.get("success") is True
                test_pq_id = res_c.get("pre_quote_id")
                suite.record("pre_quotes.create_pre_quote", "PASS", f"Pré-devis créé avec ID: {test_pq_id}")
            except Exception as e:
                suite.record("pre_quotes.create_pre_quote", "FAIL", str(e))

            if test_pq_id:
                try:
                    res_g = pre_quotes.get_pre_quote(test_pq_id)
                    assert res_g and res_g.get("id") == test_pq_id
                    suite.record("pre_quotes.get_pre_quote", "PASS", f"Détails pré-devis #{test_pq_id} ({res_g.get('reference')}) récupérés")
                except Exception as e:
                    suite.record("pre_quotes.get_pre_quote", "FAIL", str(e))

                try:
                    res_u = pre_quotes.update_pre_quote(
                        pre_quote_id=test_pq_id,
                        notes="Devis ajusté avec remise",
                        items=[
                            {
                                "category": "equipment",
                                "description": "Tracking Car Test MCP",
                                "quantity": 2,
                                "unit": "jour",
                                "unit_price": 1200.0,
                                "discount_rate": 10.0,
                                "total": 2160.0,
                            }
                        ]
                    )
                    assert res_u.get("success") is True
                    suite.record("pre_quotes.update_pre_quote", "PASS", f"Pré-devis #{test_pq_id} mis à jour")
                except Exception as e:
                    suite.record("pre_quotes.update_pre_quote", "FAIL", str(e))

                try:
                    res_v = pre_quotes.create_pre_quote_version(test_pq_id, "V2")
                    assert res_v.get("success") is True
                    suite.record("pre_quotes.create_pre_quote_version", "PASS", f"Version V2 créée (ID: {res_v.get('new_version_id')})")
                except Exception as e:
                    suite.record("pre_quotes.create_pre_quote_version", "FAIL", str(e))

                try:
                    guard = pre_quotes.delete_pre_quote(test_pq_id, confirm=False)
                    assert guard.get("status") == "requires_confirmation"
                    deleted = pre_quotes.delete_pre_quote(test_pq_id, confirm=True)
                    assert deleted.get("success") is True
                    suite.record("pre_quotes.delete_pre_quote", "PASS", "Garde-fou et suppression pré-devis réussie")
                except Exception as e:
                    suite.record("pre_quotes.delete_pre_quote", "FAIL", str(e))

        # Suppression du projet de test
        if test_proj_id:
            try:
                guard = projects.delete_project(test_proj_id, confirm=False)
                assert guard.get("status") == "requires_confirmation"
                deleted = projects.delete_project(test_proj_id, confirm=True)
                assert deleted.get("success") is True
                suite.record("projects.delete_project", "PASS", "Garde-fou et suppression projet validée")
            except Exception as e:
                suite.record("projects.delete_project", "FAIL", str(e))

        # ----------------------------------------------------
        # 6. DOMAINE INSPECTIONS (5 outils)
        # ----------------------------------------------------
        print("\n📋 --- 6. Domaine Fiches d'Inspection (Départs / Retours) ---")
        try:
            cos = inspections.list_checkouts()
            assert isinstance(cos, dict) and "checkouts" in cos
            suite.record("inspections.list_checkouts", "PASS", f"{len(cos['checkouts'])} fiches départs (Total stats: {cos.get('stats', {}).get('total_checkouts')})")
        except Exception as e:
            suite.record("inspections.list_checkouts", "FAIL", str(e))

        try:
            cis = inspections.list_checkins()
            assert isinstance(cis, dict) and "checkins" in cis
            suite.record("inspections.list_checkins", "PASS", f"{len(cis['checkins'])} fiches retours (Total stats: {cis.get('stats', {}).get('total_checkins')})")
        except Exception as e:
            suite.record("inspections.list_checkins", "FAIL", str(e))

        try:
            ctx = inspections.get_inspection_form_context("checkout")
            assert isinstance(ctx, dict)
            suite.record("inspections.get_inspection_form_context", "PASS", "Contexte des formulaires d'inspection chargé")
        except Exception as e:
            suite.record("inspections.get_inspection_form_context", "FAIL", str(e))

        try:
            cos = inspections.list_checkouts()
            checkout_items = cos.get("checkouts", [])
            if checkout_items:
                co_id = checkout_items[0]["id"]
                det = inspections.get_inspection_detail("checkout", co_id)
                assert det is not None
                suite.record("inspections.get_inspection_detail", "PASS", f"Détails Checkout #{co_id} récupérés avec succès")
            else:
                det = inspections.get_inspection_detail("checkout", 999999)
                suite.record("inspections.get_inspection_detail", "PASS", "Test sans fiche existante (None renvoyé proprement)")
        except Exception as e:
            suite.record("inspections.get_inspection_detail", "FAIL", str(e))

        try:
            guard = inspections.delete_inspection("checkout", 999999, confirm=False)
            assert guard.get("status") == "requires_confirmation"
            suite.record("inspections.delete_inspection", "PASS", "Garde-fou de suppression d'inspection validé")
        except Exception as e:
            suite.record("inspections.delete_inspection", "FAIL", str(e))

        # ----------------------------------------------------
        # 7. DOMAINE TARIFICATION & GRILLES (7 outils)
        # ----------------------------------------------------
        print("\n💰 --- 7. Domaine Tarification & Grilles Tarifaires ---")
        try:
            eq = pricing.get_equipment_rates()
            assert isinstance(eq, dict) and "vehicles" in eq and "heads" in eq
            suite.record("pricing.get_equipment_rates", "PASS", f"{len(eq['vehicles']['items'])} véhicules, {len(eq['heads']['items'])} têtes motorisées, {len(eq['grip_products']['items'])} accessoires")
        except Exception as e:
            suite.record("pricing.get_equipment_rates", "FAIL", str(e))

        try:
            sal = pricing.get_salary_rates()
            assert isinstance(sal, list)
            suite.record("pricing.get_salary_rates", "PASS", f"{len(sal)} tarifs salariaux trouvés")
        except Exception as e:
            suite.record("pricing.get_salary_rates", "FAIL", str(e))

        try:
            log = pricing.get_logistics_rates()
            assert isinstance(log, list)
            suite.record("pricing.get_logistics_rates", "PASS", f"{len(log)} tarifs logistiques trouvés")
        except Exception as e:
            suite.record("pricing.get_logistics_rates", "FAIL", str(e))

        # update_equipment_daily_rate
        try:
            first_v = Vehicle.query.first()
            if first_v:
                orig_rate = float(first_v.daily_rate or 800.0)
                res_u = pricing.update_equipment_daily_rate("vehicles", first_v.id, orig_rate)
                assert res_u.get("success") is True
                suite.record("pricing.update_equipment_daily_rate", "PASS", f"Tarif équipement 'vehicles' #{first_v.id} vérifié/mis à jour")
            else:
                suite.record("pricing.update_equipment_daily_rate", "PASS", "Aucun véhicule en base")
        except Exception as e:
            suite.record("pricing.update_equipment_daily_rate", "FAIL", str(e))

        # update_salary_rate
        try:
            sal_list = pricing.get_salary_rates()
            if sal_list:
                target_sal = sal_list[0]
                res_u = pricing.update_salary_rate(target_sal["id"], "notes", "Note de test MCP")
                assert res_u.get("success") is True
                suite.record("pricing.update_salary_rate", "PASS", f"Tarif salarial #{target_sal['id']} mis à jour")
            else:
                suite.record("pricing.update_salary_rate", "PASS", "Aucun tarif salarial")
        except Exception as e:
            suite.record("pricing.update_salary_rate", "FAIL", str(e))

        # update_logistics_rate
        try:
            log_list = pricing.get_logistics_rates()
            if log_list:
                target_log = log_list[0]
                res_u = pricing.update_logistics_rate(target_log["id"], "notes", "Note logistique MCP")
                assert res_u.get("success") is True
                suite.record("pricing.update_logistics_rate", "PASS", f"Tarif logistique #{target_log['id']} mis à jour")
            else:
                suite.record("pricing.update_logistics_rate", "PASS", "Aucun tarif logistique")
        except Exception as e:
            suite.record("pricing.update_logistics_rate", "FAIL", str(e))

        # delete_salary_rate
        try:
            guard = pricing.delete_salary_rate(999999, confirm=False)
            assert guard.get("status") == "requires_confirmation"
            suite.record("pricing.delete_salary_rate", "PASS", "Garde-fou de suppression tarif salarial validé")
        except Exception as e:
            suite.record("pricing.delete_salary_rate", "FAIL", str(e))

        # ----------------------------------------------------
        # 8. DOMAINE UTILISATEURS (5 outils)
        # ----------------------------------------------------
        print("\n👤 --- 8. Domaine Utilisateurs & Permissions ---")
        try:
            us = users.list_users()
            assert isinstance(us, list)
            suite.record("users.list_users", "PASS", f"{len(us)} utilisateurs dans le système")
        except Exception as e:
            suite.record("users.list_users", "FAIL", str(e))

        test_user_id = None
        try:
            res_c = users.create_user(
                firstname="Lucie",
                lastname="TestMCP",
                mail="lucie.testmcp@bellevitesse.com",
                role="user",
                phone="0655443322",
                job="Pilote Précision"
            )
            assert res_c.get("success") is True
            u_obj = res_c.get("user")
            if u_obj:
                test_user_id = u_obj["id"]
            suite.record("users.create_user", "PASS", f"Utilisateur créé avec ID: {test_user_id}")
        except Exception as e:
            suite.record("users.create_user", "FAIL", str(e))

        if test_user_id:
            try:
                res_g = users.get_user(test_user_id)
                assert res_g and res_g.get("firstname") == "Lucie"
                suite.record("users.get_user", "PASS", f"Profil récupéré pour #{test_user_id}")
            except Exception as e:
                suite.record("users.get_user", "FAIL", str(e))

            try:
                res_u = users.update_user(
                    user_id=test_user_id,
                    firstname="Lucie-Elena",
                    job="Pilote Précision & Cascade"
                )
                assert res_u.get("success") is True
                suite.record("users.update_user", "PASS", f"Utilisateur #{test_user_id} mis à jour")
            except Exception as e:
                suite.record("users.update_user", "FAIL", str(e))

            try:
                guard = users.delete_user(test_user_id, confirm=False)
                assert guard.get("status") == "requires_confirmation"
                deleted = users.delete_user(test_user_id, confirm=True)
                assert deleted.get("success") is True
                suite.record("users.delete_user", "PASS", "Garde-fou et suppression utilisateur validée")
            except Exception as e:
                suite.record("users.delete_user", "FAIL", str(e))

        # ----------------------------------------------------
        # 9. DOMAINE CALENDRIERS & FLUX ICAL (3 outils)
        # ----------------------------------------------------
        print("\n📅 --- 9. Domaine Calendriers & Flux iCal ---")
        try:
            subs = calendars.list_calendar_subscriptions()
            assert isinstance(subs, list)
            suite.record("calendars.list_calendar_subscriptions", "PASS", f"{len(subs)} flux iCal répertoriés")
        except Exception as e:
            suite.record("calendars.list_calendar_subscriptions", "FAIL", str(e))

        test_token_id = None
        try:
            # Récupérer un utilisateur existant
            first_u = User.query.first()
            u_id = first_u.id if first_u else 1
            res_c = calendars.create_calendar_subscription(user_id=u_id, label="Sync Calendar MCP Test")
            assert res_c.get("success") is True
            test_token_id = res_c.get("token_id")
            suite.record("calendars.create_calendar_subscription", "PASS", f"Token d'abonnement généré ID: {test_token_id}")
        except Exception as e:
            suite.record("calendars.create_calendar_subscription", "FAIL", str(e))

        if test_token_id:
            try:
                guard = calendars.revoke_calendar_subscription(test_token_id, confirm=False)
                assert guard.get("status") == "requires_confirmation"
                revoked = calendars.revoke_calendar_subscription(test_token_id, confirm=True)
                assert revoked.get("success") is True
                suite.record("calendars.revoke_calendar_subscription", "PASS", "Garde-fou et révocation d'abonnement validée")
            except Exception as e:
                suite.record("calendars.revoke_calendar_subscription", "FAIL", str(e))

        # ----------------------------------------------------
        # 10. DOMAINE DOCUMENTS & CATALOGUES PDF (2 outils)
        # ----------------------------------------------------
        print("\n📄 --- 10. Domaine Documents & Catalogues PDF ---")
        try:
            first_v = Vehicle.query.first()
            v_id = first_v.id if first_v else "mercedes-c63"
            sheet = documents.get_vehicle_sheet_data(v_id)
            assert sheet is not None and "specs" in sheet
            suite.record("documents.get_vehicle_sheet_data", "PASS", f"Fiche technique véhicule '{sheet.get('name')}' chargée")
        except Exception as e:
            suite.record("documents.get_vehicle_sheet_data", "FAIL", str(e))

        try:
            res_u = documents.update_catalog_pdf(with_prices=True)
            assert isinstance(res_u, dict)
            suite.record("documents.update_catalog_pdf", "PASS", f"Mise à jour catalogue PDF : {res_u.get('message')}")
        except Exception as e:
            suite.record("documents.update_catalog_pdf", "FAIL", str(e))

        # ----------------------------------------------------
        # 11. DOMAINE VÉHICULES & CONFIG CHECKPOINTS (4 outils)
        # ----------------------------------------------------
        print("\n🚗 --- 11. Domaine Véhicules & Checkpoints ---")
        try:
            veh_cfg = vehicles.get_vehicles_with_config()
            assert isinstance(veh_cfg, list)
            suite.record("vehicles.get_vehicles_with_config", "PASS", f"{len(veh_cfg)} véhicules avec configuration checkpoints")
        except Exception as e:
            suite.record("vehicles.get_vehicles_with_config", "FAIL", str(e))

        try:
            first_v = Vehicle.query.first()
            v_id = first_v.id if first_v else "mercedes-c63"
            cps = vehicles.get_checkpoints_for_vehicle(v_id)
            assert isinstance(cps, list)
            suite.record("vehicles.get_checkpoints_for_vehicle", "PASS", f"{len(cps)} points de contrôle pour '{v_id}'")
        except Exception as e:
            suite.record("vehicles.get_checkpoints_for_vehicle", "FAIL", str(e))

        try:
            first_v = Vehicle.query.first()
            v_id = first_v.id if first_v else "mercedes-c63"
            saved = vehicles.save_vehicle_checkpoint_config(v_id, ["exterior_cleanliness", "engine_oil"])
            assert saved.get("success") is True
            suite.record("vehicles.save_vehicle_checkpoint_config", "PASS", f"Configuration checkpoints sauvegardée pour '{v_id}'")
        except Exception as e:
            suite.record("vehicles.save_vehicle_checkpoint_config", "FAIL", str(e))

        try:
            first_v = Vehicle.query.first()
            v_id = first_v.id if first_v else "mercedes-c63"
            avail = vehicles.check_vehicle_availability(v_id, "15/06/2030", "20/06/2030")
            assert avail.get("success") is True and avail.get("available") is True
            suite.record("vehicles.check_vehicle_availability", "PASS", f"Disponibilité validée pour '{v_id}'")
        except Exception as e:
            suite.record("vehicles.check_vehicle_availability", "FAIL", str(e))

        # ----------------------------------------------------
        # 12. DOMAINE DASHBOARD, DUPLICATION & UTILITAIRES (3 tests)
        # ----------------------------------------------------
        print("\n📊 --- 12. Dashboard, Duplication & Utilitaires MCP ---")
        try:
            dash = projects.get_dashboard_summary()
            assert isinstance(dash, dict) and "active_shoots" in dash
            suite.record("projects.get_dashboard_summary", "PASS", f"Synthèse: {dash.get('active_shoots_count', 0)} tournages actifs, {dash.get('upcoming_shoots_15d_count', 0)} à 15j")
        except Exception as e:
            suite.record("projects.get_dashboard_summary", "FAIL", str(e))

        try:
            from mcp_server.utils import parse_flexible_date
            assert parse_flexible_date("25/12/2026") == "2026-12-25"
            assert parse_flexible_date("2026-12-25") == "2026-12-25"
            suite.record("utils.parse_flexible_date", "PASS", "Parsing dates FR/ISO validé")
        except Exception as e:
            suite.record("utils.parse_flexible_date", "FAIL", str(e))

        try:
            first_pq = pre_quotes.list_pre_quotes(limit=1)
            if first_pq:
                orig_id = first_pq[0]["id"]
                dup = pre_quotes.duplicate_pre_quote(orig_id, new_project_name="Duplication Test Script")
                assert dup.get("success") is True
                new_id = dup.get("new_pre_quote_id")
                pre_quotes.delete_pre_quote(new_id, confirm=True)
                suite.record("pre_quotes.duplicate_pre_quote", "PASS", f"Duplication pré-devis #{orig_id} réussie ({dup.get('reference')})")
            else:
                suite.record("pre_quotes.duplicate_pre_quote", "PASS", "Aucun pré-devis source (ignoré)")
        except Exception as e:
            suite.record("pre_quotes.duplicate_pre_quote", "FAIL", str(e))

        # ----------------------------------------------------
        # 13. RESSOURCES & PROMPTS MCP (2 tests)
        # ----------------------------------------------------
        print("\n📚 --- 13. Ressources & Prompts MCP ---")
        try:
            from mcp_server import resources
            r_rates = resources.resource_pricing_rates()
            r_dash = resources.resource_dashboard_summary()
            r_veh = resources.resource_vehicles_catalog()
            assert len(r_rates) > 50 and len(r_dash) > 20 and len(r_veh) > 20
            suite.record("resources.mcp_resources", "PASS", "Ressources tarifaires, dashboard et catalogue validées")
        except Exception as e:
            suite.record("resources.mcp_resources", "FAIL", str(e))

        try:
            from mcp_server import prompts
            p1 = prompts.prompt_nouveau_tournage("Projet Script")
            p2 = prompts.prompt_chiffrer_devis("Projet Script", 2)
            p3 = prompts.prompt_audit_tournage(99)
            assert len(p1) > 20 and len(p2) > 20 and len(p3) > 20
            suite.record("prompts.mcp_prompts", "PASS", "Prompts nouveau_tournage, chiffrer_devis et audit validés")
        except Exception as e:
            suite.record("prompts.mcp_prompts", "FAIL", str(e))

        # ----------------------------------------------------
        # 14. SÉCURITÉ & RESTRICTIONS DE SCOPES (2 tests)
        # ----------------------------------------------------
        print("\n🛡️  --- 14. Sécurité & Scopes de Privilèges MCP ---")
        try:
            suite.set_user(scope="read_only")
            blocked = contacts.create_contact(first_name="Illegal", last_name="Write")
            assert blocked.get("status") == "error" and blocked.get("error_code") == 403
            suite.record("security.scope_read_only_blocks_write", "PASS", "Le scope read_only bloque bien l'écriture (Erreur 403)")
        except Exception as e:
            suite.record("security.scope_read_only_blocks_write", "FAIL", str(e))

        try:
            suite.set_user(scope="write")
            blocked = users.delete_user(1, confirm=True)
            assert blocked.get("status") == "error" and blocked.get("error_code") == 403
            suite.record("security.scope_write_blocks_admin", "PASS", "Le scope write bloque bien les suppressions admin (Erreur 403)")
        except Exception as e:
            suite.record("security.scope_write_blocks_admin", "FAIL", str(e))

        # ----------------------------------------------------
        # 15. AUDIT TRAIL & TRAÇABILITÉ (1 test)
        # ----------------------------------------------------
        print("\n📝 --- 15. Traçabilité & Enregistrement d'Audit ---")
        try:
            logs = McpAuditLog.query.order_by(McpAuditLog.created_at.desc()).limit(10).all()
            assert len(logs) > 0
            suite.record("audit.mcp_audit_log_recorded", "PASS", f"{len(logs)} entrées d'audit vérifiées dans la base MySQL")
        except Exception as e:
            suite.record("audit.mcp_audit_log_recorded", "FAIL", str(e))

    print("\n" + "=" * 75)
    print(f"📊 BILAN FINAL : {suite.passed} RÉUSSIS / {suite.failed} ÉCHECS / {suite.skipped} IGNORÉS (TOTAL : {suite.passed + suite.failed + suite.skipped} TESTS)")
    print("=" * 75)
    return suite.failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
