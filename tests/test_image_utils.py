import io
import os
import tempfile
import unittest
from PIL import Image

from utils.image_utils import optimize_and_save_image


class ImageUtilsTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_resize_large_image(self):
        """Vérifie qu'une image de grande dimension est redimensionnée à max 1920px."""
        # Créer une image 3000 x 2000
        img = Image.new("RGB", (3000, 2000), color=(255, 100, 50))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        buf.seek(0)

        target_path = os.path.join(self.temp_dir.name, "output_large.jpg")
        success = optimize_and_save_image(buf, target_path, max_dimension=1920, quality=85)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(target_path))

        with Image.open(target_path) as out_img:
            w, h = out_img.size
            self.assertLessEqual(max(w, h), 1920)
            self.assertEqual(w, 1920)
            self.assertEqual(h, 1280)

    def test_convert_rgba_to_jpeg(self):
        """Vérifie qu'une image avec canal alpha (RGBA) est convertie sans erreur en JPEG."""
        img = Image.new("RGBA", (800, 600), color=(0, 128, 255, 200))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        target_path = os.path.join(self.temp_dir.name, "rgba_converted.jpg")
        success = optimize_and_save_image(buf, target_path, max_dimension=1920, quality=85)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(target_path))

        with Image.open(target_path) as out_img:
            self.assertEqual(out_img.mode, "RGB")

    def test_save_png_format(self):
        """Vérifie la sauvegarde d'un fichier PNG."""
        img = Image.new("RGBA", (400, 300), color=(50, 200, 50, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        target_path = os.path.join(self.temp_dir.name, "image.png")
        success = optimize_and_save_image(buf, target_path)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(target_path))

    def test_fallback_non_image(self):
        """Vérifie le fallback gracieux lorsqu'un fichier texte ou corrompu est fourni."""
        raw_text = b"Ceci n'est pas une image mais un document texte."
        buf = io.BytesIO(raw_text)

        target_path = os.path.join(self.temp_dir.name, "document.txt")
        success = optimize_and_save_image(buf, target_path)
        self.assertFalse(success)  # Retourne False pour indiquer que ce n'est pas une image optimisée
        self.assertTrue(os.path.exists(target_path))

        with open(target_path, "rb") as f:
            self.assertEqual(f.read(), raw_text)


if __name__ == "__main__":
    unittest.main()
