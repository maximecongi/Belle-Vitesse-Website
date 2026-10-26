import os
import secrets
from datetime import datetime

from flask import abort, current_app, render_template, request, send_from_directory, session

from utils.document_utils import (
    generate_pdf_access_token,
    validate_pdf_access_token,
    verify_canonical_seal,
    compute_file_sha256,
    verify_hmac_seal,
    verify_pdf_hash,
)


def handle_document_download(filepath, as_attachment=None):
    """
    Gestionnaire générique pour les téléchargements de documents sécurisés.
    Valide soit la session admin connectée, soit l'en-tête administratif 'X-Check-Token',
    SOIT le jeton HMAC limité dans le temps 't' issu des arguments de la requête.
    """
    # 1. Vérifier si l'utilisateur est authentifié dans l'espace admin (Option A : toute l'équipe BV)
    if session.get("admin_authenticated"):
        pass  # Accès autorisé pour tout collaborateur connecté
    else:
        # 2. Vérifier le secret Admin API (X-Check-Token)
        token_header = request.headers.get("X-Check-Token")
        expected_header = os.getenv("CHECK_API_TOKEN")
        if expected_header and token_header and secrets.compare_digest(token_header, expected_header):
            pass  # Autorisé par le secret admin
        else:
            # 2.5 Vérifier un éventuel Bearer JWT (API mobile / iPad)
            auth_header = request.headers.get("Authorization", "")
            is_jwt_valid = False
            if auth_header.startswith("Bearer "):
                try:
                    from utils.jwt_auth import decode_token
                    payload = decode_token(auth_header.split("Bearer ")[-1])
                    if payload and payload.get("user_id"):
                        is_jwt_valid = True
                except Exception:
                    pass

            if is_jwt_valid:
                pass  # Autorisé par token JWT
            else:
                # 3. Vérifier le jeton temporaire HMAC (t) pour les tiers externes (Pilotes, Productions)
                access_token = request.args.get("t", "")
                if not access_token or not validate_pdf_access_token(filepath, access_token):
                    abort(403)

    output_base = current_app.config.get(
        "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))
    full_path = os.path.join(output_base, filepath)

    # Si le document est en cours de compilation en tâche de fond, attendre brièvement qu'il soit écrit
    if not os.path.exists(full_path):
        import time
        for _ in range(6):
            time.sleep(0.5)
            if os.path.exists(full_path):
                break

    filename = os.path.basename(filepath)
    if as_attachment is None:
        # Forcer le mode pièce jointe pour les attestations, uploads tiers ou requêtes explicites
        if (
            "attachment" in request.path
            or "insurance" in filepath.lower()
            or not filepath.lower().endswith(".pdf")
            or request.args.get("download") == "1"
        ):
            as_attachment = True
        else:
            as_attachment = False

    try:
        response = send_from_directory(
            output_base,
            filepath,
            as_attachment=as_attachment,
            download_name=filename,
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
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
    from models import db, AppSetting
    signed_doc = db.session.get(mode_config["signed_model"], identifier)
    if not signed_doc:
        abort(404)

    raw_data = signed_doc.data_snapshot or {}
    data = raw_data

    # Récupérer l'entité source si disponible
    source_record = None
    if mode_config.get("model"):
        model_cls = mode_config["model"]
        if hasattr(model_cls, "waiver_id"):
            source_record = model_cls.query.filter_by(waiver_id=identifier).first()
        elif hasattr(model_cls, "inspection_id"):
            source_record = model_cls.query.filter_by(inspection_id=identifier).first()
        elif hasattr(model_cls, "inspection_number"):
            source_record = model_cls.query.filter_by(inspection_number=identifier).first()

    # 1. Vérifier l'intégrité du Sceau (Seal)
    seal_valid = False
    if isinstance(data, dict) and data.get("version") == "2.0":
        # Vérification Sceau Canonique v2
        expected_sig_sha = data.get("signature_sha256")
        output_base = current_app.config.get(
            "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))
        sig_path = signed_doc.signature
        if sig_path:
            full_sig_path = os.path.join(output_base, sig_path.lstrip("/"))
            actual_sig_sha = compute_file_sha256(full_sig_path)
            if actual_sig_sha and actual_sig_sha == expected_sig_sha:
                # Contrôle d'intégrité de la contre-signature BV si présente
                expected_bv_sha = data.get("bv_signature_sha256") or data.get("snapshot", {}).get("bv_signature_sha256")
                bv_valid = True
                if expected_bv_sha and source_record and getattr(source_record, "bv_signature_data", None):
                    full_bv_path = os.path.join(output_base, source_record.bv_signature_data.lstrip("/"))
                    actual_bv_sha = compute_file_sha256(full_bv_path)
                    if actual_bv_sha != expected_bv_sha:
                        current_app.logger.warning(
                            f"⚠️ Altération détectée du PNG de contre-signature BV pour {identifier} : {actual_bv_sha} != {expected_bv_sha}")
                        bv_valid = False

                if bv_valid:
                    seal_valid = verify_canonical_seal(signed_doc.hash, data)
                else:
                    seal_valid = False
            else:
                current_app.logger.warning(
                    f"⚠️ Altération détectée du PNG de signature pour {identifier} : {actual_sig_sha} != {expected_sig_sha}")
                seal_valid = False
        else:
            seal_valid = False
    else:
        # Fallback pour documents historiques v1
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

    company_name = AppSetting.get("company_name", "Belle Vitesse SAS")
    company_address = AppSetting.get("company_address", "")

    display_data = dict(data.get("snapshot", {})) if isinstance(data.get("snapshot"), dict) else dict(data)
    display_data.setdefault("signed_at", data.get("signed_at"))
    display_data.setdefault("signer_ip", data.get("signer_ip"))
    if "signed_at" in display_data and isinstance(display_data["signed_at"], str):
        try:
            display_data["signed_at"] = datetime.fromisoformat(display_data["signed_at"])
        except (ValueError, TypeError):
            pass

    return render_template(
        mode_config["template_verify"],
        config=mode_config,
        route_base=mode_config.get("route_base", "checkout"),
        data=display_data,
        seal_valid=seal_valid,
        pdf_valid=pdf_valid,
        pdf_error=pdf_error,
        signed_doc=signed_doc,
        source_record=source_record,
        waiver=source_record,
        inspection_id=identifier,
        document_hash=signed_doc.hash,
        project_name=display_data.get('project_name', display_data.get('project', '—')),
        has_pdf_hash=bool(signed_doc.pdf_file_hash),
        pdf_download_url=pdf_download_url,
        company_name=company_name,
        company_address=company_address
    )
