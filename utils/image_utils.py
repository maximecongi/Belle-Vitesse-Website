"""
Utilitaires pour le traitement, l'optimisation et la compression des images.
Utilise Pillow pour redresser l'orientation EXIF des smartphones et réduire la taille des fichiers.
"""

import io
import logging
from pathlib import Path
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif'}


def optimize_and_save_image(file_storage, target_path, max_dimension=1920, quality=85):
    """
    Optimise et sauvegarde une image uploadée (Werkzeug FileStorage, bytes ou chemin).
    
    1. Redresse l'image selon son orientation EXIF (smartphone).
    2. Redimensionne proportionnellement si max(largeur, hauteur) > max_dimension.
    3. Compresse en format optimisé (JPEG/WebP/PNG) avec une qualité configurable (défaut: 85).
    4. Fallback gracieux vers un enregistrement brut si ce n'est pas une image ou en cas d'erreur.
    
    Retourne True si l'image a été optimisée, False si sauvegardée brute.
    """
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    suffix = target_path.suffix.lower()

    try:
        # Extraire les octets bruts
        if hasattr(file_storage, 'read'):
            raw_data = file_storage.read()
            if hasattr(file_storage, 'seek'):
                file_storage.seek(0)
        elif isinstance(file_storage, (str, Path)):
            with open(file_storage, 'rb') as f:
                raw_data = f.read()
        elif isinstance(file_storage, bytes):
            raw_data = file_storage
        else:
            if hasattr(file_storage, 'save'):
                file_storage.save(target_path)
                return False
            raise ValueError(f"Type file_storage non supporté : {type(file_storage)}")

        if not raw_data:
            return False

        # Tentative d'ouverture de l'image avec Pillow
        try:
            with Image.open(io.BytesIO(raw_data)) as img:
                # 1. Redresser l'orientation EXIF (photos smartphone)
                try:
                    img = ImageOps.exif_transpose(img)
                except Exception:
                    pass

                # 2. Conversion de mode pour compatibilité format
                if img.mode in ('RGBA', 'LA', 'P'):
                    if suffix == '.png':
                        img = img.convert('RGBA')
                    else:
                        # Fond blanc pour conversion JPEG
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        if len(img.split()) > 3:
                            background.paste(img, mask=img.split()[3])
                        else:
                            background.paste(img)
                        img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                # 3. Redimensionner si les dimensions dépassent max_dimension
                w, h = img.size
                if max(w, h) > max_dimension:
                    img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

                # 4. Sauvegarder optimisé
                if suffix in ('.jpg', '.jpeg'):
                    img.save(target_path, 'JPEG', quality=quality, optimize=True)
                elif suffix == '.webp':
                    img.save(target_path, 'WEBP', quality=quality, method=6)
                elif suffix == '.png':
                    img.save(target_path, 'PNG', optimize=True)
                else:
                    img.save(target_path, 'JPEG', quality=quality, optimize=True)

                return True

        except Exception as img_err:
            logger.warning(f"⚠️ Pillow ne peut pas traiter le fichier comme image ({img_err}), sauvegarde brute : {target_path}")
            with open(target_path, 'wb') as f:
                f.write(raw_data)
            return False

    except Exception as e:
        logger.error(f"❌ Erreur critique lors de la sauvegarde du fichier {target_path} : {e}")
        if hasattr(file_storage, 'save'):
            file_storage.save(target_path)
        return False
