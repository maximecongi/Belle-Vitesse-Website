"""
services/admin/meeting_report_service.py
Service métier pour le parsing, la mise en page et la génération PDF des comptes-rendus de réunion Belle Vitesse.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import markdown
from flask import current_app, render_template

from utils.document_utils import render_pdf_from_template

MONTHS_FR = {
    "janvier": 1,
    "fevrier": 2,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
    "décembre": 12,
    "janv": 1,
    "févr": 2,
    "fevr": 2,
    "avr": 4,
    "juil": 7,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "déc": 12,
    "dec": 12,
}


def parse_meeting_date(raw_date: Optional[str]) -> Tuple[str, str]:
    """
    Extrait et normalise une date de réunion et génère l'identifiant au format BVMR-JJMMAAAA.
    Retourne (date_affichee, bvmr_id).
    """
    now = datetime.now()
    default_id = f"BVMR-{now.strftime('%d%m%Y')}"
    default_display = now.strftime("%d/%m/%Y")

    if not raw_date or not raw_date.strip():
        return default_display, default_id

    s = raw_date.strip()

    # Formats strptime standards
    patterns = [
        "%a, %d %b %y",
        "%a, %d %b %Y",
        "%d/%m/%Y",
        "%d/%m/%y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d.%m.%Y",
    ]
    for p in patterns:
        try:
            dt = datetime.strptime(s, p)
            return dt.strftime("%d/%m/%Y"), f"BVMR-{dt.strftime('%d%m%Y')}"
        except ValueError:
            pass

    # Détection textuelle en français (ex: "5 novembre 2026" ou "05 nov. 2026")
    m = re.search(r"(\d{1,2})\s+([a-zA-Z\u00C0-\u017F\.]+)\s+(\d{2,4})", s)
    if m:
        try:
            day = int(m.group(1))
            mo_str = m.group(2).lower().rstrip(".")
            yr = int(m.group(3))
            if yr < 100:
                yr += 2000
            if mo_str in MONTHS_FR:
                dt = datetime(yr, MONTHS_FR[mo_str], day)
                return dt.strftime("%d/%m/%Y"), f"BVMR-{dt.strftime('%d%m%Y')}"
        except Exception:
            pass

    return s, default_id


def normalize_markdown_list_indentation(text: str) -> str:
    """
    Normalise l'indentation des listes imbriquées (2 espaces -> 4 espaces)
    pour garantir un parsing conforme en arborescence HTML par Python-Markdown.
    """
    lines = text.splitlines()
    out = []
    for line in lines:
        m = re.match(r"^( +)([-*+]|\d+\.)\s+(.*)$", line)
        if m:
            spaces = len(m.group(1))
            bullet = m.group(2)
            rest = m.group(3)
            level = max(1, (spaces + 1) // 2)
            out.append("    " * level + bullet + " " + rest)
        else:
            out.append(line)
    return "\n".join(out)


def parse_meeting_report(
    markdown_text: str,
    custom_title: Optional[str] = None,
    custom_date: Optional[str] = None,
    custom_ref: Optional[str] = None,
    custom_doc_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyse un texte Markdown de compte-rendu de réunion et prépare
    les structures de données et le code HTML injecté de la charte Belle Vitesse.
    """
    if not markdown_text:
        markdown_text = ""

    lines = markdown_text.strip().splitlines()
    extracted_title = ""
    extracted_date = ""
    body_lines = []

    found_title = False
    found_date = False

    for line in lines:
        stripped = line.strip()
        # 1. Extraction du premier titre H1 (# ...)
        if not found_title and stripped.startswith("# "):
            extracted_title = stripped[2:].strip()
            found_title = True
            continue

        # 2. Extraction facultative de la date juste sous le titre
        if (
            found_title
            and not found_date
            and stripped
            and not stripped.startswith("#")
            and not stripped.startswith("-")
            and not stripped.startswith("*")
            and not stripped.startswith(">")
            and len(stripped) < 80
        ):
            extracted_date = stripped
            found_date = True
            continue

        body_lines.append(line)

    final_title = (custom_title or extracted_title or "Compte-Rendu de Réunion").strip()
    raw_date = custom_date or extracted_date or ""
    date_display, auto_ref = parse_meeting_date(raw_date)

    final_ref = (custom_ref or auto_ref).strip()
    final_doc_type = (custom_doc_type or "COMPTE RENDU DE RÉUNION").strip()

    # Normalisation et conversion Markdown
    body_text = "\n".join(body_lines)
    normalized_body = normalize_markdown_list_indentation(body_text)

    # Conversion Markdown vers HTML
    raw_html = markdown.markdown(
        normalized_body,
        extensions=["extra", "sane_lists"],
    )

    # Post-traitement pour injecter les classes sémantiques Belle Vitesse
    # H2 -> Titre de section officiel avec carré or .dot-before
    processed_html = re.sub(
        r"<h2>(.*?)</h2>",
        r'<h2 class="cgl-section-title pdf-section-title dot-before">\1</h2>',
        raw_html,
    )
    # H3 -> Sous-titre hiérarchique
    processed_html = re.sub(
        r"<h3>(.*?)</h3>",
        r'<h3 class="cgl-subtitle pdf-subtitle">\1</h3>',
        processed_html,
    )
    # Citations/Notes blockquote -> boîte de contexte sobre Belle Vitesse
    processed_html = re.sub(
        r"<blockquote>\s*(.*?)\s*</blockquote>",
        r'<div class="pdf-context-box">\1</div>',
        processed_html,
        flags=re.DOTALL,
    )
    # Listes à puces -> classe stylée pdf-bullets-list
    processed_html = re.sub(
        r"<ul>",
        r'<ul class="pdf-bullets-list">',
        processed_html,
    )

    return {
        "title": final_title,
        "date_str": date_display,
        "doc_id": final_ref,
        "doc_type_title": final_doc_type,
        "html_content": processed_html,
        "raw_markdown": markdown_text,
    }


def generate_meeting_report_pdf(report_data: Dict[str, Any], base_url: Optional[str] = None) -> bytes:
    """
    Compile le compte-rendu au format PDF WeasyPrint vectoriel haute fidélité.
    """
    company_name = current_app.config.get("COMPANY_NAME", "Belle Vitesse")
    html_content = render_template(
        "pdf/meeting_report.html",
        report=report_data,
        doc_header_title=report_data.get("doc_type_title", "COMPTE RENDU DE RÉUNION"),
        doc_id=report_data.get("doc_id"),
        doc_date_str=report_data.get("date_str"),
        company_name=company_name,
        is_preview=False,
    )

    return render_pdf_from_template(
        html_content=html_content,
        base_url=base_url or "http://localhost",
        stylesheets=["css/pdf/meeting-report-pdf.css"],
        filename=f"{report_data.get('doc_id', 'BVMR')}.pdf",
        compress=True,
        continuous=False,
        include_base_pdf=True,
    )
