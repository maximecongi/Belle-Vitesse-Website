"""
tests/test_risk_assessment.py — Tests unitaires et d'intégration pour le Risk Assessment (BVRA).
"""

import json
import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.base import BaseTestCase
from models import (
    Contact,
    Production,
    Project,
    RiskAssessmentWaiver,
    User,
    Vehicle,
    WaiverSignedDocument,
    WaiverToken,
    db,
)
from services.admin.risk_assessment_config import (
    DEFAULT_GENERAL_RISK_ASSESSMENT,
    DEFAULT_VEHICLE_RISK_ASSESSMENT,
    get_all_vehicle_risk_assessment_catalog,
    get_general_risk_assessment,
    get_merged_risk_assessment_for_project,
    get_risk_assessment_for_vehicles,
    save_general_risk_assessment,
    save_vehicle_risk_assessment,
)
from services.admin.waivers import (
    create_risk_assessment_waiver,
    delete_risk_assessment_waiver,
    generate_risk_assessment_waiver,
    list_risk_assessment_waivers,
    reset_risk_assessment_waiver,
    send_risk_assessment_waiver,
)


class RiskAssessmentComprehensiveTest(BaseTestCase):
    """Suite de tests complète pour l'Analyse des Risques (BVRA)."""

    def _create_mock_project(self):
        """Crée un projet avec production, contact et véhicules de test en mémoire."""
        user = User(
            firstname="Admin",
            lastname="BV",
            mail="admin@bellevitesse.com",
            role="administrator",
        )
        db.session.add(user)

        prod = Production(name="Studio Action SAS")
        db.session.add(prod)
        db.session.flush()

        contact = Contact(
            first_name="Jean",
            last_name="Régisseur",
            mail="regisseur@studioaction.com",
            phone="0611223344",
            job_title="Régisseur Général",
            production_id=prod.id,
        )
        db.session.add(contact)
        db.session.flush()

        v1 = Vehicle(
            id="rec_erover",
            fields={
                "Nom": "eRover 01 (Polaris Kinetic)",
                "name": "eRover 01 (Polaris Kinetic)",
                "slug": "erover",
                "type": "Travelling",
                "Statut": "Disponible",
            },
        )
        db.session.add(v1)

        project = Project(
            name="Tournage Cascade Haute Vitesse",
            production_id=prod.id,
            production_contact_id=contact.id,
            departure_date=date(2026, 6, 1),
            return_date=date(2026, 6, 5),
            date_mode="continuous",
            vehicles_to_check="rec_erover",
            shooting_locations=[
                {"name": "Circuit de Mortefontaine", "address": "Mortefontaine"}
            ],
        )
        db.session.add(project)
        db.session.commit()
        return project

    def test_risk_assessment_config_defaults(self):
        """Vérifie la dotation par défaut du catalogue de risques et les fonctions CRUD."""
        general = get_general_risk_assessment()
        self.assertGreaterEqual(len(general), 16)

        # Vérification des deux niveaux de risques
        major_risks = [r for r in general if r["level"] == "major"]
        standard_risks = [r for r in general if r["level"] == "standard"]
        self.assertGreater(len(major_risks), 0, "Doit comporter des risques majeurs")
        self.assertGreater(
            len(standard_risks), 0, "Doit comporter des risques standards"
        )

        # Vérification du bilinguisme
        first_risk = general[0]
        self.assertIn("title_fr", first_risk)
        self.assertIn("title_en", first_risk)
        self.assertIn("description_fr", first_risk)
        self.assertIn("description_en", first_risk)
        self.assertIn("recommendations_fr", first_risk)
        self.assertIn("recommendations_en", first_risk)

        # Vérification des véhicules spécifiques
        catalog = get_all_vehicle_risk_assessment_catalog()
        self.assertIn("erover", catalog)
        self.assertIn("erider", catalog)
        self.assertGreater(len(catalog["erover"]["risks"]), 0)

        # Test de sauvegarde
        ok, msg = save_general_risk_assessment(general)
        self.assertTrue(ok)

    def test_risk_assessment_waiver_lifecycle(self):
        """Teste le cycle de vie complet d'un RiskAssessmentWaiver (création, génération, reset, suppression)."""
        project = self._create_mock_project()

        # 1. Création
        ok, msg = create_risk_assessment_waiver(
            project_id=project.id,
            signer_role="key_grip",
            signer_first_name="Luc",
            signer_last_name="Machiniste",
            signer_email="luc.machiniste@prod.com",
            signer_company="Studio Action SAS",
        )
        self.assertTrue(ok, f"Échec de la création : {msg}")
        waiver = RiskAssessmentWaiver.query.filter_by(project_id=project.id).first()
        self.assertIsNotNone(waiver)
        waiver_id = waiver.waiver_id

        # Vérification du préfixe BVRA-
        self.assertTrue(
            waiver_id.startswith("BVRA-"),
            f"L'ID doit commencer par BVRA- (obtenu: {waiver_id})",
        )

        # Vérification de l'accès via le projet
        project.clear_waiver_cache()
        active_list = project.active_risk_assessments
        self.assertEqual(len(active_list), 1)
        self.assertEqual(active_list[0].waiver_id, waiver_id)
        self.assertEqual(active_list[0].signer_role_label, "Chef Machiniste")

        # 2. Génération / Envoi
        ok_send, send_msg = send_risk_assessment_waiver(waiver_id)
        self.assertTrue(ok_send, f"Échec de l'envoi : {send_msg}")

        # 3. Liste globale
        waivers = list_risk_assessment_waivers(project_id=project.id)
        self.assertEqual(len(waivers), 1)
        self.assertEqual(waivers[0]["waiver_id"], waiver_id)
        self.assertEqual(waivers[0]["signer_role_label"], "Chef Machiniste")

        # 4. Réinitialisation
        ok_reset, reset_msg = reset_risk_assessment_waiver(waiver_id)
        self.assertTrue(ok_reset, f"Échec du reset : {reset_msg}")

        # 5. Suppression
        ok_del, del_msg = delete_risk_assessment_waiver(waiver_id)
        self.assertTrue(ok_del, f"Échec de suppression : {del_msg}")
        project.clear_waiver_cache()
        self.assertEqual(len(project.active_risk_assessments), 0)

    def test_risk_assessment_signature_flow(self):
        """Teste le parcours public de signature électronique et le scellement cryptographique."""
        project = self._create_mock_project()

        ok, msg = create_risk_assessment_waiver(
            project_id=project.id,
            signer_role="location_manager",
            signer_first_name="Claire",
            signer_last_name="Régisseuse",
            signer_email="claire@prod.com",
        )
        self.assertTrue(ok, f"Échec création : {msg}")
        waiver = RiskAssessmentWaiver.query.filter_by(project_id=project.id).first()
        self.assertIsNotNone(waiver)

        # Envoi pour générer le token public
        ok_send, send_msg = send_risk_assessment_waiver(waiver.waiver_id)
        self.assertTrue(ok_send, f"Échec de l'envoi : {send_msg}")

        token_obj = WaiverToken.query.filter_by(waiver_id=waiver.waiver_id).first()
        self.assertIsNotNone(token_obj)

        # 1. GET page de signature
        res_get = self.client.get(f"/sign/risk-assessment/{token_obj.token}")
        self.assertEqual(res_get.status_code, 200)
        self.assertIn(b"Analyse des Risques (BVRA)", res_get.data)
        self.assertIn(b"RISQUE MAJEUR", res_get.data)
        self.assertIn(b"RISQUE", res_get.data)

        # 2. POST signature
        fake_png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        payload = {
            "signature": fake_png,
            "first_name": "Claire",
            "last_name": "Régisseuse",
            "email": "claire@prod.com",
            "phone": "0600000000",
            "role": "location_manager",
            "role_custom": "",
            "entity_type": "freelance",
            "ack_risk_assessment": True,
        }

        res_post = self.client.post(
            f"/sign/risk-assessment/{token_obj.token}",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(res_post.status_code, 200)
        res_json = res_post.get_json()
        self.assertTrue(res_json.get("success"))

        # Vérification de l'état en BDD
        db.session.refresh(waiver)
        self.assertEqual(waiver.status, "signed")
        self.assertIsNotNone(waiver.signed_at)
        self.assertIsNotNone(waiver.hash)

        # Vérification du document scellé
        signed_doc = WaiverSignedDocument.query.filter_by(
            waiver_id=waiver.waiver_id
        ).first()
        self.assertIsNotNone(signed_doc)
        self.assertEqual(signed_doc.hash, waiver.hash)

        # 3. Vérification publique de l'attestation scellée
        from utils.document_utils import generate_document_verification_token

        verify_token = generate_document_verification_token(
            "risk_assessment", waiver.waiver_id, 1, signed_doc.hash
        )
        verify_url = (
            f"/risk-assessment/verify/{waiver.waiver_id}?version=1&t={verify_token}"
        )
        res_verify = self.client.get(verify_url)
        self.assertEqual(res_verify.status_code, 200)
        self.assertIn(b"Analyse des Risques BVRA", res_verify.data)

    def test_risk_assessment_roles_labels(self):
        """Vérifie le mapping et libellé de tous les rôles acceptés pour le BVRA."""
        roles_expectations = {
            "production": "Directeur de production",
            "stunt_coordinator": "Coordinateur Cascades",
            "key_grip": "Chef Machiniste",
            "location_manager": "Régisseur Général",
            "pilot": "Pilote",
            "operator": "Cadreur",
            "first_ad": "1er Assistant Réalisateur",
        }

        w = RiskAssessmentWaiver()
        for role_key, expected_label in roles_expectations.items():
            w.signer_role = role_key
            self.assertEqual(w.signer_role_label, expected_label)

        # Test rôle personnalisé
        w.signer_role = "other"
        w.signer_role_custom = "Chef Électricien"
        self.assertEqual(w.signer_role_label, "Chef Électricien")

    def test_admin_fleet_risk_assessment_route(self):
        """Vérifie que la route admin du catalogue BVRA répond correctement et contient les contrôles d'édition."""
        self.login_as_admin()

        res = self.client.get("/admin/fleet/risk-assessment")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"d'analyse (BVRA)", res.data)
        self.assertIn(b"Risques G", res.data)
        self.assertIn(b"/admin/fleet/risk-assessment/edit/general", res.data)
        self.assertIn(b"/admin/fleet/risk-assessment/edit/vehicle/", res.data)

        # Vérifier que le bouton Matrice Flotte a bien été retiré de fleet_list
        res_fleet = self.client.get("/admin/fleet")
        if res_fleet.status_code == 200:
            self.assertNotIn(b"Matrice Flotte", res_fleet.data)
            self.assertIn(b"d'analyse (BVRA)", res_fleet.data)

    def test_admin_sidebar_contains_bvra_navigation(self):
        """Vérifie que l'entrée Analyses des risques (BVRA) est visible dans la barre latérale sous Documents."""
        self.login_as_admin()
        res = self.client.get("/admin/projects")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Analyses des risques (BVRA)", res.data)
        self.assertIn(b"/admin/risk-assessments", res.data)

    def test_admin_fleet_risk_assessment_save_post(self):
        """Vérifie la modification et persistance des risques généraux et par véhicule via POST."""
        self.login_as_admin()

        # 1. Sauvegarde des risques généraux
        updated_general = [
            {
                "id": "collision_cascade",
                "category_fr": "COLLISIONS",
                "category_en": "COLLISIONS",
                "title_fr": "Collision haute vitesse test",
                "title_en": "High speed collision test",
                "level": "major",
                "description_fr": "Risque majeur d'impact cinétique.",
                "description_en": "Major kinetic impact risk.",
                "recommendations_fr": [
                    "Ralentir immédiatement.",
                    "Porter un casque homologué.",
                ],
                "recommendations_en": [
                    "Slow down immediately.",
                    "Wear an approved helmet.",
                ],
            }
        ]

        res_post_gen = self.client.post(
            "/admin/fleet/risk-assessment",
            data={"action": "save_general", "risks_json": json.dumps(updated_general)},
            follow_redirects=True,
        )
        self.assertEqual(res_post_gen.status_code, 200)
        saved_gen = get_general_risk_assessment()
        self.assertEqual(len(saved_gen), 1)
        self.assertEqual(saved_gen[0]["title_fr"], "Collision haute vitesse test")
        self.assertEqual(saved_gen[0]["level"], "major")

        # 2. Sauvegarde des risques spécifiques véhicule
        updated_erover_risks = [
            {
                "id": "erover_propulsion_bug",
                "category_fr": "DÉFAILLANCE",
                "category_en": "FAILURE",
                "title_fr": "Coupure moteur eRover",
                "title_en": "eRover engine shutdown",
                "level": "standard",
                "description_fr": "Arrêt inopiné du système d'alimentation électrique.",
                "description_en": "Unexpected power shutdown.",
                "recommendations_fr": ["Contrôler le coupe-circuit."],
                "recommendations_en": ["Check kill-switch."],
            }
        ]

        res_post_veh = self.client.post(
            "/admin/fleet/risk-assessment",
            data={
                "action": "save_vehicle",
                "vehicle_key": "erover",
                "label": "eRover Polaris Custom",
                "risks_json": json.dumps(updated_erover_risks),
            },
            follow_redirects=True,
        )
        self.assertEqual(res_post_veh.status_code, 200)
        cat = get_all_vehicle_risk_assessment_catalog()
        self.assertIn("erover", cat)
        self.assertEqual(cat["erover"]["label"], "eRover Polaris Custom")
        self.assertEqual(len(cat["erover"]["risks"]), 1)
        self.assertEqual(cat["erover"]["risks"][0]["title_fr"], "Coupure moteur eRover")

    def test_risk_assessment_pdf_preview_and_render_contains_vehicle_risks(self):
        """Vérifie que l'aperçu PDF et les documents générés contiennent bien les risques spécifiques aux véhicules."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["_fresh"] = True

        # 1. Test de la route d'aperçu général (Mock)
        res_preview = self.client.get("/preview/pdf/risk-assessment")
        self.assertEqual(res_preview.status_code, 200)
        html_preview = res_preview.data.decode("utf-8")
        self.assertIn("RISQUES SPÉCIFIQUES", html_preview)
        self.assertIn("SPECIFIC RISKS", html_preview)
        self.assertIn("eRover (Polaris Kinetic)", html_preview)

        # 2. Test avec un projet réel et véhicule assigné
        project = self._create_mock_project()
        ok, msg = create_risk_assessment_waiver(
            project_id=project.id,
            signer_role="stunt_coordinator",
            signer_first_name="Alex",
            signer_last_name="Cascadeur",
            signer_email="alex@stunts.com",
        )
        self.assertTrue(ok, f"Échec création : {msg}")
        waiver = RiskAssessmentWaiver.query.filter_by(project_id=project.id).first()
        self.assertIsNotNone(waiver)

        # Vérification des détails véhicules et sections de risques
        details = waiver.vehicles_details
        self.assertGreaterEqual(len(details), 1)
        self.assertEqual(details[0]["slug"], "erover")

        v_sections = get_risk_assessment_for_vehicles(details)
        self.assertGreaterEqual(len(v_sections), 1)
        self.assertIn("eRover", v_sections[0]["label"])

        # Test de l'aperçu spécifique à ce waiver
        res_waiver_preview = self.client.get(
            f"/preview/pdf/risk-assessment?waiver_id={waiver.waiver_id}"
        )
        self.assertEqual(res_waiver_preview.status_code, 200)
        html_waiver = res_waiver_preview.data.decode("utf-8")
        self.assertIn("RISQUES SPÉCIFIQUES", html_waiver)
        self.assertIn("eRover", html_waiver)

    def test_project_vehicle_toggle_road_legal_ajax(self):
        """Vérifie l'API AJAX de basculement du statut Road Legal / Route fermée d'un véhicule."""
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_user_role"] = "administrateur"

        project = self._create_mock_project()

        # eRover est non-homologué route par défaut
        self.assertFalse(project.is_vehicle_road_legal("rec_erover"))

        # 1. Bascule vers homologué route
        resp = self.client.post(
            f"/admin/projects/{project.id}/vehicle/rec_erover/toggle-road-legal",
            json={},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["is_road_legal"])
        self.assertEqual(data["label_fr"], "Homologué route")

        db.session.refresh(project)
        self.assertTrue(project.is_vehicle_road_legal("rec_erover"))

        # 2. Re-bascule vers non-homologué (route fermée uniquement)
        resp2 = self.client.post(
            f"/admin/projects/{project.id}/vehicle/rec_erover/toggle-road-legal",
            json={},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.get_json()
        self.assertFalse(data2["is_road_legal"])
        self.assertEqual(data2["label_fr"], "Route fermée")

        db.session.refresh(project)
        self.assertFalse(project.is_vehicle_road_legal("rec_erover"))

    def test_risk_assessment_road_legal_callouts_render_and_condition(self):
        """Vérifie l'intégration et le conditionnement dynamique des 3 blocs d'avertissement dans le PDF BVRA."""
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_user_role"] = "administrateur"

        project = self._create_mock_project()
        ok, msg = create_risk_assessment_waiver(
            project_id=project.id,
            signer_role="stunt_coordinator",
            signer_first_name="Max",
            signer_last_name="Cascade",
            signer_email="max@stunts.com",
        )
        self.assertTrue(ok)
        waiver = RiskAssessmentWaiver.query.filter_by(project_id=project.id).first()

        # 1. Avec eRover non-homologué : les 3 blocs doivent être présents
        res1 = self.client.get(
            f"/preview/pdf/risk-assessment?waiver_id={waiver.waiver_id}"
        )
        self.assertEqual(res1.status_code, 200)
        html1 = res1.data.decode("utf-8")

        # Bloc 1 (FR & EN)
        self.assertIn("Utilisation sur route fermée uniquement", html1)
        self.assertIn("IMPÉRATIF SÉCURITÉ", html1)
        self.assertIn("Use on closed roads only", html1)
        self.assertIn("SAFETY MANDATE", html1)
        self.assertIn("L'eRover 01 (Polaris Kinetic) roule uniquement sur une route fermée", html1)

        # Bloc 2 & 3
        self.assertIn("À SIGNER", html1)
        self.assertIn("Règles de sécurité", html1)
        self.assertIn("INFORMATION", html1)
        self.assertIn("Le manuel officiel du véhicule est disponible à bord", html1)

        # 2. Quand le véhicule est basculé en "Homologué route", le bloc 1 doit disparaître
        project.set_vehicle_road_legal("rec_erover", True)
        db.session.commit()

        res2 = self.client.get(
            f"/preview/pdf/risk-assessment?waiver_id={waiver.waiver_id}"
        )
        self.assertEqual(res2.status_code, 200)
        html2 = res2.data.decode("utf-8")

        self.assertNotIn("Utilisation sur route fermée uniquement", html2)
        self.assertNotIn("Use on closed roads only", html2)
        # Mais les blocs 2 et 3 doivent rester affichés
        self.assertIn("À SIGNER", html2)
        self.assertIn("Règles de sécurité", html2)
        self.assertIn("INFORMATION", html2)
        self.assertIn("Le manuel officiel du véhicule est disponible à bord", html2)

    def test_risk_assessment_preview_mock_and_query_param(self):
        """Vérifie le comportement de la prévisualisation directe avec mock ou simulation ?road_legal=1."""
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_user_role"] = "administrateur"

        # 1. Preview direct sans argument : le mock a des véhicules non-road legal par défaut (eRover, eRider)
        res_default = self.client.get("/preview/pdf/risk-assessment")
        self.assertEqual(res_default.status_code, 200)
        html_default = res_default.data.decode("utf-8")
        self.assertIn("Utilisation sur route fermée uniquement", html_default)
        self.assertIn(
            "L'eRover (Polaris Kinetic) et l'eRider (Stark Varg) roulent uniquement sur une route fermée",
            html_default,
        )

        # 2. Preview avec ?road_legal=1 : le bloc fermé ne doit PAS s'afficher
        res_road_legal = self.client.get("/preview/pdf/risk-assessment?road_legal=1")
        self.assertEqual(res_road_legal.status_code, 200)
        html_road_legal = res_road_legal.data.decode("utf-8")
        self.assertNotIn("Utilisation sur route fermée uniquement", html_road_legal)
        self.assertNotIn("Use on closed roads only", html_road_legal)
        # Mais les blocs 2 & 3 sont toujours présents
        self.assertIn("À SIGNER", html_road_legal)
        self.assertIn("Règles de sécurité", html_road_legal)
        self.assertIn("INFORMATION", html_road_legal)

        # 3. Preview avec ?project_id=... pour un projet dont tous les véhicules sont homologués route
        project = self._create_mock_project()
        project.set_vehicle_road_legal("rec_erover", True)
        db.session.commit()

        res_proj = self.client.get(f"/preview/pdf/risk-assessment?project_id={project.id}")
        self.assertEqual(res_proj.status_code, 200)
        html_proj = res_proj.data.decode("utf-8")
        self.assertNotIn("Utilisation sur route fermée uniquement", html_proj)

    def test_catalog_overview_and_edit_routes(self):
        """Vérifie l'affichage de la vue d'ensemble du catalogue et des pages d'édition dédiées."""
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_user_role"] = "administrator"

        # 1. Vue d'ensemble du catalogue
        res_cat = self.client.get("/admin/fleet/risk-assessment")
        self.assertEqual(res_cat.status_code, 200)
        html_cat = res_cat.data.decode("utf-8")
        self.assertIn("Modèles d'analyse (BVRA)", html_cat)
        self.assertIn("Risques Généraux", html_cat)
        self.assertIn("Risques Spécifiques par Véhicules", html_cat)
        self.assertIn("Rechercher un risque...", html_cat)
        self.assertIn("Tout déplier", html_cat)

        # 2. Page d'édition des risques généraux
        res_edit_gen = self.client.get("/admin/fleet/risk-assessment/edit/general")
        self.assertEqual(res_edit_gen.status_code, 200)
        html_edit_gen = res_edit_gen.data.decode("utf-8")
        self.assertIn("Modifier les Risques Généraux", html_edit_gen)
        self.assertIn("Retour au catalogue", html_edit_gen)
        self.assertIn("Niveau de risque", html_edit_gen)
        self.assertIn("Catégorie", html_edit_gen)
        self.assertIn("Aperçu PDF", html_edit_gen)

        # 3. Page d'édition des risques spécifiques d'un véhicule (eRover)
        res_edit_v = self.client.get("/admin/fleet/risk-assessment/edit/vehicle/erover")
        self.assertEqual(res_edit_v.status_code, 200)
        html_edit_v = res_edit_v.data.decode("utf-8")
        self.assertIn("Modifier les Risques Spécifiques", html_edit_v)
        self.assertIn("eRover", html_edit_v)

    def test_ajax_api_endpoints_risk_assessment(self):
        """Vérifie les endpoints AJAX save-risk, delete-risk et reorder-risks."""
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_user_role"] = "administrator"

        test_risk_id = "test_risk_ajax_123"
        new_risk_payload = {
            "scope": "general",
            "risk": {
                "id": test_risk_id,
                "category_fr": "ZONE DE TOURNAGE",
                "category_en": "SHOOTING AREA",
                "level": "major",
                "title_fr": "Risque Test Unitaire AJAX",
                "title_en": "Unit Test AJAX Risk",
                "description_fr": "Description test en français.",
                "description_en": "Test description in English.",
                "recommendations_fr": ["Consigne test 1"],
                "recommendations_en": ["Test instruction 1"],
            },
        }

        # 1. Sauvegarde d'un risque
        res_save = self.client.post(
            "/admin/fleet/risk-assessment/api/save-risk",
            data=json.dumps(new_risk_payload),
            content_type="application/json",
        )
        self.assertEqual(res_save.status_code, 200)
        data_save = json.loads(res_save.data.decode("utf-8"))
        self.assertEqual(data_save.get("status"), "success")
        self.assertEqual(data_save["risk"]["title_fr"], "Risque Test Unitaire AJAX")

        # 2. Réorganisation
        res_reorder = self.client.post(
            "/admin/fleet/risk-assessment/api/reorder-risks",
            data=json.dumps({"scope": "general", "risk_ids": [test_risk_id]}),
            content_type="application/json",
        )
        self.assertEqual(res_reorder.status_code, 200)
        data_reorder = json.loads(res_reorder.data.decode("utf-8"))
        self.assertEqual(data_reorder.get("status"), "success")

        # 3. Suppression du risque créé
        res_delete = self.client.post(
            "/admin/fleet/risk-assessment/api/delete-risk",
            data=json.dumps({"scope": "general", "risk_id": test_risk_id}),
            content_type="application/json",
        )
        self.assertEqual(res_delete.status_code, 200)
        data_delete = json.loads(res_delete.data.decode("utf-8"))
        self.assertEqual(data_delete.get("status"), "success")

    def test_save_single_risk_requires_title_and_aligns_translations(self):
        """Titre FR obligatoire ; recommandations EN alignées sur FR, lignes vides ignorées."""
        from services.admin.risk_assessment_config import save_single_risk

        ok, msg, _, _ = save_single_risk("general", {"id": "x", "title_fr": "  "})
        self.assertFalse(ok)
        self.assertIn("obligatoire", msg)

        ok, _, saved, _ = save_single_risk("general", {
            "id": "align_test",
            "title_fr": "Alignement",
            "level": "bogus",
            "recommendations_fr": ["A", "", "C"],
            "recommendations_en": ["A en"],
            "_translation_status": {"is_complete": False},
        })
        self.assertTrue(ok)
        self.assertEqual(saved["level"], "standard")
        self.assertEqual(saved["recommendations_fr"], ["A", "C"])
        self.assertEqual(saved["recommendations_en"], ["A en", ""])
        stored = next(r for r in get_general_risk_assessment() if r["id"] == "align_test")
        self.assertNotIn("_translation_status", stored)

    def test_edit_pages_do_not_mutate_default_constants(self):
        """Les vues ne doivent pas injecter _translation_status dans les constantes par défaut."""
        self.login_as_admin()
        self.client.get("/admin/fleet/risk-assessment")
        self.client.get("/admin/fleet/risk-assessment/edit/general")
        for r in DEFAULT_GENERAL_RISK_ASSESSMENT:
            self.assertNotIn("_translation_status", r)

    def test_deleting_last_vehicle_risk_keeps_empty_list(self):
        """Supprimer tous les risques d'un véhicule ne doit pas restaurer la dotation par défaut."""
        from services.admin.risk_assessment_config import delete_single_risk

        key = next(iter(DEFAULT_VEHICLE_RISK_ASSESSMENT))
        risk_ids = [r["id"] for r in get_all_vehicle_risk_assessment_catalog()[key]["risks"]]
        self.assertTrue(risk_ids)
        for rid in risk_ids:
            ok, _, _ = delete_single_risk("vehicle", rid, vehicle_key=key)
            self.assertTrue(ok)
        self.assertEqual(get_all_vehicle_risk_assessment_catalog()[key]["risks"], [])

    def test_delete_unknown_risk_returns_error(self):
        """La suppression d'un identifiant inexistant est signalée."""
        from services.admin.risk_assessment_config import delete_single_risk

        ok, msg, _ = delete_single_risk("general", "does_not_exist")
        self.assertFalse(ok)
        self.assertIn("introuvable", msg)


    def test_shared_categories_span_general_and_vehicles(self):
        """Les catégories sont communes : une catégorie créée sur un véhicule est proposée partout."""
        from services.admin.risk_assessment_config import (
            get_shared_risk_categories,
            save_single_risk,
        )

        key = next(iter(DEFAULT_VEHICLE_RISK_ASSESSMENT))
        ok, _, _, _ = save_single_risk("vehicle", {
            "id": "shared_cat_test",
            "title_fr": "Risque catégorie partagée",
            "category_fr": "CATÉGORIE PARTAGÉE",
            "category_en": "SHARED CATEGORY",
        }, vehicle_key=key)
        self.assertTrue(ok)

        cats = get_shared_risk_categories()
        by_fr = {c["fr"]: c["en"] for c in cats}
        self.assertEqual(by_fr.get("CATÉGORIE PARTAGÉE"), "SHARED CATEGORY")
        self.assertEqual(by_fr.get("ZONE DE TOURNAGE"), "SHOOTING AREA")
        self.assertEqual(len(by_fr), len(cats))  # pas de doublon

        self.login_as_admin()
        html = self.client.get("/admin/fleet/risk-assessment/edit/general").data.decode("utf-8")
        self.assertIn('id="bvra-categories-data"', html)
        self.assertIn("SHARED CATEGORY", html)

if __name__ == "__main__":
    unittest.main()
