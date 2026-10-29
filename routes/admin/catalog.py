from flask import (
    Blueprint,
    render_template,
    current_app,
    redirect,
    url_for,
    flash,
    send_from_directory,
    request,
)
from utils.decorators import require_roles
from services.admin.catalog import (
    get_catalog_data,
    update_stored_catalog,
    get_catalog_directory,
    get_latest_catalog_info,
)
import os
import glob


catalog_bp = Blueprint('admin_catalog', __name__, url_prefix='/admin')
"""Initialise les routes pour le catalogue de prix."""

@catalog_bp.route("/catalog/pdf", endpoint="admin_catalog_pdf")
@require_roles("administrator", "manager", "commercial")
def admin_catalog_pdf():
    """Sert le dernier catalogue (avec ou sans prix) généré en téléchargement."""
    prices_param = request.args.get("prices", "1")
    with_prices = prices_param != "0"
    
    directory = get_catalog_directory()
    prefix = "Belle_Vitesse_CATALOGUE_P_" if with_prices else "Belle_Vitesse_CATALOGUE_WP_"
    pattern = os.path.join(directory, f"{prefix}*.pdf")
    matching_files = glob.glob(pattern)
    
    if not matching_files:
        # Si aucun fichier catalogue n'existe, on le génère
        success, msg = update_stored_catalog(with_prices=with_prices)
        if not success:
            return f"Erreur génération initiale : {msg}", 500
        
        matching_files = glob.glob(pattern)
        if not matching_files:
            return "Erreur : Fichier catalogue généré introuvable.", 500
    
    # Trier les fichiers par date de modification (mtime) décroissante pour prendre le plus récent
    matching_files.sort(key=os.path.getmtime, reverse=True)
    
    # Servir le fichier correspondant trouvé
    file_path = matching_files[0]
    filename = os.path.basename(file_path)
    
    response = send_from_directory(
        directory,
        filename,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf",
        max_age=0,
    )
    # Empêcher tout cache client (navigateur ou proxy) pour garantir le téléchargement immédiat de la dernière version
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@catalog_bp.route("/catalog/update", endpoint="admin_catalog_update")
@require_roles("administrator", "manager", "commercial")
def admin_catalog_update():
    """Force la mise à jour du fichier PDF du catalogue."""
    prices_param = request.args.get("prices", "1")
    with_prices = prices_param != "0"
    
    success, msg = update_stored_catalog(with_prices=with_prices)
    if success:
        flash("Le catalogue PDF a été mis à jour avec succès !", "success")
    else:
        flash(f"Erreur lors de la mise à jour : {msg}", "error")
    return redirect(url_for("admin_catalog.admin_catalog_preview", prices=prices_param))

@catalog_bp.route("/catalog/preview", endpoint="admin_catalog_preview")
@require_roles("administrator", "manager", "commercial")
def admin_catalog_preview():
    """Affiche la version HTML du catalogue pour le développement et la prévisualisation."""
    prices_param = request.args.get("prices", "1")
    with_prices = prices_param != "0"
    try:
        data = get_catalog_data(with_prices=with_prices)
        latest_info = get_latest_catalog_info(with_prices=with_prices)
        data["catalog_timestamp"] = latest_info["timestamp"]
        data["catalog_filename"] = latest_info["filename"]
        data["catalog_updated_at"] = latest_info["updated_at"]
        return render_template("pdf/catalog.html", **data)
    except Exception as e:
        current_app.logger.error(f"❌ Erreur prévisualisation catalogue : {e}")
        return f"Erreur : {str(e)}", 500

def init_catalog_routes(app):
    """Enregistre le blueprint admin_catalog (compatibilité ascendante)."""
    if "admin_catalog" not in app.blueprints:
        app.register_blueprint(catalog_bp)
