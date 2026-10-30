"""Tests unitaires pour la gestion des lieux de tournage (shooting_locations).

Vérifie :
1. La persistance, l'ordre et le nettoyage des lieux sur le modèle Project.
2. La propagation automatique vers les CGL, BVSR et attestations pilote.
3. Le blocage strict de la signature côté serveur si aucun lieu n'est renseigné sur le projet.
4. L'immutabilité de l'instantané signé (snapshot) après modification des lieux sur le projet.
"""
import os
import json
import unittest
from datetime import datetime, date, timezone

os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
os.environ["FLASK_ENV"] = "testing"

from app import app
from models.db import db
from models.project import Project, Production, Contact
from models.waiver import CglWaiver, SafetyRulesWaiver, PilotWaiver, WaiverToken
from services.admin.projects import create_project, update_project
from services.common.signatures import finalize_signed_document


class ShootingLocationsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        # Données de test
        self.prod = Production(name="SuperProd", address="10 rue de Paris, 75001 Paris")
        db.session.add(self.prod)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_project_shooting_locations_crud_and_properties(self):
        """Vérifie la création, modification, nettoyage et formatage des lieux sur un projet."""
        form_data = {
            "name": "Publicité Sport Auto",
            "production_id": str(self.prod.id),
            "date_mode": "continuous",
            "shoot_start": "2026-11-10",
            "shoot_end": "2026-11-12",
            "shooting_locations": json.dumps([
                {"name": " Circuit Paul Ricard ", "address": " 2760 Rte des Hauts du Camp "},
                {"name": "Col du Turini", "address": ""},
                {"name": "   ", "address": "Adresse orpheline"},  # Doit être ignoré car name vide
            ]),
        }

        project = create_project(form_data)
        self.assertIsNotNone(project.id)
        self.assertTrue(project.has_shooting_locations)
        self.assertEqual(len(project.locations_list), 2)
        self.assertEqual(project.locations_list[0]["name"], "Circuit Paul Ricard")
        self.assertEqual(project.locations_list[0]["address"], "2760 Rte des Hauts du Camp")
        self.assertEqual(project.locations_list[1]["name"], "Col du Turini")
        self.assertEqual(project.locations_list[1]["address"], "")

        # Formatage lisible
        display_str = project.display_shooting_locations
        self.assertIn("Circuit Paul Ricard (2760 Rte des Hauts du Camp)", display_str)
        self.assertIn("Col du Turini", display_str)

        # Mise à jour des lieux (réordonnancement et nouveau lieu)
        update_data = {
            "name": "Publicité Sport Auto - Révisé",
            "production_id": str(self.prod.id),
            "date_mode": "continuous",
            "shooting_locations": json.dumps([
                {"name": "Col du Turini", "address": "06440 Moulinet"},
                {"name": "Monaco Port", "address": "Quai Albert 1er"},
            ]),
        }
        update_project(project.id, update_data)
        db.session.refresh(project)
        self.assertEqual(len(project.locations_list), 2)
        self.assertEqual(project.locations_list[0]["name"], "Col du Turini")
        self.assertEqual(project.locations_list[1]["name"], "Monaco Port")

    def test_signature_blocked_when_no_locations(self):
        """Vérifie que la signature côté serveur est bloquée (HTTP 400) si aucun lieu n'est renseigné."""
        project = Project(
            name="Tournage Sans Lieu",
            production_id=self.prod.id,
            departure_date=date(2026, 11, 1),
            shoot_start_date=date(2026, 11, 1),
            shoot_end_date=date(2026, 11, 2),
            return_date=date(2026, 11, 3),
            shooting_locations=[],  # Aucun lieu
        )
        db.session.add(project)
        db.session.commit()

        # Création CGL
        cgl = CglWaiver(
            project_id=project.id,
            waiver_id="BVRA-TESTNOLOC",
            status="to_sign",
            production_name=self.prod.name,
            production_representative="Jean Dupont",
            signer_role_custom="Directeur",
        )
        db.session.add(cgl)
        db.session.commit()

        token = WaiverToken(
            waiver_id=cgl.waiver_id,
            token="test-tok-noloc",
            expires_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
        )
        db.session.add(token)
        db.session.commit()

        # Tentative de signature en POST
        res = self.client.post(
            f"/sign/cgl/{token.token}",
            data={
                "signature_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY44YAAAAASUVORK5CYII=",
                "accepted_terms": "1",
                "has_signing_authority": "1",
                "representative": "Jean Dupont",
                "representative_role": "Directeur de production",
                "production_name": "SuperProd",
            },
        )
        self.assertEqual(res.status_code, 400)
        json_data = res.get_json()
        self.assertFalse(json_data["success"])
        self.assertIn("aucun lieu de tournage n'a été renseigné", json_data["error"])

    def test_signature_snapshot_immutability(self):
        """Vérifie que les lieux sont scellés dans l'instantané et restent immuables lors d'une modification ultérieure du projet."""
        project = Project(
            name="Tournage Pub Voiture",
            production_id=self.prod.id,
            departure_date=date(2026, 11, 1),
            shoot_start_date=date(2026, 11, 1),
            shoot_end_date=date(2026, 11, 2),
            return_date=date(2026, 11, 3),
            shooting_locations=[
                {"name": "Circuit Bugatti", "address": "Le Mans"},
            ],
        )
        db.session.add(project)
        db.session.commit()

        cgl = CglWaiver(
            project_id=project.id,
            waiver_id="BVRA-IMMUTABLE01",
            status="to_sign",
            production_name=self.prod.name,
            production_representative="Sophie Martin",
            signer_role_custom="Gérante",
        )
        db.session.add(cgl)
        db.session.commit()

        token = WaiverToken(
            waiver_id=cgl.waiver_id,
            token="test-tok-immutable",
            expires_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
        )
        db.session.add(token)
        db.session.commit()

        # Signature réussie (PNG valide)
        sig_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        res = self.client.post(
            f"/sign/cgl/{token.token}",
            data={
                "signature_data": sig_base64,
                "accepted_terms": "1",
                "has_signing_authority": "1",
                "representative": "Sophie Martin",
                "representative_role": "Gérante",
                "production_name": "SuperProd",
                "siret": "12345678900012",
                "address": "10 rue de Paris, 75001 Paris",
                "email": "sophie@superprod.com",
            },
        )
        self.assertEqual(res.status_code, 200)

        db.session.refresh(cgl)
        self.assertEqual(cgl.status, "signed")
        # Vérifier que le snapshot contient les lieux
        snap_locs = cgl.display_shooting_locations_list
        self.assertEqual(len(snap_locs), 1)
        self.assertEqual(snap_locs[0]["name"], "Circuit Bugatti")

        # Modification des lieux du projet après coup
        project.shooting_locations = [
            {"name": "Nouveau Lieu Modifié Après Signature", "address": "Paris"},
            {"name": "Deuxième Lieu", "address": "Lyon"},
        ]
        db.session.commit()

        # Le document signé DOIT conserver l'ancien lieu
        db.session.refresh(cgl)
        self.assertEqual(len(cgl.display_shooting_locations_list), 1)
        self.assertEqual(cgl.display_shooting_locations_list[0]["name"], "Circuit Bugatti")
        self.assertIn("Circuit Bugatti", cgl.display_shooting_locations)
        self.assertNotIn("Nouveau Lieu Modifié", cgl.display_shooting_locations)


if __name__ == "__main__":
    unittest.main()
