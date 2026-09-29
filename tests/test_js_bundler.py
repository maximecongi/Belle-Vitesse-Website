import os
import unittest
from pathlib import Path

from scripts.build_bundles import (
    ADMIN_JS_FILES,
    PUBLIC_JS_FILES,
    build_admin_js_bundle,
    build_public_js_bundle,
    ensure_bundles_fresh,
    find_static_dir,
    is_bundle_outdated,
)


class TestJsBundler(unittest.TestCase):
    def setUp(self):
        self.static_dir = find_static_dir()
        self.assertIsNotNone(self.static_dir, "Le dossier static doit exister")

    def test_admin_js_files_exist(self):
        """Vérifie que chaque fichier source déclaré dans ADMIN_JS_FILES existe sur le disque."""
        for rel_path in ADMIN_JS_FILES:
            src = self.static_dir / rel_path
            self.assertTrue(
                src.exists(),
                f"Le fichier source JS admin {rel_path} est introuvable sous {self.static_dir}",
            )
            self.assertGreater(
                src.stat().st_size,
                0,
                f"Le fichier source JS admin {rel_path} ne doit pas être vide",
            )

    def test_public_js_files_exist(self):
        """Vérifie que chaque fichier source déclaré dans PUBLIC_JS_FILES existe sur le disque."""
        for rel_path in PUBLIC_JS_FILES:
            src = self.static_dir / rel_path
            self.assertTrue(
                src.exists(),
                f"Le fichier source JS public {rel_path} est introuvable sous {self.static_dir}",
            )
            self.assertGreater(
                src.stat().st_size,
                0,
                f"Le fichier source JS public {rel_path} ne doit pas être vide",
            )

    def test_build_admin_js_bundle(self):
        """Vérifie la génération du bundle JS admin et la présence des modules extraits."""
        bundle_path = build_admin_js_bundle(self.static_dir)
        self.assertTrue(bundle_path.exists())
        self.assertGreater(bundle_path.stat().st_size, 100_000)

        content = bundle_path.read_text(encoding="utf-8")
        # Vérification de la présence des nouveaux modules extraits
        self.assertIn("incident-form.js", content)
        self.assertIn("incident-detail.js", content)
        self.assertIn("project-form.js", content)
        self.assertIn("inspections.js", content)
        self.assertIn("initIncidentForm", content)
        self.assertIn("initIncidentDetail", content)
        self.assertIn("initProjectForm", content)
        self.assertIn("initInspectionDetail", content)

    def test_build_public_js_bundle(self):
        """Vérifie la génération du bundle JS public."""
        bundle_path = build_public_js_bundle(self.static_dir)
        self.assertTrue(bundle_path.exists())
        self.assertGreater(bundle_path.stat().st_size, 5_000)

        content = bundle_path.read_text(encoding="utf-8")
        self.assertIn("public.bundle.js", content)

    def test_ensure_bundles_fresh(self):
        """Vérifie que ensure_bundles_fresh fonctionne sans lever d'erreur."""
        # Un premier appel avec force=True
        updated = ensure_bundles_fresh(force=True)
        self.assertTrue(updated)

        # Un second appel immédiat ne doit rien reconstruire
        updated_again = ensure_bundles_fresh(force=False)
        self.assertFalse(updated_again)


if __name__ == "__main__":
    unittest.main()
