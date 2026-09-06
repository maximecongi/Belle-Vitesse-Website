import os
import sys
import unittest
from datetime import date
from unittest.mock import MagicMock

# Mock Weasyprint avant l'import de Flask
mock_weasyprint = MagicMock()
mock_html_inst = MagicMock()
mock_html_inst.write_pdf.return_value = (
    b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
    b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n"
    b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"
)
mock_weasyprint.HTML.return_value = mock_html_inst
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint

from app import create_app  # noqa: E402
from models import db, Project, Production, User, Vehicle  # noqa: E402
from models.incident import Incident  # noqa: E402
from services.admin import incidents as incident_service  # noqa: E402
from mcp_server.tools import incidents as mcp_incidents  # noqa: E402
from mcp_server.context import CURRENT_MCP_USER  # noqa: E402
from mcp_auth.auth import McpUserContext  # noqa: E402


class IncidentsTestCase(unittest.TestCase):
    def setUp(self):
        os.environ["FLASK_ENV"] = "testing"
        os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        os.environ["WTF_CSRF_ENABLED"] = "False"
        os.environ["USE_SSH_TUNNEL"] = "false"

        self.app = create_app()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Création des données de test
        self.prod = Production(name="Production Marvel Studio")
        db.session.add(self.prod)
        db.session.commit()

        self.user = User(
            firstname="Maxime",
            lastname="Congi",
            mail="pilot@bellevitesse.com",
            role="super administrator",
        )
        db.session.add(self.user)
        db.session.commit()

        self.project = Project(
            name="Publicité Circuit",
            production_id=self.prod.id,
            departure_date=date.today(),
            shoot_start_date=date.today(),
            shoot_end_date=date.today(),
        )
        db.session.add(self.project)

        self.vehicle = Vehicle(
            id="mercedes-c63",
            daily_rate=1500,
            fields={"name": "Mercedes C63 AMG", "unique_id": "BV-CAR-01"},
        )
        db.session.add(self.vehicle)
        db.session.commit()

        # Utilisateur MCP admin
        self.admin_mcp_user = McpUserContext(
            user_id=self.user.id,
            mail=self.user.mail,
            firstname=self.user.firstname,
            lastname=self.user.lastname,
            role="super administrator",
            scope="admin",
        )
        CURRENT_MCP_USER.set(self.admin_mcp_user)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_create_incident(self):
        """Vérifie la création d'un incident avec calcul automatique du numéro BVIC."""
        form_data = {
            "title": "Choc jupe avant sur vibreur",
            "project_id": self.project.id,
            "vehicle_id": self.vehicle.id,
            "equipment_name": "Tête Flight Head",
            "reported_by_id": self.user.id,
            "incident_date": "2026-09-04",
            "incident_time": "15:30",
            "location": "Virage 4",
            "category": "carrosserie",
            "severity": "modere",
            "status": "signale",
            "shooting_impact": "retard",
            "description": "Fissure de la fibre suite à passage sur vibreur haut.",
            "immediate_actions": "Remplacement lame avant par pièce de rechange.",
            "estimated_cost": "850.00",
            "insurance_declared": "1",
            "insurance_reference": "SIN-2026-001",
        }
        inc = incident_service.create_incident(form_data)
        self.assertIsNotNone(inc.id)
        self.assertTrue(inc.incident_number.startswith("BVIC-"))
        self.assertEqual(inc.title, "Choc jupe avant sur vibreur")
        self.assertEqual(inc.category, "carrosserie")
        self.assertEqual(inc.severity, "modere")
        self.assertEqual(float(inc.estimated_cost), 850.0)
        self.assertTrue(inc.insurance_declared)

    def test_auto_reporter_and_project_equipment_context(self):
        """Vérifie l'assignation automatique du déclarant et le filtrage des véhicules/têtes par projet."""
        self.project.vehicles_to_check = self.vehicle.id
        self.project.heads_to_check = "head-flight-01"
        db.session.commit()

        # 1. Création sans reported_by_id : doit utiliser automatiquement l'utilisateur connecté/disponible
        inc = incident_service.create_incident({
            "title": "Incident sans déclarant explicite",
            "project_id": self.project.id,
            "incident_date": "2026-09-04",
        })
        self.assertIsNotNone(inc.reported_by_id)
        self.assertEqual(inc.reported_by_id, self.user.id)

        # 2. Vérification du contexte de formulaire enrichi avec véhicules et têtes du projet
        ctx = incident_service.get_incident_form_context()
        p_data = next((p for p in ctx["projects"] if p["id"] == self.project.id), None)
        self.assertIsNotNone(p_data)
        self.assertGreaterEqual(len(p_data["vehicles"]), 1)
        self.assertEqual(p_data["vehicles"][0]["id"], self.vehicle.id)
        self.assertGreaterEqual(len(p_data["heads"]), 1)
        self.assertEqual(p_data["heads"][0]["id"], "head-flight-01")

    def test_list_incidents_and_kpi_stats(self):
        """Vérifie le calcul des statistiques KPI et les filtres de recherche."""
        incident_service.create_incident({
            "title": "Incident Mineur",
            "incident_date": "2026-09-04",
            "severity": "mineur",
            "status": "signale",
            "estimated_cost": 200.0,
        })
        incident_service.create_incident({
            "title": "Incident Critique Bloquant",
            "incident_date": "2026-09-04",
            "severity": "critique",
            "status": "en_reparation",
            "estimated_cost": 3500.0,
            "project_id": self.project.id,
        })

        res = incident_service.list_incidents()
        self.assertEqual(len(res["incidents"]), 2)
        stats = res["stats"]
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["in_progress"], 2)
        self.assertEqual(stats["critical"], 1)
        self.assertEqual(stats["reparation"], 1)
        self.assertEqual(stats["total_estimated_cost"], 3700.0)

        # Filtre par sévérité
        crit_res = incident_service.list_incidents(severity="critique")
        self.assertEqual(len(crit_res["incidents"]), 1)
        self.assertEqual(crit_res["incidents"][0]["title"], "Incident Critique Bloquant")

        # Recherche textuelle
        q_res = incident_service.list_incidents(query="Bloquant")
        self.assertEqual(len(q_res["incidents"]), 1)

    def test_get_incident_detail(self):
        """Vérifie la restitution des données enrichies d'un incident."""
        inc = incident_service.create_incident({
            "title": "Panne assistance caméra car",
            "project_id": self.project.id,
            "vehicle_id": self.vehicle.id,
            "reported_by_id": self.user.id,
            "incident_date": "2026-09-04",
            "severity": "critique",
            "status": "en_expertise",
        })

        detail = incident_service.get_incident_detail(inc.id)
        self.assertIsNotNone(detail)
        self.assertEqual(detail["incident_number"], inc.incident_number)
        self.assertEqual(detail["project"]["name"], "Publicité Circuit")
        self.assertEqual(detail["vehicle"]["name"], "Mercedes C63 AMG")
        self.assertEqual(detail["reporter"]["name"], "Maxime Congi")

        # Recherche par numéro BVIC
        detail_by_num = incident_service.get_incident_detail(inc.incident_number)
        self.assertEqual(detail_by_num["id"], inc.id)

    def test_update_incident_and_resolution(self):
        """Vérifie la mise à jour et l'horodatage de résolution."""
        inc = incident_service.create_incident({
            "title": "Crevaison pneu arrière",
            "incident_date": "2026-09-04",
            "severity": "mineur",
            "status": "signale",
        })

        updated = incident_service.update_incident(
            record_id=inc.id,
            form_data={
                "status": "resolu",
                "actual_cost": "180.00",
                "resolution_notes": "Pneu changé avec le train de secours.",
            }
        )
        self.assertEqual(updated.status, "resolu")
        self.assertIsNotNone(updated.resolved_at)
        self.assertEqual(float(updated.actual_cost), 180.0)

    def test_delete_incident_soft_delete(self):
        """Vérifie le soft-delete et le mécanisme de confirmation."""
        inc = incident_service.create_incident({
            "title": "Incident temporaire",
            "incident_date": "2026-09-04",
        })

        # Sans confirmation
        guard = incident_service.delete_incident(inc.id, confirm=False)
        self.assertEqual(guard.get("status"), "requires_confirmation")

        # Avec confirmation
        res = incident_service.delete_incident(inc.id, confirm=True)
        self.assertTrue(res.get("success"))

        # Vérifie qu'il n'apparaît plus dans la liste
        active_list = incident_service.list_incidents()
        self.assertEqual(len(active_list["incidents"]), 0)

        # Mais existe toujours en base avec deleted_at
        in_db = db.session.get(Incident, inc.id)
        self.assertIsNotNone(in_db.deleted_at)

    def test_generate_incident_pdf(self):
        """Vérifie la génération du rapport PDF officiel selon la DA Belle Vitesse."""
        inc = incident_service.create_incident({
            "title": "Dégât optique 24-70mm",
            "project_id": self.project.id,
            "vehicle_id": self.vehicle.id,
            "reported_by_id": self.user.id,
            "incident_date": "2026-09-04",
            "location": "Plateau A",
            "severity": "modere",
            "status": "en_expertise",
            "description": "Légère rayure sur lentille frontale.",
            "estimated_cost": "1200.00",
        })

        pdf_bytes, filename = incident_service.generate_incident_pdf(inc.id)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(len(pdf_bytes) > 0)
        self.assertTrue(filename.startswith("Belle_Vitesse_INCIDENT_"))
        self.assertTrue(filename.endswith(".pdf"))

    def test_mcp_incident_tools(self):
        """Vérifie l'exposition et le fonctionnement des outils MCP pour l'IA."""
        # 1. Create via MCP
        res_c = mcp_incidents.create_incident(
            title="Incident créé par MCP",
            incident_date="2026-09-04",
            severity="critique",
            project_id=self.project.id,
            vehicle_id=self.vehicle.id,
            description="Test par agent IA",
            estimated_cost=2500.0,
        )
        self.assertTrue(res_c.get("success"))
        inc_id = res_c.get("incident_id")

        # 2. List via MCP
        res_l = mcp_incidents.list_incidents(severity="critique")
        self.assertIsInstance(res_l.get("incidents"), list)
        self.assertGreaterEqual(len(res_l["incidents"]), 1)

        # 3. Get via MCP
        res_g = mcp_incidents.get_incident(inc_id)
        self.assertEqual(res_g.get("title"), "Incident créé par MCP")

        # 4. Update via MCP
        res_u = mcp_incidents.update_incident(
            incident_id=inc_id,
            status="cloture",
            resolution_notes="Résolu par IA",
            actual_cost=2400.0,
        )
        self.assertTrue(res_u.get("success"))
        self.assertEqual(res_u.get("status"), "cloture")

        # 5. Delete via MCP
        del_guard = mcp_incidents.delete_incident(inc_id, confirm=False)
        self.assertEqual(del_guard.get("status"), "requires_confirmation")

        del_res = mcp_incidents.delete_incident(inc_id, confirm=True)
        self.assertTrue(del_res.get("success"))

    def test_commercial_role_cannot_access_incidents(self):
        """Vérifie qu'un utilisateur avec le rôle Commercial ne peut pas accéder aux incidents."""
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 999
            sess["admin_user_role"] = "Commercial"

        # 1. Accès à la liste des incidents -> bloqué avec redirection vers le dashboard
        resp = client.get("/admin/incidents", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.headers.get("Location", "").endswith("/admin/dashboard"))

        # 2. Accès au formulaire de création -> bloqué
        resp_new = client.get("/admin/incidents/new", follow_redirects=False)
        self.assertEqual(resp_new.status_code, 302)
        self.assertTrue(resp_new.headers.get("Location", "").endswith("/admin/dashboard"))


if __name__ == "__main__":
    unittest.main()

