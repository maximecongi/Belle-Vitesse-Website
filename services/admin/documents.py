import logging
from flask import url_for
from models import db, CheckoutSignedDocument, CheckinSignedDocument

logger = logging.getLogger(__name__)


def get_signed_document_info(inspection_id, is_checkout=True):
    """
    Fetch signed document info (PDF URL, Hash) and generate a temporary access token.
    """
    model = CheckoutSignedDocument if is_checkout else CheckinSignedDocument
    signed_doc = db.session.get(model, inspection_id)

    if not signed_doc or not signed_doc.pdf_url:
        return None

    pdf_url = signed_doc.pdf_url
    # Extract path from URL - handles both filename for legacy and full path
    # URLs are like /checkout/document/PATH or /checkin/document/PATH
    delimiter = "/document/"
    if delimiter not in pdf_url:
        # Fallback for legacy filenames stored directly
        path_part = pdf_url
    else:
        path_part = pdf_url.split(delimiter)[-1].split("?")[0]

    from utils.document_utils import generate_pdf_access_token

    # Import the appropriate token generator
    if is_checkout:
        endpoint = "download_checkout_document"
    else:
        endpoint = "download_checkin_document"

    token = generate_pdf_access_token(path_part)

    return {
        "hash": getattr(signed_doc, 'hash', None),
        "pdf_url": url_for(endpoint, filepath=path_part, t=token)
    }
