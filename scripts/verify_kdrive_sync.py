#!/usr/bin/env python3
"""
Vérification et réconciliation périodique kDrive.

Ce script :
1. Vérifie que tous les projets actifs disposent d'un dossier kDrive existant et correctement nommé/placé.
2. Répare ou recrée les dossiers manquants ou supprimés accidentellement.
3. Purge les dossiers kDrive résiduels des projets supprimés en BDD (avec remontée récursive des parents vides).
4. Relance les téléversements (PDFs scellés, photos) restés en attente ou en échec.

Usage :
    python scripts/verify_kdrive_sync.py            # Audit et réconciliation réelle
    python scripts/verify_kdrive_sync.py --dry-run  # Simulation sans modification
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Configuration du chemin pour les imports du projet
_root = Path(__file__).parent.parent
sys.path.append(str(_root))

from dotenv import load_dotenv
from utils.cron_helper import monitor_cron_job
from utils.scripts_helper import build_minimal_app

load_dotenv(_root / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("kdrive_reconcile")


def run_kdrive_reconciliation(dry_run: bool = False):
    """Exécute la vérification et la synchronisation de l'ensemble de l'écosystème kDrive."""
    from models import Project, KDriveObject, db
    from services.common.kdrive import KDriveService
    from services.common.kdrive.paths import build_project_path
    from services.common.kdrive.tasks import task_retry_pending_kdrive_objects

    app, tunnel = build_minimal_app()
    stats = {
        "active_checked": 0,
        "active_recreated": 0,
        "subfolders_repaired": 0,
        "active_synced": 0,
        "deleted_purged": 0,
        "objects_retried": 0,
    }

    try:
        with app.app_context():
            service = KDriveService()
            logger.info(
                f"🚀 Démarrage vérification & réconciliation kDrive "
                f"({'SIMULATION / DRY-RUN' if dry_run else 'MODE RÉEL'})..."
            )

            # ── 1. Audit des Projets Actifs ──────────────────────────────────────────
            active_projects = (
                Project.query.filter(Project.deleted_at.is_(None))
                .order_by(Project.id.desc())
                .all()
            )
            stats["active_checked"] = len(active_projects)
            logger.info(f"📂 Audit de {len(active_projects)} projet(s) actif(s)...")

            for project in active_projects:
                needs_full_tree = False
                reason = ""

                if not project.kdrive_folder_id or project.kdrive_sync_status != "synced":
                    needs_full_tree = True
                    reason = "non synchronisé ou ID manquant"
                else:
                    # Vérifier si le dossier existe toujours réellement sur kDrive
                    try:
                        file_meta = service.client.get_file(project.kdrive_folder_id)
                        if not file_meta or file_meta.get("status") in ("deleted", "trashed"):
                            needs_full_tree = True
                            reason = "dossier introuvable ou supprimé sur kDrive"
                    except Exception:
                        needs_full_tree = True
                        reason = "erreur accès kDrive (404 / supprimé)"

                if needs_full_tree:
                    logger.warning(
                        f"⚠️ Projet #{project.id} ({project.name}) nécessite une recréation complète ({reason})."
                    )
                    if not dry_run:
                        try:
                            service.ensure_project_tree(project.id)
                            stats["active_recreated"] += 1
                            logger.info(f"✅ Arborescence kDrive recréée pour projet #{project.id}.")
                        except Exception as e:
                            logger.error(f"❌ Échec création arborescence projet #{project.id} : {e}")
                    else:
                        stats["active_recreated"] += 1
                else:
                    # Le dossier principal existe, auditons les sous-dossiers
                    # (1_DEVIS, 2_FACTURES, 3_LISTES, 4_SÉCURITÉ + ses 4 sous-dossiers, 5_BTS, 6_INCIDENTS)
                    try:
                        repaired = service.check_and_repair_project_structure(project, dry_run=dry_run)
                        if repaired:
                            stats["subfolders_repaired"] += len(repaired)
                            action_label = "détecté(s) manquant(s)" if dry_run else "réparé(s)"
                            logger.warning(
                                f"🔧 Projet #{project.id} ({project.name}) : sous-dossier(s) {action_label} -> {', '.join(repaired)}"
                            )
                        else:
                            stats["active_synced"] += 1
                            logger.info(f"✓ Projet #{project.id} ({project.name}) : arborescence complète 100% conforme.")
                    except Exception as e:
                        logger.error(f"❌ Échec audit sous-dossiers projet #{project.id} : {e}")

            # ── 2. Audit des Projets Supprimés ayant encore un dossier kDrive ────────
            orphan_deleted_projects = (
                Project.query.filter(
                    Project.deleted_at.is_not(None),
                    Project.kdrive_folder_id.is_not(None),
                )
                .order_by(Project.id.desc())
                .all()
            )

            if orphan_deleted_projects:
                logger.info(f"🧹 Détection de {len(orphan_deleted_projects)} projet(s) supprimé(s) avec dossier kDrive résiduel...")
                for p_del in orphan_deleted_projects:
                    logger.info(
                        f"🗑️ Purge kDrive du projet supprimé #{p_del.id} '{p_del.name}' (Dossier ID={p_del.kdrive_folder_id})..."
                    )
                    if not dry_run:
                        try:
                            service.delete_project_folder(p_del.id, p_del.kdrive_folder_id)
                            stats["deleted_purged"] += 1
                        except Exception as e:
                            logger.error(f"❌ Erreur purge projet supprimé #{p_del.id} : {e}")
            else:
                logger.info("✓ Aucun projet supprimé orphelin à purger.")

            # ── 3. Relance des Objets kDrive (photos, PDF) en attente ou échec ────────
            if not dry_run:
                logger.info("🔄 Relance des objets de documents en attente de synchronisation...")
                try:
                    task_retry_pending_kdrive_objects(limit=100)
                except Exception as e:
                    logger.error(f"❌ Erreur retry kdrive objects : {e}")

            # ── 4. Rattrapage des Documents Signés Non Synchronisés ──────────────────
            if not dry_run:
                logger.info("🔍 Contrôle des documents signés non synchronisés (décharges)...")
                import json
                from models import PilotWaiver, ProductionWaiver, CheckoutVehicle, CheckinVehicle, Incident
                stats["documents_caught_up"] = 0

                # 1. Décharges Pilote
                try:
                    signed_pilot = PilotWaiver.query.filter(
                        PilotWaiver.status == "signed",
                        PilotWaiver.deleted_at.is_(None)
                    ).all()
                    logger.info(f"🔍 Décharges pilote signées en BDD : {len(signed_pilot)}")
                    for pw in signed_pilot:
                        if not pw.project_id:
                            logger.warning(f"⚠️ Décharge pilote {pw.waiver_id} sans project_id, ignorée.")
                            continue
                        synced_pdf = KDriveObject.query.filter_by(
                            entity_id=pw.waiver_id, role="pdf", status="synced"
                        ).first()
                        if not synced_pdf:
                            if pw.signed_pdf_path:
                                logger.info(f"📤 Rattrapage décharge pilote {pw.waiver_id} (projet #{pw.project_id})...")
                                fspecs = [{"role": "pdf", "path": pw.signed_pdf_path, "filename": os.path.basename(pw.signed_pdf_path)}]
                                if pw.pilot_license_path:
                                    fspecs.append({"role": "license", "path": pw.pilot_license_path})
                                if pw.pilot_insurance_path:
                                    fspecs.append({"role": "insurance", "path": pw.pilot_insurance_path})
                                if pw.pilot_identity_path:
                                    fspecs.append({"role": "identity", "path": pw.pilot_identity_path})
                                try:
                                    service.upload_bundle_sync(pw.project_id, "pilot_waiver", pw.waiver_id, fspecs)
                                    stats["documents_caught_up"] += 1
                                    logger.info(f"✅ Décharge pilote {pw.waiver_id} synchronisée avec succès.")
                                except Exception as e_pw:
                                    logger.error(f"❌ Échec rattrapage décharge pilote {pw.waiver_id} : {e_pw}", exc_info=True)
                            else:
                                logger.warning(f"⚠️ Décharge pilote {pw.waiver_id} marquée 'signed' mais sans signed_pdf_path.")
                        else:
                            logger.info(f"✓ Décharge pilote {pw.waiver_id} déjà synchronisée sur kDrive (file_id={synced_pdf.kdrive_file_id}).")
                except Exception as e_pilot:
                    logger.error(f"❌ Erreur contrôle décharges pilote : {e_pilot}", exc_info=True)

                # 2. Décharges Production
                try:
                    signed_prod = ProductionWaiver.query.filter(
                        ProductionWaiver.status == "signed",
                        ProductionWaiver.deleted_at.is_(None)
                    ).all()
                    logger.info(f"🔍 Décharges production signées en BDD : {len(signed_prod)}")
                    for prw in signed_prod:
                        if not prw.project_id:
                            continue
                        synced_pdf = KDriveObject.query.filter_by(
                            entity_id=prw.waiver_id, role="pdf", status="synced"
                        ).first()
                        if not synced_pdf:
                            if prw.signed_pdf_path:
                                logger.info(f"📤 Rattrapage décharge production {prw.waiver_id}...")
                                fspecs = [{"role": "pdf", "path": prw.signed_pdf_path, "filename": os.path.basename(prw.signed_pdf_path)}]
                                if prw.production_insurance_path:
                                    fspecs.append({"role": "insurance", "path": prw.production_insurance_path})
                                try:
                                    service.upload_bundle_sync(prw.project_id, "production_waiver", prw.waiver_id, fspecs)
                                    stats["documents_caught_up"] += 1
                                    logger.info(f"✅ Décharge production {prw.waiver_id} synchronisée avec succès.")
                                except Exception as e_prw:
                                    logger.error(f"❌ Échec rattrapage décharge prod {prw.waiver_id} : {e_prw}")
                        else:
                            logger.info(f"✓ Décharge prod {prw.waiver_id} déjà synchronisée sur kDrive.")
                except Exception as e_prod:
                    logger.error(f"❌ Erreur contrôle décharges production : {e_prod}", exc_info=True)

                # 3. Inspections Check-out signées
                try:
                    checkouts = CheckoutVehicle.query.filter(
                        CheckoutVehicle.status == "signed",
                        CheckoutVehicle.deleted_at.is_(None)
                    ).all()
                    logger.info(f"🔍 Inspections Check-out signées en BDD : {len(checkouts)}")
                    for co in checkouts:
                        if not co.project_id:
                            continue
                        synced_pdf = KDriveObject.query.filter_by(
                            entity_id=co.inspection_number, role="pdf", status="synced"
                        ).first()
                        if not synced_pdf:
                            if co.signed_pdf_path:
                                logger.info(f"📤 Rattrapage check-out {co.inspection_number}...")
                                fspecs = [{"role": "pdf", "path": co.signed_pdf_path, "filename": os.path.basename(co.signed_pdf_path)}]
                                for p_field in [co.interior_photos, co.exterior_photos]:
                                    if p_field:
                                        try:
                                            for p in (json.loads(p_field) if isinstance(p_field, str) else p_field):
                                                if p:
                                                    fspecs.append({"role": "photo", "path": p})
                                        except Exception:
                                            pass
                                try:
                                    service.upload_bundle_sync(co.project_id, "checkout", co.inspection_number, fspecs)
                                    stats["documents_caught_up"] += 1
                                    logger.info(f"✅ Check-out {co.inspection_number} synchronisé avec succès.")
                                except Exception as e_co:
                                    logger.error(f"❌ Échec rattrapage checkout {co.inspection_number} : {e_co}")
                        else:
                            logger.info(f"✓ Check-out {co.inspection_number} déjà synchronisé sur kDrive.")
                except Exception as e_co_all:
                    logger.error(f"❌ Erreur contrôle inspections check-out : {e_co_all}", exc_info=True)

                # 4. Inspections Check-in signées
                try:
                    checkins = CheckinVehicle.query.filter(
                        CheckinVehicle.status == "signed",
                        CheckinVehicle.deleted_at.is_(None)
                    ).all()
                    logger.info(f"🔍 Inspections Check-in signées en BDD : {len(checkins)}")
                    for ci in checkins:
                        if not ci.project_id:
                            continue
                        synced_pdf = KDriveObject.query.filter_by(
                            entity_id=ci.inspection_number, role="pdf", status="synced"
                        ).first()
                        if not synced_pdf:
                            if ci.signed_pdf_path:
                                logger.info(f"📤 Rattrapage check-in {ci.inspection_number}...")
                                fspecs = [{"role": "pdf", "path": ci.signed_pdf_path, "filename": os.path.basename(ci.signed_pdf_path)}]
                                for p_field in [ci.interior_photos, ci.exterior_photos]:
                                    if p_field:
                                        try:
                                            for p in (json.loads(p_field) if isinstance(p_field, str) else p_field):
                                                if p:
                                                    fspecs.append({"role": "photo", "path": p})
                                        except Exception:
                                            pass
                                try:
                                    service.upload_bundle_sync(ci.project_id, "checkin", ci.inspection_number, fspecs)
                                    stats["documents_caught_up"] += 1
                                    logger.info(f"✅ Check-in {ci.inspection_number} synchronisé avec succès.")
                                except Exception as e_ci:
                                    logger.error(f"❌ Échec rattrapage checkin {ci.inspection_number} : {e_ci}")
                        else:
                            logger.info(f"✓ Check-in {ci.inspection_number} déjà synchronisé sur kDrive.")
                except Exception as e_ci_all:
                    logger.error(f"❌ Erreur contrôle inspections check-in : {e_ci_all}", exc_info=True)

                # 5. Incidents scellés / signés
                try:
                    incidents = Incident.query.filter(
                        Incident.signature_status == "signed",
                        Incident.deleted_at.is_(None)
                    ).all()
                    logger.info(f"🔍 Incidents signés en BDD : {len(incidents)}")
                    for inc in incidents:
                        if not inc.project_id:
                            continue
                        synced_pdf = KDriveObject.query.filter_by(
                            entity_id=inc.incident_number, role="pdf", status="synced"
                        ).first()
                        if not synced_pdf:
                            if inc.signed_pdf_path:
                                logger.info(f"📤 Rattrapage incident {inc.incident_number}...")
                                fspecs = [{"role": "pdf", "path": inc.signed_pdf_path, "filename": os.path.basename(inc.signed_pdf_path)}]
                                for p in (inc.photos_list or []):
                                    if p:
                                        fspecs.append({"role": "photo", "path": p})
                                for d in (inc.documents_list or []):
                                    if d:
                                        fspecs.append({"role": "document", "path": d})
                                try:
                                    service.upload_bundle_sync(inc.project_id, "incident", inc.incident_number, fspecs)
                                    stats["documents_caught_up"] += 1
                                    logger.info(f"✅ Incident {inc.incident_number} synchronisé avec succès.")
                                except Exception as e_inc:
                                    logger.error(f"❌ Échec rattrapage incident {inc.incident_number} : {e_inc}")
                        else:
                            logger.info(f"✓ Incident {inc.incident_number} déjà synchronisé sur kDrive.")
                except Exception as e_inc_all:
                    logger.error(f"❌ Erreur contrôle incidents : {e_inc_all}", exc_info=True)

            logger.info(
                f"🏁 Réconciliation kDrive terminée : "
                f"{stats['active_synced']} synchro 100% OK, "
                f"{stats['active_recreated']} arborescence(s) recréée(s), "
                f"{stats['subfolders_repaired']} sous-dossier(s) "
                f"{'détecté(s) manquant(s)' if dry_run else 'réparé(s)'}, "
                f"{stats.get('documents_caught_up', 0)} document(s) rattrapé(s), "
                f"{stats['deleted_purged']} orphelin(s) purgé(s)."
            )
            return stats
    finally:
        if tunnel and tunnel.is_active:
            tunnel.stop()
            logger.info("🔌 SSH Tunnel fermé.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vérification et réconciliation périodique kDrive")
    parser.add_argument("--dry-run", action="store_true", help="Simuler sans modifier kDrive ni la base")
    args = parser.parse_args()

    if args.dry_run:
        run_kdrive_reconciliation(dry_run=True)
    else:
        with monitor_cron_job("verify_kdrive_sync"):
            run_kdrive_reconciliation(dry_run=False)
