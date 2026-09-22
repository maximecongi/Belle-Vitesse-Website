"""
Module de gestion de l'arborescence et du cycle de vie des projets sur kDrive.
Fournit le mixin ProjectTreeMixin.
"""
import logging
from typing import Any, Dict, List, Optional

from models.db import db
from models.kdrive import KDriveObject
from models.project import Project
from services.common.kdrive.client import KDriveError
from services.common.kdrive.config import KDRIVE_ROOT_FOLDER_ID
from services.common.kdrive.paths import (
    PROJECT_SUBFOLDERS,
    build_project_path,
    build_project_rel_path,
    clean_segment,
    format_name,
    get_project_date_reference,
)

logger = logging.getLogger("kdrive.tree")


class ProjectTreeMixin:
    """
    Mixin responsable de la création, vérification, déplacement
    et suppression des arborescences de projets sur kDrive.
    """

    def ensure_project_tree(self, project_id_or_obj) -> Optional[int]:
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

        # 1. Récupération de l'ancien dossier parent avant le déplacement
        old_parent_id = None
        try:
            curr_meta = self.client.get_file(project.kdrive_folder_id)
            old_parent_id = curr_meta.get("parent_id")
        except Exception as e_meta:
            logger.warning(f"⚠️ Impossible de récupérer l'ancien parent de {project.kdrive_folder_id}: {e_meta}")

        # 2. Assurer l'existence du nouveau dossier parent (<Nouveau_Projet>)
        segments = new_parent_rel.split("/")
        grandparent_rel = "/".join(segments[:-1])
        dest_parent_name = segments[-1]

        dest_dir_res = self.client.create_directory(
            parent_id=KDRIVE_ROOT_FOLDER_ID,
            name=dest_parent_name,
            relative_path=grandparent_rel,
        )
        new_dest_id = dest_dir_res["id"]

        # 3. Déplacement atomique du dossier <project_id>
        move_res = self.client.move(
            file_id=project.kdrive_folder_id,
            destination_directory_id=new_dest_id,
            conflict="error",
        )

        # 4. Nettoyage de l'ancien emplacement : suppression de l'ancien parent s'il est devenu vide (remonte récursivement)
        if old_parent_id and old_parent_id != new_dest_id:
            try:
                self._prune_empty_parents_upwards(old_parent_id)
            except Exception as e_prune:
                logger.warning(f"⚠️ Erreur nettoyage ancien dossier parent {old_parent_id}: {e_prune}")

        project.kdrive_path = build_project_path(project)
        project.kdrive_last_cancel_id = move_res.get("cancel_id")
        project.kdrive_sync_status = "synced"
        project.kdrive_last_error = None
        db.session.commit()

        logger.info(f"✅ Projet {project.name} déplacé avec succès vers {project.kdrive_path}")
        return move_res

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

    def rename_production_folders(self, old_name: str, new_name: str) -> Dict[str, Any]:
        """
        Recherche tous les dossiers de production portant l'ancien nom dans l'arborescence kDrive
        (1_TOURNAGES/<Année>/<Mois>/<old_name>) et les renomme avec le nouveau nom.

        En l'absence de collision : renommage direct via POST /2/.../rename (ultra-rapide et atomique).
        En cas de collision (le nouveau nom existe déjà dans le même mois) : déplace les sous-dossiers projets
        vers le dossier existant et purge l'ancien dossier devenu vide.

        Met également à jour project.kdrive_path pour l'ensemble des projets rattachés.
        """
        old_clean = format_name(old_name, "production")
        new_clean = format_name(new_name, "production")

        if old_clean == new_clean:
            logger.info(f"ℹ️ Aucun renommage kDrive nécessaire pour la production '{old_name}' (nom identique après normalisation en majuscules: '{new_clean}').")
            return {"renamed": 0, "merged": 0, "total": 0}

        logger.info(f"🏷️ Démarrage du renommage de la production kDrive : '{old_clean}' -> '{new_clean}'...")

        renamed_count = 0
        merged_count = 0

        try:
            years, _, _ = self.client.list_files(KDRIVE_ROOT_FOLDER_ID, limit=50)
            for y in years:
                if y.get("type") != "dir":
                    continue
                y_id, y_name = y["id"], y.get("name")

                months, _, _ = self.client.list_files(y_id, limit=50)
                for m in months:
                    if m.get("type") != "dir":
                        continue
                    m_id, m_name = m["id"], m.get("name")

                    # Vérifier si l'ancien dossier de production existe sous ce mois (insensible à la casse)
                    old_prod_folder = self.client.get_child_by_name(m_id, old_clean, case_insensitive=True)
                    if not old_prod_folder:
                        continue

                    old_prod_id = old_prod_folder["id"]
                    month_path = f"{y_name}/{m_name}"

                    # Vérifier si le nouveau nom existe déjà sous ce mois (collision potentielle)
                    new_prod_folder = self.client.get_child_by_name(m_id, new_clean, case_insensitive=True)

                    if not new_prod_folder or new_prod_folder["id"] == old_prod_id:
                        # Cas standard : pas de collision avec un autre dossier -> Renommage direct
                        if old_prod_folder.get("name") != new_clean:
                            logger.info(f"⚡ Renommage direct kDrive du dossier production '{old_prod_folder.get('name')}' -> '{new_clean}' sous {month_path} (ID={old_prod_id})...")
                            self.client.rename(old_prod_id, new_clean)
                            renamed_count += 1
                        else:
                            logger.info(f"ℹ️ Le dossier {month_path}/{new_clean} porte déjà exactement le nom cible.")
                    else:
                        # Cas de collision : un autre dossier porte déjà le nom cible -> fusionner le contenu
                        dest_prod_id = new_prod_folder["id"]
                        logger.warning(f"⚠️ Collision détectée sous {month_path} : '{new_clean}' existe déjà (ID={dest_prod_id}). Déplacement des projets...")
                        children, _, _ = self.client.list_files(old_prod_id, limit=200)
                        for child in children:
                            child_id = child["id"]
                            child_name = child.get("name")
                            logger.info(f"📦 Déplacement du projet '{child_name}' vers la nouvelle production...")
                            self.client.move(child_id, dest_prod_id, conflict="error")

                        # Supprimer l'ancien dossier de production désormais vide
                        self.client.delete(old_prod_id)
                        merged_count += 1

        except Exception as err:
            logger.error(f"❌ Erreur lors du renommage des dossiers kDrive de la production '{old_name}' : {err}")
            raise

        # Mise à jour des kdrive_path de tous les projets en base qui étaient rattachés à cette production
        from models import Production
        prod_obj = Production.query.filter(
            (Production.name == new_name) | (Production.name == old_name)
        ).first()
        if not prod_obj:
            for cand in Production.query.all():
                if cand.name and format_name(cand.name, "production") in (new_clean, old_clean):
                    prod_obj = cand
                    break

        if prod_obj and hasattr(prod_obj, "projects"):
            for p in prod_obj.projects:
                if p.deleted_at is None and p.kdrive_folder_id:
                    try:
                        p.kdrive_path = build_project_path(p)
                    except Exception as e_path:
                        logger.warning(f"⚠️ Impossible de recalculer kdrive_path pour projet #{p.id}: {e_path}")
            db.session.commit()

        total = renamed_count + merged_count
        logger.info(f"✅ Renommage kDrive de la production terminé : {renamed_count} renommé(s), {merged_count} fusionné(s) (Total {total} mois).")
        return {"renamed": renamed_count, "merged": merged_count, "total": total}
