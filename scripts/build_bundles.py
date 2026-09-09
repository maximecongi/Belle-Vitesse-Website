#!/usr/bin/env python3
"""
Script de génération des bundles CSS (public et admin) pour Belle Vitesse.
Peut être exécuté :
- Localement : python3 scripts/build_bundles.py
- Lors du déploiement : appelé par deploy.sh sur l'hôte
- Dans Docker : appelé par entrypoint.sh au démarrage
- Dans Flask : appelé par ensure_bundles_fresh()
"""
import os
import sys
from pathlib import Path
from typing import List, Optional

PUBLIC_CSS_FILES: List[str] = [
    "css/normalize.css",
    "css/main.css",
    "css/slider.css",
    "css/header.css",
    "css/footer.css",
    "css/home.css",
    "css/categories.css",
    "css/vehicle.css",
    "css/grip.css",
    "css/about-us.css",
    "css/contact.css",
    "css/terms-and-conditions.css",
    "css/animation.css",
    "css/mouse-scrolling-animation.css",
    "css/filtersliders.css",
    "css/newsletter.css",
]

ADMIN_CSS_FILES: List[str] = [
    "css/admin/admin-base.css",
    "css/admin/admin-sidebar.css",
    "css/admin/admin-components.css",
    "css/admin/admin-login.css",
    "css/admin/admin-dashboard.css",
    "css/admin/admin-contacts.css",
    "css/admin/calendar.css",
    "css/admin/admin-pricing.css",
    "css/admin/admin-utilities.css",
    "css/admin/admin-projects.css",
    "css/admin/prequote.css",
    "css/admin/admin-js.css",
    "css/admin/admin-booking.css",
    "css/admin/admin-cmdk.css",
]


def find_static_dir(base_dir: Optional[str] = None) -> Path:
    """Localise le dossier static du projet."""
    if base_dir:
        p = Path(base_dir)
        if (p / "css").exists():
            return p
        if (p / "static" / "css").exists():
            return p / "static"

    # Recherche relative depuis le script
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    candidate = repo_root / "static"
    if (candidate / "css").exists():
        return candidate

    # Dossier courant
    cwd_candidate = Path.cwd() / "static"
    if (cwd_candidate / "css").exists():
        return cwd_candidate

    raise FileNotFoundError("❌ Impossible de localiser le dossier 'static' de Belle Vitesse.")


def build_public_bundle(static_dir: Path) -> Path:
    """Génère static/css/styles.bundle.css."""
    target = static_dir / "css" / "styles.bundle.css"
    content_chunks = []

    for rel_path in PUBLIC_CSS_FILES:
        src = static_dir / rel_path
        if src.exists():
            content_chunks.append(f"/* ── {rel_path} ── */\n" + src.read_text(encoding="utf-8"))
        else:
            print(f"⚠️  Fichier public manquant : {src}", file=sys.stderr)

    # Concaténer styles.css en filtrant les @import
    styles_src = static_dir / "css" / "styles.css"
    if styles_src.exists():
        filtered_lines = [
            line for line in styles_src.read_text(encoding="utf-8").splitlines()
            if not line.strip().startswith("@import")
        ]
        content_chunks.append("/* ── css/styles.css (règles globales) ── */\n" + "\n".join(filtered_lines))

    bundle_content = "\n\n".join(content_chunks) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(bundle_content, encoding="utf-8")
    return target


def build_admin_bundle(static_dir: Path) -> Path:
    """Génère static/css/admin/admin.bundle.css."""
    target = static_dir / "css" / "admin" / "admin.bundle.css"
    content_chunks = []

    for rel_path in ADMIN_CSS_FILES:
        src = static_dir / rel_path
        if src.exists():
            content_chunks.append(f"/* ── {rel_path} ── */\n" + src.read_text(encoding="utf-8"))
        else:
            print(f"⚠️  Fichier admin manquant : {src}", file=sys.stderr)

    bundle_content = "\n\n".join(content_chunks) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(bundle_content, encoding="utf-8")
    return target


def is_bundle_outdated(bundle_path: Path, source_files: List[str], static_dir: Path) -> bool:
    """Vérifie si un bundle est manquant ou plus ancien que ses sources."""
    if not bundle_path.exists():
        return True
    try:
        bundle_mtime = bundle_path.stat().st_mtime
        for rel in source_files:
            src = static_dir / rel
            if src.exists() and src.stat().st_mtime > bundle_mtime:
                return True
    except Exception:
        return True
    return False


def ensure_bundles_fresh(static_dir_path: Optional[str] = None, force: bool = False) -> bool:
    """
    Vérifie et régénère les bundles CSS uniquement s'ils sont obsolètes ou absents.
    Retourne True si au moins un bundle a été régénéré.
    """
    try:
        s_dir = find_static_dir(static_dir_path)
    except Exception as e:
        print(f"⚠️ Erreur détection static: {e}", file=sys.stderr)
        return False

    updated = False
    admin_bundle = s_dir / "css" / "admin" / "admin.bundle.css"
    if force or is_bundle_outdated(admin_bundle, ADMIN_CSS_FILES, s_dir):
        out = build_admin_bundle(s_dir)
        print(f"✅ Admin bundle régénéré : {out} ({out.stat().st_size:,} octets)")
        updated = True

    public_bundle = s_dir / "css" / "styles.bundle.css"
    public_sources = PUBLIC_CSS_FILES + ["css/styles.css"]
    if force or is_bundle_outdated(public_bundle, public_sources, s_dir):
        out = build_public_bundle(s_dir)
        print(f"✅ Public bundle régénéré : {out} ({out.stat().st_size:,} octets)")
        updated = True

    return updated


def main():
    force = "--force" in sys.argv or "-f" in sys.argv or True
    try:
        s_dir = find_static_dir()
        print(f"📦 Dossier static localisé : {s_dir}")
        admin_out = build_admin_bundle(s_dir)
        print(f"✅ Admin bundle généré : {admin_out} ({admin_out.stat().st_size:,} octets)")
        pub_out = build_public_bundle(s_dir)
        print(f"✅ Public bundle généré : {pub_out} ({pub_out.stat().st_size:,} octets)")
    except Exception as e:
        print(f"❌ Erreur lors de la génération des bundles : {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
