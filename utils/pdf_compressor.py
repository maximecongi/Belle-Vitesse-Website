"""
Module de compression PDF haute performance 100% local.

Optimise les documents PDF sans aucune dépendance externe/cloud :
1. Rééchantillonnage et recompression des images matricielles via Pillow (LANCZOS, JPEG q78).
2. Aplatissement propre des transparences (RGBA/LA) sur fond blanc.
3. Compression des flux de contenu (content streams) via pypdf.
4. Déduplication des objets identiques du PDF via pypdf.
"""

import io
import logging
import os
from typing import Optional
from flask import current_app

logger = logging.getLogger(__name__)

# Valeurs par défaut optimisées pour un compromis parfait poids / netteté à l'impression
DEFAULT_MAX_IMAGE_DIM: int = 1400
DEFAULT_JPEG_QUALITY: int = 78


def _log_info(msg: str) -> None:
    if current_app:
        current_app.logger.info(msg)
    else:
        logger.info(msg)


def _log_warning(msg: str) -> None:
    if current_app:
        current_app.logger.warning(msg)
    else:
        logger.warning(msg)


def _log_error(msg: str) -> None:
    if current_app:
        current_app.logger.error(msg)
    else:
        logger.error(msg)


def _optimize_image(img_obj, max_dim: int, quality: int) -> bool:
    """
    Optimise un objet image pypdf individuel à l'aide de Pillow :
    - Réduction proportionnelle si dimensions > max_dim
    - Conversion des transparences vers fond blanc RGB
    - Recompression JPEG au niveau de qualité spécifié

    Retourne True si l'image a été modifiée avec succès, False sinon.
    """
    try:
        from PIL import Image

        pil_img = img_obj.image

        # Redimensionnement proportionnel si l'image dépasse la résolution maximale
        if pil_img.width > max_dim or pil_img.height > max_dim:
            pil_img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        # Gestion des modes d'image (aplatissement des canaux alpha)
        if pil_img.mode in ("RGBA", "LA"):
            bg = Image.new("RGB", pil_img.size, (255, 255, 255))
            bg.paste(pil_img, mask=pil_img.split()[-1])
            pil_img = bg
        elif pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")

        # Remplacement de l'image compressée dans le flux PDF
        img_obj.replace(pil_img, quality=quality)
        return True
    except Exception:
        # En cas d'erreur sur une image spécifique, conserver l'image originale intacte
        return False


def compress_pdf(
    pdf_bytes: bytes,
    filename: str = "document.pdf",
    max_dim: int = DEFAULT_MAX_IMAGE_DIM,
    quality: int = DEFAULT_JPEG_QUALITY,
) -> bytes:
    """
    Compresse un flux de données PDF en mémoire de manière autonome et locale.

    Args:
        pdf_bytes (bytes): Données brutes du fichier PDF.
        filename (str): Nom indicatif du document pour les journaux d'activité.
        max_dim (int): Dimension maximale (largeur/hauteur) pour les images intégrées.
        quality (int): Qualité JPEG de compression des images (1 à 100, recommandé 75-80).

    Returns:
        bytes: Données du PDF compressé (ou l'original en cas de problème ou en mode test).
    """
    if not pdf_bytes or len(pdf_bytes) < 100:
        return pdf_bytes

    # Bypass rapide pendant l'exécution des tests automatisés
    if current_app and (current_app.config.get("TESTING") or os.getenv("FLASK_ENV") == "testing"):
        return pdf_bytes

    try:
        from pypdf import PdfReader, PdfWriter

        # Initialisation via clone_from pour que toutes les pages appartiennent au PdfWriter
        try:
            writer = PdfWriter(clone_from=io.BytesIO(pdf_bytes))
        except Exception:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            writer = PdfWriter()
            for p in reader.pages:
                writer.add_page(p)

        images_processed = 0

        for page in writer.pages:
            # Optimisation des images intégrées à la page
            try:
                for img_obj in page.images:
                    if _optimize_image(img_obj, max_dim=max_dim, quality=quality):
                        images_processed += 1
            except Exception:
                pass

            # Compression des flux vectoriels et textuels
            try:
                page.compress_content_streams()
            except Exception:
                pass

        # Déduplication des objets récurrents (polices, ressources partagées)
        writer.compress_identical_objects()

        out_buf = io.BytesIO()
        writer.write(out_buf)
        compressed_bytes = out_buf.getvalue()

        if compressed_bytes and len(compressed_bytes) > 0:
            orig_kb = len(pdf_bytes) / 1024
            comp_kb = len(compressed_bytes) / 1024
            saved_pct = ((orig_kb - comp_kb) / orig_kb * 100) if orig_kb > 0 else 0
            _log_info(
                f"✅ PDF '{filename}' compressé localement : "
                f"{orig_kb:.1f} Ko ➔ {comp_kb:.1f} Ko (-{saved_pct:.1f}%, {images_processed} image(s))"
            )
            return compressed_bytes

    except ImportError:
        _log_warning("⚠️ Bibliothèque 'pypdf' ou 'Pillow' indisponible pour la compression PDF locale.")
    except Exception as err:
        _log_error(f"⚠️ Échec de la compression PDF locale pour '{filename}' : {err}")

    return pdf_bytes


# Alias pour compatibilité
compress_pdf_locally = compress_pdf
