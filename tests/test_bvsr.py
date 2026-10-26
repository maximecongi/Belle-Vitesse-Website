import os
import sys
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Isolation stricte en mémoire
os.environ["FLASK_ENV"] = "testing"
os.environ["TESTING"] = "True"
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
os.environ["WTF_CSRF_ENABLED"] = "False"
os.environ["USE_SSH_TUNNEL"] = "false"

# Mock weasyprint pour éviter les dépendances système GTK/Pango en test
mock_weasyprint = MagicMock()
mock_weasyprint.HTML = MagicMock()
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint

from app import create_app
from models import (
    Contact,
    Production,
    Project,
    SafetyRulesWaiver,
    User,
    Vehicle,
    WaiverToken,
    db,
)
from services.admin.safety_rules_config import (
    DEFAULT_VEHICLE_SAFETY_RULES,
    get_all_vehicle_safety_rules_catalog,
    get_safety_rules_for_vehicles,
    save_vehicle_safety_rules,
)
from services.admin.waivers import (
    countersign_safety_rules,
    create_safety_rules_waiver,
    delete_safety_rules_waiver,
    generate_safety_rules_waiver,
    list_safety_rules_waivers,
    reset_safety_rules_waiver,
    send_safety_rules_waiver,
)


class BvsrComprehensiveTest(unittest.TestCase):
    """Suite de tests unitaires et d'intégration pour les Règles de Sécurité Universelles (BVSR)."""

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

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _create_mock_project(self):
        """Crée un jeu complet de données de test en mémoire (isolé)."""
        user = User(
            firstname="Admin",
            lastname="BV",
            mail="admin@bellevitesse.com",
            role="administrator"
        )
        db.session.add(user)

        prod = Production(name="Studio Tournage SAS")
        db.session.add(prod)
        db.session.flush()

        contact = Contact(
            first_name="Marc",
            last_name="Directeur",
            mail="marc@prod.com",
            phone="0611223344",
            job_title="Directeur de Production",
            production_id=prod.id
        )
        db.session.add(contact)
        db.session.flush()

        v1 = Vehicle(id="rec_v1", fields={"Nom": "eRover 01", "Type": "erover"})
        v2 = Vehicle(id="rec_v2", fields={"Nom": "eRider Dual", "Type": "erider"})
        db.session.add_all([v1, v2])
        db.session.flush()

        proj = Project(
            name="Publicité Commerciale Haute Vitesse",
            production_id=prod.id,
            production_contact_id=contact.id,
            departure_date=date(2026, 8, 1),
            shoot_start_date=date(2026, 8, 2),
            shoot_end_date=date(2026, 8, 4),
            return_date=date(2026, 8, 5),
            vehicles_to_check=f"{v1.id}, {v2.id}"
        )
        db.session.add(proj)
        db.session.commit()
        return proj, prod, contact, [v1, v2]

    def test_01_catalog_and_fleet_rules(self):
        """Vérifie le chargement et la mise à jour dynamique des règles véhicules dans la configuration flotte."""
        with self.app.app_context():
            catalog = get_all_vehicle_safety_rules_catalog()
            self.assertIn("erover", catalog)
            self.assertIn("erider", catalog)
            self.assertIn("ecar", catalog)

            # Test de correspondance avec les véhicules d'un projet
            vehicle_list = [{"name": "eRover 01", "slug": "erover"}, {"name": "eRider Dual", "slug": "erider"}]
            rules = get_safety_rules_for_vehicles(vehicle_list)
            self.assertEqual(len(rules), 2)
            rule_labels = [r["label"] for r in rules]
            self.assertTrue(any("eRover" in lbl for lbl in rule_labels))
            self.assertTrue(any("eRider" in lbl for lbl in rule_labels))

            # Test d'ajout/modification d'une famille personnalisée
            save_vehicle_safety_rules(
                vehicle_key="buggy_electrique",
                label="Buggy Électrique Cascades",
                keywords=["buggy", "custom"],
                rules_fr=["Casque intégral obligatoire", "Arceau 4 points"],
                rules_en=["Full face helmet required", "4-point roll cage"]
            )
            updated_cat = get_all_vehicle_safety_rules_catalog()
            self.assertIn("buggy_electrique", updated_cat)
            self.assertEqual(updated_cat["buggy_electrique"]["label"], "Buggy Électrique Cascades")

    def test_02_create_multiple_bvsr_waivers_per_project(self):
        """Vérifie la création de multiples engagements BVSR individuels pour différents rôles sur le même projet."""
        with self.app.app_context():
            proj, _, _, _ = self._create_mock_project()

            # Signataire 1 : Pilote sans référents par défaut
            ok1, msg1 = create_safety_rules_waiver(
                project_id=proj.id,
                signer_role="pilot",
                signer_first_name="Alex",
                signer_last_name="Pilote",
                signer_email="alex.pilote@gmail.com",
                signer_phone="0600000001",
                signer_company="Freelance Stunt",
                safety_technicians=""  # Pas de référents par défaut
            )
            self.assertTrue(ok1, f"Échec création BVSR 1: {msg1}")

            # Signataire 2 : 1er Assistant Réalisateur avec référents spécifiés
            ok2, msg2 = create_safety_rules_waiver(
                project_id=proj.id,
                signer_role="first_ad",
                signer_first_name="Claire",
                signer_last_name="Ad",
                signer_email="claire@cinema.fr",
                signer_phone="0600000002",
                signer_company="Studio Tournage SAS",
                safety_technicians="Maxime Perrard, Ewen Gicquel"
            )
            self.assertTrue(ok2, f"Échec création BVSR 2: {msg2}")

            # Signataire 3 : Cadreur
            ok3, msg3 = create_safety_rules_waiver(
                project_id=proj.id,
                signer_role="operator",
                signer_first_name="Sam",
                signer_last_name="Camera",
                signer_email="sam@camera.fr",
                signer_phone="0600000003"
            )
            self.assertTrue(ok3, f"Échec création BVSR 3: {msg3}")

            # Vérification des waivers en base
            waivers = SafetyRulesWaiver.query.filter_by(project_id=proj.id).all()
            self.assertEqual(len(waivers), 3)

            for w in waivers:
                self.assertTrue(w.waiver_id.startswith("BVSR-"))
                self.assertEqual(w.waiver_type, "safety_rules")
                self.assertEqual(w.status, "to_send")

            # Vérification du comportement sans référents par défaut
            w_pilot = [w for w in waivers if w.signer_role == "pilot"][0]
            self.assertIsNone(w_pilot.safety_technicians)

            # Vérification du waiver avec référents explicites
            w_ad = [w for w in waivers if w.signer_role == "first_ad"][0]
            self.assertEqual(w_ad.safety_technicians, "Maxime Perrard, Ewen Gicquel")

    def test_03_public_signing_flow_no_friction(self):
        """Vérifie le portail public de signature BVSR : AUCUN numéro de permis ni upload requis."""
        with self.app.app_context():
            proj, _, _, _ = self._create_mock_project()

            create_safety_rules_waiver(
                project_id=proj.id,
                signer_role="pilot",
                signer_first_name="Romain",
                signer_last_name="Racer",
                signer_email="romain@racer.com"
            )
            waiver = SafetyRulesWaiver.query.filter_by(project_id=proj.id).first()

            # Envoi du waiver pour générer le token public
            ok_send, _ = send_safety_rules_waiver(waiver.waiver_id)
            self.assertTrue(ok_send)

            self.assertEqual(waiver.status, "to_sign")
            token = WaiverToken.query.filter_by(waiver_id=waiver.waiver_id).first()
            self.assertIsNotNone(token)

            # GET portail de signature
            res_get = self.client.get(f"/sign/safety-rules/{token.token}")
            self.assertEqual(res_get.status_code, 200)
            self.assertIn(b"BVSR-", res_get.data)

            # POST signature : AUCUN numéro de permis ni upload requis !
            post_data = {
                "first_name": "Romain",
                "last_name": "Racer",
                "email": "romain@racer.com",
                "phone": "+33611223344",
                "company": "Cascade Prod",
                "ack_rules": "1",
                "ack_authority": "1",
                "signature_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            }


            res_post = self.client.post(
                f"/sign/safety-rules/{token.token}",
                data=post_data
            )

            self.assertEqual(res_post.status_code, 200)
            json_res = res_post.get_json()
            self.assertTrue(json_res.get("success"))

            # Vérification du statut signé
            db.session.refresh(waiver)
            self.assertEqual(waiver.status, "signed")
            self.assertIsNotNone(waiver.signed_at)
            self.assertEqual(waiver.signer_name, "Romain Racer")

    def test_04_admin_countersign_safety_rules(self):
        """Vérifie la contresignature Belle Vitesse d'un engagement BVSR signé."""
        with self.app.app_context():
            proj, _, _, _ = self._create_mock_project()
            create_safety_rules_waiver(project_id=proj.id, signer_role="pilot", signer_first_name="Test")
            waiver = SafetyRulesWaiver.query.filter_by(project_id=proj.id).first()
            waiver.status = "signed"
            db.session.commit()

            ok, msg = countersign_safety_rules(
                waiver.waiver_id,
                signature_data="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                signer_name="Maxime"
            )

            self.assertTrue(ok)
            db.session.refresh(waiver)
            self.assertEqual(waiver.status, "signed")
            self.assertIsNotNone(waiver.bv_signed_at)
            self.assertEqual(waiver.bv_signer_name, "Maxime")

    def test_05_reset_and_delete_safety_rules(self):
        """Vérifie la réinitialisation et la suppression sécurisée d'un engagement BVSR."""
        with self.app.app_context():
            proj, _, _, _ = self._create_mock_project()
            create_safety_rules_waiver(project_id=proj.id, signer_role="operator")
            waiver = SafetyRulesWaiver.query.filter_by(project_id=proj.id).first()
            waiver_id = waiver.waiver_id

            # Reset
            ok_rst, _ = reset_safety_rules_waiver(waiver_id)
            self.assertTrue(ok_rst)
            db.session.refresh(waiver)
            self.assertEqual(waiver.status, "to_generate")

            # Delete (soft-delete)
            ok_del, _ = delete_safety_rules_waiver(waiver_id)
            self.assertTrue(ok_del)
            db.session.refresh(waiver)
            self.assertIsNotNone(waiver.deleted_at)
            active_list = list_safety_rules_waivers(project_id=proj.id)
            self.assertEqual(len(active_list), 0)

    def test_06_admin_safety_rules_list_and_route(self):
        """Vérifie le listing des règles de sécurité et la route GET /admin/safety-rules."""
        with self.app.app_context():
            proj, _, _, _ = self._create_mock_project()
            create_safety_rules_waiver(project_id=proj.id, signer_role="pilot", signer_first_name="Jean", signer_last_name="Pilote")
            create_safety_rules_waiver(project_id=proj.id, signer_role="first_ad", signer_first_name="Claire", signer_last_name="Ad")

            # Vérifie le listing de service
            items = list_safety_rules_waivers()
            self.assertGreaterEqual(len(items), 2)
            self.assertIn("id", items[0])
            self.assertIn("signer_name", items[0])
            self.assertIn("signer_role_label", items[0])

            # Vérifie l'accès à la route administrative GET /admin/safety-rules
            admin_user = User.query.filter_by(role="administrator").first()
            with self.client.session_transaction() as sess:
                sess["admin_authenticated"] = True
                sess["admin_user_id"] = admin_user.id
                sess["admin_user_role"] = "administrator"

            response = self.client.get("/admin/safety-rules")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"R\xc3\xa8gles de S\xc3\xa9curit\xc3\xa9", response.data)
            self.assertIn(b"Jean Pilote", response.data)

    def test_07_admin_safety_rules_catalog_ui_and_save(self):
        """Vérifie l'affichage du catalogue BVSR avec véhicules réels, l'absence du bouton ajouter et l'enregistrement par vehicle_id."""
        with self.app.app_context():
            user = User(
                firstname="Admin",
                lastname="BV",
                mail="admin2@bellevitesse.com",
                role="administrator"
            )
            db.session.add(user)
            db.session.commit()

            with self.client.session_transaction() as sess:
                sess["admin_authenticated"] = True
                sess["admin_user_id"] = user.id
                sess["admin_user_role"] = "administrator"

            # 1. Vérification GET du catalogue (pas de bouton ajouter, pas de slug/keywords)
            res_get = self.client.get("/admin/fleet/safety-rules")
            self.assertEqual(res_get.status_code, 200)
            html = res_get.data.decode("utf-8")
            self.assertIn("bvsr-catalog-card", html)
            self.assertIn("bvsr-preview-box", html)
            self.assertIn("bvsr-preview-list", html)
            self.assertIn("bvsr-modal-container", html)
            self.assertIn("bvsr-rules-container", html)
            self.assertIn("modal_vehicle_id", html)
            # Vérifie la suppression du bouton Ajouter et des champs slug/keywords
            self.assertNotIn("btn-open-new-rule-modal", html)
            self.assertNotIn("modal_vehicle_key", html)
            self.assertNotIn("modal_keywords", html)

            # 2. Vérification POST avec saisie par puces dynamiques (vehicle_id, rules_fr[] et rules_en[])
            post_data = {
                "vehicle_id": "test_buggy",
                "label": "Buggy Tout-Terrain 4x4",
                "rules_fr": ["Casque homologué obligatoire en roulage", "Harnais 4 points bouclé"],
                "rules_en": ["Approved helmet mandatory while driving", "4-point harness fastened"]
            }
            res_post = self.client.post("/admin/fleet/safety-rules", data=post_data, follow_redirects=True)
            self.assertEqual(res_post.status_code, 200)
            post_html = res_post.data.decode("utf-8")
            self.assertIn("Buggy Tout-Terrain 4x4", post_html)
            self.assertIn("Casque homologué obligatoire en roulage", post_html)
            self.assertIn("Approved helmet mandatory while driving", post_html)

            # Vérification dans le catalogue mémoire
            catalog = get_all_vehicle_safety_rules_catalog()
            self.assertIn("test_buggy", catalog)
            self.assertEqual(len(catalog["test_buggy"]["rules_fr"]), 2)
            self.assertEqual(catalog["test_buggy"]["rules_fr"][0], "Casque homologué obligatoire en roulage")


if __name__ == '__main__':
    unittest.main()

