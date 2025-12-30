#imports
import os
from datetime import timedelta, datetime 
import hashlib
import re
from flask import Flask, session, redirect, render_template, request, url_for, abort, jsonify
from pyairtable import Table
from collections import defaultdict


# Config
app = Flask(__name__, 
            static_folder=os.getenv("STATIC_FOLDER"),
            static_url_path=os.getenv("STATIC_URL_PATH"))  

AIRTABLE_SECRET_TOKEN = os.getenv("AIRTABLE_SECRET_TOKEN")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
TABLE_VEHICULES = Table(AIRTABLE_SECRET_TOKEN, AIRTABLE_BASE_ID, "vehicules")
#TABLE_HEADS = Table(AIRTABLE_SECRET_TOKEN, AIRTABLE_BASE_ID, "heads")
#TABLE_SUPPORTS = Table(AIRTABLE_SECRET_TOKEN, AIRTABLE_BASE_ID, "supports")
TABLE_CONFIGS = Table(AIRTABLE_SECRET_TOKEN, AIRTABLE_BASE_ID, "configs")

# WEBSITE
# Website - Navigation
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/vehicules')
def vehicules():
    vehicules = TABLE_VEHICULES.all(sort=["order"])
    return render_template('vehicules.html', vehicules=vehicules)

@app.route('/vehicules/<slug>')
def vehicule(slug):
    vehicule = TABLE_VEHICULES.first(formula=f"{{slug}}='{slug}'")
    all_configs = TABLE_CONFIGS.all()
    configs = [c for c in all_configs if vehicule['id'] in c['fields'].get('vehicule', [])]
    
    configs_grouped = defaultdict(list)
    for config in configs:
        type_name = config['fields'].get('type', 'Sans type')
        configs_grouped[type_name].append(config)
    
    configs_grouped = dict(reversed(list(configs_grouped.items())))
    
    return render_template('vehicule.html', vehicule=vehicule, configs_grouped=configs_grouped)

@app.route('/heads')
def heads():
    heads = TABLE_VEHICULES.all()
    return render_template('home.html', heads=heads)

@app.route('/supports')
def supports():
    supports = TABLE_VEHICULES.all()
    return render_template('supports.html', supports=supports)


if __name__ == '__main__':
    app.run(debug=True)