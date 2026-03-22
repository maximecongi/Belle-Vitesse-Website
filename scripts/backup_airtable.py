import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from pyairtable import Api

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

AIRTABLE_TOKEN = os.getenv("AIRTABLE_SECRET_TOKEN")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")

if not all([AIRTABLE_TOKEN, BASE_ID]):
    print("❌ Missing Airtable environment variables.")
    exit(1)

# Tables to backup
# Update these IDs or Names based on your actual tables
TABLES = {
    "Checkouts": "tblCheckouts",  # You might need to verify the table ID or Name
    "Projects": "tblProjects"
    # If you use table names in your app, use them here.
    # If your app uses Table IDs, put them here.
}
# Retrieving names from App or Utils?
# In utils/database.py and utils/checkout.py we assume TABLE_CHECKOUT and TABLE_PROJECTS are initialized.
# We can just iterate over known names used in the app if we know them.
# Let's use the names "Checkouts" and "Projets" (french/english mix in previous conversions?)
# In routes.py: TABLE_CHECKOUT = Table(api, base_id, "Checkouts") -> so name is "Checkouts"
# TABLE_PROJECTS = Table(api, base_id, "Projets") -> name is "Projets"

TABLE_NAMES = ["Checkouts", "Projets", "Véhicules", "Production"]

# Setup backup directory
TIMESTAMP = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
BACKUP_DIR = Path(__file__).parent.parent / 'backups' / 'airtable' / TIMESTAMP
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

print(f"📦 Starting Airtable backup to {BACKUP_DIR}...")

api = Api(AIRTABLE_TOKEN)
table_api = api.base(BASE_ID)

for table_name in TABLE_NAMES:
    print(f"   Downloading '{table_name}'...")
    try:
        table = table_api.table(table_name)
        records = table.all()

        outfile = BACKUP_DIR / f"{table_name}.json"
        with open(outfile, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        print(f"   ✅ Saved {len(records)} records.")
    except Exception as e:
        print(f"   ⚠️ Failed to download '{table_name}': {e}")

print("✅ Airtable backup completed.")
