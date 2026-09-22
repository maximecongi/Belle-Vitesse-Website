import functools
import logging
import os
import threading
from typing import Any, Dict, List, Optional

from flask import current_app, has_app_context
from redis import Redis
from rq import Queue as RQQueue

from app import create_app
from models.db import db
from models.kdrive import KDriveObject
from models.project import Project
from services.common.kdrive.service import KDriveService

logger = logging.getLogger("kdrive.tasks")

FLASK_ENV = os.getenv("FLASK_ENV", "production")
REDIS_HOST = os.getenv("REDIS_HOST", "bv_redis" if FLASK_ENV == "production" else "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB_KDRIVE", 1))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

_redis_conn: Optional[Redis] = None
_rq_queue: Optional[RQQueue] = None


def get_redis_connection() -> Optional[Redis]:
    global _redis_conn
    if _redis_conn is None:
        try:
            _redis_conn = Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                socket_connect_timeout=2,
            )
            _redis_conn.ping()
        except Exception as err:
            logger.warning(f"⚠️ Redis non disponible pour kDrive ({err}), repli local.")
            _redis_conn = None
    return _redis_conn


def get_rq_queue() -> Optional[RQQueue]:
    global _rq_queue
    conn = get_redis_connection()
    if conn and _rq_queue is None:
        _rq_queue = RQQueue("kdrive", connection=conn)
    return _rq_queue


# ── Tâches Workers (exécutées dans le conteneur worker RQ ou thread local) ──────

def _with_app_context(func):
    """Décorateur assurant qu'une tâche RQ s'exécute dans un contexte Flask actif."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if has_app_context():
            return func(*args, **kwargs)
        app = create_app()
        with app.app_context():
            return func(*args, **kwargs)
    return wrapper


@_with_app_context
def task_create_project_tree(project_id: int):
    """Tâche RQ : Crée l'arborescence kDrive du projet."""
    logger.info(f"🚀 [kDrive Job] task_create_project_tree pour projet ID={project_id}")
    service = KDriveService()
    service.ensure_project_tree(project_id)


@_with_app_context
def task_upload_document_bundle(project_id: int, entity_type: str, entity_id: str, file_specs: List[Dict[str, Any]]):
    """Tâche RQ : Upload un lot de fichiers (PDF + photos) pour une entité."""
    logger.info(f"🚀 [kDrive Job] task_upload_document_bundle pour {entity_type} {entity_id} ({len(file_specs)} fichiers)")
    try:
        service = KDriveService()
        uploaded = service.upload_bundle_sync(project_id, entity_type, entity_id, file_specs)
        logger.info(f"✅ [kDrive Job] {len(uploaded)}/{len(file_specs)} fichier(s) uploadé(s) pour {entity_type} {entity_id}")
        return len(uploaded)
    except Exception as exc:
        logger.error(f"❌ [kDrive Job] Échec upload_document_bundle {entity_type} {entity_id} : {exc}", exc_info=True)
        raise


@_with_app_context
def task_move_project_folder(
    project_id: int,
    old_year: Optional[str] = None,
    old_month: Optional[str] = None,
    old_prod_name: Optional[str] = None,
    old_proj_name: Optional[str] = None,
):
    """Tâche RQ : Déplace l'arborescence kDrive suite à modification du projet."""
    logger.info(f"🚀 [kDrive Job] task_move_project_folder pour projet ID={project_id}")
    service = KDriveService()
    service.move_project_folder(project_id, old_year, old_month, old_prod_name, old_proj_name)


@_with_app_context
def task_delete_document(entity_type: str, entity_id: str):
    """Tâche RQ : Supprime un document par son ID sur kDrive."""
    logger.info(f"🚀 [kDrive Job] task_delete_document pour {entity_type} {entity_id}")
    service = KDriveService()
    service.delete_entity(entity_type, entity_id)


