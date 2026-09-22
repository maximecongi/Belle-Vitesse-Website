import os
from functools import lru_cache
from datetime import datetime, timezone
from flask import g, request, session, has_request_context
from extensions import cache
from models import AppSetting, User, db
from models.user import ROLE_TRANSLATION
from utils.decorators import normalize_role
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

MONTHS_FR = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril", 5: "Mai", 6: "Juin",
    7: "Juillet", 8: "Août", 9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"
}
MONTHS_EN = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"
}

DEFAULT_SETTINGS = {
    "company_name": "Belle Vitesse SAS",
    "company_representative": "Simon Maignan",
    "company_siret": "981 514 040 00014",
    "company_address": "39 rue Maurice Gunsbourg, 94200 Ivry-sur-Seine",
    "company_phone": "+33 6 65 51 40 40",
    "company_email": "contact@bellevitesse.com",
    "company_vat": "FR32981514040",
    "company_capital": "10 000 €",
    "company_rcs": "Créteil",
    "host_name": "Infomaniak Network SA",
    "host_address": "Rue Eugène-Marziano 25, 1227 Genève, Suisse",
    "bank_iban": "",
    "bank_bic": "",
    "delivery_base_distance": "100",
    "delivery_base_price": "200",
    "delivery_high_rate": "0.5",
}

ROLE_PERMISSIONS = {
    'technicien': {
        'sections': {'dashboard', 'departs', 'retours', 'flotte', 'tools'},
        'nav': {
            'dashboard', 'checkouts',
            'checkins', 'incidents', 'fleet', 'signature'
        },
    },
    'user': {
        'sections': {'dashboard', 'departs', 'retours', 'flotte', 'tools'},
        'nav': {
            'dashboard', 'checkouts',
            'checkins', 'incidents', 'fleet', 'signature'
        },
    },
    'commercial': {
        'sections': {'dashboard', 'tournages', 'flotte', 'admin', 'tools'},
        'nav': {
            'dashboard', 'projects', 'archives', 'booking',
            'productions', 'contacts', 'fleet', 'pricing', 'catalog_pdf', 'mcp_connector',
            'calendar', 'signature'
        },
    },
    'manager': {
        'sections': {'dashboard', 'tournages', 'departs', 'retours', 'flotte', 'admin', 'tools'},
        'nav': {
            'dashboard', 'projects', 'archives', 'booking',
            'productions', 'contacts', 'checkouts', 'production_waivers',
            'pilot_waivers', 'checkins', 'incidents', 'fleet', 'users', 'pricing',
            'catalog_pdf', 'mcp_connector', 'calendar', 'newsletter',
            'signature', 'catalog_update'
        },
    },
    'administrateur': {
        'sections': {'dashboard', 'tournages', 'departs', 'retours', 'flotte', 'admin', 'tools'},
        'nav': {
            'dashboard', 'projects', 'archives', 'booking',
            'productions', 'contacts', 'checkouts', 'production_waivers',
            'pilot_waivers', 'checkins', 'incidents', 'fleet', 'vehicles', 'checkpoints',
            'users', 'pricing', 'catalog_pdf', 'mcp_connector', 'settings', 'calendar',
            'newsletter', 'signature', 'docs', 'api_docs', 'catalog_update'
        },
    },
    'administrator': {
        'sections': {'dashboard', 'tournages', 'departs', 'retours', 'flotte', 'admin', 'tools'},
        'nav': {
            'dashboard', 'projects', 'archives', 'booking',
            'productions', 'contacts', 'checkouts', 'production_waivers',
            'pilot_waivers', 'checkins', 'incidents', 'fleet', 'vehicles', 'checkpoints',
            'users', 'pricing', 'catalog_pdf', 'mcp_connector', 'settings', 'calendar',
            'newsletter', 'signature', 'docs', 'api_docs', 'catalog_update'
        },
    },
    'super administrateur': {'sections': {'all'}, 'nav': {'all'}},
    'super administrator': {'sections': {'all'}, 'nav': {'all'}},
}


def resolve_user_role(current_user_dict: dict, session_role: str = "") -> str:
    """Résolution déterministe du rôle utilisateur pour les permissions d'interface."""
    raw_role = ""
    if current_user_dict:
        raw_role = current_user_dict.get(
            'role_lower') or current_user_dict.get('role') or ""
    if not raw_role and session_role:
        raw_role = session_role
    raw_role = str(raw_role).lower().strip()

    if 'super' in raw_role:
        return 'super administrateur'
    elif 'admin' in raw_role:
        return 'administrateur'
    elif 'manager' in raw_role:
        return 'manager'
    elif 'commercial' in raw_role:
        return 'commercial'
    elif raw_role in ('technicien', 'user'):
        return 'technicien'
    elif current_user_dict and current_user_dict.get('is_admin'):
        return 'super administrateur'
    else:
        s_lower = str(session_role or '').lower()
        if 'super' in s_lower:
            return 'super administrateur'
        elif 'admin' in s_lower:
            return 'administrateur'
        return 'technicien'


