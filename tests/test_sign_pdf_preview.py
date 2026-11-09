"""
Aperçu PDF live des formulaires publics de signature (CGL, BVSR, BVPA, BVRA).

Vérifie que :
- la route POST /sign/<type>/<token>/preview rend le vrai template PDF avec les valeurs saisies,
  surlignées et liées au champ du formulaire (https://preview.invalid/field/<nom>) ;
- rien n'est persisté (waiver inchangé, aucun SignatureEvent) ;
- le rendu final (hors aperçu) ne contient aucune trace de surlignage.
"""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.base import BaseTestCase
from tests import test_cgl as _cgl_suite
from models import CglWaiver, SignatureEvent, WaiverToken, db
from services.admin.waivers import create_cgl, get_or_create_waiver_signing_url

FIELD_URL = "https://preview.invalid/field/"


class SignPdfPreviewTest(BaseTestCase):
    """Réutilise le jeu de données projet / production de la suite CGL."""

    _create_mock_project = _cgl_suite.CglComprehensiveTest._create_mock_project

    def _cgl_token(self):
        with self.app.app_context():
            proj, _, _ = self._create_mock_project()
            create_cgl(proj.id)
            cgl = CglWaiver.query.filter_by(project_id=proj.id).first()
            _, sign_url = get_or_create_waiver_signing_url(cgl.waiver_id, waiver_type="cgl")
            return sign_url.split("/sign/cgl/")[-1], cgl.waiver_id

    def _preview(self, token, data):
        captured = {}

        def fake_render(html_content, **kwargs):
            captured["html"] = html_content
            captured["kwargs"] = kwargs
            return b"%PDF-1.4 preview"

        with patch("utils.document_utils.render_pdf_from_template", side_effect=fake_render):
            resp = self.client.post(f"/sign/cgl/{token}/preview", data=data)
        return resp, captured

    def test_preview_renders_highlighted_fields_without_persisting(self):
        token, waiver_id = self._cgl_token()
        with self.app.app_context():
            events_before = SignatureEvent.query.count()

        resp, captured = self._preview(token, {
            "production_name": "Lumière Films SAS",
            "representative": "Alice Martin",
            "representative_role": "Gérante",
            "siret": "",
            "legal_form": "SAS",
            "legal_country": "France",
            "order_ref": "BVBC-42",
            "city": "Lyon",
        })

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "application/pdf")
        self.assertEqual(resp.headers.get("Cache-Control"), "no-store")
        self.assertFalse(captured["kwargs"]["compress"])

        html = captured["html"]
        # Valeurs saisies surlignées et reliées à leur champ
        self.assertIn(f'href="{FIELD_URL}production_name">Lumière Films SAS</a>', html)
        self.assertIn(f'href="{FIELD_URL}representative">Alice Martin</a>', html)
        self.assertIn(f'href="{FIELD_URL}order_ref">BVBC-42</a>', html)
        self.assertIn(f'href="{FIELD_URL}city">Lyon</a>', html)
        # Champ vide : placeholder cliquable
        self.assertIn("pf-mark--empty", html)
        self.assertIn(f'href="{FIELD_URL}siret">[SIRET]</a>', html)
        self.assertIn("APERÇU — NON SIGNÉ", html)
        self.assertIn("css/pdf/form-preview.css", html)

        # Rien n'a été persisté
        with self.app.app_context():
            cgl = CglWaiver.query.filter_by(waiver_id=waiver_id).first()
            self.assertNotEqual(cgl.production_name, "Lumière Films SAS")
            self.assertEqual(cgl.display_order_ref, "")
            self.assertIn(cgl.status, ("to_sign", "to_send"))
            self.assertEqual(SignatureEvent.query.count(), events_before)

    def test_identical_preview_is_served_from_cache(self):
        token, _ = self._cgl_token()
        data = {"production_name": "Cache Films SAS"}
        with patch("utils.document_utils.render_pdf_from_template", return_value=b"%PDF-1.4 cache") as render:
            first = self.client.post(f"/sign/cgl/{token}/preview", data=data)
            second = self.client.post(f"/sign/cgl/{token}/preview", data=data)
            third = self.client.post(f"/sign/cgl/{token}/preview", data={"production_name": "Autre SAS"})
        self.assertEqual(first.headers.get("X-Preview-Cache"), "miss")
        self.assertEqual(second.headers.get("X-Preview-Cache"), "hit")
        self.assertEqual(second.get_data(), b"%PDF-1.4 cache")
        self.assertEqual(third.headers.get("X-Preview-Cache"), "miss")
        self.assertEqual(render.call_count, 2)

    def test_busy_server_returns_429_with_retry_after(self):
        import routes.public.waivers as public_waivers
        token, _ = self._cgl_token()
        slots = public_waivers._PREVIEW_MAX_CONCURRENT
        for _ in range(slots):
            self.assertTrue(public_waivers._preview_render_slots.acquire(blocking=False))
        try:
            with patch.object(public_waivers, "_PREVIEW_ACQUIRE_TIMEOUT_S", 0.01), \
                    patch("utils.document_utils.render_pdf_from_template") as render:
                resp = self.client.post(f"/sign/cgl/{token}/preview", data={"production_name": "Occupé SAS"})
            self.assertEqual(resp.status_code, 429)
            self.assertEqual(resp.headers.get("Retry-After"), str(public_waivers._PREVIEW_RETRY_AFTER_S))
            render.assert_not_called()
        finally:
            for _ in range(slots):
                public_waivers._preview_render_slots.release()

    def test_rate_limit_key_is_per_token(self):
        import routes.public.waivers as public_waivers
        with self.app.test_request_context("/sign/cgl/abc/preview", method="POST"):
            from flask import request
            request.view_args = {"token": "abc"}
            self.assertEqual(public_waivers._preview_rate_key(), "sign-preview:abc")

    def test_preview_token_errors(self):
        resp = self.client.post("/sign/cgl/inexistant/preview", data={})
        self.assertEqual(resp.status_code, 404)

        token, waiver_id = self._cgl_token()
        with self.app.app_context():
            cgl = CglWaiver.query.filter_by(waiver_id=waiver_id).first()
            cgl.status = "signed"
            db.session.commit()
        resp = self.client.post(f"/sign/cgl/{token}/preview", data={})
        self.assertEqual(resp.status_code, 409)

    def test_sign_page_embeds_preview_container(self):
        token, _ = self._cgl_token()
        html = self.client.get(f"/sign/cgl/{token}").get_data(as_text=True)
        self.assertIn('id="cgl-pdf-preview"', html)
        self.assertIn(f"/sign/cgl/{token}/preview", html)
        self.assertIn('data-pf-field="production_name"', html)
        self.assertIn("pdf.js/3.11.174/pdf.min.js", html)

    def test_final_render_has_no_preview_markup(self):
        """Le PDF scellé (sans form_preview) ne doit contenir aucun surlignage ni lien d'aperçu."""
        token, waiver_id = self._cgl_token()
        with self.app.app_context(), self.app.test_request_context("/"):
            from flask import render_template
            from services.common.signatures import build_document_render_context
            cgl = CglWaiver.query.filter_by(waiver_id=waiver_id).first()
            cgl.production_name = "Lumière Films SAS"
            cgl.sign_data = {"order_ref": "BVBC-42"}
            html = render_template("pdf/cgl.html", **build_document_render_context("cgl", cgl))
            db.session.rollback()
        self.assertNotIn("pf-mark", html)
        self.assertNotIn("preview.invalid", html)
        self.assertNotIn("APERÇU — NON SIGNÉ", html)
        self.assertNotIn("form-preview.css", html)
        # Correctifs : raison sociale saisie et réf. commande présentes dans le PDF final
        self.assertIn("Lumière Films SAS", html)
        self.assertIn("BVBC-42", html)

    def test_other_document_types_preview(self):
        """BVSR / BVPA / BVRA : nom, prénom, e-mail surlignés et reliés aux noms POST."""
        from models import PilotWaiver
        from services.admin.waivers import create_pilot_waiver

        with self.app.app_context():
            proj, _, _ = self._create_mock_project()
            create_pilot_waiver(project_id=proj.id, signer_first_name="Lucas", signer_last_name="Moreau")
            pw = PilotWaiver.query.filter_by(project_id=proj.id).first()
            _, url = get_or_create_waiver_signing_url(pw.waiver_id, waiver_type="pilot_waiver")
            token = url.split("/sign/pilot-attestation/")[-1]

        captured = {}

        def fake_render(html_content, **kwargs):
            captured["html"] = html_content
            return b"%PDF-1.4 preview"

        with patch("utils.document_utils.render_pdf_from_template", side_effect=fake_render):
            resp = self.client.post(f"/sign/pilot-attestation/{token}/preview", data={
                "first_name": "Lucas", "last_name": "", "email": "lucas@stunt.fr", "signer_role": "pilot",
            })
        self.assertEqual(resp.status_code, 200)
        html = captured["html"]
        self.assertIn(f'href="{FIELD_URL}first_name">Lucas</a>', html)
        self.assertIn(f'href="{FIELD_URL}last_name">[Nom]</a>', html)
        self.assertIn(f'href="{FIELD_URL}email">lucas@stunt.fr</a>', html)
        self.assertIn(f'href="{FIELD_URL}signer_role">Pilote</a>', html)


if __name__ == "__main__":
    unittest.main()
