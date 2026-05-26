import os
import requests
from flask import current_app
from models import AppSetting

def compress_pdf_with_ilovepdf(pdf_bytes: bytes) -> bytes:
    """
    Compresses PDF bytes using the iLovePDF REST API.
    Raises Exception if compression fails.
    """
    # 1. Retrieve Public and Secret API keys
    public_key = AppSetting.get('ilovepdf_public_key', os.getenv('ILOVEPDF_PUBLIC_KEY', ''))
    secret_key = AppSetting.get('ilovepdf_secret_key', os.getenv('ILOVEPDF_SECRET_KEY', ''))

    if not public_key or not secret_key:
        raise ValueError("iLovePDF API keys are not configured (public_key or secret_key is missing).")

    current_app.logger.info("Starting iLovePDF compression...")

    # 2. Authenticate
    auth_url = "https://api.ilovepdf.com/v1/auth"
    auth_resp = requests.post(auth_url, json={"public_key": public_key}, timeout=10)
    auth_resp.raise_for_status()
    token = auth_resp.json().get("token")
    if not token:
        raise ValueError("Failed to retrieve token from iLovePDF auth endpoint.")

    headers = {"Authorization": f"Bearer {token}"}

    # 3. Start task
    start_url = "https://api.ilovepdf.com/v1/start/compress"
    start_resp = requests.get(start_url, headers=headers, timeout=10)
    start_resp.raise_for_status()
    start_data = start_resp.json()
    server = start_data.get("server")
    task_id = start_data.get("task")
    if not server or not task_id:
        raise ValueError("Failed to retrieve server and task ID from iLovePDF start endpoint.")

    # 4. Upload file
    upload_url = f"https://{server}/v1/upload"
    files = {"file": ("catalog.pdf", pdf_bytes, "application/pdf")}
    data = {"task": task_id}
    upload_resp = requests.post(upload_url, headers=headers, data=data, files=files, timeout=30)
    upload_resp.raise_for_status()
    server_filename = upload_resp.json().get("server_filename")
    if not server_filename:
        raise ValueError("Failed to retrieve server_filename from iLovePDF upload endpoint.")

    # 5. Process task
    process_url = f"https://{server}/v1/process"
    process_payload = {
        "task": task_id,
        "tool": "compress",
        "files": [
            {
                "server_filename": server_filename,
                "filename": "catalog.pdf"
            }
        ],
        "compression_level": "low"
    }
    process_resp = requests.post(process_url, headers=headers, json=process_payload, timeout=60)
    process_resp.raise_for_status()

    # 6. Download file
    download_url = f"https://{server}/v1/download/{task_id}"
    download_resp = requests.get(download_url, headers=headers, timeout=60)
    download_resp.raise_for_status()

    compressed_bytes = download_resp.content
    current_app.logger.info("✅ PDF compressed successfully via iLovePDF API.")
    return compressed_bytes