def get_user_permissions(user_role: str, is_admin: bool = False) -> dict:
    """Retourne la matrice des permissions (sections et nav) pour un rôle."""
    if is_admin or user_role in ('super administrateur', 'super administrator'):
        return {'sections': {'all'}, 'nav': {'all'}}
    return ROLE_PERMISSIONS.get(user_role, ROLE_PERMISSIONS['technicien'])


@lru_cache(maxsize=1)
def _get_privacy_date(template_path: str) -> datetime:
    """Récupère la date de modification du template de politique de confidentialité (mise en cache)."""
    try:
        if os.path.exists(template_path):
            mtime = os.path.getmtime(template_path)
            return datetime.fromtimestamp(mtime)
    except Exception:
        pass
    return datetime.now()


def _safe_float(val, default):
    """Convertit une valeur en float de manière sécurisée."""
    try:
        return float(val) if val is not None else float(default)
    except (ValueError, TypeError):
        return float(default)


def get_company_context():
    """
    Charge et retourne les paramètres de la société depuis AppSetting (avec cache Redis / DB).
    Utilisé pour injecter de manière garantie les coordonnées de la société dans tous les templates
    (ERP admin, site public, e-mails transactionnels, exports PDF).
    """
    try:
        settings = AppSetting.get_all_as_dict(DEFAULT_SETTINGS)
    except Exception:
        settings = DEFAULT_SETTINGS.copy()

    return {
        "company_name": settings.get("company_name", DEFAULT_SETTINGS["company_name"]),
        "company_representative": settings.get("company_representative", DEFAULT_SETTINGS["company_representative"]),
        "company_siret": settings.get("company_siret", DEFAULT_SETTINGS["company_siret"]),
        "company_address": settings.get("company_address", DEFAULT_SETTINGS["company_address"]),
        "company_phone": settings.get("company_phone", DEFAULT_SETTINGS["company_phone"]),
        "company_email": settings.get("company_email", DEFAULT_SETTINGS["company_email"]),
        "company_vat": settings.get("company_vat", DEFAULT_SETTINGS["company_vat"]),
        "company_capital": settings.get("company_capital", DEFAULT_SETTINGS["company_capital"]),
        "company_rcs": settings.get("company_rcs", DEFAULT_SETTINGS["company_rcs"]),
        "host_name": settings.get("host_name", DEFAULT_SETTINGS["host_name"]),
        "host_address": settings.get("host_address", DEFAULT_SETTINGS["host_address"]),
        "bank_iban": settings.get("bank_iban", ""),
        "bank_bic": settings.get("bank_bic", ""),
        "DELIVERY_CONFIG": {
            "base_distance": _safe_float(settings.get("delivery_base_distance"), 100),
            "base_price": _safe_float(settings.get("delivery_base_price"), 200),
            "high_rate": _safe_float(settings.get("delivery_high_rate"), 0.5)
        },
    }


