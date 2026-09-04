import os
import secrets
from datetime import datetime

from flask import abort, current_app, render_template, request, send_from_directory, session

from utils.document_utils import (
    generate_pdf_access_token,
    validate_pdf_access_token,
    verify_hmac_seal,
    verify_pdf_hash,
)


def handle_document_download(filepath):
    """
    Gestionnaire générique pour les téléchargements de documents sécurisés.
    Valide soit la session admin connectée, soit l'en-tête administratif 'X-Check-Token',
    SOIT le jeton HMAC limité dans le temps 't' issu des arguments de la requête.
    """
    # 1. Vérifier si l'utilisateur est authentifié dans l'espace admin
    if session.get("admin_authenticated"):
        pass  # Accès autorisé pour tout administrateur connecté
    else:
        # 2. Vérifier le secret Admin API (X-Check-Token)
        token_header = request.headers.get("X-Check-Token")
        expected_header = os.getenv("CHECK_API_TOKEN")
        if expected_header and token_header and secrets.compare_digest(token_header, expected_header):
            pass  # Autorisé par le secret admin
        else:
            # 3. Vérifier le jeton temporaire (t)
            access_token = request.args.get("t", "")
            if not access_token or not validate_pdf_access_token(filepath, access_token):
                abort(403)

    output_base = current_app.config.get(
        "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))

    try:
        return send_from_directory(output_base, filepath)
    except Exception:
        abort(404)

def handle_document_verify(mode_config, identifier):
    """
    Gestionnaire générique pour la vérification des documents (Retours, Départs, Décharges).

    mode_config : dict contenant :
        - signed_model : Le modèle SQLAlchemy pour le document signé.
        - seal_prefix : Préfixe pour le HMAC (ex: 'INSPECTION', 'WAIVER').
        - template_verify : Chemin vers le template HTML.
        - route_base : URL de base pour les liens du document (ex: 'pilot-waiver').
        - get_seal_args : Callback (data, signed_doc) -> liste d'arguments pour le scellement.
    identifier : La clé primaire (inspection_id ou waiver_id).
    """
    from models import db
    signed_doc = db.session.get(mode_config["signed_model"], identifier)
    if not signed_doc:
        abort(404)

    data = signed_doc.data_snapshot
    # Normaliser la date pour l'affichage dans le template
    if 'signed_at' in data and isinstance(data['signed_at'], str):
        try:
            data['signed_at'] = datetime.fromisoformat(data['signed_at'])
        except (ValueError, TypeError):
            pass

    # 1. Vérifier l'intégrité du Sceau (Seal)
    seal_args = mode_config["get_seal_args"](data, signed_doc)
    seal_valid = verify_hmac_seal(
        signed_doc.hash, mode_config["seal_prefix"], *seal_args)

    pdf_valid = None
    pdf_error = None
    if request.method == "POST":
        uploaded_file = request.files.get("pdf")
        if uploaded_file:
            if not uploaded_file.filename.lower().endswith(".pdf"):
                pdf_error = "Le fichier doit être un PDF."
            elif not signed_doc.pdf_file_hash:
                pdf_error = "Pas d'empreinte enregistrée pour ce document."
            else:
                pdf_valid = verify_pdf_hash(
                    uploaded_file.read(), signed_doc.pdf_file_hash)

    # 2. URL de téléchargement PDF avec un nouveau jeton frais
    pdf_download_url = None
    if signed_doc.pdf_url:
        # Extract relative path from stored URL
        if "/document/" in signed_doc.pdf_url:
            path_part = signed_doc.pdf_url.split("/document/")[-1].split("?")[0]
        elif "/attachment/" in signed_doc.pdf_url:
            path_part = signed_doc.pdf_url.split("/attachment/")[-1].split("?")[0]
        else:
            path_part = signed_doc.pdf_url

        token = generate_pdf_access_token(path_part)
        pdf_download_url = f"/{mode_config['route_base']}/document/{path_part}?t={token}"

    return render_template(
        mode_config["template_verify"],
        data=data,
        seal_valid=seal_valid,
        pdf_valid=pdf_valid,
        pdf_error=pdf_error,
        signed_doc=signed_doc,
        inspection_id=identifier,
        document_hash=signed_doc.hash,
        project_name=data.get('project_name', data.get('project', '—')),
        has_pdf_hash=bool(signed_doc.pdf_file_hash),
        pdf_download_url=pdf_download_url
    )
