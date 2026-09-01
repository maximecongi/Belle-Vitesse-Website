from datetime import datetime, timezone
from flask import g, request, session, has_request_context
from extensions import cache
from models import AppSetting, User, db
from utils.i18n import t, ts, alt_url, DEFAULT_LANG
from utils.database import get_vehicles, get_heads, get_grips_categories
from services.admin.status_mapping import (
    CHECKPOINT_STATUS_MAP,
    INSPECTION_STATUS_MAP,
    format_checkpoint_status,
    format_inspection_status,
    get_checkpoint_key,
    get_inspection_key,
)


def init_context_processors(app):
    """Enregistre les processeurs de contexte globaux pour les templates Jinja2."""
    @app.context_processor
    def inject_globals():
        import os
        launch_mode = os.getenv("LAUNCH_MODE") == "true"

        # Calculer la date de dernière mise à jour de la politique de confidentialité
        try:
            template_path = os.path.join(app.root_path, 'templates', 'public', 'privacy-policy.html')
            if os.path.exists(template_path):
                mtime = os.path.getmtime(template_path)
                privacy_date = datetime.fromtimestamp(mtime)
            else:
                privacy_date = datetime.now()
        except Exception:
            privacy_date = datetime.now()

        lang = g.get('lang', DEFAULT_LANG) if has_request_context() else DEFAULT_LANG
        months_fr = {
            1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril", 5: "Mai", 6: "Juin",
            7: "Juillet", 8: "Août", 9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"
        }
        months_en = {
            1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
            7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"
        }
        months = months_fr if lang == 'fr' else months_en
        privacy_last_update = f"{months[privacy_date.month]} {privacy_date.year}"

        if not has_request_context():
            return {
                "now": datetime.now(timezone.utc),
                "is_admin": False,
                "lang": DEFAULT_LANG,
                "t": t, "ts": ts, "alt_url": alt_url,
                "launch_mode": launch_mode,
                "privacy_last_update": privacy_last_update,
            }

        # Évite les appels DB lourds pour les pages d'erreur et les pages d'authentification
        # afin de prévenir les pannes en cascade et les blocages au login.
        is_auth_page = request.path in ('/admin/login', '/admin/logout') or request.path.startswith('/admin/auth/')
        if getattr(g, '_rendering_error', False) or is_auth_page:
            return {
                "now": datetime.now(timezone.utc),
                "is_admin": request.path.startswith('/admin'),
                "lang": g.get('lang', DEFAULT_LANG),
                "t": t, "ts": ts, "alt_url": alt_url,
                "launch_mode": launch_mode,
                "privacy_last_update": privacy_last_update,
            }

        is_admin = request.path.startswith('/admin')
        lang = g.get('lang', DEFAULT_LANG)

        def _safe_setting_float(key, default):
            try:
                val = AppSetting.get(key)
                return float(val) if val is not None else float(default)
            except (ValueError, TypeError):
                return float(default)

        # Variables globales de base
        ctx = {
            "now": datetime.now(timezone.utc),
            "is_admin": is_admin,
            "lang": lang,
            "t": t,
            "ts": ts,
            "alt_url": alt_url,
            "launch_mode": launch_mode,
            "privacy_last_update": privacy_last_update,
            "company_name": AppSetting.get("company_name", "Belle Vitesse SAS"),
            "company_representative": AppSetting.get("company_representative", "Simon Maignan"),
            "company_siret": AppSetting.get("company_siret", "981 514 040 00014"),
            "company_address": AppSetting.get("company_address", "33 rue Maurice Gunsbourg, 94200 Ivry-sur-Seine, France"),
            "company_phone": AppSetting.get("company_phone", "+33 6 65 51 40 40"),
            "company_email": AppSetting.get("company_email", "contact@bellevitesse.com"),
            "company_vat": AppSetting.get("company_vat", "FR32981514040"),
            "company_capital": AppSetting.get("company_capital", "10 000 €"),
            "company_rcs": AppSetting.get("company_rcs", "Créteil"),
            "host_name": AppSetting.get("host_name", "Infomaniak Network SA"),
            "host_address": AppSetting.get("host_address", "Rue Eugène-Marziano 25, 1227 Genève, Suisse"),
            "bank_iban": AppSetting.get("bank_iban", ""),
            "bank_bic": AppSetting.get("bank_bic", ""),
            "DELIVERY_CONFIG": {
                "base_distance": _safe_setting_float("delivery_base_distance", 100),
                "base_price": _safe_setting_float("delivery_base_price", 200),
                "high_rate": _safe_setting_float("delivery_high_rate", 0.5)
            },
            "PRE_QUOTE_CAT_MAP": {
                "equipment": "Équipement",
                "salary": "Salaire",
                "logistics": "Logistique",
                "insurance": "Assurances",
                "custom": "Autre"
            },
            # Utilitaires de mapping de statuts
            "get_inspection_key": get_inspection_key,
            "get_checkpoint_key": get_checkpoint_key,
            "format_inspection_status": format_inspection_status,
            "format_checkpoint_status": format_checkpoint_status,
            "INSPECTION_STATUS_MAP": INSPECTION_STATUS_MAP,
            "CHECKPOINT_STATUS_MAP": CHECKPOINT_STATUS_MAP,
        }

        def _load_db_context(is_admin):
            """Charge les données dynamiques depuis la base de données pour le contexte."""
            if is_admin:
                user_id = session.get('admin_user_id')
                session_role = session.get('admin_user_role')
                user_dict = None
                if user_id:
                    role_cache_part = session_role.lower() if session_role else "default"
                    cache_key = f"user_v3:{user_id}:{role_cache_part}"
                    user_dict = cache.get(cache_key)

                    if not user_dict or not isinstance(user_dict, dict) or "role_lower" not in user_dict:
                        user_obj = db.session.get(User, user_id)
                        if user_obj:
                            from models.user import ROLE_TRANSLATION
                            from utils.decorators import normalize_role
                            effective_role = session_role if session_role else (user_obj.role if user_obj.role else "Technicien")
                            role_lower = normalize_role(effective_role)
                            role_display = ROLE_TRANSLATION.get(role_lower, effective_role)
                            # Stocke un dict, pas un objet ORM (évite DetachedInstanceError avec Redis)
                            user_dict = {
                                "id": user_obj.id,
                                "firstname": user_obj.firstname,
                                "lastname": user_obj.lastname,
                                "role": role_display,
                                "role_lower": role_lower,
                                "is_admin": role_lower in ('administrateur', 'super administrateur', 'administrator', 'super administrator'),
                                "db_role": user_obj.role or "Technicien",
                                "mail": user_obj.mail or "",
                                "job": getattr(user_obj, 'job', '') or "",
                                "phone": getattr(user_obj, 'phone', '') or "",
                            }
                            cache.set(cache_key, user_dict, timeout=300)

                from models.user import ROLE_TRANSLATION
                from utils.decorators import normalize_role
                fallback_role = session.get('admin_user_role', 'Technicien')
                fallback_role_lower = normalize_role(fallback_role)
                fallback_role_display = ROLE_TRANSLATION.get(fallback_role_lower, fallback_role)
                return {
                    "current_user": user_dict if user_dict else {
                        "id": session.get('admin_user_id', 0),
                        "firstname": session.get('admin_user_firstname', ''),
                        "lastname": session.get('admin_user_lastname', ''),
                        "role": fallback_role_display,
                        "role_lower": fallback_role_lower,
                        "is_admin": fallback_role_lower in ('administrateur', 'super administrateur', 'administrator', 'super administrator'),
                        "mail": "",
                        "job": "",
                        "phone": ""
                    },
                    "vehicles": get_vehicles(),
                }
            else:
                return {
                    "vehicles": get_vehicles(),
                    "heads": get_heads(),
                    "grips_categories": get_grips_categories(),
                }

        # Tentative de chargement avec retry en cas d'erreur DB
        for attempt in range(2):
            try:
                ctx.update(_load_db_context(is_admin))
                break
            except Exception as e:
                if attempt == 0:
                    app.logger.warning(
                        f"⚠️ Erreur DB dans le context processor (nouvelle tentative) : {e}")
                    continue
                app.logger.error(
                    f"❌ Erreur DB dans le context processor (abandon) : {e}")
                if is_admin:
                    ctx["current_user"] = {
                        "firstname": "", "lastname": "", "role": "User", "role_lower": "user", "is_admin": False}
                    ctx["vehicles"] = []
                else:
                    ctx.update({"vehicles": [], "heads": [],
                               "grips_categories": []})

        return ctx
