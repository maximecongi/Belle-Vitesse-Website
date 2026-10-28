"""
Tests unitaires pour le nouveau système unifié de Contrats CGL (BVRA) et Règles de Sécurité Universelles (BVSR).
Remplace intégralement les anciens tests de double décharge pilote/production.
"""

from datetime import date, datetime, timezone
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock weasyprint si non disponible dans l'environnement de test
mock_weasyprint = MagicMock()
mock_weasyprint.HTML = MagicMock()
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint

from app import create_app
from models import (
    CglWaiver,
    Contact,
    Production,
    Project,
    SafetyRulesWaiver,
    User,
    Vehicle,
    Waiver,
    WaiverSignedDocument,
    WaiverToken,
    db,
)
from services.admin.waivers import (
    _format_project_shooting_dates,
    create_cgl,
    create_safety_rules_waiver,
    delete_cgl,
    delete_cgl_internal,
    delete_safety_rules_waiver,
    delete_safety_rules_waiver_internal,
    delete_waiver,
    delete_waiver_internal,
    format_waiver_shooting_dates,
    generate_cgl,
    generate_safety_rules_waiver,
    generate_waiver,
    list_cgl,
    list_safety_rules_waivers,
    reset_cgl,
    reset_safety_rules_waiver,
    reset_waiver,
    send_cgl,
    send_safety_rules_waiver,
    send_waiver,
)
from services.common.signatures import finalize_signed_document
from utils.document_utils import compute_hmac_seal


