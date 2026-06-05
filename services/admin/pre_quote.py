import os
from datetime import datetime
from decimal import Decimal
from flask import current_app, render_template
from models import PreQuote, PreQuoteVersion, db, AppSetting, Production
from utils.document_utils import render_pdf_from_template
import logging

logger = logging.getLogger(__name__)


def generate_reference():
    """Génère une référence unique séquentielle :DP-YYYY-NNN."""
    year = datetime.now().year

    # On cherche le dernier numéro pour cette année
    prefix = f"DP-{year}-"
    last_quote = PreQuote.query.filter(PreQuote.reference.like(
        f"{prefix}%")).order_by(PreQuote.reference.desc()).first()

    if last_quote:
        try:
            last_number = int(last_quote.reference.split('-')[-1])
            next_number = last_number + 1
        except (ValueError, IndexError):
            next_number = 1
    else:
        next_number = 1

    return f"{prefix}{next_number:03d}"


def get_delivery_config():
    """Récupère les paramètres de livraison globaux depuis AppSetting."""
    def _safe_float(key, default):
        try:
            val = AppSetting.get(key)
            return float(val) if val is not None else float(default)
        except (ValueError, TypeError):
            return float(default)
            
    return {
        "base_distance": _safe_float("delivery_base_distance", 100.0),
        "base_price": _safe_float("delivery_base_price", 200.0),
        "high_rate": _safe_float("delivery_high_rate", 0.5)
    }


def calculate_totals(prestations, tva_rate=20.00, insurance_rate=10.00):
    """Calcule les totaux HT, TVA et TTC pour une liste de prestations."""
    total_rental_ht = Decimal('0.00')
    tva_rate = Decimal(str(tva_rate))
    insurance_rate = Decimal(str(insurance_rate))

    # Récupérer la configuration de livraison
    deliv_cfg = get_delivery_config()
    base_dist = Decimal(str(deliv_cfg["base_distance"]))
    base_price = Decimal(str(deliv_cfg["base_price"]))
    high_rate = Decimal(str(deliv_cfg["high_rate"]))

    # On calcule la base de location HT (en excluant d'éventuels anciens items 'insurance')
    for item in prestations:
        if item.get('category') == 'insurance':
            continue
        qty = Decimal(str(item.get('quantity', 0)))
        if item.get('is_mad'):
            item['discount_rate'] = 100.0
        discount = Decimal(str(item.get('discount_rate', 0)))
        
        if item.get('unit') == 'km':
            # Formule progressive avec le multiplicateur x2 pour aller/retour sur les tarifs kilométriques
            if qty <= base_dist:
                total_item_price = base_price
            else:
                total_item_price = base_price + (qty - base_dist) * high_rate * Decimal('2')
            
            line_total = total_item_price * (Decimal('1') - (discount / Decimal('100')))
            item['total'] = float(line_total)
            item['unit_price'] = float(total_item_price)
        else:
            price = Decimal(str(item.get('unit_price', 0)))
            line_total = (qty * price) * (Decimal('1') - (discount / Decimal('100')))
            item['total'] = float(line_total)
            
        # Exclude all salary items from the main HT sum
        if item.get('category') == 'salary':
            continue

        total_rental_ht += line_total

    insurance_amount = total_rental_ht * (insurance_rate / Decimal('100'))
    total_ht = total_rental_ht + insurance_amount
    tva_amount = total_ht * (tva_rate / Decimal('100'))
    total_ttc = total_ht + tva_amount

    return {
        'total_rental_ht': total_rental_ht,
        'insurance_rate': insurance_rate,
        'insurance_amount': insurance_amount,
        'total_ht': total_ht,
        'tva_amount': tva_amount,
        'total_ttc': total_ttc,
        'tva_rate': tva_rate
    }


def extract_vehicle_ids_from_prestations(prestations):
    from utils.database import get_vehicles
    vehicles = get_vehicles()
    name_to_id = {}
    for v in vehicles:
        name = v.get("fields", {}).get("name")
        if name:
            name_to_id[name.strip().lower()] = v["id"]
            
    matched_ids = []
    for item in prestations:
        if item.get("category") == "equipment":
            desc = item.get("description", "").strip().lower()
            if desc in name_to_id:
                matched_ids.append(name_to_id[desc])
    return matched_ids


def extract_head_ids_from_prestations(prestations):
    from utils.database import get_heads
    heads = get_heads()
    name_to_id = {}
    for h in heads:
        name = h.get("fields", {}).get("name")
        if name:
            name_to_id[name.strip().lower()] = h["id"]
            
    matched_ids = []
    for item in prestations:
        if item.get("category") == "equipment":
            desc = item.get("description", "").strip().lower()
            if desc in name_to_id:
                matched_ids.append(name_to_id[desc])
    return matched_ids


