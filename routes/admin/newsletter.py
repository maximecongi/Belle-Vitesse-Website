from flask import (
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from extensions import csrf
from services.public.newsletter import (
    list_newsletter_subscribers,
    remove_newsletter_subscriber_by_id,
)
from utils.decorators import require_roles
from utils.mailer import send_newsletter_campaign


def init_newsletter_routes(app):
    # ── Newsletter ────────────────────────────────────────────────

    @app.route("/admin/newsletter")
    @require_roles('administrator')
    def admin_newsletter_dashboard():
        try:
            subscribers = list_newsletter_subscribers()
            return render_template("admin/newsletter_dashboard.html", subscribers=subscribers)
        except Exception as e:
            current_app.logger.error(f"❌ Erreur dans le tableau de bord newsletter : {e}")
            flash(
                f"Erreur lors du chargement de la newsletter : {str(e)}", "error")
            return redirect(url_for("admin_dashboard"))

    @app.route("/admin/newsletter/delete/<int:subscriber_id>", methods=["POST"])
    @csrf.exempt
    @require_roles('administrator')
    def admin_newsletter_delete(subscriber_id):
        try:
            if remove_newsletter_subscriber_by_id(subscriber_id):
                flash("Abonné supprimé avec succès.", "success")
            else:
                flash("Abonné non trouvé.", "error")
            return redirect(url_for("admin_newsletter_dashboard"))
        except Exception as e:
            current_app.logger.error(f"❌ Erreur lors de la suppression de l'abonné : {e}")
            flash(f"Erreur lors de la suppression : {str(e)}", "error")
            return redirect(url_for("admin_newsletter_dashboard"))

    @app.route("/admin/newsletter/compose", methods=["GET", "POST"])
    @csrf.exempt
    @require_roles('administrator')
    def admin_newsletter_compose():
        if request.method == "POST":
            subject = request.form.get("subject")
            body = request.form.get("body")

            if not subject or not body:
                flash("Le sujet et le message sont obligatoires.", "error")
                return render_template("admin/newsletter_compose.html", subject=subject, body=body)

            try:
                subscribers = list_newsletter_subscribers()
                if not subscribers:
                    flash("Aucun abonné dans la liste.", "error")
                    return redirect(url_for("admin_newsletter_dashboard"))

                success_count, failed_count = send_newsletter_campaign(
                    subject, body, subscribers)

                if success_count > 0:
                    flash(
                        f"Newsletter envoyée avec succès à {success_count} abonnés.", "success")
                if failed_count > 0:
                    flash(
                        f"Échec de l'envoi pour {failed_count} abonnés.", "warning")

                return redirect(url_for("admin_newsletter_dashboard"))
            except Exception as e:
                current_app.logger.error(
                    f"❌ Erreur lors de l'envoi de la campagne newsletter : {e}")
                flash(f"Erreur lors de l'envoi : {str(e)}", "error")

        return render_template("admin/newsletter_compose.html")

