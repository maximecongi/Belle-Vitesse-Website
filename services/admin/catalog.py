import os
from datetime import datetime
from flask import render_template, current_app
from models import Vehicle, Head, AppSetting
from utils.database import get_configs_for_vehicle
from utils.document_utils import render_pdf_from_template


def get_catalog_data(with_prices=True):
    """Récupère et formate les données pour le catalogue de prix."""
    from flask import request

    base_url = request.url_root.rstrip("/")

    def ensure_absolute(url):
        if url and url.startswith("/"):
            return f"{base_url}{url}"
        return url

    # Récupération des véhicules via l'ORM pour avoir accès aux colonnes SQL (daily_rate)
    vehicles_objs = Vehicle.query.order_by(Vehicle.display_order).all()
    vehicles = []

    for v in vehicles_objs:
        fields = v.fields or {}
        if not fields.get("name"):
            continue

        vehicle_id = v.id
        configs_raw = get_configs_for_vehicle(vehicle_id)

        # Groupement des configs avec photos (on utilise 'small' pour compresser le PDF)
        configs_grouped = {}
        for c in configs_raw:
            c_fields = c.get("fields", {})
            c_type = c_fields.get("type", "Other")
            if c_type not in configs_grouped:
                configs_grouped[c_type] = []

            # Utilisation de 'large' pour les configs selon votre demande
            img_url = (
                c_fields.get("image", [{}])[0]
                .get("thumbnails", {})
                .get("large", {})
                .get("url")
            )

            configs_grouped[c_type].append(
                {"name": c_fields.get("name"), "image": ensure_absolute(img_url)}
            )

        vehicles.append(
            {
                "name": fields.get("name"),
                "daily_rate": float(v.daily_rate) if v.daily_rate else 0.0,
                "thumbnail": ensure_absolute(
                    fields.get("thumbnail", [{}])[0]
                    .get("thumbnails", {})
                    .get("large", {})
                    .get("url")
                    or fields.get("gallery", [{}])[0]
                    .get("thumbnails", {})
                    .get("large", {})
                    .get("url")
                ),
                "specs": {
                    "vitesse": fields.get("max_speed"),
                    "passengers": fields.get("passengers"),
                    "setups": fields.get("setups"),
                },
                "configs": configs_grouped,
            }
        )

    # Récupération des têtes via l'ORM
    heads_objs = Head.query.order_by(Head.display_order).all()
    heads = []
    for h in heads_objs:
        fields = h.fields or {}
        if not fields.get("name"):
            continue

        heads.append(
            {
                "name": fields.get("name"),
                "daily_rate": float(h.daily_rate) if h.daily_rate else 0.0,
                "thumbnail": ensure_absolute(
                    fields.get("thumbnail", [{}])[0]
                    .get("thumbnails", {})
                    .get("large", {})
                    .get("url")
                    or fields.get("gallery", [{}])[0]
                    .get("thumbnails", {})
                    .get("large", {})
                    .get("url")
                ),
            }
        )

    # Paramètres de l'entreprise
    settings = {
        "company_name": AppSetting.get("company_name", "Belle Vitesse SAS"),
        "company_address": AppSetting.get("company_address", ""),
        "company_siret": AppSetting.get("company_siret", ""),
        "company_phone": AppSetting.get("company_phone", ""),
        "company_email": AppSetting.get("company_email", ""),
    }

    # Calcul de la hauteur estimée (en mm) de manière dynamique pour un PDF "infini"
    h_header = 70
    h_footer = 45

    h_vehicles = 0
    # Regroupe les véhicules par ligne de 2
    for i in range(0, len(vehicles), 2):
        row_vehicles = vehicles[i:i+2]
        row_max = 0
        for v in row_vehicles:
            card_h = 85  # Hauteur de base d'une carte véhicule sans config
            if v.get("configs"):
                nb_configs = sum(len(items) for items in v["configs"].values())
                if nb_configs > 0:
                    config_rows = (nb_configs + 2) // 3
                    card_h += 15 + (config_rows * 40)
            if card_h > row_max:
                row_max = card_h
        h_vehicles += row_max + 10  # +10 pour l'espacement (grid gap)

    h_heads = 0
    # Regroupe les têtes par ligne de 3
    for i in range(0, len(heads), 3):
        h_heads += 55 + 10  # 65mm hauteur + 10mm espacement (grid gap)

    estimated_height = h_header + h_vehicles + h_heads + h_footer + 15  # +15 de marge de sécurité

    return {
        "vehicles": vehicles,
        "heads": heads,
        "settings": settings,
        "now": datetime.now(),
        "estimated_height": estimated_height,
        "with_prices": with_prices,
    }


