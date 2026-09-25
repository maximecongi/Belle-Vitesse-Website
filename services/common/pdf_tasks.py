import functools
import logging
import os
import threading
from typing import Any, Dict, List, Optional, Union

from flask import current_app, has_app_context

from services.common.redis_queue import get_rq_queue
from utils.document_utils import compute_pdf_hash, render_pdf_from_template

logger = logging.getLogger("pdf.tasks")


def _with_app_context(func):
    """Décorateur assurant qu'une tâche s'exécute dans un contexte Flask actif."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if has_app_context():
            return func(*args, **kwargs)
        from app import create_app
        app = create_app()
        with app.app_context():
            return func(*args, **kwargs)
    return wrapper


@_with_app_context
def task_render_pdf_to_file(
    html_content: str,
    output_file_path: str,
    base_url: Optional[str] = None,
    stylesheets: Optional[List[str]] = None,
    compress: bool = True,
    filename: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[Union[str, int]] = None,
    post_action: Optional[str] = None,
    extra_context: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Tâche worker exécutant la compilation WeasyPrint, la compression Pillow
    et l'écriture physique du fichier PDF sur disque, suivie des post-traitements.
    """
    try:
        resolved_base_url = base_url or current_app.root_path
        doc_filename = filename or os.path.basename(output_file_path)

        logger.info(f"🚀 [PDF Job] Démarrage compilation WeasyPrint pour {doc_filename} ({output_file_path})")

        pdf_bytes = render_pdf_from_template(
            html_content=html_content,
            base_url=resolved_base_url,
            stylesheets=stylesheets,
            compress=compress,
            filename=doc_filename,
        )

        os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
        with open(output_file_path, "wb") as f:
            f.write(pdf_bytes)

        file_hash = compute_pdf_hash(pdf_bytes)
        output_base = current_app.config.get(
            "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output")
        )
        rel_pdf_path = os.path.relpath(output_file_path, output_base)

        logger.info(
            f"✅ [PDF Job] Fichier généré avec succès ({len(pdf_bytes)} octets, sha256={file_hash[:12]}...)"
        )

        # Post-traitements selon l'entité
        if entity_type == "waiver" and entity_id:
            from models.db import db
            from models.waiver import (
                PilotWaiver,
                PilotWaiverSignedDocument,
                ProductionWaiver,
                ProductionWaiverSignedDocument,
            )

            waiver = (
                PilotWaiver.query.filter_by(waiver_id=str(entity_id)).first()
                or ProductionWaiver.query.filter_by(waiver_id=str(entity_id)).first()
            )
            if waiver:
                waiver.signed_pdf_path = rel_pdf_path
                signed_doc = (
                    PilotWaiverSignedDocument.query.filter_by(waiver_id=str(entity_id)).first()
                    or ProductionWaiverSignedDocument.query.filter_by(waiver_id=str(entity_id)).first()
                )
                if signed_doc:
                    signed_doc.pdf_file_hash = file_hash
                db.session.commit()

                if post_action == "waiver_post_actions":
                    from services.common.signatures import (
                        _dispatch_kdrive_document_bundle,
                        _send_waiver_confirmation_email,
                    )
                    mode = (extra_context or {}).get("mode", "pilot")
                    _dispatch_kdrive_document_bundle(
                        mode,
                        waiver,
                        rel_pdf_path,
                        resolved_base_url,
                        (extra_context or {}).get("current_hash"),
                        (extra_context or {}).get("snapshot", {}),
                    )
                    _send_waiver_confirmation_email(mode, waiver, output_file_path)

        elif entity_type == "inspection" and entity_id:
            from models.db import db
            from models.inspection import (
                CheckinRecord,
                CheckinSignedDocument,
                CheckoutRecord,
                CheckoutSignedDocument,
            )

            record = (
                CheckoutRecord.query.filter(
                    (CheckoutRecord.inspection_number == str(entity_id))
                    | (CheckoutRecord.id == entity_id)
                ).first()
                or CheckinRecord.query.filter(
                    (CheckinRecord.inspection_number == str(entity_id))
                    | (CheckinRecord.id == entity_id)
                ).first()
            )
            if record:
                record.signed_pdf_path = rel_pdf_path
                signed_doc = (
                    CheckoutSignedDocument.query.filter_by(inspection_id=record.id).first()
                    or CheckinSignedDocument.query.filter_by(inspection_id=record.id).first()
                )
                if signed_doc:
                    signed_doc.pdf_file_hash = file_hash
                db.session.commit()

                if post_action == "inspection_post_actions":
                    from services.common.signatures import _dispatch_kdrive_document_bundle
                    mode = (extra_context or {}).get("mode", "checkout")
                    _dispatch_kdrive_document_bundle(
                        mode,
                        record,
                        rel_pdf_path,
                        resolved_base_url,
                        (extra_context or {}).get("current_hash"),
                        (extra_context or {}).get("snapshot", {}),
                    )

        elif entity_type == "incident" and entity_id:
            from models.db import db
            from models.incident import Incident, IncidentSignedDocument

            inc = Incident.query.filter(
                (Incident.id == entity_id) | (Incident.incident_number == str(entity_id))
            ).first()
            if inc:
                inc.signed_pdf_path = rel_pdf_path
                inc.pdf_file_hash = file_hash
                signed_doc = IncidentSignedDocument.query.filter_by(
                    incident_number=inc.incident_number
                ).first()
                if signed_doc:
                    signed_doc.pdf_file_hash = file_hash
                db.session.commit()

                if post_action == "incident_post_actions":
                    to_email = (extra_context or {}).get("to_email")
                    if to_email:
                        from utils.mailer import send_incident_signed_confirmation_email
                        send_incident_signed_confirmation_email(inc, to_email, output_file_path)

        return True

    except Exception as e:
        logger.error(
            f"❌ [PDF Job] Erreur lors de la génération PDF {output_file_path} : {e}",
            exc_info=True,
        )
        raise


