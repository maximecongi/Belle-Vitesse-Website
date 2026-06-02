from flask import (
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
    send_file,
    jsonify,
    session
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
    get_pre_quote_pdf,
    create_pre_quote_version,
    restore_pre_quote_version
)
from models import PreQuote, Production, Project, PreQuoteVersion
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
                user_id = session.get('admin_user_id')
                quote = create_pre_quote(data, user_id=user_id)
                return jsonify({"status": "success", "id": quote.id})
            except Exception as e:
                current_app.logger.error(f"❌ Erreur création pré-devis : {e}")
                return jsonify({"status": "error", "message": str(e)}), 400

        productions = list_productions()
        projects = Project.query.filter(Project.deleted_at == None).order_by(Project.departure_date.desc(), Project.name).all()
        return render_template("admin/pre_quote_form.html", is_edit=False, productions=productions, projects=projects)

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

        # Enrichissement des prestations de type salaire pour compatibilité
        from models import SalaryRate
        try:
            all_salaries = SalaryRate.query.all()
            salary_by_full_name = {}
            salary_by_position_only = {}
            
            from services.admin.pricing import _make_renfort_rate_dict
            all_salaries_dicts = []
            for s in all_salaries:
                all_salaries_dicts.append(s.to_dict())
                if s.annexe == "Annexe 1":
                    all_salaries_dicts.append(_make_renfort_rate_dict(s))

            for s_dict in all_salaries_dicts:
                if not s_dict.get('position'):
                    continue
                pos_lower = s_dict['position'].lower().strip()
                annexe_lower = s_dict['annexe'].lower().strip() if s_dict['annexe'] else ""
                full_name = f"{pos_lower} ({annexe_lower})" if annexe_lower else pos_lower
                
                salary_by_full_name[full_name] = s_dict
                if pos_lower not in salary_by_position_only:
                    salary_by_position_only[pos_lower] = s_dict

            enriched = []
            for item in (quote.prestations or []):
                new_item = dict(item)
                if new_item.get('category') == 'salary':
                    desc_lower = new_item.get('description', '').lower().strip()
                    matched_rate = None
                    if desc_lower in salary_by_full_name:
                        matched_rate = salary_by_full_name[desc_lower]
                    elif desc_lower in salary_by_position_only:
                        matched_rate = salary_by_position_only[desc_lower]
                    else:
                        for full_name, rate in salary_by_full_name.items():
                            if full_name in desc_lower or desc_lower in full_name:
                                matched_rate = rate
                                break
                    
                    if matched_rate:
                        if 'annexe' not in new_item:
                            new_item['annexe'] = matched_rate['annexe']
                        if 'rates' not in new_item:
                            new_item['rates'] = {
                                "10h": float(matched_rate['inter_10h']) if matched_rate['inter_10h'] else 0.0,
                                "8h": float(matched_rate['inter_8h']) if matched_rate['inter_8h'] else 0.0
                            }
                        if 'salary_rate_type' not in new_item:
                            old_type = new_item.get('salary_rate_type', '')
                            if '10h' in old_type:
                                new_item['salary_rate_type'] = '10h'
                            elif '8h' in old_type:
                                new_item['salary_rate_type'] = '8h'
                            else:
                                price = new_item.get('unit_price', 0.0)
                                guessed = '10h'
                                for k, v in new_item['rates'].items():
                                    if abs(float(v) - float(price)) < 0.01:
                                        guessed = k
                                        break
                                new_item['salary_rate_type'] = guessed
                    else:
                        if 'annexe' not in new_item:
                            desc = new_item.get('description', '')
                            for possible in ['Facture', 'Annexe 1', 'Annexe 3', 'Annexe 1 renfort', 'USPA', 'USPA renfort', 'Court-métrage', 'Publicité']:
                                if f"({possible})" in desc:
                                    new_item['annexe'] = possible
                                    break
                            else:
                                new_item['annexe'] = 'Facture'
                        if 'rates' not in new_item:
                            new_item['rates'] = {
                                "10h": new_item.get('unit_price', 0.0),
                                "8h": 0.0
                            }
                        if 'salary_rate_type' not in new_item:
                            new_item['salary_rate_type'] = '10h'
                enriched.append(new_item)
            quote.prestations = enriched
        except Exception as e:
            current_app.logger.error(f"❌ Erreur lors de l'enrichissement des salaires : {e}")

        productions = list_productions()
        projects = Project.query.filter(Project.deleted_at == None).order_by(Project.departure_date.desc(), Project.name).all()
        return render_template("admin/pre_quote_form.html", quote=quote, is_edit=True, productions=productions, projects=projects)


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
            data = request.get_json() or {}
            if not data or 'status' not in data:
                return jsonify({"status": "error", "message": "Missing status"}), 400
            
            update_pre_quote(quote_id, {'status': data['status']})
            
            # Versionner automatiquement si le statut change vers envoyé, accepté, refusé
            new_status = data['status']
            if new_status in ['sent', 'accepted', 'rejected']:
                note = data.get('note')
                if not note:
                    status_labels = {
                        'sent': 'Envoyé',
                        'accepted': 'Accepté',
                        'rejected': 'Refusé'
                    }
                    note = f"Changement de statut en {status_labels.get(new_status, new_status)}"
                create_pre_quote_version(quote_id, note)
                
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400

    @app.route("/admin/api/pre-quotes/<int:quote_id>/version", methods=["POST"])
    @require_roles('administrator', 'manager', 'commercial')
    def admin_api_quote_create_version(quote_id):
        try:
            data = request.get_json() or {}
            note = data.get('note', '')
            version = create_pre_quote_version(quote_id, note)
            return jsonify({"status": "success", "version_number": version.version_number})
        except Exception as e:
            current_app.logger.error(f"❌ Erreur création version pré-devis : {e}")
            return jsonify({"status": "error", "message": str(e)}), 400

    @app.route("/admin/api/pre-quotes/version/<int:version_id>/restore", methods=["POST"])
    @require_roles('administrator', 'manager', 'commercial')
    def admin_api_quote_restore_version(version_id):
        try:
            quote = restore_pre_quote_version(version_id)
            return jsonify({"status": "success", "quote_id": quote.id})
        except Exception as e:
            current_app.logger.error(f"❌ Erreur restauration version pré-devis : {e}")
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
            name_with_annexe = f"{s['position']} ({s['annexe']})" if s['annexe'] else s['position']
            price_10h = float(s['inter_10h']) if s['inter_10h'] else 0.0
            price_8h = float(s['inter_8h']) if s['inter_8h'] else 0.0
            items.append({
                "id": s['id'],
                "category": "salary",
                "sub_category": s['group_name'],
                "name": name_with_annexe,
                "position": s['position'],
                "annexe": s['annexe'],
                "price": price_10h,  # Par défaut 10h
                "unit": "jour(s)",
                "rates": {
                    "10h": price_10h,
                    "8h": price_8h
                }
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
