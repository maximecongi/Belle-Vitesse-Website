from flask import (
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
    send_file,
    jsonify
)
from io import BytesIO
from services.admin import (
    list_productions,
)
from services.admin.pre_quote import (
    list_pre_quotes,
    create_pre_quote,
    update_pre_quote,
    delete_pre_quote,
    get_pre_quote_pdf
)
from models import PreQuote, Production
from utils.decorators import require_roles


def init_pre_quotes_routes(app):
    @app.route("/admin/pre-quotes")
    @require_roles('administrator', 'manager', 'commercial')
    def admin_pre_quotes_list():
        try:
            pre_quotes = list_pre_quotes()
            return render_template("admin/pre_quotes_list.html", pre_quotes=pre_quotes)
        except Exception as e:
            current_app.logger.error(
                f"❌ Erreur lors de la récupération des pré-devis : {e}")
            flash(f"Erreur : {str(e)}", "error")
            return render_template("admin/pre_quotes_list.html", pre_quotes=[])

    @app.route("/admin/pre-quotes/new", methods=["GET", "POST"])
    @require_roles('administrator', 'manager', 'commercial')
    def admin_pre_quote_new():
        if request.method == "POST":
            try:
                # On reçoit du JSON pour les prestations
                data = request.get_json() if request.is_json else request.form.to_dict()
                if not request.is_json:
                    # Traitement spécial si ce n'est pas du JSON (form classique)
                    # Mais l'interface sera probablement du JS/JSON
                    pass

                # user_id à récupérer de la session
                quote = create_pre_quote(data, user_id=None)
                return jsonify({"status": "success", "id": quote.id})
            except Exception as e:
                current_app.logger.error(f"❌ Erreur création pré-devis : {e}")
                return jsonify({"status": "error", "message": str(e)}), 400

        productions = list_productions()
        return render_template("admin/pre_quote_form.html", is_edit=False, productions=productions)

    @app.route("/admin/pre-quotes/<int:quote_id>/edit", methods=["GET", "POST"])
    @require_roles('administrator', 'manager', 'commercial')
    def admin_pre_quote_edit(quote_id):
        quote = PreQuote.query.get_or_404(quote_id)
        if request.method == "POST":
            try:
                data = request.get_json()
                update_pre_quote(quote_id, data)
                return jsonify({"status": "success"})
            except Exception as e:
                current_app.logger.error(
                    f"❌ Erreur modification pré-devis : {e}")
                return jsonify({"status": "error", "message": str(e)}), 400

        productions = list_productions()
        return render_template("admin/pre_quote_form.html", quote=quote, is_edit=True, productions=productions)


    @app.route("/admin/pre-quotes/<int:quote_id>/pdf")
    @require_roles('administrator', 'manager', 'commercial')
    def admin_pre_quote_pdf(quote_id):
        try:
            pdf_bytes = get_pre_quote_pdf(quote_id)
            quote = PreQuote.query.get(quote_id)
            return send_file(
                BytesIO(pdf_bytes),
                mimetype='application/pdf',
                as_attachment=False,
                download_name=f"PreQuote_{quote.reference}.pdf"
            )
        except Exception as e:
            current_app.logger.error(f"❌ Erreur génération PDF : {e}")
            flash(f"Erreur PDF : {str(e)}", "error")
            return redirect(url_for('admin_pre_quotes_list'))

    @app.route("/admin/pre-quotes/<int:quote_id>/delete", methods=["POST"])
    @require_roles('administrator', 'manager', 'commercial')
    def admin_pre_quote_delete(quote_id):
        try:
            delete_pre_quote(quote_id)
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400

    @app.route("/admin/api/pre-quotes/<int:quote_id>/status", methods=["POST"])
    @require_roles('administrator', 'manager', 'commercial')
    def admin_api_quote_status(quote_id):
        try:
            data = request.get_json()
            if not data or 'status' not in data:
                return jsonify({"status": "error", "message": "Missing status"}), 400
            
            update_pre_quote(quote_id, {'status': data['status']})
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400

    @app.route("/admin/api/pre-quotes/all-rates")
    @require_roles('administrator', 'manager', 'commercial')
    def admin_api_all_rates():
        """Récupère tous les tarifs disponibles (équipement, salaires, logistique)."""
        from services.admin.pricing import list_equipment_rates, list_salary_rates, list_logistics_rates

        equipment = list_equipment_rates()
        salaries = list_salary_rates()
        logistics = list_logistics_rates()

        # Formatage simplifié pour le modal
        items = []

        # Equipement
        for cat, data in equipment.items():
            for item in data['items']:
                items.append({
                    "id": item['id'],
                    "category": "equipment",
                    "sub_category": data['label'],
                    "name": item['name'],
                    "price": item['daily_rate'],
                    "unit": "jour(s)"
                })

        # Salaires
        for s in salaries:
            items.append({
                "id": s['id'],
                "category": "salary",
                "sub_category": s['group_name'],
                "name": s['position'],
                "price": s['invoice_10h'],  # Par défaut 10h
                "unit": "jour(s)"
            })

        # Logistique
        for l in logistics:
            items.append({
                "id": l['id'],
                "category": "logistics",
                "sub_category": "Logistique",
                "name": l['item_name'],
                "price": l['daily_rate'],
                "unit": "unité(s)"
            })

        # Option de livraison à distance virtuelle
        items.append({
            "id": "delivery_distance",
            "category": "logistics",
            "sub_category": "Logistique",
            "name": "Livraison/Retour ( distance )",
            "price": 200.00,
            "unit": "km"
        })

        return jsonify(items)
