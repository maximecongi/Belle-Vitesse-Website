#!/usr/bin/env python3
"""
Script de génération des bundles CSS et JavaScript (public et admin) pour Belle Vitesse.
Peut être exécuté :
- Localement : python3 scripts/build_bundles.py [--force]
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
    "css/home-intro.css",
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
    "css/verification.css",
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
    "css/admin/admin-js.css",
    "css/admin/admin-booking.css",
    "css/admin/admin-cmdk.css",
    "css/admin/admin-fleet.css",
    "css/admin/admin-incidents.css",
    "css/admin/admin-mcp.css",
]

ADMIN_JS_FILES: List[str] = [
    "js/src/admin/flash.js",
    "js/src/admin/nav.js",
    "js/src/admin/selects.js",
    "js/src/admin/tables.js",
    "js/src/admin/charts.js",
    "js/src/admin/calendar.js",
    "js/src/admin/project.js",
    "js/src/admin/cmdk.js",
    "js/src/admin/inspections.js",
    "js/src/admin/photo-annotator.js",
    "js/src/admin/ios-bridge.js",
    "js/src/admin/waiver-search.js",
    "js/src/admin/incident-form.js",
    "js/src/admin/incident-detail.js",
    "js/src/admin/project-form.js",
    "js/src/admin.js",
]

PUBLIC_JS_FILES: List[str] = [
    "js/src/initialization.js",
    "js/src/home-intro.js",
    "js/src/splide.js",
    "js/src/countup.js",
    "js/src/configurator.js",
    "js/src/infinite-scroll.js",
    "js/src/filtersliders.js",
]


def validate_css_syntax(rel_path: str, content: str) -> None:
    """Valide l'équilibrage des accolades, parenthèses et commentaires d'un fichier CSS."""
    open_comments = content.count('/*')
    close_comments = content.count('*/')
    if open_comments != close_comments:
        raise ValueError(f"Déséquilibre de commentaires /* */ dans {rel_path} ({open_comments} ouverts, {close_comments} fermés)")

    i = 0
    n = len(content)
    in_comment = False
    in_str = None
    brace_diff = 0
    line_num = 1

    while i < n:
        c = content[i]
        if c == '\n':
            line_num += 1

        if in_comment:
            if c == '*' and i + 1 < n and content[i + 1] == '/':
                in_comment = False
                i += 2
                continue
        elif in_str:
            if c == '\\':
                i += 2
                continue
            elif c == in_str:
                in_str = None
        else:
            if c == '/' and i + 1 < n and content[i + 1] == '*':
                in_comment = True
                i += 2
                continue
            elif c in ('"', "'"):
                in_str = c
            elif c == '{':
                brace_diff += 1
            elif c == '}':
                brace_diff -= 1
                if brace_diff < 0:
                    raise ValueError(f"Accolade fermante '}}' en trop à la ligne {line_num} dans {rel_path}")
        i += 1

    if brace_diff != 0:
        raise ValueError(f"Accolade(s) ouvrante(s) '{{' non fermée(s) (diff={brace_diff}) dans {rel_path}")


def validate_js_syntax(rel_path: str, content: str) -> None:
    """Valide la syntaxe d'un fichier JS via node si disponible, avec vérification des commentaires."""
    open_comments = content.count('/*')
    close_comments = content.count('*/')
    if open_comments != close_comments:
        raise ValueError(f"Déséquilibre de commentaires /* */ dans {rel_path} ({open_comments} ouverts, {close_comments} fermés)")

    import shutil
    import subprocess
    node_bin = shutil.which("node")
    if node_bin:
        try:
            res = subprocess.run(
                [node_bin, "--check"],
                input=content,
                text=True,
                capture_output=True,
                timeout=5
            )
            if res.returncode != 0:
                raise ValueError(f"Erreur de syntaxe JS dans {rel_path} :\n{res.stderr.strip()}")
        except ValueError:
            raise
        except Exception:
            pass


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
            txt = src.read_text(encoding="utf-8")
            validate_css_syntax(rel_path, txt)
            content_chunks.append(f"/* ── {rel_path} ── */\n" + txt)
        else:
            print(f"⚠️  Fichier public manquant : {src}", file=sys.stderr)

    # Concaténer styles.css en filtrant les @import
    styles_src = static_dir / "css" / "styles.css"
    if styles_src.exists():
        styles_raw = styles_src.read_text(encoding="utf-8")
        validate_css_syntax("css/styles.css", styles_raw)
        filtered_lines = [
            line for line in styles_raw.splitlines()
            if not line.strip().startswith("@import")
        ]
        content_chunks.append("/* ── css/styles.css (règles globales) ── */\n" + "\n".join(filtered_lines))

    bundle_content = "\n\n".join(content_chunks) + "\n"
    validate_css_syntax("css/styles.bundle.css", bundle_content)
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
            txt = src.read_text(encoding="utf-8")
            validate_css_syntax(rel_path, txt)
            content_chunks.append(f"/* ── {rel_path} ── */\n" + txt)
        else:
            print(f"⚠️  Fichier admin manquant : {src}", file=sys.stderr)

    bundle_content = "\n\n".join(content_chunks) + "\n"
    validate_css_syntax("css/admin/admin.bundle.css", bundle_content)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(bundle_content, encoding="utf-8")
    return target


