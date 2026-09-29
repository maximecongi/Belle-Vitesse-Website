#!/usr/bin/env python3
"""
Script de migration des signatures Base64 vers des fichiers PNG physiques sur disque.
Désengorge le buffer pool MySQL/InnoDB en remplaçant les chaînes Base64 volumineuses
par des chemins relatifs légers (ex: signatures/waivers/BVPW-123.png).

Usage:
  python3 scripts/migrate_signatures_to_files.py [--dry-run]
"""

import argparse
import sys
from pathlib import Path

# Ajout de la racine du projet au PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from models.db import db
from models.incident import Incident, IncidentSignedDocument, IncidentToken
from models.waiver import (
    CheckinSignedDocument,
    CheckoutSignedDocument,
    PilotWaiver,
    PilotWaiverSignedDocument,
    ProductionWaiver,
    ProductionWaiverSignedDocument,
)
from utils.signature_storage import save_signature_image


def is_base64_signature(val: str) -> bool:
    if not val or not isinstance(val, str):
        return False
    val = val.strip()
    return val.startswith("data:image/") or len(val) > 300


def migrate_signatures(dry_run: bool = False, app=None):
    if app is None:
        app = create_app()
    with app.app_context():
        print(f"🚀 Démarrage de la migration des signatures vers PNG (dry_run={dry_run})...")
        migrated_count = 0
        total_bytes_saved = 0

        # 1. Pilot Waivers
        pilot_waivers = PilotWaiver.query.filter(PilotWaiver.signature_data.isnot(None)).all()
        for pw in pilot_waivers:
            if is_base64_signature(pw.signature_data):
                doc_id = pw.waiver_id or f"waiver_{pw.id}"
                old_len = len(pw.signature_data)
                print(f"  [PilotWaiver] Migration {doc_id} ({old_len:,} caractères)...")
                if not dry_run:
                    rel_path = save_signature_image(pw.signature_data, "waivers", doc_id)
                    pw.signature_data = rel_path
                migrated_count += 1
                total_bytes_saved += old_len

        # 2. Production Waivers
        prod_waivers = ProductionWaiver.query.filter(ProductionWaiver.signature_data.isnot(None)).all()
        for prw in prod_waivers:
            if is_base64_signature(prw.signature_data):
                doc_id = prw.waiver_id or f"waiver_{prw.id}"
                old_len = len(prw.signature_data)
                print(f"  [ProductionWaiver] Migration {doc_id} ({old_len:,} caractères)...")
                if not dry_run:
                    rel_path = save_signature_image(prw.signature_data, "waivers", doc_id)
                    prw.signature_data = rel_path
                migrated_count += 1
                total_bytes_saved += old_len

        # 3. Incidents (BV & Prod)
        incidents = Incident.query.all()
        for inc in incidents:
            if is_base64_signature(inc.bv_signature_data):
                doc_id = inc.incident_number or f"inc_{inc.id}"
                old_len = len(inc.bv_signature_data)
                print(f"  [Incident BV] Migration {doc_id} ({old_len:,} caractères)...")
                if not dry_run:
                    rel_path = save_signature_image(inc.bv_signature_data, "incidents", doc_id, suffix="_bv")
                    inc.bv_signature_data = rel_path
                migrated_count += 1
                total_bytes_saved += old_len

            if is_base64_signature(inc.prod_signature_data):
                doc_id = inc.incident_number or f"inc_{inc.id}"
                old_len = len(inc.prod_signature_data)
                print(f"  [Incident Prod] Migration {doc_id} ({old_len:,} caractères)...")
                if not dry_run:
                    rel_path = save_signature_image(inc.prod_signature_data, "incidents", doc_id, suffix="_prod")
                    inc.prod_signature_data = rel_path
                migrated_count += 1
                total_bytes_saved += old_len

        # 4. Signed Documents Archives
        signed_doc_models = [
            ("CheckoutSignedDocument", CheckoutSignedDocument, "checkouts", "inspection_id"),
            ("CheckinSignedDocument", CheckinSignedDocument, "checkins", "inspection_id"),
            ("PilotWaiverSignedDocument", PilotWaiverSignedDocument, "waivers", "waiver_id"),
            ("ProductionWaiverSignedDocument", ProductionWaiverSignedDocument, "waivers", "waiver_id"),
            ("IncidentSignedDocument", IncidentSignedDocument, "incidents", "incident_number"),
        ]

        for label, model_cls, folder, pk_field in signed_doc_models:
            docs = model_cls.query.all()
            for d in docs:
                sig_val = getattr(d, "signature", None)
                if is_base64_signature(sig_val):
                    pk_val = getattr(d, pk_field, f"doc_{getattr(d, 'id', '0')}")
                    old_len = len(sig_val)
                    print(f"  [{label}] Migration {pk_val} ({old_len:,} caractères)...")
                    if not dry_run:
                        rel_path = save_signature_image(sig_val, folder, pk_val)
                        d.signature = rel_path
                    migrated_count += 1
                    total_bytes_saved += old_len

        if not dry_run:
            db.session.commit()
            print(f"✅ Migration terminée avec succès : {migrated_count} signature(s) déportée(s) sur disque.")
            print(f"📦 Économie mémoire/base : ~{total_bytes_saved / 1024:.1f} Ko libérés.")
        else:
            print(f"🔍 [DRY-RUN] Détection de {migrated_count} signature(s) éligible(s).")
            print(f"📦 Économie potentielle : ~{total_bytes_saved / 1024:.1f} Ko.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migration des signatures Base64 vers PNG.")
    parser.add_argument("--dry-run", action="store_true", help="Simule sans écrire sur disque ni modifier la DB.")
    args = parser.parse_args()
    migrate_signatures(dry_run=args.dry_run)
