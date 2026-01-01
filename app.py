# imports
import os
from utils.specs import build_specs
from datetime import timedelta, datetime
import hashlib
import re
from flask import Flask, session, redirect, render_template, request, url_for, abort, jsonify
from pyairtable import Table
from collections import defaultdict
from flask_caching import Cache

# Config
app = Flask(__name__,
            static_folder=os.getenv("STATIC_FOLDER"),
            static_url_path=os.getenv("STATIC_URL_PATH"))

AIRTABLE_SECRET_TOKEN = os.getenv("AIRTABLE_SECRET_TOKEN")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
TABLE_VEHICULES = Table(AIRTABLE_SECRET_TOKEN, AIRTABLE_BASE_ID, "vehicules")
# TABLE_HEADS = Table(AIRTABLE_SECRET_TOKEN, AIRTABLE_BASE_ID, "heads")
# TABLE_SUPPORTS = Table(AIRTABLE_SECRET_TOKEN, AIRTABLE_BASE_ID, "supports")
TABLE_CONFIGS = Table(AIRTABLE_SECRET_TOKEN, AIRTABLE_BASE_ID, "configs")

# Cache Configuration
cache = Cache()

# Configuration pour développement (simple) / production (redis)
if os.getenv("FLASK_ENV") == "production":
    app.config['CACHE_TYPE'] = 'redis'
    app.config['CACHE_REDIS_URL'] = os.getenv(
        'REDIS_URL', 'redis://localhost:6379/0')
else:
    app.config['CACHE_TYPE'] = 'simple'

app.config['CACHE_DEFAULT_TIMEOUT'] = 3600  # 1 heure
app.config['CACHE_KEY_PREFIX'] = 'myapp_'

cache.init_app(app)

# WEBSITE
# Website - Navigation


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/vehicules')
@cache.cached(timeout=3600)
def vehicules():
    vehicules = TABLE_VEHICULES.all(sort=["order"])
    return render_template('vehicules.html', vehicules=vehicules)


@app.route('/vehicules/<slug>')
@cache.cached(timeout=3600, query_string=True)
def vehicule(slug):
    vehicule = TABLE_VEHICULES.first(formula=f"{{slug}}='{slug}'")
    all_configs = TABLE_CONFIGS.all()
    configs = [c for c in all_configs if vehicule['id']
               in c['fields'].get('vehicule', [])]

    configs_grouped = defaultdict(list)
    for config in configs:
        type_name = config['fields'].get('type', 'Sans type')
        configs_grouped[type_name].append(config)

    specs_left, specs_right = build_specs(vehicule["fields"])

    configs_grouped = dict(reversed(list(configs_grouped.items())))
    return render_template('vehicule.html', vehicule=vehicule, configs_grouped=configs_grouped, specs_left=specs_left, specs_right=specs_right)


@app.route('/heads')
@cache.cached(timeout=3600)
def heads():
    heads = TABLE_VEHICULES.all(sort=["order"])
    return render_template('heads.html', heads=heads)


@app.route('/heads/<slug>')
@cache.cached(timeout=3600, query_string=True)
def head(slug):
    head = TABLE_VEHICULES.first(formula=f"{{slug}}='{slug}'")
    return render_template('head.html', head=head)


@app.route('/supports')
@cache.cached(timeout=3600)
def supports():
    supports = TABLE_VEHICULES.all(sort=["order"])
    return render_template('supports.html', supports=supports)


@app.route('/supports/<slug>')
@cache.cached(timeout=3600, query_string=True)
def support(slug):
    support = TABLE_VEHICULES.first(formula=f"{{slug}}='{slug}'")
    return render_template('support.html', support=support)


@app.route('/about-us')
def about_us():
    return render_template('about-us.html')


@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.route('/terms-and-conditions')
def terms_and_conditions():
    return render_template('terms-and-conditions.html')


# Cache Management
@app.route('/admin/cache/clear', methods=['POST'])
def clear_cache():
    """Efface tout le cache (à protéger avec authentification)"""
    cache.clear()
    return jsonify({'status': 'Cache cleared successfully'}), 200


@app.route('/admin/cache/clear/<cache_key>', methods=['POST'])
def clear_cache_key(cache_key):
    """Efface une clé de cache spécifique (à protéger avec authentification)"""
    cache.delete(cache_key)
    return jsonify({'status': f'Cache key {cache_key} deleted'}), 200


if __name__ == '__main__':
    app.run(debug=True)