def build_admin_js_bundle(static_dir: Path) -> Path:
    """Génère static/js/admin/admin.bundle.js en concaténant les modules JS admin."""
    target = static_dir / "js" / "admin" / "admin.bundle.js"
    content_chunks = [
        "/**\n * admin.bundle.js — Bundle JavaScript unifié pour l'administration Belle Vitesse.\n * Concaténé et validé automatiquement par scripts/build_bundles.py.\n */"
    ]

    for rel_path in ADMIN_JS_FILES:
        src = static_dir / rel_path
        if src.exists():
            txt = src.read_text(encoding="utf-8").strip()
            validate_js_syntax(rel_path, txt)
            # Ajout d'un point-virgule défensif pour éviter toute collision ASI
            content_chunks.append(f"/* ── {rel_path} ── */\n{txt}\n;")
        else:
            print(f"⚠️  Fichier JS admin manquant : {src}", file=sys.stderr)

    bundle_content = "\n\n".join(content_chunks) + "\n"
    validate_js_syntax("js/admin/admin.bundle.js", bundle_content)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(bundle_content, encoding="utf-8")
    return target


def build_public_js_bundle(static_dir: Path) -> Path:
    """Génère static/js/public.bundle.js en concaténant les scripts du site public."""
    target = static_dir / "js" / "public.bundle.js"
    content_chunks = [
        "/**\n * public.bundle.js — Bundle JavaScript unifié pour le site public Belle Vitesse.\n * Concaténé et validé automatiquement par scripts/build_bundles.py.\n */"
    ]

    for rel_path in PUBLIC_JS_FILES:
        src = static_dir / rel_path
        if src.exists():
            txt = src.read_text(encoding="utf-8").strip()
            validate_js_syntax(rel_path, txt)
            content_chunks.append(f"/* ── {rel_path} ── */\n{txt}\n;")
        else:
            print(f"⚠️  Fichier JS public manquant : {src}", file=sys.stderr)

    bundle_content = "\n\n".join(content_chunks) + "\n"
    validate_js_syntax("js/public.bundle.js", bundle_content)
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
    Vérifie et régénère les bundles CSS et JS uniquement s'ils sont obsolètes ou absents.
    Retourne True si au moins un bundle a été régénéré.
    """
    try:
        s_dir = find_static_dir(static_dir_path)
    except Exception as e:
        print(f"⚠️ Erreur détection static: {e}", file=sys.stderr)
        return False

    updated = False

    # 1. Admin CSS
    admin_css_bundle = s_dir / "css" / "admin" / "admin.bundle.css"
    if force or is_bundle_outdated(admin_css_bundle, ADMIN_CSS_FILES, s_dir):
        out = build_admin_bundle(s_dir)
        print(f"✅ Admin CSS bundle régénéré : {out} ({out.stat().st_size:,} octets)")
        updated = True

    # 2. Public CSS
    public_css_bundle = s_dir / "css" / "styles.bundle.css"
    public_css_sources = PUBLIC_CSS_FILES + ["css/styles.css"]
    if force or is_bundle_outdated(public_css_bundle, public_css_sources, s_dir):
        out = build_public_bundle(s_dir)
        print(f"✅ Public CSS bundle régénéré : {out} ({out.stat().st_size:,} octets)")
        updated = True

    # 3. Admin JS
    admin_js_bundle = s_dir / "js" / "admin" / "admin.bundle.js"
    if force or is_bundle_outdated(admin_js_bundle, ADMIN_JS_FILES, s_dir):
        out = build_admin_js_bundle(s_dir)
        print(f"✅ Admin JS bundle régénéré : {out} ({out.stat().st_size:,} octets)")
        updated = True

    # 4. Public JS
    public_js_bundle = s_dir / "js" / "public.bundle.js"
    if force or is_bundle_outdated(public_js_bundle, PUBLIC_JS_FILES, s_dir):
        out = build_public_js_bundle(s_dir)
        print(f"✅ Public JS bundle régénéré : {out} ({out.stat().st_size:,} octets)")
        updated = True

    return updated


def main():
    force = "--force" in sys.argv or "-f" in sys.argv
    try:
        s_dir = find_static_dir()
        print(f"📦 Dossier static localisé : {s_dir}")

        admin_css_out = build_admin_bundle(s_dir)
        print(f"✅ Admin CSS bundle généré : {admin_css_out} ({admin_css_out.stat().st_size:,} octets)")

        pub_css_out = build_public_bundle(s_dir)
        print(f"✅ Public CSS bundle généré : {pub_css_out} ({pub_css_out.stat().st_size:,} octets)")

        admin_js_out = build_admin_js_bundle(s_dir)
        print(f"✅ Admin JS bundle généré : {admin_js_out} ({admin_js_out.stat().st_size:,} octets)")

        pub_js_out = build_public_js_bundle(s_dir)
        print(f"✅ Public JS bundle généré : {pub_js_out} ({pub_js_out.stat().st_size:,} octets)")

    except Exception as e:
        print(f"❌ Erreur lors de la génération des bundles : {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
