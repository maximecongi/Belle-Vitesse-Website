import unittest
from datetime import date, timedelta

from tests.base import BaseTestCase


class CmdKSearchApiTestCase(BaseTestCase):

    def _login_as_manager(self):
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_role"] = "manager"
            sess["admin_user_id"] = 1

    def test_cmdk_search_empty_suggestions_and_active_project(self):
        """Vérifie que sans terme de recherche, les projets en cours pointent vers le Project Hub."""
        self._login_as_manager()
        from models import db, Project, Production

        with self.app.app_context():
            prod = Production(name="Warner Test")
            db.session.add(prod)
            db.session.commit()

            today = date.today()
            proj = Project(
                project_id="BVPR-ACTIVE-001",
                name="Tournage Actif En Cours",
                production_id=prod.id,
                departure_date=today - timedelta(days=1),
                return_date=today + timedelta(days=2)
            )
            db.session.add(proj)
            db.session.commit()
            proj_id = proj.id

        resp = self.client.get("/admin/api/search")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("results", data)

        results = data["results"]
        # Vérifie qu'il y a des suggestions
        self.assertTrue(len(results) > 0)

        # Vérifie que le projet actif pointe directement vers le Project Hub
        hub_project = next((r for r in results if r.get("id") == f"proj-{proj_id}"), None)
        self.assertIsNotNone(hub_project, "Le projet actif doit apparaître dans les suggestions")
        self.assertEqual(hub_project["url"], f"/admin/projects/{proj_id}")
        self.assertEqual(hub_project["category"], "Projets en cours")
        self.assertEqual(hub_project["entity_type"], "project")

    def test_cmdk_search_project_points_to_hub(self):
        """Vérifie que la recherche d'un projet renvoie vers /admin/projects/<id> (Project Hub)."""
        self._login_as_manager()
        from models import db, Project, Production

        with self.app.app_context():
            prod = Production(name="Marvel Studio")
            db.session.add(prod)
            db.session.commit()

            proj = Project(
                project_id="BVPR-2026-999",
                name="Super Production Cinéma",
                production_id=prod.id,
                departure_date=date(2026, 11, 10),
                return_date=date(2026, 11, 20)
            )
            db.session.add(proj)
            db.session.commit()
            proj_id = proj.id

        resp = self.client.get("/admin/api/search?q=Super+Production")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        proj_result = next((r for r in data["results"] if r.get("id") == f"proj-{proj_id}"), None)
        self.assertIsNotNone(proj_result)
        self.assertEqual(proj_result["url"], f"/admin/projects/{proj_id}")
        self.assertEqual(proj_result["category"], "Projets")
        self.assertEqual(proj_result["entity_type"], "project")

    def test_cmdk_search_project_by_production_name(self):
        """Vérifie que chercher le nom de la société de production cliente remonte bien le projet rattaché."""
        self._login_as_manager()
        from models import db, Project, Production

        with self.app.app_context():
            prod = Production(name="Legendary Pictures")
            db.session.add(prod)
            db.session.commit()

            proj = Project(
                project_id="BVPR-2026-DUNE",
                name="Dune Partie 3",
                production_id=prod.id,
                departure_date=date(2026, 12, 1)
            )
            db.session.add(proj)
            db.session.commit()
            proj_id = proj.id

        # Recherche par "Legendary"
        resp = self.client.get("/admin/api/search?q=Legendary")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        proj_result = next((r for r in data["results"] if r.get("id") == f"proj-{proj_id}"), None)
        self.assertIsNotNone(proj_result, "Le projet doit être trouvé quand on cherche sa production")
        self.assertEqual(proj_result["url"], f"/admin/projects/{proj_id}")

    def test_cmdk_search_checkouts_and_checkins(self):
        """Vérifie l'indexation des contrôles BVO et BVI avec lien direct vers leur fiche détaillée."""
        self._login_as_manager()
        from models import db, Project, Production, CheckoutVehicle, CheckinVehicle

        with self.app.app_context():
            prod = Production(name="Production Vidéo")
            db.session.add(prod)
            db.session.commit()

            proj = Project(
                project_id="BVPR-INS-001",
                name="Tournage Pub Voiture",
                production_id=prod.id
            )
            db.session.add(proj)
            db.session.commit()

            co = CheckoutVehicle(
                inspection_number="BVO-2026-1234",
                project_id=proj.id,
                status="signed",
                inspection_date=date(2026, 11, 5)
            )
            ci = CheckinVehicle(
                inspection_number="BVI-2026-5678",
                project_id=proj.id,
                status="signed",
                inspection_date=date(2026, 11, 8)
            )
            db.session.add_all([co, ci])
            db.session.commit()
            co_id = co.id
            ci_id = ci.id

        # Recherche Check-out
        resp_co = self.client.get("/admin/api/search?q=BVO-2026")
        self.assertEqual(resp_co.status_code, 200)
        data_co = resp_co.get_json()
        co_res = next((r for r in data_co["results"] if r.get("id") == f"checkout-{co_id}"), None)
        self.assertIsNotNone(co_res)
        self.assertEqual(co_res["url"], f"/admin/checkouts/{co_id}")
        self.assertEqual(co_res["category"], "Contrôles Départs")
        self.assertEqual(co_res["entity_type"], "checkout")

        # Recherche Check-in
        resp_ci = self.client.get("/admin/api/search?q=BVI-2026")
        self.assertEqual(resp_ci.status_code, 200)
        data_ci = resp_ci.get_json()
        ci_res = next((r for r in data_ci["results"] if r.get("id") == f"checkin-{ci_id}"), None)
        self.assertIsNotNone(ci_res)
        self.assertEqual(ci_res["url"], f"/admin/checkins/{ci_id}")
        self.assertEqual(ci_res["category"], "Contrôles Retours")
        self.assertEqual(ci_res["entity_type"], "checkin")

    def test_cmdk_search_waiver_points_to_project_hub_section(self):
        """Vérifie que les décharges BVSR/BVTC/BVPA pointent vers le Project Hub avec l'ancre #waivers."""
        self._login_as_manager()
        from models import db, Project, Production, SafetyRulesWaiver

        with self.app.app_context():
            prod = Production(name="Production CGL")
            db.session.add(prod)
            db.session.commit()

            proj = Project(
                project_id="BVPR-WAI-001",
                name="Tournage Documentaire",
                production_id=prod.id
            )
            db.session.add(proj)
            db.session.commit()

            waiver = SafetyRulesWaiver(
                waiver_id="BVSR-2026-0088",
                project_id=proj.id,
                signer_first_name="Jean",
                signer_last_name="Dupont",
                status="signed"
            )
            db.session.add(waiver)
            db.session.commit()
            w_id = waiver.id
            proj_id = proj.id

        resp = self.client.get("/admin/api/search?q=BVSR-2026-0088")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        w_res = next((r for r in data["results"] if r.get("id") == f"waiver-{w_id}"), None)
        self.assertIsNotNone(w_res)
        self.assertEqual(w_res["url"], f"/admin/projects/{proj_id}#waivers")
        self.assertEqual(w_res["category"], "Décharges")
        self.assertEqual(w_res["entity_type"], "waiver")

    def test_cmdk_search_contacts_and_productions_direct_edit(self):
        """Vérifie que les contacts et productions pointent directement vers leur fiche d'édition."""
        self._login_as_manager()
        from models import db, Contact, Production

        with self.app.app_context():
            prod = Production(name="Studio Lumina Paris")
            db.session.add(prod)
            db.session.commit()

            contact = Contact(
                first_name="Sophie",
                last_name="Marceau",
                mail="sophie@cinema.fr",
                production_id=prod.id,
                job_title="Réalisatrice"
            )
            db.session.add(contact)
            db.session.commit()
            c_id = contact.id
            p_id = prod.id

        # Recherche Contact
        resp_c = self.client.get("/admin/api/search?q=Sophie+Marceau")
        self.assertEqual(resp_c.status_code, 200)
        data_c = resp_c.get_json()
        c_res = next((r for r in data_c["results"] if r.get("id") == f"contact-{c_id}"), None)
        self.assertIsNotNone(c_res)
        self.assertEqual(c_res["url"], f"/admin/contacts/{c_id}/edit")
        self.assertEqual(c_res["category"], "Contacts")

        # Recherche Production
        resp_p = self.client.get("/admin/api/search?q=Studio+Lumina")
        self.assertEqual(resp_p.status_code, 200)
        data_p = resp_p.get_json()
        p_res = next((r for r in data_p["results"] if r.get("id") == f"prod-{p_id}"), None)
        self.assertIsNotNone(p_res)
        self.assertEqual(p_res["url"], f"/admin/productions/{p_id}/edit")
        self.assertEqual(p_res["category"], "Productions")

    def test_cmdk_scope_filtering_prefix(self):
        """Vérifie que le préfixe de scope (ex: p:nom) isole les résultats."""
        self._login_as_manager()
        from models import db, Project, Production, Contact

        with self.app.app_context():
            prod = Production(name="Alpha Production")
            db.session.add(prod)
            db.session.commit()

            proj = Project(
                project_id="BVPR-ALPHA-01",
                name="Projet Alpha",
                production_id=prod.id
            )
            contact = Contact(
                first_name="Alpha",
                last_name="Man",
                mail="alphaman@test.fr"
            )
            db.session.add_all([proj, contact])
            db.session.commit()
            proj_id = proj.id

        # Recherche avec p:
        resp = self.client.get("/admin/api/search?q=p:Alpha")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        # Tous les résultats doivent être des projets
        for item in data["results"]:
            self.assertEqual(item["entity_type"], "project")

        proj_res = next((r for r in data["results"] if r.get("id") == f"proj-{proj_id}"), None)
        self.assertIsNotNone(proj_res)

    def test_cmdk_cumulative_scopes_filtering(self):
        """Vérifie que les scopes cumulatifs (ex: scope=project,inspection) filtrent fidèlement les entités."""
        self._login_as_manager()
        from models import db, Project, Production, Contact
        from models.inspection import CheckoutVehicle

        with self.app.app_context():
            prod = Production(name="Delta Films")
            db.session.add(prod)
            db.session.commit()

            proj = Project(
                project_id="BVPR-DELTA-01",
                name="Tournage Delta Force",
                production_id=prod.id
            )
            db.session.add(proj)
            db.session.commit()

            co = CheckoutVehicle(
                project_id=proj.id,
                inspection_number="BVO-DELTA-01",
                notes="Contrôle Delta départ"
            )
            contact = Contact(
                first_name="Delta",
                last_name="Agent",
                mail="delta@cinema.fr"
            )
            db.session.add_all([co, contact])
            db.session.commit()

            proj_id = proj.id
            co_id = co.id
            contact_id = contact.id

        # Recherche avec scope cumulatif : project + inspection
        resp = self.client.get("/admin/api/search?q=Delta&scope=project,inspection")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        self.assertIn("scope", data)
        self.assertEqual(data["scope"], "inspection,project")

        entity_types = {item["entity_type"] for item in data["results"]}
        # Doit contenir project et/ou checkout, mais JAMAIS contact
        self.assertIn("project", entity_types)
        self.assertIn("checkout", entity_types)
        self.assertNotIn("contact", entity_types)

        # Vérifie la présence effective du projet et du checkout
        self.assertTrue(any(r["id"] == f"proj-{proj_id}" for r in data["results"]))
        self.assertTrue(any(r["id"] == f"checkout-{co_id}" for r in data["results"]))
        # Vérifie l'absence formelle du contact
        self.assertFalse(any(r["id"] == f"contact-{contact_id}" for r in data["results"]))


if __name__ == "__main__":
    unittest.main()
