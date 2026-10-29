"""
Tests unitaires pour la gestion du cache et du téléchargement du catalogue PDF.
Vérifie la non-persistance en cache client/proxy et la présence des en-têtes anti-cache.
"""
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
from app import create_app
from models import db, User
from services.admin.catalog import (
    get_catalog_directory,
    get_latest_catalog_info,
    invalidate_catalog_cache,
    update_stored_catalog,
)


class TestCatalogCacheAndDownload(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.app.config["OUTPUT_FOLDER"] = self.temp_dir

        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_user_role"] = "super administrateur"

    def tearDown(self):
        db.session.rollback()
        self.ctx.pop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_catalog_directory_uses_config_output_folder(self):
        """Vérifie que get_catalog_directory utilise bien la configuration OUTPUT_FOLDER."""
        directory = get_catalog_directory()
        self.assertTrue(directory.startswith(self.temp_dir))
        self.assertTrue(os.path.exists(directory))

    @patch("services.admin.catalog.generate_catalog_pdf")
    def test_update_stored_catalog_atomic_and_cleanup(self, mock_gen):
        """Vérifie que la génération crée le fichier atomiquement et nettoie les anciens."""
        mock_gen.return_value = b"%PDF-1.4 dummy catalog content"
        
        success, msg = update_stored_catalog(with_prices=True)
        self.assertTrue(success)

        info1 = get_latest_catalog_info(with_prices=True)
        self.assertIsNotNone(info1["filename"])
        self.assertIsNotNone(info1["timestamp"])
        self.assertIsNotNone(info1["updated_at"])

        file1 = os.path.join(get_catalog_directory(), info1["filename"])
        self.assertTrue(os.path.exists(file1))

        # Deuxième génération : l'ancien fichier doit être remplacé/supprimé
        success2, msg2 = update_stored_catalog(with_prices=True)
        self.assertTrue(success2)

        info2 = get_latest_catalog_info(with_prices=True)
        file2 = os.path.join(get_catalog_directory(), info2["filename"])
        self.assertTrue(os.path.exists(file2))

        # Vérifier qu'il ne reste qu'un seul PDF dans le répertoire pour with_prices
        pdf_files = [f for f in os.listdir(get_catalog_directory()) if f.startswith("Belle_Vitesse_CATALOGUE_P_")]
        self.assertEqual(len(pdf_files), 1)

    @patch("services.admin.catalog.generate_catalog_pdf")
    def test_download_headers_prevent_caching(self, mock_gen):
        """Vérifie que la route /admin/catalog/pdf renvoie des en-têtes anti-cache stricts."""
        mock_gen.return_value = b"%PDF-1.4 dummy catalog content"
        update_stored_catalog(with_prices=True)

        resp = self.client.get("/admin/catalog/pdf?prices=1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("Content-Type"), "application/pdf")
        
        # Vérification des en-têtes anti-cache
        cache_control = resp.headers.get("Cache-Control", "")
        self.assertIn("no-cache", cache_control)
        self.assertIn("no-store", cache_control)
        self.assertIn("must-revalidate", cache_control)
        self.assertIn("max-age=0", cache_control)
        self.assertEqual(resp.headers.get("Pragma"), "no-cache")
        self.assertEqual(resp.headers.get("Expires"), "0")

    @patch("services.admin.catalog.generate_catalog_pdf")
    def test_preview_contains_cache_buster_timestamp(self, mock_gen):
        """Vérifie que la prévisualisation HTML injecte le timestamp cache buster sur le lien de téléchargement."""
        mock_gen.return_value = b"%PDF-1.4 dummy catalog content"
        update_stored_catalog(with_prices=True)

        info = get_latest_catalog_info(with_prices=True)
        resp = self.client.get("/admin/catalog/preview?prices=1")
        self.assertEqual(resp.status_code, 200)

        html = resp.data.decode("utf-8")
        # Le lien de téléchargement doit contenir t=<timestamp>
        expected_query = f"t={info['timestamp']}"
        self.assertIn(expected_query, html)
        # Le bouton doit avoir data-action="update-catalog"
        self.assertIn('data-action="update-catalog"', html)
        # La feuille de style catalog.css et le script admin.bundle.js doivent être versionnés avec ?v=
        self.assertIn('catalog.css?v=', html)
        self.assertIn('admin.bundle.js?v=', html)

    def test_invalidate_catalog_cache_safe(self):
        """Vérifie que l'invalidation du cache ne lève aucune exception."""
        try:
            invalidate_catalog_cache()
        except Exception as e:
            self.fail(f"invalidate_catalog_cache a levé une exception inattendue : {e}")

