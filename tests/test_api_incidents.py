from datetime import date

from models import Incident, db
from tests.base import BaseTestCase
from utils.jwt_auth import generate_token


class ApiIncidentsTest(BaseTestCase):
    """Suite de tests unitaires pour le Blueprint REST v1 api_incidents_bp."""

    def setUp(self):
        super().setUp()
        self.user = self.create_user(
            firstname="Admin",
            lastname="Test",
            mail="admin.api@bellevitesse.com",
            role="Administrator",
        )
        self.token = generate_token(self.user)
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    def test_api_incidents_no_auth(self):
        """Vérifie le rejet 401 sans jeton d'authentification."""
        resp = self.client.get("/api/v1/incidents")
        self.assertEqual(resp.status_code, 401)

        resp = self.client.get("/api/v1/incidents/1")
        self.assertEqual(resp.status_code, 401)

        resp = self.client.get("/api/v1/incidents/stats")
        self.assertEqual(resp.status_code, 401)

    def test_api_incidents_empty_list(self):
        """Vérifie le retour 200 avec liste vide."""
        resp = self.client.get("/api/v1/incidents", headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("items", data)
        self.assertEqual(len(data["items"]), 0)
        self.assertEqual(data["total"], 0)

    def test_api_incidents_list_with_data(self):
        """Vérifie le listing et la pagination des incidents créés."""
        proj = self.create_project(name="Tournage Incident API")
        inc = Incident(
            incident_number="INC-2026-TEST01",
            project_id=proj.id,
            title="Pneu crevé",
            description="Crevaison lente sur roue arrière",
            category="vehicule",
            severity="modere",
            status="signale",
            incident_date=date(2026, 11, 4),
            reported_by_id=self.user.id,
        )
        db.session.add(inc)
        db.session.commit()

        # Liste brute
        resp = self.client.get("/api/v1/incidents", headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("items", data)
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["incident_number"], "INC-2026-TEST01")
        self.assertEqual(data["items"][0]["title"], "Pneu crevé")

        # Liste paginée
        resp_paginated = self.client.get("/api/v1/incidents?page=1&per_page=10", headers=self.auth_headers)
        self.assertEqual(resp_paginated.status_code, 200)
        p_data = resp_paginated.get_json()
        self.assertIn("items", p_data)
        self.assertEqual(p_data["total"], 1)
        self.assertEqual(len(p_data["items"]), 1)

    def test_api_incidents_detail_and_404(self):
        """Vérifie la route de consultation détaillée d'un incident et le 404."""
        proj = self.create_project(name="Tournage Detail API")
        inc = Incident(
            incident_number="INC-2026-DETAIL01",
            project_id=proj.id,
            title="Caméra déséquilibrée",
            description="Problème nacelle",
            category="materiel_camera",
            severity="critique",
            status="signale",
            incident_date=date(2026, 11, 4),
            reported_by_id=self.user.id,
        )
        db.session.add(inc)
        db.session.commit()

        resp = self.client.get(f"/api/v1/incidents/{inc.id}", headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        detail = resp.get_json()
        self.assertEqual(detail["incident_number"], "INC-2026-DETAIL01")
        self.assertEqual(detail["title"], "Caméra déséquilibrée")
        self.assertEqual(detail["severity"], "critique")

        # Non-trouvé
        resp_404 = self.client.get("/api/v1/incidents/99999", headers=self.auth_headers)
        self.assertEqual(resp_404.status_code, 404)
        self.assertIn("error", resp_404.get_json())

    def test_api_incidents_stats(self):
        """Vérifie le calcul et le retour des indicateurs statistiques (stats)."""
        proj = self.create_project(name="Tournage Stats API")
        inc1 = Incident(
            incident_number="INC-STAT-01",
            project_id=proj.id,
            title="Panne batterie",
            severity="mineur",
            status="signale",
            incident_date=date(2026, 11, 1),
            reported_by_id=self.user.id,
        )
        inc2 = Incident(
            incident_number="INC-STAT-02",
            project_id=proj.id,
            title="Choc pare-chocs",
            severity="critique",
            status="resolu",
            incident_date=date(2026, 11, 2),
            reported_by_id=self.user.id,
        )
        db.session.add_all([inc1, inc2])
        db.session.commit()

        resp = self.client.get("/api/v1/incidents/stats", headers=self.auth_headers)
        self.assertEqual(resp.status_code, 200)
        stats = resp.get_json()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["critical"], 1)
        self.assertEqual(stats["active"], 1)  # signale
        self.assertEqual(stats["resolved"], 1)
        self.assertEqual(stats["by_status"]["signale"], 1)
        self.assertEqual(stats["by_status"]["resolu"], 1)
        self.assertEqual(stats["by_severity"]["critique"], 1)
        self.assertEqual(stats["by_severity"]["mineur"], 1)
