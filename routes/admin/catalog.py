from flask import (
    render_template,
    current_app,
    redirect,
    url_for,
    flash,
    send_from_directory,
)
from utils.decorators import require_roles
from services.admin.catalog import get_catalog_data, update_stored_catalog
import os


def init_catalog_routes(app):
    """Initialise les routes pour le catalogue de prix."""

    @app.route("/admin/catalog/pdf", endpoint="admin_catalog_pdf")
    @require_roles("administrator", "manager", "commercial")
    def admin_catalog_pdf():
        """Sert le dernier catalogue (avec ou sans prix) généré en téléchargement."""
        import datetime
        import glob
        from flask import request
        
        prices_param = request.args.get("prices", "1")
        with_prices = prices_param != "0"
        
        output_base = os.getenv('OUTPUT_FOLDER', os.path.join(current_app.root_path, 'output'))
        directory = os.path.join(output_base, "catalog")
        
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
        
        return send_from_directory(
            directory,
            filename,
            as_attachment=True,
            download_name=filename,
            mimetype="application/pdf",
        )

    @app.route("/admin/catalog/update", endpoint="admin_catalog_update")
    @require_roles("administrator", "manager", "commercial")
    def admin_catalog_update():
        """Force la mise à jour du fichier PDF du catalogue."""
        from flask import request
        prices_param = request.args.get("prices", "1")
        with_prices = prices_param != "0"
        
        success, msg = update_stored_catalog(with_prices=with_prices)
        if success:
            flash("Le catalogue PDF a été mis à jour avec succès !", "success")
        else:
            flash(f"Erreur lors de la mise à jour : {msg}", "error")
        return redirect(url_for("admin_catalog_preview", prices=prices_param))

    @app.route("/admin/catalog/preview", endpoint="admin_catalog_preview")
    @require_roles("administrator", "manager", "commercial")
    def admin_catalog_preview():
        """Affiche la version HTML du catalogue pour le développement et la prévisualisation."""
        from flask import request
        prices_param = request.args.get("prices", "1")
        with_prices = prices_param != "0"
        try:
            data = get_catalog_data(with_prices=with_prices)
            return render_template("pdf/catalog.html", **data)
        except Exception as e:
            current_app.logger.error(f"❌ Erreur prévisualisation catalogue : {e}")
            return f"Erreur : {str(e)}", 500