class WaiversCglAndSafetyRulesTest(unittest.TestCase):
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

    def _create_mock_data(self):
        user = User(firstname="Admin", lastname="BV", mail="admin@bellevitesse.com", role="administrator")
        db.session.add(user)

        prod = Production(name="Studio Horizon", mail="contact@studiohorizon.com")
        db.session.add(prod)
        db.session.flush()

        proj = Project(
            name="Tournage Pub Alpes",
            project_id="BVPR-ALPES01",
            production_id=prod.id,
            departure_date=date(2026, 6, 2),
            shoot_start_date=date(2026, 6, 3),
            shoot_end_date=date(2026, 6, 5),
            return_date=date(2026, 6, 6),
            vehicles_to_check="1",
        )
        db.session.add(proj)
        db.session.commit()

        return user, proj

    def test_create_and_list_cgl_and_safety_rules(self):
        """Vérifie la création et le listage respectif des contrats CGL et engagements BVSR."""
        with self.app.app_context():
            user, proj = self._create_mock_data()

            # Création CGL
            s_cgl, msg_cgl = create_cgl(proj.id)
            self.assertTrue(s_cgl, msg_cgl)

            # Création BVSR (invitation manuelle avec rôle)
            s_sr, msg_sr = create_safety_rules_waiver(
                project_id=proj.id,
                signer_first_name="Luc",
                signer_last_name="Pilote",
                signer_email="luc.pilote@example.com",
                signer_role="pilot",
            )
            self.assertTrue(s_sr, msg_sr)

            # Vérification list_cgl
            cgl_items = list_cgl()
            self.assertEqual(len(cgl_items), 1)
            self.assertEqual(cgl_items[0]["project_name"], "Tournage Pub Alpes")
            self.assertTrue(cgl_items[0]["waiver_id"].startswith("BVRA"))
            self.assertEqual(cgl_items[0]["raw_status"], "to_send")

            # Vérification list_safety_rules_waivers
            sr_items = list_safety_rules_waivers()
            self.assertEqual(len(sr_items), 1)
            self.assertEqual(sr_items[0]["project_name"], "Tournage Pub Alpes")
            self.assertTrue(sr_items[0]["waiver_id"].startswith("BVSR"))
            self.assertEqual(sr_items[0]["signer_role"], "pilot")
            self.assertEqual(sr_items[0]["raw_status"], "to_send")

    def test_soft_delete_and_recreate_cgl_and_bvsr(self):
        """Vérifie le soft-delete et la recréation sans conflit d'unicité."""
        with self.app.app_context():
            user, proj = self._create_mock_data()

            create_cgl(proj.id)
            create_safety_rules_waiver(
                proj.id,
                signer_first_name="Marc",
                signer_last_name="Cadreur",
                signer_email="marc@example.com",
                signer_role="technician",
            )

            cgl = CglWaiver.query.filter_by(project_id=proj.id).first()
            sr = SafetyRulesWaiver.query.filter_by(project_id=proj.id).first()

            # Suppression unitaire
            del_cgl, _ = delete_cgl(cgl.waiver_id)
            self.assertTrue(del_cgl)
            del_sr, _ = delete_safety_rules_waiver(sr.waiver_id)
            self.assertTrue(del_sr)

            # Ne doivent plus apparaître dans les listes actives
            self.assertEqual(len(list_cgl()), 0)
            self.assertEqual(len(list_safety_rules_waivers()), 0)

            # Recréation pour le même projet
            re_cgl, _ = create_cgl(proj.id)
            self.assertTrue(re_cgl)
            re_sr, _ = create_safety_rules_waiver(
                proj.id,
                signer_first_name="Marc",
                signer_last_name="Cadreur",
                signer_email="marc@example.com",
                signer_role="technician",
            )
            self.assertTrue(re_sr)

            self.assertEqual(len(list_cgl()), 1)
            self.assertEqual(len(list_safety_rules_waivers()), 1)

    def test_automatic_cgl_creation_on_project_create(self):
        """Vérifie que le CGL est créé automatiquement si une production est associée, mais PAS les règles de sécurité."""
        from services.admin.projects import create_project

        with self.app.app_context():
            prod = Production(name="Prod Automatique")
            db.session.add(prod)
            db.session.flush()

            class MockForm(dict):
                def getlist(self, name):
                    return []

            form = MockForm({
                "name": "Tournage Automatique CGL",
                "production_id": str(prod.id),
                "departure_date": date(2026, 7, 1),
                "shoot_start": date(2026, 7, 2),
                "shoot_end": date(2026, 7, 4),
                "return_date": date(2026, 7, 5),
            })
            ok = create_project(form)
            self.assertTrue(ok)

            new_proj = Project.query.filter_by(name="Tournage Automatique CGL").first()
            self.assertIsNotNone(new_proj)

            # CGL automatique présent
            self.assertIsNotNone(new_proj.active_cgl)
            self.assertEqual(new_proj.active_cgl.waiver_type, "cgl")
            self.assertTrue(new_proj.active_cgl.waiver_id.startswith("BVRA"))
            self.assertEqual(new_proj.active_cgl.status, "to_send")

            # Aucune règle de sécurité créée automatiquement (invitation manuelle uniquement)
            self.assertEqual(len(new_proj.active_safety_rules), 0)

    def test_verify_cgl_route(self):
        """Vérifie l'accès à la route publique de vérification scellée pour un contrat CGL."""
        with self.app.app_context():
            user, proj = self._create_mock_data()
            create_cgl(proj.id)
            cgl = CglWaiver.query.filter_by(project_id=proj.id).first()
            cgl.status = "signed"
            cgl.production_name = "Studio Horizon"
            cgl.production_representative = "Claire Directrice"

            seal_args = ["Studio Horizon", "Claire Directrice"]
            sig_data = "signatures/waivers/mock_cgl.png"
            iso_signed = "2026-06-02T10:00:00"
            h = compute_hmac_seal("BVRA", cgl.waiver_id, *seal_args, sig_data, iso_signed)

            signed_doc = WaiverSignedDocument(
                waiver_id=cgl.waiver_id,
                hash=h,
                pdf_file_hash="mock-pdf-hash",
                data_snapshot={
                    "_seal_production_name": "Studio Horizon",
                    "_seal_representative": "Claire Directrice",
                    "production": "Studio Horizon",
                    "project": "Tournage Pub Alpes",
                    "production_representative": "Claire Directrice",
                    "_seal_signed_at": iso_signed,
                },
                signature=sig_data,
                pdf_url=f"/cgl/document/{cgl.waiver_id}.pdf",
            )
            db.session.add(signed_doc)
            db.session.commit()

            # Route publique canonique : /cgl/verify/<waiver_id>
            from utils.document_utils import generate_document_verification_token
            token = generate_document_verification_token("cgl", cgl.waiver_id, 1, signed_doc.hash)
            verify_url = f"/cgl/verify/{cgl.waiver_id}?version=1&t={token}"
            resp = self.client.get(verify_url)
            self.assertEqual(resp.status_code, 200)
            self.assertIn("CGL Scellées".encode("utf-8"), resp.data)
            self.assertIn(cgl.waiver_id.encode("utf-8"), resp.data)

            # Inexistant -> 404
            resp_404 = self.client.get("/cgl/verify/BVRA-INEXISTANT")
            self.assertEqual(resp_404.status_code, 404)

    def test_verify_safety_rules_route(self):
        """Vérifie l'accès à la route publique de vérification scellée pour les règles de sécurité (BVSR)."""
        with self.app.app_context():
            user, proj = self._create_mock_data()
            create_safety_rules_waiver(
                proj.id,
                signer_first_name="Jean",
                signer_last_name="Pilote",
                signer_email="jean@example.com",
                signer_role="pilot",
            )
            sr = SafetyRulesWaiver.query.filter_by(project_id=proj.id).first()
            sr.status = "signed"

            full_name = "Jean Pilote"
            role_label = sr.signer_role_label
            seal_args = [full_name, role_label]
            sig_data = "signatures/waivers/mock_sr.png"
            iso_signed = "2026-06-02T11:00:00"
            h = compute_hmac_seal("BVSR", sr.waiver_id, *seal_args, sig_data, iso_signed)

            signed_doc = WaiverSignedDocument(
                waiver_id=sr.waiver_id,
                hash=h,
                pdf_file_hash="mock-pdf-hash",
                data_snapshot={
                    "_seal_signer_name": full_name,
                    "_seal_signer_role": role_label,
                    "signer_name": full_name,
                    "signer_role": "pilot",
                    "project": "Tournage Pub Alpes",
                    "_seal_signed_at": iso_signed,
                },
                signature=sig_data,
                pdf_url=f"/safety-rules/document/{sr.waiver_id}.pdf",
            )
            db.session.add(signed_doc)
            db.session.commit()

            # Route publique canonique : /safety-rules/verify/<waiver_id>
            from utils.document_utils import generate_document_verification_token
            token = generate_document_verification_token("safety_rules", sr.waiver_id, 1, signed_doc.hash)
            verify_url = f"/safety-rules/verify/{sr.waiver_id}?version=1&t={token}"
            resp = self.client.get(verify_url)
            self.assertEqual(resp.status_code, 200)
            self.assertIn("Règles BVSR Scellées".encode("utf-8"), resp.data)
            self.assertIn(sr.waiver_id.encode("utf-8"), resp.data)

            # Inexistant -> 404
            resp_404 = self.client.get("/safety-rules/verify/BVSR-NONEXISTENT")
            self.assertEqual(resp_404.status_code, 404)

    def test_finalize_signed_document_cgl_and_safety_rules(self):
        """Vérifie le cycle complet de signature électronique et scellement HMAC pour CGL et BVSR."""
        SAMPLE_BASE64_PNG = (
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        with self.app.app_context(), self.app.test_request_context("/"):
            user, proj = self._create_mock_data()

            # 1. Finalisation CGL
            create_cgl(proj.id)
            cgl = CglWaiver.query.filter_by(project_id=proj.id).first()
            cgl.production_representative = "Claire Directrice"
            db.session.commit()

            res_cgl = finalize_signed_document(
                mode="cgl",
                record_id=cgl.id,
                signature_data=SAMPLE_BASE64_PNG,
                signed_ip="127.0.0.1",
            )
            self.assertTrue(res_cgl)
            self.assertEqual(res_cgl["document_id"], cgl.waiver_id)
            self.assertEqual(cgl.status, "signed")

            # 2. Finalisation Règles de sécurité (BVSR)
            create_safety_rules_waiver(
                proj.id,
                signer_first_name="Luc",
                signer_last_name="Pilote",
                signer_email="luc@example.com",
                signer_role="pilot",
            )
            sr = SafetyRulesWaiver.query.filter_by(project_id=proj.id).first()

            res_sr = finalize_signed_document(
                mode="safety_rules",
                record_id=sr.id,
                signature_data=SAMPLE_BASE64_PNG,
                signed_ip="127.0.0.1",
            )
            self.assertTrue(res_sr)
            self.assertEqual(res_sr["document_id"], sr.waiver_id)
            self.assertEqual(sr.status, "signed")

    def test_one_click_send_routes(self):
        """Vérifie l'envoi en 1 clic par POST avec redirection return_to pour CGL et Règles de Sécurité."""
        with self.app.app_context():
            user, proj = self._create_mock_data()

            prod_c = Contact(first_name="Marie", last_name="Prod", mail="prod@example.com")
            db.session.add(prod_c)
            db.session.flush()
            proj.production_contact_id = prod_c.id
            db.session.commit()

            create_cgl(proj.id)
            create_safety_rules_waiver(
                proj.id,
                signer_first_name="Marc",
                signer_last_name="Opérateur",
                signer_email="marc@example.com",
                signer_role="technician",
            )

            cgl = CglWaiver.query.filter_by(project_id=proj.id).first()
            sr = SafetyRulesWaiver.query.filter_by(project_id=proj.id).first()

            with self.client.session_transaction() as sess:
                sess["admin_authenticated"] = True
                sess["admin_user_id"] = user.id
                sess["admin_user_role"] = "administrator"

            with patch("utils.mailer.send_cgl_invitation_email", return_value=True), \
                 patch("utils.mailer.send_safety_rules_invitation_email", return_value=True):

                target_url = f"/admin/projects/{proj.id}"

                # Envoi CGL
                resp_cgl = self.client.post(
                    f"/admin/cgl/{cgl.waiver_id}/send",
                    data={"return_to": target_url},
                    follow_redirects=False,
                )
                self.assertEqual(resp_cgl.status_code, 302)
                self.assertEqual(resp_cgl.headers["Location"], target_url)
                db.session.refresh(cgl)
                self.assertEqual(cgl.status, "to_sign")

                # Envoi BVSR
                resp_sr = self.client.post(
                    f"/admin/safety-rules/{sr.waiver_id}/send",
                    data={"return_to": target_url},
                    follow_redirects=False,
                )
                self.assertEqual(resp_sr.status_code, 302)
                self.assertEqual(resp_sr.headers["Location"], target_url)
                db.session.refresh(sr)
                self.assertEqual(sr.status, "to_sign")

    def test_polymorphism_and_unified_waiver_model(self):
        """Vérifie le Single Table Inheritance sur le modèle Waiver unifié."""
        with self.app.app_context():
            user, proj = self._create_mock_data()

            s1, _ = create_cgl(proj.id)
            self.assertTrue(s1)
            s2, _ = create_safety_rules_waiver(proj.id)
            self.assertTrue(s2)

            all_waivers = Waiver.query.filter_by(project_id=proj.id).all()
            self.assertEqual(len(all_waivers), 2)

            cgl_w = next(w for w in all_waivers if w.waiver_type == "cgl")
            self.assertIsInstance(cgl_w, CglWaiver)

            sr_w = next(w for w in all_waivers if w.waiver_type == "safety_rules")
            self.assertIsInstance(sr_w, SafetyRulesWaiver)

            # Reset générique
            sr_w.signature_data = "signed-mock"
            db.session.commit()
            r_ok, _ = reset_waiver(sr_w.waiver_id)
            self.assertTrue(r_ok)
            db.session.refresh(sr_w)
            self.assertIsNone(sr_w.signature_data)

            # Suppression unitaire générique
            del_ok, _ = delete_waiver(sr_w.waiver_id)
            self.assertTrue(del_ok)
            db.session.refresh(sr_w)
            self.assertIsNotNone(sr_w.deleted_at)

            # Suppression interne globale du projet
            delete_waiver_internal(proj.id)
            for w in Waiver.query.filter_by(project_id=proj.id).all():
                self.assertIsNotNone(w.deleted_at)

    def test_waiver_deletion_dispatches_kdrive_cleanups(self):
        """Vérifie que la suppression d'un CGL signé ou non signé et le reset déclenchent dispatch_delete_document."""
        with self.app.app_context():
            user, proj = self._create_mock_data()

            s1, _ = create_cgl(proj.id)
            self.assertTrue(s1)
            cgl = CglWaiver.query.filter_by(project_id=proj.id).first()

            with patch("services.common.kdrive.dispatch_delete_document") as mock_dispatch:
                # 1. Reset d'un CGL non signé
                r_ok, _ = reset_waiver(cgl.waiver_id)
                self.assertTrue(r_ok)
                mock_dispatch.assert_called_with("cgl", cgl.waiver_id)

                # 2. Suppression d'un CGL non signé
                mock_dispatch.reset_mock()
                d_ok, _ = delete_waiver(cgl.waiver_id)
                self.assertTrue(d_ok)
                mock_dispatch.assert_called_with("cgl", cgl.waiver_id)

            # 3. Suppression d'un CGL signé (soft-delete avec preuve)
            s2, _ = create_cgl(proj.id)
            self.assertTrue(s2)
            cgl2 = CglWaiver.query.filter_by(project_id=proj.id, deleted_at=None).first()
            cgl2.status = "signed"
            signed_doc = WaiverSignedDocument(
                waiver_id=cgl2.waiver_id,
                version=1,
                hash="mock-hash-123",
                pdf_file_hash="mock-pdf-hash-123",
                data_snapshot={"signer_name": "Jean Dupont"},
            )
            db.session.add(signed_doc)
            db.session.commit()

            with patch("services.common.kdrive.dispatch_delete_document") as mock_dispatch_signed:
                d_ok2, _ = delete_waiver(cgl2.waiver_id)
                self.assertTrue(d_ok2)
                # Même pour un document signé juridiquement scellé en base, son dossier kDrive est bien supprimé
                mock_dispatch_signed.assert_called_once_with("cgl", cgl2.waiver_id)
                db.session.refresh(cgl2)
                self.assertIsNotNone(cgl2.deleted_at)

    def test_shooting_dates_formatting_and_properties(self):
        """Vérifie que les dates de tournage sont correctement synthétisées et exposées."""
        with self.app.app_context():
            proj_continuous = Project(
                name="Tournage Continu",
                date_mode="continuous",
                shoot_start_date=date(2026, 10, 1),
                shoot_end_date=date(2026, 10, 5),
            )
            self.assertEqual(_format_project_shooting_dates(proj_continuous, default_sep=" au "), "01/10/2026 au 05/10/2026")

            raw_dates = "12/10/2026, 13/10/2026, 14/10/2026, 17/11/2026"
            self.assertEqual(format_waiver_shooting_dates(raw_dates, default_sep=" au "), "12/10/2026 au 17/11/2026")

            cgl = CglWaiver(
                project_name="Projet Test Dates",
                production_name="Studio Test",
                shooting_dates=raw_dates,
                project_id=1,
            )
            self.assertEqual(cgl.display_shooting_dates, "12/10/2026 au 17/11/2026")
            self.assertEqual(cgl.display_project_name, "Projet Test Dates")
            self.assertEqual(cgl.display_production_name, "Studio Test")

    def test_admin_cgl_delete_route_with_return_to(self):
        """Vérifie la suppression d'une CGL par route admin POST avec redirection return_to."""
        with self.app.app_context():
            user, proj = self._create_mock_data()
            create_cgl(proj.id)
            cgl = CglWaiver.query.filter_by(project_id=proj.id).first()
            self.assertIsNotNone(cgl)

            with self.client.session_transaction() as sess:
                sess["admin_authenticated"] = True
                sess["admin_user_id"] = user.id
                sess["admin_user_role"] = "administrator"

            target_url = f"/admin/projects/{proj.id}"
            resp = self.client.post(
                f"/admin/cgl/{cgl.waiver_id}/delete",
                data={"return_to": target_url},
                follow_redirects=False,
            )
            self.assertEqual(resp.status_code, 302)
            self.assertEqual(resp.headers["Location"], target_url)

            db.session.refresh(cgl)
            self.assertIsNotNone(cgl.deleted_at)


if __name__ == "__main__":
    unittest.main()