def create_pre_quote(data, user_id=None):
    """Crée un nouveau pré-devis."""
    reference = generate_reference()
    totals = calculate_totals(
        data.get('prestations', []),
        tva_rate=data.get('tva_rate', 20.00),
        insurance_rate=data.get('insurance_rate', 10.00)
    )

    quote = PreQuote(
        reference=reference,
        production_id=data['production_id'],
        project_name=data.get('project_name'),
        prestations=[p for p in data.get('prestations', []) if p.get('category') != 'insurance'],
        insurance_rate=totals['insurance_rate'],
        insurance_amount=totals['insurance_amount'],
        total_ht=totals['total_ht'],
        tva_rate=totals['tva_rate'],
        tva_amount=totals['tva_amount'],
        total_ttc=totals['total_ttc'],
        status=data.get('status', 'draft'),
        show_discounts=data.get('show_discounts', True),
        user_id=user_id
    )

    db.session.add(quote)
    db.session.flush()

    # Liaison ou création automatique de projet
    project_id = data.get('project_id')
    if project_id == 'new':
        from models import Project
        from services.admin.waivers import create_pilot_waiver, create_production_waiver
        veh_ids = extract_vehicle_ids_from_prestations(quote.prestations)
        head_ids = extract_head_ids_from_prestations(quote.prestations)
        project = Project(
            name=quote.project_name or f"Projet {quote.reference}",
            production_id=quote.production_id,
            vehicles_to_check=",".join(veh_ids),
            heads_to_check=",".join(head_ids)
        )
        db.session.add(project)
        db.session.flush()
        
        create_pilot_waiver(project.id)
        create_production_waiver(project.id)
        quote.project_id = project.id
    elif project_id:
        quote.project_id = int(project_id)

    db.session.commit()
    return quote


def update_pre_quote(quote_id, data):
    """Met à jour un pré-devis existant."""
    quote = PreQuote.query.get_or_404(quote_id)

    if 'production_id' in data:
        quote.production_id = data['production_id']
    if 'project_name' in data:
        quote.project_name = data['project_name']
    
    if 'prestations' in data or 'tva_rate' in data or 'insurance_rate' in data:
        prestations = data.get('prestations', quote.prestations)
        tva_rate = data.get('tva_rate', quote.tva_rate)
        insurance_rate = data.get('insurance_rate', quote.insurance_rate)
        
        logger.info(f"📊 Mise à jour pré-devis #{quote_id}: insurance_rate reçu={insurance_rate}, tva_rate reçu={tva_rate}")
        
        # Filtrer les anciens items d'assurance si présents
        clean_prestations = [p for p in prestations if p.get('category') != 'insurance']
        
        totals = calculate_totals(clean_prestations, tva_rate=tva_rate, insurance_rate=insurance_rate)
        
        quote.prestations = clean_prestations
        quote.insurance_rate = totals['insurance_rate']
        quote.insurance_amount = totals['insurance_amount']
        quote.total_ht = totals['total_ht']
        quote.tva_rate = totals['tva_rate']
        quote.tva_amount = totals['tva_amount']
        quote.total_ttc = totals['total_ttc']
        
        logger.info(f"📊 Pré-devis #{quote_id} sauvegardé: insurance_rate={quote.insurance_rate}, insurance_amount={quote.insurance_amount}")

    if 'status' in data:
        quote.status = data['status']
    if 'show_discounts' in data:
        quote.show_discounts = data['show_discounts']

    # Liaison ou création automatique de projet
    if 'project_id' in data:
        project_id = data['project_id']
        if project_id == 'new':
            from models import Project
            from services.admin.waivers import create_pilot_waiver, create_production_waiver
            veh_ids = extract_vehicle_ids_from_prestations(quote.prestations)
            head_ids = extract_head_ids_from_prestations(quote.prestations)
            project = Project(
                name=quote.project_name or f"Projet {quote.reference}",
                production_id=quote.production_id,
                vehicles_to_check=",".join(veh_ids),
                heads_to_check=",".join(head_ids)
            )
            db.session.add(project)
            db.session.flush()
            
            create_pilot_waiver(project.id)
            create_production_waiver(project.id)
            quote.project_id = project.id
        elif project_id:
            quote.project_id = int(project_id)
        else:
            quote.project_id = None

    db.session.commit()
    return quote


