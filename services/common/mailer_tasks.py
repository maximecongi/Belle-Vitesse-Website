import functools
import logging
import os
import threading
from typing import Any, Dict, List, Optional, Union

from flask import current_app, has_app_context

from services.common.redis_queue import get_rq_queue

logger = logging.getLogger("mailer.tasks")


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
def task_send_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
    sender_type: str = "contact",
    cc: Optional[Union[str, List[str]]] = None,
    attachments: Optional[List[Union[str, Dict[str, str]]]] = None,
    extra_headers: Optional[Dict[str, str]] = None,
    timeout: int = 15,
) -> bool:
    """
    Tâche exécutée par le worker RQ (ou en direct) pour construire le message MIME
    et l'expédier via le relais SMTP configuré.
    """
    from utils.mailer import EmailService

    try:
        msg = EmailService.build_mime_message(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            cc=cc,
            attachments=attachments,
            extra_headers=extra_headers,
        )

        recipients = [to_email]
        if cc:
            if isinstance(cc, list):
                recipients.extend(cc)
            else:
                recipients.append(cc)

        success = EmailService._send_smtp_message(
            msg,
            recipients,
            sender_type=sender_type,
            timeout=timeout,
        )

        if success:
            logger.info(f"✅ [Mailer Job] E-mail '{subject}' expédié avec succès à {to_email}")
        else:
            logger.error(f"❌ [Mailer Job] Échec d'envoi de l'e-mail '{subject}' à {to_email}")

        return success

    except Exception as e:
        logger.error(
            f"❌ [Mailer Job] Exception lors de l'envoi de l'e-mail '{subject}' à {to_email} : {e}",
            exc_info=True,
        )
        raise


def dispatch_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
    sender_type: str = "contact",
    cc: Optional[Union[str, List[str]]] = None,
    attachments: Optional[List[Union[str, Dict[str, str]]]] = None,
    extra_headers: Optional[Dict[str, str]] = None,
    timeout: int = 15,
    sync: bool = False,
) -> bool:
    """
    Achemine l'e-mail transactionnel de manière asynchrone :
    1. En mode test (ou si sync=True) : exécution synchrone immédiate.
    2. Tente de déléguer la tâche à la file RQ 'emails'.
    3. Si Redis / RQ est indisponible (ex: dev local sans Redis), bascule sur un thread daemon.
    """
    is_testing = (
        sync
        or os.getenv("FLASK_ENV") == "testing"
        or os.getenv("TESTING") == "True"
        or (current_app and current_app.config.get("TESTING"))
        or (current_app and getattr(current_app, "testing", False))
    )

    if is_testing:
        return task_send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            sender_type=sender_type,
            cc=cc,
            attachments=attachments,
            extra_headers=extra_headers,
            timeout=timeout,
        )

    # 1. Tenter d'enfiler dans RQ
    queue = get_rq_queue("emails")
    if queue is not None:
        try:
            job = queue.enqueue(
                "services.common.mailer_tasks.task_send_email",
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                sender_type=sender_type,
                cc=cc,
                attachments=attachments,
                extra_headers=extra_headers,
                timeout=timeout,
                job_timeout=60,
                result_ttl=3600,
                failure_ttl=86400,
            )
            logger.info(f"📬 [RQ emails] E-mail '{subject}' mis en file pour {to_email} (job ID: {job.id})")
            return True
        except Exception as rq_err:
            logger.warning(
                f"⚠️ [RQ emails] Échec de mise en file pour {to_email} ({rq_err}), bascule sur thread daemon."
            )

    # 2. Repli vers thread daemon si Redis/RQ indisponible
    app = current_app._get_current_object() if current_app else None

    def _async_thread_worker():
        if app:
            with app.app_context():
                try:
                    task_send_email(
                        to_email=to_email,
                        subject=subject,
                        html_content=html_content,
                        text_content=text_content,
                        sender_type=sender_type,
                        cc=cc,
                        attachments=attachments,
                        extra_headers=extra_headers,
                        timeout=timeout,
                    )
                except Exception as thread_err:
                    logger.error(f"❌ [Thread fallback] Erreur envoi email: {thread_err}")
        else:
            try:
                task_send_email(
                    to_email=to_email,
                    subject=subject,
                    html_content=html_content,
                    text_content=text_content,
                    sender_type=sender_type,
                    cc=cc,
                    attachments=attachments,
                    extra_headers=extra_headers,
                    timeout=timeout,
                )
            except Exception as thread_err:
                logger.error(f"❌ [Thread fallback] Erreur envoi email: {thread_err}")

    thread = threading.Thread(target=_async_thread_worker, daemon=True)
    thread.start()
    logger.info(f"🧵 [Thread fallback] E-mail '{subject}' expédié en arrière-plan pour {to_email}")
    return True
