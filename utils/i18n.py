from flask import abort, g, request, session, url_for
from utils.database import get_all_static

SUPPORTED_LANGS = ('en', 'fr')
DEFAULT_LANG = 'en'


def t(fields, key):
    """Traduit un champ de contenu dynamique (colonnes suffixées).
    Priorité : clé_fr → clé_en → clé (colonne originale)."""
    lang = g.get('lang', DEFAULT_LANG)
    return (fields.get(f'{key}_{lang}')
            or fields.get(f'{key}_en')
            or fields.get(key, ''))


def ts(key):
    """Traduit une chaîne UI statique (table de traduction par ligne).
    Priorité : langue courante → en → clé brute."""
    lang = g.get('lang', DEFAULT_LANG)
    static_all = get_all_static()
    return (static_all.get(lang, {}).get(key)
            or static_all.get('en', {}).get(key, key))


def alt_url(target_lang):
    """Génère l'URL de la page courante dans une autre langue (absolue pour le SEO)."""
    if request.endpoint and request.view_args is not None:
        try:
            args = dict(request.view_args)
            args['lang'] = target_lang
            return url_for(request.endpoint, _external=True, **args)
        except Exception:
            pass
    return url_for('home', lang=target_lang, _external=True)


def init_i18n(app):
    """Initialise la gestion i18n sur l'application Flask."""
    @app.url_value_preprocessor
    def pull_lang(endpoint, values):
        """Extrait la langue de l'URL, la stocke dans g.lang et en session."""
        if values and 'lang' in values:
            lang = values.pop('lang')
            if lang in SUPPORTED_LANGS:
                g.lang = lang
                session['lang'] = lang
            else:
                abort(404)
        else:
            g.lang = session.get('lang', DEFAULT_LANG)

    @app.url_defaults
    def inject_lang(endpoint, values):
        """Injecte automatiquement la langue dans url_for() pour les routes concernées."""
        if 'lang' in values or not app.url_map.is_endpoint_expecting(endpoint, 'lang'):
            return
        values['lang'] = g.get('lang', session.get('lang', DEFAULT_LANG))
