import unittest
from pathlib import Path


class TestAutosaveDraftSystem(unittest.TestCase):

    def test_bundle_contains_draft_store_and_autosave(self):
        """Vérifie que les scripts de brouillon sont déclarés et compilés dans admin.bundle.js."""
        from scripts.build_bundles import ADMIN_JS_FILES

        self.assertIn("js/src/admin/draft-store.js", ADMIN_JS_FILES)
        self.assertIn("js/src/admin/inspection-autosave.js", ADMIN_JS_FILES)
        self.assertIn("js/src/admin/incident-autosave.js", ADMIN_JS_FILES)

        # L'ordre doit être respecté : draft-store avant inspection-autosave et incident-autosave
        idx_ds = ADMIN_JS_FILES.index("js/src/admin/draft-store.js")
        idx_insp = ADMIN_JS_FILES.index("js/src/admin/inspection-autosave.js")
        idx_inc = ADMIN_JS_FILES.index("js/src/admin/incident-autosave.js")

        self.assertLess(idx_ds, idx_insp)
        self.assertLess(idx_ds, idx_inc)

        bundle_path = Path("static/js/admin/admin.bundle.js")
        self.assertTrue(bundle_path.exists())
        content = bundle_path.read_text(encoding="utf-8")

        self.assertIn("BvDraftStore", content)
        self.assertTrue("initInspectionAutosave" in content or "inspection:edit:" in content)
        self.assertTrue("initIncidentAutosave" in content or "incident:edit:" in content)

    def test_form_identifiers_for_autosave(self):
        """Vérifie que les formulaires d'inspection et d'incident portent bien les IDs requis."""
        co_template = Path("templates/admin/checkout_form.html").read_text(encoding="utf-8")
        ci_template = Path("templates/admin/checkin_form.html").read_text(encoding="utf-8")
        inc_template = Path("templates/admin/incident_form.html").read_text(encoding="utf-8")

        self.assertIn('id="inspectionForm"', co_template)
        self.assertIn('id="inspectionForm"', ci_template)
        self.assertIn('id="incidentForm"', inc_template)

    def test_draft_store_file_integrity(self):
        """Vérifie la présence et les méthodes fondamentales de draft-store.js."""
        ds_file = Path("static/js/src/admin/draft-store.js")
        self.assertTrue(ds_file.exists())
        src = ds_file.read_text(encoding="utf-8")

        self.assertIn("bv_drafts_db", src)
        self.assertIn("saveDraft", src)
        self.assertIn("loadDraft", src)
        self.assertIn("deleteDraft", src)
        self.assertIn("isOnline", src)
        self.assertIn("saveToLocalStorageFallback", src)

    def test_css_draft_badges_in_bundle(self):
        """Vérifie que les classes CSS des brouillons sont présentes dans le bundle CSS."""
        bundle_css = Path("static/css/admin/admin.bundle.css").read_text(encoding="utf-8")
        self.assertIn(".inspection-autosave-banner", bundle_css)
        self.assertIn(".draft-photos-badge", bundle_css)
        self.assertIn(".draft-offline-alert", bundle_css)
        self.assertIn(".admin-banner", bundle_css)
        self.assertIn(".admin-banner--warning", bundle_css)
        self.assertIn(".admin-banner--success", bundle_css)
        self.assertIn(".admin-banner--danger", bundle_css)

    def test_admin_banner_macro_and_project_migration(self):
        """Vérifie la macro admin_banner et son utilisation dans project_form.html."""
        macros_src = Path("templates/admin/macros.html").read_text(encoding="utf-8")
        self.assertIn("{% macro admin_banner(", macros_src)
        self.assertIn("admin-banner--", macros_src)

        project_src = Path("templates/admin/project_form.html").read_text(encoding="utf-8")
        self.assertIn("admin_banner", project_src)
        self.assertIn("Duplication de tournage", project_src)

    def test_create_admin_banner_js_helper(self):
        """Vérifie que window.createAdminBanner est exporté et compilé."""
        bundle_js = Path("static/js/admin/admin.bundle.js").read_text(encoding="utf-8")
        self.assertIn("createAdminBanner", bundle_js)

    def test_badge_select_sync_restoration(self):
        """Vérifie que les fonctions de synchronisation des sélecteurs badge-select sont présentes."""
        selects_src = Path("static/js/src/admin/selects.js").read_text(encoding="utf-8")
        self.assertIn("syncBadgeSelectUI", selects_src)
        self.assertIn("window.syncBadgeSelectUI", selects_src)

        autosave_src = Path("static/js/src/admin/inspection-autosave.js").read_text(encoding="utf-8")
        self.assertIn("syncBadgeSelectUI", autosave_src)
        self.assertIn("badge-select-trigger", autosave_src)

        bundle_js = Path("static/js/admin/admin.bundle.js").read_text(encoding="utf-8")
        self.assertIn("syncBadgeSelectUI", bundle_js)


if __name__ == "__main__":
    unittest.main()

