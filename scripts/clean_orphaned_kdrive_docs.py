#!/usr/bin/env python3
"""
Script CLI de nettoyage des documents et dossiers orphelins sur kDrive.

Scanne les documents supprimés (soft-delete avec deleted_at != NULL) et les objets kDrive
orphelins en base de données, et supprime leurs dossiers correspondants sur Infomaniak kDrive.

Usage :
    python scripts/clean_orphaned_kdrive_docs.py              # Simulation (dry-run par défaut)
    python scripts/clean_orphaned_kdrive_docs.py --force      # Exécution réelle de la purge
    python scripts/clean_orphaned_kdrive_docs.py --type cgl   # Filtre sur un type spécifique (cgl, safety_rules, checkout, checkin, incident)
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Configuration du chemin pour les imports du projet
_root = Path(__file__).resolve().parent.parent
sys.path.append(str(_root))

from dotenv import load_dotenv
load_dotenv(_root / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("clean_orphaned_kdrive_docs")


def clean_orphaned_documents(filter_type: str = "all", dry_run: bool = True):
    """
    Détecte et supprime les dossiers kDrive résiduels pour les entités supprimées.
    """
    from models import (
        CglWaiver,
        SafetyRulesWaiver,
        CheckoutVehicle,
        CheckinVehicle,
        Incident,
        KDriveObject,
    )
    from services.common.kdrive import KDriveService

    service = KDriveService()
    entities_to_clean = []  # list of tuples (entity_type, entity_id, label)

    # 1. CGL supprimés
    if filter_type in ("all", "cgl"):
        deleted_cgls = CglWaiver.query.filter(CglWaiver.deleted_at.isnot(None)).all()
        for cgl in deleted_cgls:
            entities_to_clean.append(("cgl", cgl.waiver_id, f"CGL {cgl.waiver_id} (supprimé le {cgl.deleted_at})"))

    # 2. Règles de sécurité supprimées
    if filter_type in ("all", "safety_rules"):
        deleted_srs = SafetyRulesWaiver.query.filter(SafetyRulesWaiver.deleted_at.isnot(None)).all()
        for sr in deleted_srs:
            entities_to_clean.append(("safety_rules", sr.waiver_id, f"BVSR {sr.waiver_id} (supprimé le {sr.deleted_at})"))

    # 3. Checkouts supprimés
    if filter_type in ("all", "checkout"):
        deleted_cos = CheckoutVehicle.query.filter(CheckoutVehicle.deleted_at.isnot(None)).all()
        for co in deleted_cos:
            entities_to_clean.append(("checkout", co.inspection_number, f"Checkout {co.inspection_number} (supprimé le {co.deleted_at})"))

    # 4. Checkins supprimés
    if filter_type in ("all", "checkin"):
        deleted_cis = CheckinVehicle.query.filter(CheckinVehicle.deleted_at.isnot(None)).all()
        for ci in deleted_cis:
            entities_to_clean.append(("checkin", ci.inspection_number, f"Checkin {ci.inspection_number} (supprimé le {ci.deleted_at})"))

    # 5. Incidents supprimés
    if filter_type in ("all", "incident"):
        deleted_incs = Incident.query.filter(Incident.deleted_at.isnot(None)).all()
        for inc in deleted_incs:
            entities_to_clean.append(("incident", inc.incident_number, f"Incident {inc.incident_number} (supprimé le {inc.deleted_at})"))

    # 6. Objets kdrive_objects dont l'entité n'existe plus ou est orpheline
    all_kdrive_objs = KDriveObject.query.all()
    seen_entities = {(e[0], e[1]) for e in entities_to_clean}

    for obj in all_kdrive_objs:
        canon_type = "cgl" if obj.entity_type in ("cgl", "cgl_waiver") else (
            "safety_rules" if obj.entity_type in ("safety_rules", "safety_rules_waiver") else obj.entity_type
        )
        if filter_type != "all" and canon_type != filter_type:
            continue
        if (canon_type, obj.entity_id) in seen_entities:
            continue

        # Vérifier si l'entité existe encore en actif
        is_active = False
        if canon_type == "cgl":
            rec = CglWaiver.query.filter_by(waiver_id=obj.entity_id).first()
            is_active = bool(rec and rec.deleted_at is None)
        elif canon_type == "safety_rules":
            rec = SafetyRulesWaiver.query.filter_by(waiver_id=obj.entity_id).first()
            is_active = bool(rec and rec.deleted_at is None)
        elif canon_type == "checkout":
            rec = CheckoutVehicle.query.filter_by(inspection_number=obj.entity_id).first()
            is_active = bool(rec and rec.deleted_at is None)
        elif canon_type == "checkin":
            rec = CheckinVehicle.query.filter_by(inspection_number=obj.entity_id).first()
            is_active = bool(rec and rec.deleted_at is None)
        elif canon_type == "incident":
            rec = Incident.query.filter_by(incident_number=obj.entity_id).first()
            is_active = bool(rec and rec.deleted_at is None)

        if not is_active:
            seen_entities.add((canon_type, obj.entity_id))
            entities_to_clean.append((canon_type, obj.entity_id, f"{canon_type.upper()} {obj.entity_id} (orphelin KDriveObject)"))

    logger.info(f"🔎 {len(entities_to_clean)} entité(s) supprimée(s) ou orpheline(s) détectée(s).")

    if not entities_to_clean:
        logger.info("✨ Aucun document orphelin détecté.")
        return

    purged_count = 0
    for entity_type, entity_id, label in entities_to_clean:
        if dry_run:
            logger.info(f"🔍 [DRY-RUN] Purge simulée pour {label}")
        else:
            logger.info(f"🗑️ Purge kDrive en cours pour {label}...")
            try:
                res = service.delete_entity(entity_type, entity_id)
                if res:
                    logger.info(f"  ✓ Nettoyage réussi pour {label}")
                    purged_count += 1
                else:
                    logger.info(f"  ℹ️ Aucun fichier kDrive résiduel pour {label}")
            except Exception as exc:
                logger.error(f"  ❌ Erreur purge {label} : {exc}")

    if dry_run:
        logger.info(f"\n💡 [DRY-RUN] {len(entities_to_clean)} entité(s) scannée(s). Pour appliquer réellement la purge, relancez avec --force.")
    else:
        logger.info(f"\n✅ Nettoyage terminé : {purged_count}/{len(entities_to_clean)} entités kDrive purgées.")


def main():
    parser = argparse.ArgumentParser(description="Nettoyage des documents orphelins sur kDrive")
    parser.add_argument("--force", action="store_true", help="Applique réellement la suppression sur kDrive (sans --force, dry-run actif)")
    parser.add_argument("--dry-run", action="store_true", help="Mode simulation sans modification (actif par défaut)")
    parser.add_argument("--type", choices=["all", "cgl", "safety_rules", "checkout", "checkin", "incident"], default="all", help="Type de document à nettoyer")
    args = parser.parse_args()

    dry_run = not args.force or args.dry_run

    from utils.scripts_helper import build_minimal_app
    app, tunnel = build_minimal_app()
    try:
        with app.app_context():
            logger.info(f"--- Nettoyage des documents orphelins kDrive ({'SIMULATION' if dry_run else 'EXÉCUTION RÉELLE'}) ---")
            clean_orphaned_documents(filter_type=args.type, dry_run=dry_run)
    finally:
        if tunnel:
            tunnel.stop()


if __name__ == "__main__":
    main()
