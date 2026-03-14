import logging
import requests as http_requests

logger = logging.getLogger(__name__)


def trigger_n8n_webhook(url: str, method: str = "POST", **kwargs) -> bool:
    """
    Trigger an n8n webhook with the given URL, HTTP method, and arguments as payload.

    Args:
        url (str): The n8n webhook URL.
        method (str): The HTTP method to use (POST, DELETE, etc.).
        **kwargs: The data to send in the JSON payload.

    Returns:
        bool: True if the webhook was triggered successfully, False otherwise.
    """
    if not url:
        logger.warning("⚠️ Webhook URL is empty.")
        return False

    # Extract ID for logging if available (e.g., inspection_id)
    doc_id = kwargs.get("inspection_id") or kwargs.get(
        "waiver_id") or kwargs.get("id", "")
    log_suffix = f" for {doc_id}" if doc_id else ""

    logger.info(f"🚀 Triggering n8n webhook ({method}){log_suffix}...")

    try:
        response = http_requests.request(method, url, json=kwargs, timeout=10)
        if response.status_code in [200, 201, 204]:
            logger.info(f"✅ n8n webhook triggered{log_suffix}")
            return True
        else:
            logger.error(
                f"❌ n8n webhook failed{log_suffix}: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ n8n webhook exception{log_suffix}: {e}")
        return False
