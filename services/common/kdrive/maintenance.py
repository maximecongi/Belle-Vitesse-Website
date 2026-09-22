"""
Module de maintenance et de nettoyage de l'arborescence kDrive.
Fournit le mixin MaintenanceMixin.
"""
import logging
from typing import List, Optional

from models.db import db
from models.kdrive import KDriveObject
from services.common.kdrive.config import KDRIVE_ROOT_FOLDER_ID
from services.common.kdrive.paths import DOC_FOLDERS

logger = logging.getLogger("kdrive.maintenance")


class MaintenanceMixin:
    """
    Mixin responsable de la maintenance de l'arborescence kDrive :
    purge des conteneurs projets orphelins, suppression d'entités (documents/incidents)
    et remontée récursive de nettoyage des dossiers parents vides.
    """

    def prune_orphan_project_containers(self, dry_run: bool = False) -> List[str]:
        """
        Scanne UNIQUEMENT le niveau externe de l'arborescence kDrive :
        1_TOURNAGES / <Année> / <Mois> / <Production> / <Nom_Projet>
        Si un conteneur <Nom_Projet> ne contient aucun dossier projet (aucun BVPR-*) et est totalement vide,
        il est supprimé (ex: ancien dossier laissé après déplacement de projet comme 'TEST PROJET 4').
        Remonte ensuite supprimer la production et le mois s'ils sont devenus totalement vides.
        SANCTUARISATION ABSOLUE : ne pénètre JAMAIS dans les dossiers projets BVPR-* et ne touche
        JAMAIS à leur structure interne (1_DEVIS, 2_FACTURES, 3_LISTES, 4_SÉCURITÉ, 5_BTS, 6_INCIDENTS).
        """
        purged = []
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

                    prods, _, _ = self.client.list_files(m_id, limit=100)
                    for prod in prods:
                        if prod.get("type") != "dir":
                            continue
                        prod_id, prod_name = prod["id"], prod.get("name")

                        proj_containers, _, _ = self.client.list_files(prod_id, limit=100)
                        for pc in proj_containers:
                            if pc.get("type") != "dir":
                                continue
                            pc_id, pc_name = pc["id"], pc.get("name")

                            # Vérifier si ce conteneur de projet a des enfants
                            children, _, _ = self.client.list_files(pc_id, limit=5)
                            # S'il est totalement vide (aucun sous-dossier projet BVPR-*, aucun fichier)
                            if len(children) == 0:
                                container_path = f"{y_name}/{m_name}/{prod_name}/{pc_name}"
                                if dry_run:
                                    logger.info(f"🔍 [DRY-RUN] Conteneur projet orphelin vide détecté : '{container_path}' (ID={pc_id})")
                                else:
                                    logger.info(f"🗑️ Purge du conteneur projet orphelin vide : '{container_path}' (ID={pc_id})...")
                                    try:
                                        self.client.delete(pc_id)
                                        # Remonter vers la production puis le mois si devenus vides
                                        self._prune_empty_parents_upwards(prod_id)
                                    except Exception as e_del:
                                        logger.warning(f"⚠️ Impossible de supprimer {container_path}: {e_del}")
                                purged.append(container_path)

        except Exception as e:
            logger.error(f"❌ Erreur lors du scan des conteneurs de projet orphelins : {e}")

        return purged

    def delete_entity(self, entity_type: str, entity_id: str) -> bool:
        """
        Supprime le dossier complet d'un document ou d'un incident (<document_id>) sur kDrive.
        Supprime également toutes les entrées associées dans kdrive_objects.
        Garantit que le dossier du document (ex: BVPW-XXXX) est lui-même supprimé et ne reste pas vide.
        """
        objects = KDriveObject.query.filter_by(
            entity_type=entity_type,
            entity_id=entity_id,
        ).all()

        entity_folder_ids = set()

        # 1. Identifier le dossier racine de l'entité à partir des kdrive_objects
        for obj in objects:
            if not obj.kdrive_dir_id:
                continue
            try:
                meta = self.client.get_file(obj.kdrive_dir_id)
                folder_name = meta.get("name")
                # Si le dossier est déjà le dossier de l'entité (ex: BVPW-XXX, BVCO-XXX, BVIC-XXX)
                if folder_name == entity_id:
                    entity_folder_ids.add(obj.kdrive_dir_id)
                else:
                    # Sinon, il s'agit d'un sous-dossier (ex: 1_DÉCHARGE, PHOTOS), le parent est le dossier de l'entité
                    parent_id = meta.get("parent_id")
                    if parent_id:
                        try:
                            parent_meta = self.client.get_file(parent_id)
                            if parent_meta.get("name") == entity_id:
                                entity_folder_ids.add(parent_id)
                            else:
                                entity_folder_ids.add(obj.kdrive_dir_id)
                        except Exception:
                            entity_folder_ids.add(parent_id)
                    else:
                        entity_folder_ids.add(obj.kdrive_dir_id)
            except Exception as err:
                logger.warning(f"⚠️ Erreur identification dossier pour {obj.kdrive_dir_id} : {err}")
                entity_folder_ids.add(obj.kdrive_dir_id)

        # 2. Recherche complémentaire dans l'arborescence kDrive du projet si non trouvé
        project = None
        if objects:
            project = objects[0].project
        if not project:
            if entity_type == "pilot_waiver":
                from models import PilotWaiver
                rec = PilotWaiver.query.filter_by(waiver_id=entity_id).first()
                project = rec.project if rec else None
            elif entity_type == "production_waiver":
                from models import ProductionWaiver
                rec = ProductionWaiver.query.filter_by(waiver_id=entity_id).first()
                project = rec.project if rec else None
            elif entity_type == "checkout":
                from models import CheckoutVehicle
                rec = CheckoutVehicle.query.filter_by(inspection_number=entity_id).first()
                project = rec.project if rec else None
            elif entity_type == "checkin":
                from models import CheckinVehicle
                rec = CheckinVehicle.query.filter_by(inspection_number=entity_id).first()
                project = rec.project if rec else None
            elif entity_type == "incident":
                from models import Incident
                rec = Incident.query.filter_by(incident_number=entity_id).first()
                project = rec.project if rec else None

        if project and project.kdrive_folder_id and entity_type in DOC_FOLDERS:
            try:
                cat_rel = DOC_FOLDERS[entity_type]  # ex: 4_SÉCURITÉ/2_DÉCHARGE_PILOTE
                cat_dir_id = self.ensure_directory_path(project.kdrive_folder_id, cat_rel)
                child = self.client.get_child_by_name(cat_dir_id, entity_id)
                if child:
                    entity_folder_ids.add(child["id"])
            except Exception as e_find:
                logger.warning(f"⚠️ Recherche du dossier {entity_id} dans {entity_type} : {e_find}")

        if not entity_folder_ids and not objects:
            logger.warning(f"⚠️ Aucun dossier kDrive ni objet trouvé en base pour {entity_type} {entity_id}.")
            return False

        # 3. Suppression du/des dossier(s) racine(s) de l'entité sur kDrive
        for folder_id in entity_folder_ids:
            try:
                logger.info(f"🗑️ Suppression kDrive du dossier entité {folder_id} ({entity_id})...")
                self.client.delete(folder_id)
            except Exception as err:
                logger.error(f"❌ Erreur lors de la suppression du dossier {folder_id} : {err}")

        # 4. Nettoyage de la base de données
        for obj in objects:
            db.session.delete(obj)

        db.session.commit()
        logger.info(f"✅ Dossier entité kDrive et objets supprimés avec succès pour {entity_type} {entity_id}")
        return True

    def _prune_empty_parents_upwards(
        self, parent_id: Optional[int], stop_at_id: int = KDRIVE_ROOT_FOLDER_ID
    ):
        """
        Remonte l'arborescence kDrive depuis parent_id et supprime récursivement chaque dossier parent
        s'il est devenu totalement vide, jusqu'au premier dossier non-vide (sans jamais supprimer stop_at_id).
        """
        curr_id = parent_id
        steps = 0
        while curr_id and curr_id != stop_at_id and steps < 10:
            steps += 1
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
