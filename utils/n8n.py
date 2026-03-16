import logging
import requests as http_requests
from utils.async_tasks import run_async
from flask import current_app

logger = logging.getLogger(__name__)


def trigger_n8n_webhook(url: str, method: str = "POST", **kwargs) -> bool:
    """
    Trigger an n8n webhook with the given URL, HTTP method, and arguments as payload.
    Runs asynchronously in a background thread.
    """
    if not url:
        logger.warning("⚠️ Webhook URL is empty.")
        return False

    app = current_app._get_current_object()

    def _send():
        doc_id = kwargs.get("inspection_id") or kwargs.get(
            "waiver_id") or kwargs.get("project_id") or kwargs.get("id", "")
        log_suffix = f" for {doc_id}" if doc_id else ""

        logger.info(
            f"🚀 Triggering n8n webhook ({method}){log_suffix} asynchronously...")

        try:
            response = http_requests.request(
                method, url, json=kwargs, timeout=10)
            if response.status_code in [200, 201, 204]:
                logger.info(f"✅ n8n webhook triggered{log_suffix}")
            else:
                logger.error(
                    f"❌ n8n webhook failed{log_suffix}: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"❌ n8n webhook exception{log_suffix}: {e}")

    run_async(app, _send)
    return True