def dispatch_pdf_generation(
    html_content: str,
    output_file_path: str,
    base_url: Optional[str] = None,
    stylesheets: Optional[List[str]] = None,
    compress: bool = True,
    filename: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[Union[str, int]] = None,
    post_action: Optional[str] = None,
    extra_context: Optional[Dict[str, Any]] = None,
    sync: bool = False,
) -> bool:
    """
    Achemine la compilation PDF vers la file RQ 'pdf' (ou repli daemon thread/synchrone).
    En mode de test (ou sync=True), l'exécution est synchrone immédiate.
    """
    is_testing = (
        sync
        or os.getenv("FLASK_ENV") == "testing"
        or os.getenv("TESTING") == "True"
        or (current_app and current_app.config.get("TESTING"))
        or (current_app and getattr(current_app, "testing", False))
    )

    if is_testing:
        return task_render_pdf_to_file(
            html_content=html_content,
            output_file_path=output_file_path,
            base_url=base_url,
            stylesheets=stylesheets,
            compress=compress,
            filename=filename,
            entity_type=entity_type,
            entity_id=entity_id,
            post_action=post_action,
            extra_context=extra_context,
        )

    # 1. Mise en file d'attente RQ
    queue = get_rq_queue("pdf")
    if queue is not None:
        try:
            job = queue.enqueue(
                "services.common.pdf_tasks.task_render_pdf_to_file",
                html_content=html_content,
                output_file_path=output_file_path,
                base_url=base_url,
                stylesheets=stylesheets,
                compress=compress,
                filename=filename,
                entity_type=entity_type,
                entity_id=entity_id,
                post_action=post_action,
                extra_context=extra_context,
                job_timeout=180,
                result_ttl=3600,
                failure_ttl=86400,
            )
            logger.info(f"📬 [RQ pdf] Job de compilation PDF mis en file (ID: {job.id})")
            return True
        except Exception as rq_err:
            logger.warning(
                f"⚠️ [RQ pdf] Échec de mise en file ({rq_err}), bascule sur thread daemon."
            )

    # 2. Repli daemon thread si Redis/RQ indisponible
    app = current_app._get_current_object() if current_app else None

    def _async_thread_worker():
        if app:
            with app.app_context():
                try:
                    task_render_pdf_to_file(
                        html_content=html_content,
                        output_file_path=output_file_path,
                        base_url=base_url,
                        stylesheets=stylesheets,
                        compress=compress,
                        filename=filename,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        post_action=post_action,
                        extra_context=extra_context,
                    )
                except Exception as thread_err:
                    logger.error(f"❌ [Thread fallback PDF] Erreur génération: {thread_err}")
        else:
            try:
                task_render_pdf_to_file(
                    html_content=html_content,
                    output_file_path=output_file_path,
                    base_url=base_url,
                    stylesheets=stylesheets,
                    compress=compress,
                    filename=filename,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    post_action=post_action,
                    extra_context=extra_context,
                )
            except Exception as thread_err:
                logger.error(f"❌ [Thread fallback PDF] Erreur génération: {thread_err}")

    thread = threading.Thread(target=_async_thread_worker, daemon=True)
    thread.start()
    logger.info(f"🧵 [Thread fallback PDF] Compilation PDF lancée en arrière-plan pour {output_file_path}")
    return True
