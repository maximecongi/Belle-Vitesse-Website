import os
from datetime import datetime
from flask import render_template, current_app
from models import Vehicle, Head, AppSetting
from utils.database import get_configs_for_vehicle
from utils.document_utils import render_pdf_from_template


def get_catalog_directory():
    """Retourne le répertoire de stockage des catalogues PDF."""
    output_base = str(
        current_app.config.get("OUTPUT_FOLDER")
        or os.getenv("OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))
    )
    directory = os.path.join(output_base, "catalog")
    os.makedirs(directory, exist_ok=True)
    return directory


def get_latest_catalog_info(with_prices=True):
    """Retourne les métadonnées (horodatage, nom de fichier) du dernier catalogue généré."""
    import glob
    directory = get_catalog_directory()
    prefix = "Belle_Vitesse_CATALOGUE_P_" if with_prices else "Belle_Vitesse_CATALOGUE_WP_"
    pattern = os.path.join(directory, f"{prefix}*.pdf")
    matching_files = glob.glob(pattern)

    if not matching_files:
        return {
            "timestamp": int(datetime.now().timestamp()),
            "filename": None,
            "updated_at": None,
        }

    matching_files.sort(key=os.path.getmtime, reverse=True)
    latest_file = matching_files[0]
    mtime = os.path.getmtime(latest_file)
    return {
        "timestamp": int(mtime),
        "filename": os.path.basename(latest_file),
        "updated_at": datetime.fromtimestamp(mtime).strftime("%d/%m/%Y à %H:%M"),
    }


def invalidate_catalog_cache():
    """Invalide les caches Flask-Caching associés aux équipements et configurations."""
    try:
        from extensions import cache
        if cache:
            cache.delete("vehicles")
            cache.delete("heads")
            cache.delete("static_all")
            vehicles_objs = Vehicle.query.all()
            for v in vehicles_objs:
                cache.delete(f"configs_vehicle_{v.id}")
                if v.fields and v.fields.get("slug"):
                    cache.delete(f"vehicle_{v.fields.get('slug')}")
            heads_objs = Head.query.all()
            for h in heads_objs:
                if h.fields and h.fields.get("slug"):
                    cache.delete(f"head_{h.fields.get('slug')}")
    except Exception as e:
        current_app.logger.warning(f"⚠️ Erreur lors de l'invalidation du cache catalogue : {e}")


def get_catalog_data(with_prices=True):
    """Récupère et formate les données pour le catalogue de prix."""
    from flask import request, has_request_context

    if has_request_context():
        base_url = request.url_root.rstrip("/")
    else:
        base_url = os.getenv("BASE_URL", "https://team.bellevitesse.com")

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
        "pdf_export": False,
        "pdf_placeholder_images": {},
    }


def generate_catalog_pdf(with_prices=True, filename: str = None):
    """Génère le PDF du catalogue de prix en page continue fluide."""
    target_filename = filename or f"Belle_Vitesse_CATALOGUE_{'P' if with_prices else 'WP'}.pdf"
    from flask import has_request_context

    def get_pdf_context():
        data = get_catalog_data(with_prices=with_prices)
        data["pdf_export"] = True
        data["pdf_placeholder_images"] = {
            name: os.path.isfile(
                os.path.join(current_app.static_folder, "imgs", "placeholders", f"{name}.png")
            )
            for name in ("vehicle", "head")
        }
        return data

    if not has_request_context():
        with current_app.test_request_context(base_url="https://team.bellevitesse.com"):
            data = get_pdf_context()
            html = render_template("pdf/catalog.html", **data)
            return render_pdf_from_template(html, base_url=current_app.root_path, filename=target_filename, continuous=True)

    data = get_pdf_context()
    html = render_template("pdf/catalog.html", **data)
    pdf_bytes = render_pdf_from_template(html, base_url=current_app.root_path, filename=target_filename, continuous=True)
    return pdf_bytes


def update_stored_catalog(with_prices=True):
    """Génère et sauvegarde le PDF du catalogue sur le disque avec écriture atomique."""
    try:
        # 1. Invalider les caches applicatifs pour s'assurer de lire les données fraîches de la base
        invalidate_catalog_cache()

        upload_dir = get_catalog_directory()
        prefix = "Belle_Vitesse_CATALOGUE_P_" if with_prices else "Belle_Vitesse_CATALOGUE_WP_"

        import random
        import string

        rand_str = "".join(random.choices(string.ascii_uppercase, k=4))
        filename = f'{prefix}{datetime.now().strftime("%Y%m")}_{rand_str}.pdf'
        file_path = os.path.join(upload_dir, filename)
        tmp_file_path = f"{file_path}.tmp"

        # 2. Génération atomique dans un fichier temporaire
        pdf_bytes = generate_catalog_pdf(with_prices=with_prices, filename=filename)

        with open(tmp_file_path, "wb") as f:
            f.write(pdf_bytes)

        os.replace(tmp_file_path, file_path)

        # 3. Nettoyer les anciens catalogues SEULEMENT après confirmation de l'écriture réussie
        prefixes_to_clean = [prefix, "Belle_Vitesse_CATALOGUE_PRIX_", "Belle_Vitesse_CATALOGUE_SANS_PRIX_"]
        for f in os.listdir(upload_dir):
            if f == filename:
                continue
            is_match = any(f.startswith(p) for p in prefixes_to_clean)
            if not is_match and f.startswith("Belle_Vitesse_CATALOGUE_") and not f.startswith("Belle_Vitesse_CATALOGUE_P_") and not f.startswith("Belle_Vitesse_CATALOGUE_WP_"):
                is_match = True

            if is_match and f.endswith(".pdf"):
                try:
                    os.remove(os.path.join(upload_dir, f))
                except Exception as err:
                    current_app.logger.warning(f"Impossible de supprimer l'ancien catalogue {f}: {err}")

        return True, "Catalogue mis à jour avec succès."
    except Exception as e:
        current_app.logger.error(f"❌ Erreur lors de la sauvegarde du catalogue : {e}")
        return False, str(e)
