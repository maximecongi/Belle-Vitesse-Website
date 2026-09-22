"""
Module de téléversement et de synchronisation des documents et bundles sur kDrive.
Fournit le mixin UploadMixin.
"""
import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import current_app

from models.db import db
from models.kdrive import KDriveObject
from models.project import Project
from services.common.kdrive.paths import (
    build_document_directory_path,
    clean_segment,
)

logger = logging.getLogger("kdrive.uploads")


class UploadMixin:
    """
    Mixin responsable de la résolution des chemins locaux, de la création
    des répertoires cibles et de l'upload direct ou par lot (bundle) vers kDrive.
    """

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
        Upload d'un lot complet de fichiers (ex: 1 PDF scellé + pièces jointes).
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
