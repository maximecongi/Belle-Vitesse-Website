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
    @require_roles("administrator", "manager")
    def admin_catalog_pdf():
        """Sert le dernier catalogue de prix généré en téléchargement."""
        import datetime
        filename = (
            f"Belle_Vitesse_CATALOGUE_{datetime.datetime.now().strftime('%Y%m')}.pdf"
        )
        
        output_base = os.getenv('OUTPUT_FOLDER', os.path.join(current_app.root_path, 'output'))
        directory = os.path.join(output_base, "catalog")
        file_path = os.path.join(directory, filename)
        
        if not os.path.exists(file_path):
            # Si le fichier du mois n'existe pas, on le génère
            success, msg = update_stored_catalog()
            if not success:
                return f"Erreur génération initiale : {msg}", 500
        
        return send_from_directory(
            directory,
            filename,
            as_attachment=True,
            download_name=filename,
            mimetype="application/pdf",
        )

    @app.route("/admin/catalog/update", endpoint="admin_catalog_update")
    @require_roles("administrator", "manager")
    def admin_catalog_update():
        """Force la mise à jour du fichier PDF du catalogue."""
        success, msg = update_stored_catalog()
        if success:
            flash("Le catalogue PDF a été mis à jour avec succès !", "success")
        else:
            flash(f"Erreur lors de la mise à jour : {msg}", "error")
        return redirect(url_for("admin_catalog_preview"))

    @app.route("/admin/catalog/preview", endpoint="admin_catalog_preview")
    @require_roles("administrator", "manager")
    def admin_catalog_preview():
        """Affiche la version HTML du catalogue pour le développement et la prévisualisation."""
        try:
            data = get_catalog_data()
            return render_template("pdf/catalog.html", **data)
        except Exception as e:
            current_app.logger.error(f"❌ Erreur prévisualisation catalogue : {e}")
            return f"Erreur : {str(e)}", 500
