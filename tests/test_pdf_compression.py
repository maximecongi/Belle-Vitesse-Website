import io
import unittest
from unittest.mock import patch, MagicMock
from PIL import Image

from app import create_app
from utils.pdf_compressor import compress_pdf, compress_pdf_locally, _optimize_image
from utils.document_utils import render_pdf_from_template


class PDFCompressionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.sample_pdf = (
            b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
            b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
            b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"
        )

    def tearDown(self):
        self.ctx.pop()

    def test_compress_pdf_testing_mode_bypass(self):
        """Vérifie que la compression est ignorée en mode test pour préserver les perfs."""
        result = compress_pdf(self.sample_pdf, "test.pdf")
        self.assertEqual(result, self.sample_pdf)

    def test_compress_pdf_short_or_empty_bytes(self):
        """Vérifie qu'un contenu trop court ou vide est renvoyé tel quel."""
        self.assertEqual(compress_pdf(b"", "vide.pdf"), b"")
        self.assertEqual(compress_pdf(b"court", "court.pdf"), b"court")

    def test_compress_pdf_valid_document(self):
        """Vérifie la compression locale effective d'un document PDF valide."""
        with patch.dict(self.app.config, {"TESTING": False}):
            compressed = compress_pdf(self.sample_pdf, "document_test.pdf")
            self.assertTrue(isinstance(compressed, bytes))
            self.assertTrue(compressed.startswith(b"%PDF"))

    def test_optimize_image_downscaling_and_rgba(self):
        """Vérifie la conversion et le redimensionnement d'une image avec canal alpha."""
        # Créer une image de test RGBA 1800x1800 (> max_dim 1400)
        orig_img = Image.new("RGBA", (1800, 1800), (255, 0, 0, 128))
        mock_img_obj = MagicMock()
        mock_img_obj.image = orig_img

        success = _optimize_image(mock_img_obj, max_dim=1400, quality=75)
        self.assertTrue(success)

        # Vérifier que replace a été appelé avec une image redimensionnée et en RGB
        mock_img_obj.replace.assert_called_once()
        replaced_img, kwargs = mock_img_obj.replace.call_args
        pil_res = replaced_img[0]
        self.assertEqual(kwargs.get("quality"), 75)
        self.assertEqual(pil_res.mode, "RGB")
        self.assertLessEqual(pil_res.width, 1400)
        self.assertLessEqual(pil_res.height, 1400)

    def test_compress_pdf_resilience_on_corruption(self):
        """Vérifie que le compresseur renvoie l'original sans lever d'exception en cas de corruption."""
        with patch.dict(self.app.config, {"TESTING": False}):
            with patch("pypdf.PdfReader", side_effect=Exception("Format PDF corrompu")):
                result = compress_pdf(self.sample_pdf, "corrompu.pdf")
                self.assertEqual(result, self.sample_pdf)

    def test_render_pdf_from_template_invokes_compress_pdf(self):
        """Vérifie que render_pdf_from_template appelle bien compress_pdf du nouveau module."""
        mock_weasy = MagicMock()
        mock_html_instance = MagicMock()
        mock_html_instance.write_pdf.return_value = self.sample_pdf
        mock_weasy.HTML.return_value = mock_html_instance

        with patch.dict("sys.modules", {"weasyprint": mock_weasy}):
            with patch("utils.pdf_compressor.compress_pdf", return_value=b"%PDF-final-compressed") as mock_comp:
                pdf_out = render_pdf_from_template(
                    "<html><body>Contrat</body></html>",
                    base_url="/",
                    compress=True,
                    filename="contrat_client.pdf"
                )

                self.assertEqual(pdf_out, b"%PDF-final-compressed")
                mock_comp.assert_called_once_with(self.sample_pdf, filename="contrat_client.pdf")


if __name__ == "__main__":
    unittest.main()
