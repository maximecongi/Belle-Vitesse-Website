import logging

import requests as http_requests

logger = logging.getLogger(__name__)


def trigger_n8n_webhook(url: str, method: str = "POST", **kwargs) -> bool:
    """
    Déclenche un webhook n8n avec l'URL, la méthode HTTP et les arguments fournis comme payload.

    Args:
        url (str) : L'URL du webhook n8n.
        method (str) : La méthode HTTP à utiliser (POST, DELETE, etc.).
        **kwargs : Les données à envoyer dans le payload JSON.

    Returns:
        bool : True si le webhook a été déclenché avec succès, False sinon.
    """
    if not url:
        logger.warning("⚠️ L'URL du webhook est vide.")
        return False

    # Extraire l'ID pour le log si disponible (ex: inspection_id)
    doc_id = kwargs.get("inspection_id") or kwargs.get(
        "waiver_id") or kwargs.get("project_id") or kwargs.get("id", "")
    log_suffix = f" pour {doc_id}" if doc_id else ""

    logger.info(f"🚀 Déclenchement du webhook n8n ({method}){log_suffix}...")

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
