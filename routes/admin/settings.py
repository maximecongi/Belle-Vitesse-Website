from flask import Blueprint, render_template, request, flash, redirect, url_for, g
from models import AppSetting, db
from utils.decorators import require_roles

settings_bp = Blueprint('admin_settings', __name__, url_prefix='/admin/settings')

@settings_bp.route('/', methods=['GET', 'POST'])
@require_roles('Administrator')
def admin_settings_edit():
    """
    Vue pour éditer les paramètres globaux de l'application (Belle Vitesse).
    """
    # Liste ordonnée des clés de settings pour le formulaire
    setting_keys = [
        ('company_name', 'Nom de la société', 'Nom légal complet'),
        ('company_representative', 'Représentant légal', 'Prénom et NOM du gérant'),
        ('company_siret', 'SIRET', 'Numéro SIRET à 14 chiffres'),
        ('company_address', 'Adresse', 'Siège social au complet'),
        ('company_phone', 'Téléphone', 'Format +33 6 ...'),
        ('company_email', 'Email Contact', 'Email principal'),
        ('company_capital', 'Capital social (€)', 'Capital social de la société (ex: 10 000 €)'),
        ('company_rcs', 'RCS (Ville)', 'Ville d\'immatriculation au RCS (ex: Créteil)'),
        ('host_name', 'Nom de l\'hébergeur', 'Nom de la société d\'hébergement (ex: Infomaniak)'),
        ('host_address', 'Adresse de l\'hébergeur', 'Adresse complète de l\'hébergeur'),
        ('bank_iban', 'IBAN', 'Coordonnées bancaires pour les virements'),
        ('bank_bic', 'BIC / SWIFT', 'Code banque'),
        ('delivery_base_distance', 'Distance livraison base (km)', 'Seuil forfait de base (ex: 100)'),
        ('delivery_base_price', 'Tarif livraison base (€)', 'Forfait de base (ex: 200)'),
        ('delivery_high_rate', 'Tarif kilométrique sup. (€/km)', 'Tarif simple course (ex: 0.50)'),
    ]

    if request.method == 'POST':
        for key, label, help_text in setting_keys:
            val = request.form.get(key)
            if val is not None:
                AppSetting.set(key, val.strip())
        
        flash("Les paramètres ont été mis à jour avec succès.", "success")
        return redirect(url_for('admin_settings.admin_settings_edit'))

    # Récupération des valeurs actuelles
    settings_data = {key: AppSetting.get(key, '') for key, label, help_text in setting_keys}

    return render_template('admin/settings.html', 
                           setting_keys=setting_keys, 
                           settings_data=settings_data)