def init_context_processors(app):
    """Enregistre les processeurs de contexte globaux pour les templates Jinja2."""
    template_path = os.path.join(
        app.root_path, 'templates', 'public', 'privacy-policy.html')

    def asset_version(filename: str) -> str:
        """Retourne l'horodatage mtime du fichier statique pour le cache-busting automatique."""
        try:
            s_folder = app.static_folder or os.path.join(
                app.root_path, 'static')
            target = os.path.join(s_folder, filename)
            if os.path.exists(target):
                return str(int(os.path.getmtime(target)))
        except Exception:
            pass
        return os.getenv("STATIC_VERSION", "2.3")

    def asset_url(filename: str) -> str:
        """Génère l'URL d'un asset statique avec le paramètre ?v=<mtime> automatique."""
        from flask import url_for
        v = asset_version(filename)
        return f"{url_for('static', filename=filename)}?v={v}"

    @app.context_processor
    def inject_globals():
        launch_mode = os.getenv("LAUNCH_MODE") == "true"
        privacy_date = _get_privacy_date(template_path)

        lang = g.get(
            'lang', DEFAULT_LANG) if has_request_context() else DEFAULT_LANG
        months = MONTHS_FR if lang == 'fr' else MONTHS_EN
        privacy_last_update = f"{months[privacy_date.month]} {privacy_date.year}"

        company_ctx = get_company_context()

        if not has_request_context():
            base_ctx = {
                "now": datetime.now(timezone.utc),
                "is_admin": False,
                "lang": DEFAULT_LANG,
                "t": t, "ts": ts, "alt_url": alt_url,
                "launch_mode": launch_mode,
                "privacy_last_update": privacy_last_update,
                "asset_version": asset_version,
                "asset_url": asset_url,
                "user_role": "technicien",
                "user_perms": ROLE_PERMISSIONS['technicien'],
                "has_section": lambda s: 'all' in ROLE_PERMISSIONS['technicien']['sections'] or s in ROLE_PERMISSIONS['technicien']['sections'],
                "has_item": lambda i: 'all' in ROLE_PERMISSIONS['technicien']['nav'] or i in ROLE_PERMISSIONS['technicien']['nav'],
            }
            base_ctx.update(company_ctx)
            return base_ctx

        # Évite les appels DB lourds pour les pages d'erreur et les pages d'authentification
        # afin de prévenir les pannes en cascade et les blocages au login.
        is_auth_page = request.path in (
            '/admin/login', '/admin/logout') or request.path.startswith('/admin/auth/')
        if getattr(g, '_rendering_error', False) or is_auth_page:
            base_ctx = {
                "now": datetime.now(timezone.utc),
                "is_admin": request.path.startswith('/admin'),
                "lang": g.get('lang', DEFAULT_LANG),
                "t": t, "ts": ts, "alt_url": alt_url,
                "launch_mode": launch_mode,
                "privacy_last_update": privacy_last_update,
                "asset_version": asset_version,
                "asset_url": asset_url,
                "user_role": "technicien",
                "user_perms": ROLE_PERMISSIONS['technicien'],
                "has_section": lambda s: 'all' in ROLE_PERMISSIONS['technicien']['sections'] or s in ROLE_PERMISSIONS['technicien']['sections'],
                "has_item": lambda i: 'all' in ROLE_PERMISSIONS['technicien']['nav'] or i in ROLE_PERMISSIONS['technicien']['nav'],
            }
            base_ctx.update(company_ctx)
            return base_ctx

        is_admin = request.path.startswith('/admin')
        lang = g.get('lang', DEFAULT_LANG)

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
            "asset_version": asset_version,
            "asset_url": asset_url,
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
            "user_role": "technicien",
            "user_perms": ROLE_PERMISSIONS['technicien'],
            "has_section": lambda s: 'all' in ROLE_PERMISSIONS['technicien']['sections'] or s in ROLE_PERMISSIONS['technicien']['sections'],
            "has_item": lambda i: 'all' in ROLE_PERMISSIONS['technicien']['nav'] or i in ROLE_PERMISSIONS['technicien']['nav'],
        }
        ctx.update(company_ctx)

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
                            effective_role = session_role if session_role else (
                                user_obj.role if user_obj.role else "Technicien")
                            role_lower = normalize_role(effective_role)
                            role_display = ROLE_TRANSLATION.get(
                                role_lower, effective_role)
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

                fallback_role = session.get('admin_user_role', 'Technicien')
                fallback_role_lower = normalize_role(fallback_role)
                fallback_role_display = ROLE_TRANSLATION.get(
                    fallback_role_lower, fallback_role)
                current_user = user_dict if user_dict else {
                    "id": session.get('admin_user_id', 0),
                    "firstname": session.get('admin_user_firstname', ''),
                    "lastname": session.get('admin_user_lastname', ''),
                    "role": fallback_role_display,
                    "role_lower": fallback_role_lower,
                    "is_admin": fallback_role_lower in ('administrateur', 'super administrateur', 'administrator', 'super administrator'),
                    "mail": "",
                    "job": "",
                    "phone": ""
                }

                user_role = resolve_user_role(current_user, session_role)
                perms = get_user_permissions(
                    user_role, is_admin=current_user.get("is_admin", False))

                return {
                    "current_user": current_user,
                    "user_role": user_role,
                    "user_perms": perms,
                    "has_section": lambda s: 'all' in perms['sections'] or s in perms['sections'],
                    "has_item": lambda i: 'all' in perms['nav'] or i in perms['nav'],
                    "vehicles": get_vehicles(),
                }
            else:
                return {
                    "user_role": "technicien",
                    "user_perms": ROLE_PERMISSIONS['technicien'],
                    "has_section": lambda s: 'all' in ROLE_PERMISSIONS['technicien']['sections'] or s in ROLE_PERMISSIONS['technicien']['sections'],
                    "has_item": lambda i: 'all' in ROLE_PERMISSIONS['technicien']['nav'] or i in ROLE_PERMISSIONS['technicien']['nav'],
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
                    try:
                        db.session.rollback()
                    except Exception:
                        pass
                    continue
                app.logger.error(
                    f"❌ Erreur DB dans le context processor (abandon) : {e}")
                if is_admin:
                    ctx["current_user"] = {
                        "firstname": "", "lastname": "", "role": "User", "role_lower": "user", "is_admin": False}
                    ctx["user_role"] = "technicien"
                    ctx["user_perms"] = ROLE_PERMISSIONS['technicien']
                    ctx["has_section"] = lambda s: 'all' in ROLE_PERMISSIONS['technicien'][
                        'sections'] or s in ROLE_PERMISSIONS['technicien']['sections']
                    ctx["has_item"] = lambda i: 'all' in ROLE_PERMISSIONS['technicien']['nav'] or i in ROLE_PERMISSIONS['technicien']['nav']
                    ctx["vehicles"] = []
                else:
                    ctx.update({"vehicles": [], "heads": [],
                               "grips_categories": []})

        return ctx