@_with_app_context
def task_delete_project_folder(project_id: int, folder_id: Optional[int] = None):
    """Tâche RQ : Supprime le dossier complet du projet sur kDrive."""
    logger.info(f"🚀 [kDrive Job] task_delete_project_folder pour projet ID={project_id}, folder_id={folder_id}")
    service = KDriveService()
    service.delete_project_folder(project_id, folder_id)


@_with_app_context
def task_retry_pending_kdrive_objects(limit: int = 50):
    """
    Tâche d'autoréparation (Heartbeat) :
    Resynchronise les objets restés à l'état 'pending' ou 'failed' (attempts < 5).
    """
    logger.info(f"🔄 [kDrive Heartbeat] Recherche des objets kDrive en attente (limite={limit})...")
    pending_objs = (
        KDriveObject.query.filter(
            KDriveObject.status.in_(["pending", "failed"]),
            KDriveObject.attempts < 5,
        )
        .order_by(KDriveObject.created_at.asc())
        .limit(limit)
        .all()
    )

    if not pending_objs:
        logger.info("✓ Aucun objet kDrive en attente.")
        return

    logger.info(f"📦 {len(pending_objs)} objet(s) à resynchroniser.")
    service = KDriveService()

    for obj in pending_objs:
        try:
            service.upload_file_sync(
                project=obj.project,
                entity_type=obj.entity_type,
                entity_id=obj.entity_id,
                role=obj.role,
                local_file_path=obj.source_key,
            )
        except Exception as err:
            logger.error(f"❌ Échec resynchro objet {obj.id} ({obj.entity_type}/{obj.entity_id}) : {err}")


# ── Fonctions de dispatch appelées par Flask (après commit SQL) ────────────────

def _dispatch_task(func, *args, **kwargs):
    """
    Dispatche une tâche vers RQ si Redis est actif, sinon dans un thread d'arrière-plan en local.
    En mode TESTING / tests unitaires, n'exécute pas de thread asynchrone détaché pour éviter les courses en DB mémoire.
    """
    is_testing = False
    if has_app_context():
        try:
            is_testing = bool(current_app.config.get("TESTING"))
        except Exception:
            pass

    if is_testing or os.getenv("FLASK_ENV") == "testing":
        # En mode test, on n'exécute pas de thread asynchrone détaché
        return None

    q = get_rq_queue()
    if q is not None:
        try:
            job = q.enqueue(
                f"services.common.kdrive.tasks.{func.__name__}",
                *args,
                **kwargs,
                job_timeout=300,
            )
            logger.info(f"📨 Job kDrive envoyé dans la file RQ: {job.id} ({func.__name__})")
            return job
        except Exception as err:
            logger.warning(f"⚠️ Échec enqueue RQ ({err}), repli thread local.")

    # Exécution dans un thread détaché en dev/local avec propagation propre du contexte Flask
    app = None
    if has_app_context():
        try:
            app = current_app._get_current_object()
        except Exception:
            app = None

    def _thread_worker():
        if app:
            with app.app_context():
                func(*args, **kwargs)
        else:
            func(*args, **kwargs)

    t = threading.Thread(target=_thread_worker, daemon=True)
    t.start()
    return None


def dispatch_create_project_tree(project_id: int):
    return _dispatch_task(task_create_project_tree, project_id)


def dispatch_upload_bundle(project_id: int, entity_type: str, entity_id: str, file_specs: List[Dict[str, Any]]):
    return _dispatch_task(task_upload_document_bundle, project_id, entity_type, entity_id, file_specs)


def dispatch_move_project(
    project_id: int,
    old_year: Optional[str] = None,
    old_month: Optional[str] = None,
    old_prod_name: Optional[str] = None,
    old_proj_name: Optional[str] = None,
):
    return _dispatch_task(
        task_move_project_folder,
        project_id,
        old_year,
        old_month,
        old_prod_name,
        old_proj_name,
    )


def dispatch_delete_document(entity_type: str, entity_id: str):
    return _dispatch_task(task_delete_document, entity_type, entity_id)


def dispatch_delete_project(project_id: int, folder_id: Optional[int] = None):
    return _dispatch_task(task_delete_project_folder, project_id, folder_id)
