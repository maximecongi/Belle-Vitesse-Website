import os
from datetime import datetime
from decimal import Decimal
from flask import current_app, render_template
from models import PreQuote, db, AppSetting, Production
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


def calculate_totals(prestations, tva_rate=20.00, insurance_rate=10.00):
    """Calcule les totaux HT, TVA et TTC pour une liste de prestations."""
    total_rental_ht = Decimal('0.00')
    tva_rate = Decimal(str(tva_rate))
    insurance_rate = Decimal(str(insurance_rate))

    # On calcule la base de location HT (en excluant d'éventuels anciens items 'insurance')
    for item in prestations:
        if item.get('category') == 'insurance':
            continue
        qty = Decimal(str(item.get('quantity', 0)))
        price = Decimal(str(item.get('unit_price', 0)))
        discount = Decimal(str(item.get('discount_rate', 0)))
        
        line_total = (qty * price) * (Decimal('1') - (discount / Decimal('100')))
        item['total'] = float(line_total)
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

    if 'status' in data:
        quote.status = data['status']
    if 'show_discounts' in data:
        quote.show_discounts = data['show_discounts']

    db.session.commit()
    return quote


def get_pre_quote_pdf(quote_id):
    """Génère le PDF s'il n'existe pas ou le retourne."""
    quote = PreQuote.query.get_or_404(quote_id)

    # On pourrait mettre en cache le PDF, mais pour l'instant on le génère à chaque fois ou on le stocke
    # Le plan indique de le stocker.

    html = render_template('pdf/pre_devis.html', quote=quote,
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