def create_pre_quote_version(quote_id, note):
    """Crée une nouvelle version (snapshot) pour un pré-devis."""
    quote = PreQuote.query.get_or_404(quote_id)
    
    # Numéro de la version
    last_version = PreQuoteVersion.query.filter_by(pre_quote_id=quote_id).order_by(PreQuoteVersion.version_number.desc()).first()
    next_version = (last_version.version_number + 1) if last_version else 1
    
    # Dossier de sortie pour les PDF des pré-devis
    output_base = current_app.config.get("OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))
    pre_quotes_dir = os.path.join(output_base, "pre-quotes")
    os.makedirs(pre_quotes_dir, exist_ok=True)
    
    # Génération du PDF
    pdf_bytes = get_pre_quote_pdf(quote_id)
    relative_pdf_path = f"pre-quotes/{quote.reference}_v{next_version}.pdf"
    full_pdf_path = os.path.join(output_base, relative_pdf_path)
    
    with open(full_pdf_path, 'wb') as f:
        f.write(pdf_bytes)
        
    # Création du record de version
    version = PreQuoteVersion(
        pre_quote_id=quote.id,
        version_number=next_version,
        prestations=quote.prestations,
        total_ht=quote.total_ht,
        total_ttc=quote.total_ttc,
        insurance_rate=quote.insurance_rate,
        insurance_amount=quote.insurance_amount,
        tva_rate=quote.tva_rate,
        tva_amount=quote.tva_amount,
        pdf_path=relative_pdf_path,
        version_note=note or f"Version {next_version}"
    )
    
    db.session.add(version)
    db.session.commit()
    return version


def restore_pre_quote_version(version_id):
    """Restaure les données d'une version spécifique dans le pré-devis parent."""
    version = PreQuoteVersion.query.get_or_404(version_id)
    quote = version.pre_quote
    
    quote.prestations = version.prestations
    quote.total_ht = version.total_ht
    quote.total_ttc = version.total_ttc
    quote.insurance_rate = version.insurance_rate
    quote.insurance_amount = version.insurance_amount
    quote.tva_rate = version.tva_rate
    quote.tva_amount = version.tva_amount
    
    db.session.commit()
    return quote


def get_pre_quote_pdf(quote_id):
    """Génère le PDF s'il n'existe pas ou le retourne."""
    quote = PreQuote.query.get_or_404(quote_id)

    # Group prestations for the PDF layout
    category_order = ['equipment', 'salary', 'logistics', 'custom']
    by_cat = {}
    intermittent_salaries = []
    for item in (quote.prestations or []):
        if item.get('category') == 'salary':
            intermittent_salaries.append(item)
            continue
        cat = item.get('category', 'custom')
        if cat not in by_cat:
            by_cat[cat] = []
        by_cat[cat].append(item)
        
    grouped_prestations = []
    for cat in category_order:
        if cat in by_cat and by_cat[cat]:
            grouped_prestations.append((cat, by_cat[cat]))
            
    for cat, items in by_cat.items():
        if cat not in category_order and items:
            grouped_prestations.append((cat, items))

    # On pourrait mettre en cache le PDF, mais pour l'instant on le génère à chaque fois ou on le stocke
    # Le plan indique de le stocker.

    html = render_template('pdf/pre_devis.html', quote=quote,
                           grouped_prestations=grouped_prestations,
                           intermittent_salaries=intermittent_salaries,
                           now=datetime.now(),
                           settings={
                               'company_name': AppSetting.get('company_name', 'Belle Vitesse SAS'),
                               'company_address': AppSetting.get('company_address', '33 rue Maurice Gunsbourg, 94200 Ivry-sur-Seine'),
                               'company_phone': AppSetting.get('company_phone', '+33 6 65 51 40 40'),
                               'company_email': AppSetting.get('company_email', 'contact@bellevitesse.com'),
                               'company_siret': AppSetting.get('company_siret', '981 514 040 00014'),
                               'company_vat': AppSetting.get('company_vat', 'FR32981514040'),
                               'bank_iban': AppSetting.get('bank_iban', ''),
                               'bank_bic': AppSetting.get('bank_bic', ''),
                               'company_representative': AppSetting.get('company_representative', 'Simon Maignan'),
                           })

    pdf_bytes = render_pdf_from_template(html, base_url=current_app.root_path)

    return pdf_bytes


def list_pre_quotes():
    """Liste tous les pré-devis triés par date décroissante."""
    return PreQuote.query.order_by(PreQuote.created_at.desc()).all()


def delete_pre_quote(quote_id):
    """Supprime un pré-devis."""
    quote = PreQuote.query.get_or_404(quote_id)
    db.session.delete(quote)
    db.session.commit()
    return True
