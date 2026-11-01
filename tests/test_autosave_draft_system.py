import os
import re
from pathlib import Path


def test_bundle_contains_draft_store_and_autosave():
    """Vérifie que les scripts de brouillon sont déclarés et compilés dans admin.bundle.js."""
    from scripts.build_bundles import ADMIN_JS_FILES

    assert "js/src/admin/draft-store.js" in ADMIN_JS_FILES
    assert "js/src/admin/inspection-autosave.js" in ADMIN_JS_FILES
    assert "js/src/admin/incident-autosave.js" in ADMIN_JS_FILES

    # L'ordre doit être respecté : draft-store avant inspection-autosave et incident-autosave
    idx_ds = ADMIN_JS_FILES.index("js/src/admin/draft-store.js")
    idx_insp = ADMIN_JS_FILES.index("js/src/admin/inspection-autosave.js")
    idx_inc = ADMIN_JS_FILES.index("js/src/admin/incident-autosave.js")

    assert idx_ds < idx_insp
    assert idx_ds < idx_inc

    bundle_path = Path("static/js/admin/admin.bundle.js")
    assert bundle_path.exists()
    content = bundle_path.read_text(encoding="utf-8")

    assert "BvDraftStore" in content
    assert "initInspectionAutosave" in content or "inspection:edit:" in content
    assert "initIncidentAutosave" in content or "incident:edit:" in content


def test_form_identifiers_for_autosave():
    """Vérifie que les formulaires d'inspection et d'incident portent bien les IDs requis."""
    co_template = Path("templates/admin/checkout_form.html").read_text(encoding="utf-8")
    ci_template = Path("templates/admin/checkin_form.html").read_text(encoding="utf-8")
    inc_template = Path("templates/admin/incident_form.html").read_text(encoding="utf-8")

    assert 'id="inspectionForm"' in co_template
    assert 'id="inspectionForm"' in ci_template
    assert 'id="incidentForm"' in inc_template


def test_draft_store_file_integrity():
    """Vérifie la présence et les méthodes fondamentales de draft-store.js."""
    ds_file = Path("static/js/src/admin/draft-store.js")
    assert ds_file.exists()
    src = ds_file.read_text(encoding="utf-8")

    assert "bv_drafts_db" in src
    assert "saveDraft" in src
    assert "loadDraft" in src
    assert "deleteDraft" in src
    assert "isOnline" in src
    assert "saveToLocalStorageFallback" in src


def test_css_draft_badges_in_bundle():
    """Vérifie que les classes CSS des brouillons sont présentes dans le bundle CSS."""
    bundle_css = Path("static/css/admin/admin.bundle.css").read_text(encoding="utf-8")
    assert ".inspection-autosave-banner" in bundle_css
    assert ".draft-photos-badge" in bundle_css
    assert ".draft-offline-alert" in bundle_css

