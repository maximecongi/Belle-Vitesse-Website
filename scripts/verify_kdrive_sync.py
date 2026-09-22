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
        "orphan_containers_purged": 0,
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

            # Purge ciblée des conteneurs de projet orphelins (ex: anciens dossiers vides après déplacement de projet)
            # Ne touche JAMAIS aux sous-dossiers internes d'un projet BVPR-*
            logger.info("🧹 Scan et purge des conteneurs de projets orphelins vides (anciens dossiers déplacés)...")
            try:
                orphan_purged = service.prune_orphan_project_containers(dry_run=dry_run)
                if orphan_purged:
                    stats["orphan_containers_purged"] = len(orphan_purged)
                    logger.info(
                        f"🗑️ {len(orphan_purged)} conteneur(s) orphelin(s) purgé(s) sur kDrive -> {', '.join(orphan_purged)}"
                    )
                else:
                    logger.info("✓ Aucun conteneur projet orphelin vide détecté.")
            except Exception as e_tree:
                logger.error(f"❌ Erreur purge conteneurs orphelins : {e_tree}")

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

                from services.common.kdrive import extract_bundle_file_specs

                DOC_CONFIGS = [
                    {"label": "décharges pilote", "type": "pilot_waiver", "model": PilotWaiver, "id_attr": "waiver_id", "filter": {"status": "signed"}},
                    {"label": "décharges production", "type": "production_waiver", "model": ProductionWaiver, "id_attr": "waiver_id", "filter": {"status": "signed"}},
                    {"label": "inspections check-out", "type": "checkout", "model": CheckoutVehicle, "id_attr": "inspection_number", "filter": {"status": "signed"}},
                    {"label": "inspections check-in", "type": "checkin", "model": CheckinVehicle, "id_attr": "inspection_number", "filter": {"status": "signed"}},
                    {"label": "incidents", "type": "incident", "model": Incident, "id_attr": "incident_number", "filter": {"signature_status": "signed"}},
                ]

                for cfg in DOC_CONFIGS:
                    try:
                        records = (
                            cfg["model"].query
                            .filter_by(**cfg["filter"])
                            .filter(cfg["model"].deleted_at.is_(None))
                            .all()
                        )
                        logger.info(f"🔍 {cfg['label'].capitalize()} signées en BDD : {len(records)}")
                        for rec in records:
                            if not rec.project_id:
                                logger.warning(f"⚠️ {cfg['label']} #{rec.id} sans project_id, ignoré(e).")
                                continue
                            if rec.project and rec.project.deleted_at is not None:
                                continue

                            entity_id = getattr(rec, cfg["id_attr"])
                            synced_pdf = KDriveObject.query.filter_by(
                                entity_id=entity_id, role="pdf", status="synced"
                            ).first()

                            if not synced_pdf:
                                if rec.signed_pdf_path:
                                    logger.info(f"📤 Rattrapage {cfg['label']} {entity_id} (projet #{rec.project_id})...")
                                    fspecs = extract_bundle_file_specs(rec, entity_type=cfg["type"])
                                    try:
                                        service.upload_bundle_sync(rec.project_id, cfg["type"], entity_id, fspecs)
                                        stats["documents_caught_up"] += 1
                                        logger.info(f"✅ {cfg['label'].capitalize()} {entity_id} synchronisé(e) avec succès.")
                                    except Exception as e_up:
                                        logger.error(f"❌ Échec rattrapage {cfg['label']} {entity_id} : {e_up}")
                                else:
                                    logger.warning(f"⚠️ {cfg['label'].capitalize()} {entity_id} marqué(e) signé(e) mais sans signed_pdf_path.")
                            else:
                                logger.info(f"✓ {cfg['label'].capitalize()} {entity_id} déjà synchronisé(e) sur kDrive (file_id={synced_pdf.kdrive_file_id}).")
                    except Exception as e_cfg:
                        logger.error(f"❌ Erreur contrôle {cfg['label']} : {e_cfg}", exc_info=True)

            logger.info(
                f"🏁 Réconciliation kDrive terminée : "
                f"{stats['active_synced']} synchro 100% OK, "
                f"{stats['active_recreated']} arborescence(s) recréée(s), "
                f"{stats['subfolders_repaired']} sous-dossier(s) "
                f"{'détecté(s) manquant(s)' if dry_run else 'réparé(s)'}, "
                f"{stats.get('documents_caught_up', 0)} document(s) rattrapé(s), "
                f"{stats['deleted_purged']} projet(s) supprimé(s) purgé(s), "
                f"{stats.get('orphan_containers_purged', 0)} conteneur(s) orphelin(s) purgé(s)."
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
