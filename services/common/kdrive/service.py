import hashlib
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import current_app

from models.db import db
from models.kdrive import KDriveObject
from models.project import Project
from services.common.kdrive.client import KDriveClient, KDriveError
from services.common.kdrive.config import (
    KDRIVE_ROOT_FOLDER_ID,
    KDRIVE_UPLOAD_WORKERS,
)
from services.common.kdrive.paths import (
    DOC_FOLDERS,
    PROJECT_SUBFOLDERS,
    ROLE_SUBFOLDERS,
    build_document_directory_path,
    build_project_path,
    build_project_rel_path,
    clean_segment,
    format_name,
    get_project_date_reference,
)

logger = logging.getLogger("kdrive.service")


class KDriveService:
    """
    Service métier d'orchestration kDrive pour la plateforme Belle Vitesse.
    Garantit l'idempotence, l'accès direct aux fichiers du disque local,
    l'envoi concurrent des pièces jointes et la suppression par ID.
    """

    def __init__(self, client: Optional[KDriveClient] = None):
        self.client = client or KDriveClient()

    def _resolve_output_path(self, rel_or_abs_path: str) -> Path:
        """Résout un chemin relatif par rapport à OUTPUT_FOLDER ou le retourne s'il est absolu et existant."""
        p = Path(rel_or_abs_path)
        if p.is_absolute() and p.exists():
            return p

        output_base = None
        try:
            if current_app:
                output_base = current_app.config.get("OUTPUT_FOLDER")
        except RuntimeError:
            pass

        if not output_base:
            output_base = os.getenv("OUTPUT_FOLDER", "/app/output")

        clean_rel = str(rel_or_abs_path).lstrip("/")
        return Path(output_base) / clean_rel

    def ensure_project_tree(self, project_id_or_obj) -> int:
        """
        Crée ou retrouve l'arborescence complète d'un projet sur kDrive :
        <Année>/<Mois>/<Production>/<Projet>/<project_id>/
        ├── 1_DEVIS/
        ├── 2_FACTURES/
        ├── 3_LISTES/
        ├── 4_SÉCURITÉ/
        │   ├── 1_CHECKOUT/
        │   ├── 2_DÉCHARGE_PILOTE/
        │   ├── 3_DÉCHARGE_PRODUCTION/
        │   └── 4_CHECKIN/
        ├── 5_BTS/
        └── 6_INCIDENTS/

        Retourne l'ID kDrive du dossier <project_id>.
        """
        if isinstance(project_id_or_obj, Project):
            project = project_id_or_obj
        else:
            project = db.session.get(Project, project_id_or_obj)

        if not project:
            logger.warning(f"⚠️ Projet introuvable pour l'ID: {project_id_or_obj}")
            return None

        # 1. Si le dossier kDrive existe déjà et est valide, le réutiliser
        if project.kdrive_folder_id:
            try:
                info = self.client.get_file(project.kdrive_folder_id)
                if info and info.get("status") != "deleted":
                    logger.info(f"✓ Dossier kDrive déjà existant pour le projet {project.name} (id={project.kdrive_folder_id})")
                    return project.kdrive_folder_id
            except KDriveError:
                logger.warning(f"⚠️ Dossier {project.kdrive_folder_id} non trouvé sur kDrive, recréation nécessaire.")

        date_ref = get_project_date_reference(project)
        prod_name = project.production.name if (project.production and project.production.name) else "SANS_PRODUCTION"
        proj_name = project.name
        proj_id_clean = clean_segment(project.project_id, "project_id")

        rel_parent = build_project_rel_path(date_ref, date_ref, prod_name, proj_name)

        # 2. Création de la hiérarchie en 1 SEUL appel via relative_path
        logger.info(f"📁 Création du dossier projet kDrive: {rel_parent}/{proj_id_clean}")
        dir_res = self.client.create_directory(
            parent_id=KDRIVE_ROOT_FOLDER_ID,
            name=proj_id_clean,
            relative_path=rel_parent,
        )
        project_folder_id = dir_res["id"]

        # 3. Création des 6 sous-dossiers standards
        for sub in PROJECT_SUBFOLDERS:
            sub_res = self.client.create_directory(parent_id=project_folder_id, name=sub)
            # Pour 4_SÉCURITÉ, créer également ses 4 sous-catégories
            if sub == "4_SÉCURITÉ":
                sec_id = sub_res["id"]
                for sec_sub in ["1_CHECKOUT", "2_DÉCHARGE_PILOTE", "3_DÉCHARGE_PRODUCTION", "4_CHECKIN"]:
                    self.client.create_directory(parent_id=sec_id, name=sec_sub)

        # 4. Mise à jour du projet en base
        project.kdrive_folder_id = project_folder_id
        project.kdrive_path = build_project_path(project)
        project.kdrive_sync_status = "synced"
        project.kdrive_last_error = None
        db.session.commit()

        logger.info(f"✅ Arborescence kDrive prête pour {project.name} (id={project_folder_id})")
        return project_folder_id

    def check_and_repair_project_structure(self, project: Project, dry_run: bool = False) -> List[str]:
        """
        Vérifie que l'ensemble de l'arborescence standard (6 sous-dossiers + 4 sous-dossiers de sécurité)
        est bien présente dans le dossier kDrive du projet. Recrée automatiquement tout dossier manquant.
        Retourne la liste des dossiers qui ont dû être réparés/recréés (ou détectés manquants en dry-run).
        """
        if not project.kdrive_folder_id:
            if not dry_run:
                self.ensure_project_tree(project)
            return ["*arborescence_complete*"]

        repaired = []
        try:
            items, _, _ = self.client.list_files(project.kdrive_folder_id, limit=100)
            existing_dirs = {item["name"]: item["id"] for item in items if item.get("type") == "dir"}

            sec_id = None
            for sub in PROJECT_SUBFOLDERS:
                if sub not in existing_dirs:
                    if dry_run:
                        logger.info(f"🔍 [DRY-RUN] Sous-dossier manquant détecté : '{sub}' dans projet {project.name} (#{project.id})")
                    else:
                        logger.info(f"🔧 Réparation kDrive : création du sous-dossier manquant '{sub}' dans projet {project.name}")
                        sub_res = self.client.create_directory(parent_id=project.kdrive_folder_id, name=sub)
                        existing_dirs[sub] = sub_res["id"]
                    repaired.append(sub)

                if sub == "4_SÉCURITÉ":
                    sec_id = existing_dirs.get(sub)

            # Vérifier les sous-catégories de sécurité
            if sec_id:
                sec_items, _, _ = self.client.list_files(sec_id, limit=50)
                existing_sec = {item["name"] for item in sec_items if item.get("type") == "dir"}
                for sec_sub in ["1_CHECKOUT", "2_DÉCHARGE_PILOTE", "3_DÉCHARGE_PRODUCTION", "4_CHECKIN"]:
                    if sec_sub not in existing_sec:
                        if dry_run:
                            logger.info(f"🔍 [DRY-RUN] Sous-dossier manquant détecté : '4_SÉCURITÉ/{sec_sub}' dans projet {project.name} (#{project.id})")
                        else:
                            logger.info(f"🔧 Réparation kDrive : création du sous-dossier manquant '4_SÉCURITÉ/{sec_sub}' dans projet {project.name}")
                            self.client.create_directory(parent_id=sec_id, name=sec_sub)
                        repaired.append(f"4_SÉCURITÉ/{sec_sub}")

        except Exception as e:
            logger.error(f"❌ Erreur lors de la vérification de structure pour le projet {project.name}: {e}")

        return repaired

    def ensure_directory_path(self, parent_id: int, relative_path: str) -> int:
        """
        Assure l'existence d'une chaîne de répertoires sous parent_id et retourne l'ID du dernier dossier.
        ex: ensure_directory_path(proj_id, "4_SÉCURITÉ/1_CHECKOUT/BVCO-1234/PHOTOS")
        """
        segments = [clean_segment(s, "dir_part") for s in relative_path.strip("/").split("/") if s]
        curr_id = parent_id

        for seg in segments:
            res = self.client.create_directory(parent_id=curr_id, name=seg)
            curr_id = res["id"]

        return curr_id

    def upload_file_sync(
        self,
        project: Project,
        entity_type: str,
        entity_id: str,
        role: str,
        local_file_path: str,
        custom_filename: Optional[str] = None,
    ) -> KDriveObject:
        """
        Upload direct et idempotent d'un fichier physique local vers kDrive.
        Enregistre la trace dans la table kdrive_objects.
        """
        full_path = self._resolve_output_path(local_file_path)
        if not full_path.exists():
            raise FileNotFoundError(f"Fichier physique introuvable sur le serveur : {full_path}")

        file_bytes = full_path.read_bytes()
        file_sha256 = hashlib.sha256(file_bytes).hexdigest()
        filename = custom_filename or full_path.name
        source_key = local_file_path.lstrip("/")

        # 1. Vérification idempotence en DB
        k_obj = KDriveObject.query.filter_by(
            entity_type=entity_type,
            entity_id=entity_id,
            role=role,
            source_key=source_key,
        ).first()

        if k_obj and k_obj.status == "synced" and k_obj.kdrive_file_id:
            logger.info(f"✓ Fichier déjà synchronisé sur kDrive : {entity_type}/{entity_id}/{role} ({filename})")
            return k_obj

        if not k_obj:
            k_obj = KDriveObject(
                project_id=project.id,
                entity_type=entity_type,
                entity_id=entity_id,
                role=role,
                source_key=source_key,
                status="pending",
            )
            db.session.add(k_obj)
            db.session.commit()

        # 2. S'assurer de l'existence du dossier projet et du sous-dossier cible
        proj_folder_id = self.ensure_project_tree(project)
        rel_dir = build_document_directory_path(project, entity_type, entity_id, role)
        dest_dir_id = self.ensure_directory_path(proj_folder_id, rel_dir)

        # 3. Upload vers kDrive
        k_obj.attempts += 1
        try:
            res = self.client.upload(
                directory_id=dest_dir_id,
                filename=filename,
                content_bytes=file_bytes,
                conflict="error",
            )
            k_obj.kdrive_file_id = res["id"]
            k_obj.kdrive_dir_id = dest_dir_id
            k_obj.status = "synced"
            k_obj.last_error = None
            db.session.commit()
            logger.info(f"✅ Upload kDrive réussi: {filename} -> dossier {dest_dir_id} (file_id={res['id']})")
            return k_obj
        except Exception as err:
            k_obj.status = "failed"
            k_obj.last_error = str(err)
            db.session.commit()
            logger.error(f"❌ Échec upload kDrive {filename} : {err}")
            raise

    def upload_bundle_sync(
        self,
        project_id: int,
        entity_type: str,
        entity_id: str,
        file_specs: List[Dict[str, Any]],
    ) -> List[KDriveObject]:
        """
        Upload concurrent d'un lot complet de fichiers (ex: 1 PDF scellé + 20 photos).
        file_specs = [
            {"role": "pdf", "path": "2026/09/.../contrat.pdf", "filename": "contrat.pdf"},
            {"role": "photo", "path": "2026/09/.../photo1.jpg"},
            ...
        ]
        """
        project = db.session.get(Project, project_id)
        if not project:
            logger.warning(f"⚠️ Projet introuvable: {project_id}")
            return []

        # S'assurer d'abord que le dossier projet existe (appel unique)
        self.ensure_project_tree(project)

        results = []
        errors = []

        # Upload des fichiers du lot dans le contexte de la tâche d'arrière-plan
        for spec in file_specs:
            file_path = spec.get("path")
            if not file_path:
                continue

            try:
                k_obj = self.upload_file_sync(
                    project=project,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    role=spec.get("role", "file"),
                    local_file_path=file_path,
                    custom_filename=spec.get("filename"),
                )
                results.append(k_obj)
            except Exception as exc:
                logger.error(f"❌ Erreur bundle {entity_type}/{entity_id} sur {file_path} : {exc}")
                errors.append(str(exc))

        if errors and not results:
            raise RuntimeError(f"Échec de {len(errors)} fichier(s) dans le lot : {', '.join(errors[:3])}")

        return results

    def move_project_folder(
        self,
        project_id: int,
        old_year: Optional[str] = None,
        old_month: Optional[str] = None,
        old_prod_name: Optional[str] = None,
        old_proj_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Déplace de façon atomique le dossier racine <project_id> vers son nouvel emplacement :
        <Nouvelle_Année>/<Nouveau_Mois>/<Nouvelle_Production>/<Nouveau_Projet>/<project_id>/
        """
        project = db.session.get(Project, project_id)
        if not project:
            raise ValueError(f"Projet introuvable: {project_id}")

        if not project.kdrive_folder_id:
            logger.info(f"ℹ️ Pas de kdrive_folder_id pour le projet {project.name}, création de l'arborescence...")
            self.ensure_project_tree(project)
            return {"moved": False, "created": True}

        date_ref = get_project_date_reference(project)
        new_prod = project.production.name if (project.production and project.production.name) else "SANS_PRODUCTION"
        new_proj = project.name
        new_parent_rel = build_project_rel_path(date_ref, date_ref, new_prod, new_proj)

        old_parent_rel = ""
        if old_year and old_month and old_prod_name and old_proj_name:
            old_parent_rel = build_project_rel_path(old_year, old_month, old_prod_name, old_proj_name)

        # Si le chemin relatif du parent n'a pas changé, rien à déplacer
        if old_parent_rel and old_parent_rel == new_parent_rel:
            logger.info(f"ℹ️ Aucun changement d'emplacement pour le projet {project.name}")
            return {"moved": False, "same_path": True}

        logger.info(f"📦 Déplacement du projet {project.name} vers {new_parent_rel}...")

        # 1. Assurer l'existence du nouveau dossier parent (<Nouveau_Projet>)
        # relative_path = <Nouvelle_Année>/<Nouveau_Mois>/<Nouvelle_Production>
        segments = new_parent_rel.split("/")
        grandparent_rel = "/".join(segments[:-1])
        dest_parent_name = segments[-1]

        dest_dir_res = self.client.create_directory(
            parent_id=KDRIVE_ROOT_FOLDER_ID,
            name=dest_parent_name,
            relative_path=grandparent_rel,
        )
        new_dest_id = dest_dir_res["id"]

        # 2. Déplacement atomique du dossier <project_id>
        move_res = self.client.move(
            file_id=project.kdrive_folder_id,
            destination_directory_id=new_dest_id,
            conflict="error",
        )

        project.kdrive_path = build_project_path(project)
        project.kdrive_last_cancel_id = move_res.get("cancel_id")
        project.kdrive_sync_status = "synced"
        project.kdrive_last_error = None
        db.session.commit()

        logger.info(f"✅ Projet {project.name} déplacé avec succès vers {project.kdrive_path}")
        return move_res

    def delete_entity(self, entity_type: str, entity_id: str) -> bool:
        """
        Supprime le dossier d'un document ou d'un incident sur kDrive en utilisant EXCLUSIVEMENT son ID réel.
        Supprime les entrées associées dans kdrive_objects.
        """
        objects = KDriveObject.query.filter_by(
            entity_type=entity_type,
            entity_id=entity_id,
        ).all()

        if not objects:
            logger.warning(f"⚠️ Aucun objet kDrive trouvé en base pour {entity_type} {entity_id}.")
            return False

        # Récupération de l'ID du dossier parent de l'entité (<document_id>)
        dir_ids = {obj.kdrive_dir_id for obj in objects if obj.kdrive_dir_id}

        for dir_id in dir_ids:
            try:
                # Pour les sous-dossiers (ex: PHOTOS), on peut supprimer directement le dossier racine <document_id>
                # En vérifiant le parent ou en supprimant le dir_id
                logger.info(f"🗑️ Suppression kDrive du dossier {dir_id} pour {entity_type} {entity_id}...")
                self.client.delete(dir_id)
            except Exception as err:
                logger.error(f"❌ Erreur lors de la suppression du dossier {dir_id} : {err}")

        # Nettoyage de la base de données
        for obj in objects:
            db.session.delete(obj)

        db.session.commit()
        logger.info(f"✅ Suppression terminée pour {entity_type} {entity_id}")
        return True

    def delete_project_folder(self, project_id: int, folder_id: Optional[int] = None) -> bool:
        """
        Supprime le dossier complet d'un projet sur kDrive et nettoie ses kdrive_objects en base.
        """
        project = db.session.get(Project, project_id)
        target_folder_id = folder_id
        if not target_folder_id and project:
            target_folder_id = project.kdrive_folder_id

        # Recherche de secours si folder_id non renseigné en DB
        if not target_folder_id and project and project.project_id:
            try:
                date_ref = project.departure_date or project.shoot_start_date
                prod_name = project.production.name if project.production else "SANS_PRODUCTION"
                parent_path = build_project_rel_path(date_ref, date_ref, prod_name, project.name)
                curr_parent = KDRIVE_ROOT_FOLDER_ID
                for seg in parent_path.split("/"):
                    child = self.client.get_child_by_name(curr_parent, seg)
                    if not child:
                        curr_parent = None
                        break
                    curr_parent = child["id"]
                if curr_parent:
                    child = self.client.get_child_by_name(curr_parent, project.project_id)
                    if child:
                        target_folder_id = child["id"]
            except Exception as e:
                logger.warning(f"⚠️ Impossible de retrouver le dossier kDrive pour le projet {project_id}: {e}")

        if target_folder_id:
            try:
                parent_id = None
                try:
                    meta = self.client.get_file(target_folder_id)
                    parent_id = meta.get("parent_id")
                except Exception as meta_err:
                    logger.warning(f"⚠️ Impossible de récupérer le parent de {target_folder_id}: {meta_err}")

                logger.info(f"🗑️ Suppression kDrive du dossier projet {target_folder_id} (ID DB={project_id})...")
                self.client.delete(target_folder_id)

                # Remonte l'arborescence et supprime les parents jusqu'au premier dossier non vide
                if parent_id:
                    self._prune_empty_parents_upwards(parent_id)

            except Exception as err:
                logger.error(f"❌ Erreur suppression kDrive du dossier projet {target_folder_id} : {err}")
                if project:
                    project.kdrive_last_error = str(err)
                    project.kdrive_sync_status = "failed"
                    db.session.commit()
                return False

        # Nettoyage des kdrive_objects associés au projet
        KDriveObject.query.filter_by(project_id=project_id).delete()
        if project:
            project.kdrive_folder_id = None
            project.kdrive_sync_status = "deleted"
            project.kdrive_last_error = None
        db.session.commit()
        logger.info(f"✅ Dossier projet kDrive supprimé avec succès pour projet ID={project_id}")
        return True

    def _prune_empty_parents_upwards(
        self, parent_id: Optional[int], stop_at_id: int = KDRIVE_ROOT_FOLDER_ID
    ):
        """
        Remonte l'arborescence kDrive depuis parent_id et supprime récursivement chaque dossier parent
        s'il est devenu totalement vide, jusqu'au premier dossier non-vide (sans jamais supprimer stop_at_id).
        """
        curr_id = parent_id
        while curr_id and curr_id != stop_at_id:
            try:
                meta = self.client.get_file(curr_id)
                parent_of_curr = meta.get("parent_id")
                folder_name = meta.get("name", str(curr_id))

                # Vérifier si ce dossier a encore des enfants (fichiers ou sous-dossiers)
                items, _, _ = self.client.list_files(curr_id, limit=1)
                if len(items) == 0:
                    logger.info(
                        f"🗑️ Dossier parent vide sur kDrive, suppression : '{folder_name}' (ID={curr_id})..."
                    )
                    self.client.delete(curr_id)
                    curr_id = parent_of_curr
                else:
                    logger.info(
                        f"🛑 Dossier parent '{folder_name}' (ID={curr_id}) non-vide ({len(items)}+ élément(s)), arrêt de la remontée."
                    )
                    break
            except Exception as err:
                logger.warning(
                    f"⚠️ Arrêt de la remontée kDrive sur dossier {curr_id}: {err}"
                )
                break