def generate_catalog_pdf(with_prices=True):
    """Génère le PDF du catalogue de prix."""
    data = get_catalog_data(with_prices=with_prices)
    html = render_template("pdf/catalog.html", **data)
    pdf_bytes = render_pdf_from_template(html, base_url=current_app.root_path)
    return pdf_bytes


def update_stored_catalog(with_prices=True):
    """Génère et sauvegarde le PDF du catalogue sur le disque."""
    try:
        # Chemin de stockage via variable d'environnement
        output_base = os.getenv('OUTPUT_FOLDER', os.path.join(current_app.root_path, 'output'))
        upload_dir = os.path.join(output_base, 'catalog')
        
        prefix = "Belle_Vitesse_CATALOGUE_P_" if with_prices else "Belle_Vitesse_CATALOGUE_WP_"
        
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
        else:
            # Nettoyer l'ancien catalogue pour ne pas accumuler les fichiers avec lettres aléatoires
            prefixes_to_clean = [prefix, "Belle_Vitesse_CATALOGUE_PRIX_", "Belle_Vitesse_CATALOGUE_SANS_PRIX_"]
            for f in os.listdir(upload_dir):
                if any(f.startswith(p) for p in prefixes_to_clean) and f.endswith(".pdf"):
                    try:
                        os.remove(os.path.join(upload_dir, f))
                    except Exception as err:
                        current_app.logger.warning(f"Impossible de supprimer l'ancien catalogue {f}: {err}")

        import datetime
        import random
        import string
        
        rand_str = "".join(random.choices(string.ascii_uppercase, k=4))
        filename = f'{prefix}{datetime.datetime.now().strftime("%Y%m")}_{rand_str}.pdf'
        file_path = os.path.join(upload_dir, filename)

        # Génération
        pdf_bytes = generate_catalog_pdf(with_prices=with_prices)

        # Compression avec iLovePDF (repli sur pypdf en cas d'échec)
        compressed_successfully = False
        try:
            from utils.ilovepdf import compress_pdf_with_ilovepdf
            pdf_bytes = compress_pdf_with_ilovepdf(pdf_bytes)
            compressed_successfully = True
        except Exception as e:
            current_app.logger.warning(
                f"⚠️ Échec de la compression via iLovePDF ({e}). Utilisation du repli local (pypdf)..."
            )

        if not compressed_successfully:
            try:
                import io
                from pypdf import PdfReader, PdfWriter

                reader = PdfReader(io.BytesIO(pdf_bytes))
                writer = PdfWriter()

                for page in reader.pages:
                    writer.add_page(page)

                # Appliquer la compression sur tous les flux
                for page in writer.pages:
                    page.compress_content_streams()

                remote_buffer = io.BytesIO()
                writer.write(remote_buffer)
                pdf_bytes = remote_buffer.getvalue()
                current_app.logger.info("✅ PDF compressé avec succès via pypdf (repli).")
            except ImportError:
                current_app.logger.warning(
                    "⚠️ pypdf non installé, le catalogue ne sera pas compressé logiciellement (repli)."
                )
            except Exception as err:
                current_app.logger.error(f"⚠️ Échec de la compression PDF locale (repli) : {err}")

        # Écriture
        with open(file_path, "wb") as f:
            f.write(pdf_bytes)

        return True, "Catalogue mis à jour avec succès."
    except Exception as e:
        current_app.logger.error(f"❌ Erreur lors de la sauvegarde du catalogue : {e}")
        return False, str(e)
