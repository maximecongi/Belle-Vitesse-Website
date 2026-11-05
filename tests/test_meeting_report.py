"""
tests/test_meeting_report.py
Tests unitaires pour le module de compte-rendu de réunion Belle Vitesse (BVMR).
Isolation stricte en mémoire, nettoyage automatique et mock WeasyPrint.
"""

from services.admin.meeting_report_service import (
    generate_meeting_report_pdf,
    parse_meeting_date,
    parse_meeting_report,
)
from tests.base import BaseTestCase


class MeetingReportTestCase(BaseTestCase):
    """Suite de tests pour le module de compte-rendu de réunion."""

    SAMPLE_MARKDOWN = """# BV - Véhicules et sécurité : risk assessments, convoyage, et tarification

Thu, 05 Nov 26

## Risk Assessment et Documents Légaux

- Corpus de textes légaux et risk assessments à finaliser avant fin d’année
- Base actuelle jugée solide, mais à renvoyer aux avocats pour validation
- Documents à faire signer identifiés : CGL, risk assessment, règles de sécurité
  - Attestation pilote à fusionner dans les règles de sécurité (avec coche spécifique “non-salarié BV”)
  - Pilotes signent à chaque film (pas annuellement) pour éviter les problèmes d’excès de pouvoir

## Convoyage sur Route Ouverte

- Convoi sur route ouverte = risque majeur identifié
  - Véhicules non homologués sur voie publique
"""

    def test_parse_meeting_date_formats(self):
        """Vérifie la robustesse du parsing des dates et de l'ID format BVMR-JJMMAAAA."""
        # 1. Format anglais du prompt : "Thu, 05 Nov 26"
        disp1, id1 = parse_meeting_date("Thu, 05 Nov 26")
        self.assertEqual(disp1, "05/11/2026")
        self.assertEqual(id1, "BVMR-05112026")

        # 2. Format français textuel : "5 novembre 2026"
        disp2, id2 = parse_meeting_date("5 novembre 2026")
        self.assertEqual(disp2, "05/11/2026")
        self.assertEqual(id2, "BVMR-05112026")

        # 3. Format numérique standard : "05/11/2026"
        disp3, id3 = parse_meeting_date("05/11/2026")
        self.assertEqual(disp3, "05/11/2026")
        self.assertEqual(id3, "BVMR-05112026")

        # 4. Date vide / None : repli sur date du jour sans crash
        disp4, id4 = parse_meeting_date(None)
        self.assertTrue(id4.startswith("BVMR-"))
        self.assertRegex(id4, r"^BVMR-\d{8}$")

    def test_parse_meeting_report_structure(self):
        """Vérifie la conversion du Markdown en structure Belle Vitesse avec classes CSS appropriées."""
        result = parse_meeting_report(self.SAMPLE_MARKDOWN)

        # Vérification des métadonnées extraites
        self.assertEqual(
            result["title"],
            "BV - Véhicules et sécurité : risk assessments, convoyage, et tarification",
        )
        self.assertEqual(result["date_str"], "05/11/2026")
        self.assertEqual(result["doc_id"], "BVMR-05112026")
        self.assertEqual(result["doc_type_title"], "COMPTE RENDU DE RÉUNION")

        html = result["html_content"]

        # Titres de sections H2 avec dot-before (carré or)
        self.assertIn("cgl-section-title pdf-section-title dot-before", html)
        self.assertIn("Risk Assessment et Documents Légaux", html)
        self.assertIn("Convoyage sur Route Ouverte", html)

        # Listes imbriquées conformes
        self.assertIn('<ul class="pdf-bullets-list">', html)
        self.assertIn("Attestation pilote à fusionner", html)
        self.assertIn("règles de sécurité<ul", html)

    def test_parse_meeting_report_custom_overrides(self):
        """Vérifie que les métadonnées facultatives surchargent les valeurs extraites."""
        custom_data = parse_meeting_report(
            self.SAMPLE_MARKDOWN,
            custom_title="Titre Personnalisé",
            custom_date="12/12/2026",
            custom_ref="BVMR-SPECIAL",
            custom_doc_type="ORDRE DU JOUR",
        )

        self.assertEqual(custom_data["title"], "Titre Personnalisé")
        self.assertEqual(custom_data["doc_id"], "BVMR-SPECIAL")
        self.assertEqual(custom_data["doc_type_title"], "ORDRE DU JOUR")

    def test_admin_meeting_report_get_route(self):
        """Vérifie l'accès à la route GET /admin/tools/meeting-report."""
        # Non authentifié -> redirection vers login
        resp_unauth = self.client.get("/admin/tools/meeting-report")
        self.assertIn(resp_unauth.status_code, [302, 401, 403])

        # Authentifié admin
        self.login_as_admin()
        resp = self.client.get("/admin/tools/meeting-report")
        self.assertEqual(resp.status_code, 200)
        content = resp.get_data(as_text=True)
        self.assertIn("Compte-rendu de réunion", content)
        self.assertIn("meeting-md-input", content)
        self.assertIn("meeting-sheet", content)
        self.assertIn("BVMR-", content)

    def test_admin_meeting_report_pdf_post_route(self):
        """Vérifie la génération PDF WeasyPrint via POST /admin/tools/meeting-report/pdf."""
        self.login_as_admin()

        payload = {
            "markdown": self.SAMPLE_MARKDOWN,
            "ref": "BVMR-05112026",
            "date_str": "05/11/2026",
            "doc_type": "COMPTE RENDU DE RÉUNION",
        }

        resp = self.client.post(
            "/admin/tools/meeting-report/pdf",
            json=payload,
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "application/pdf")
        self.assertEqual(resp.headers.get("X-Document-Id"), "BVMR-05112026")
        self.assertIn("BVMR-05112026.pdf", resp.headers.get("Content-Disposition", ""))
        self.assertTrue(len(resp.data) > 0)
