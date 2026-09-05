import json
import logging
import os
from datetime import datetime
from pathlib import Path

from flask import current_app, url_for
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

from models import (
    CheckinSignedDocument,
    CheckinVehicle,
    CheckoutSignedDocument,
    CheckoutVehicle,
    Project,
    User,
    db,
)
from services.admin.status_mapping import (
    INSPECTION_STATUS_MAP,
    get_checkpoint_key,
    get_inspection_key,
)
from services.admin.utils import _delete_inspection_files, _is_ready, _parse_photos_json
from utils.checkpoints import (
    ALL_POSSIBLE_CHECKPOINTS,
    BASE_CHECKPOINTS,
    CHECKPOINT_TO_MODEL_MAP,
    get_checkpoints_for_vehicle,
)
from utils.database import get_vehicles
from utils.document_utils import generate_pdf_access_token
from utils.formatting import format_date_fr

logger = logging.getLogger(__name__)


# ── Configuration & Métadonnées ───────────────────────────────────

def get_inspection_config(mode):
    """
    Retourne les modèles et métadonnées spécifiques pour un mode d'inspection donné (Départ ou Retour).
    """
    if mode == "checkout":
        from models import CheckoutSignedDocument, CheckoutToken
        return {
            "model": CheckoutVehicle,
            "token_model": CheckoutToken,
            "signed_model": CheckoutSignedDocument,
            "webhook_env": "N8N_WEBHOOK_CHECKOUT_SIGN",
            "photos_path_func": "get_checkout_photos_path",
            "responsible_attr": "controller",
            "is_checkout": True,
            "stats_key": "checkouts"
        }
    else:
        from models import CheckinSignedDocument, CheckinToken
        return {
            "model": CheckinVehicle,
            "token_model": CheckinToken,
            "signed_model": CheckinSignedDocument,
            "webhook_env": "N8N_WEBHOOK_CHECKIN_SIGN",
            "photos_path_func": "get_checkin_photos_path",
            "responsible_attr": "controller",
            "is_checkout": False,
            "stats_key": "checkins"
        }


# ── Opérations Cœur (Unifiées) ───────────────────────────────────

def list_inspections_unified(mode):
    """
    Récupérateur générique pour les listes de départs (Checkout) ou de retours (Checkin).
    Calcule également les statistiques pour le tableau de bord.
    """
    config = get_inspection_config(mode)
    record_model = config["model"]
    resp_attr = config["responsible_attr"]

    # Chargement lié optimisé pour éviter le problème N+1
    records = record_model.query.join(Project).filter(
        record_model.deleted_at == None,
        Project.deleted_at == None
    ).options(
        joinedload(record_model.project).joinedload(Project.production),
        joinedload(getattr(record_model, resp_attr))
    ).order_by(record_model.created_at.desc()).all()

    vehicles = get_vehicles()
    vehicle_map = {v["id"]: v.get("fields", {}) for v in vehicles}

    from services.admin.vehicle_config import get_checkpoint_configs
    batch_configs = get_checkpoint_configs()

    # Calcul des statistiques sommaires
    total = len(records)
    signed = sum(1 for r in records if get_inspection_key(
        r.status) == "signed")
    pending = sum(1 for r in records if get_inspection_key(
        r.status) == "completed")

    formatted = [_format_base_inspection_admin(
        r, vehicle_map, batch_configs) for r in records]

    return {
        config["stats_key"]: formatted,
        "stats": {
            f"total_{config['stats_key']}": total,
            f"signed_{config['stats_key']}": signed,
            f"pending_{config['stats_key']}": pending,
        }
    }


def get_inspection_detail_unified(mode, record_id):
    """
    Récupère les détails complets d'une inspection spécifique (Checkout ou Checkin).
    Inclut les informations du document signé si disponible.
    """
    config = get_inspection_config(mode)
    record_model = config["model"]
    resp_attr = config["responsible_attr"]

    record = record_model.query.join(Project).filter(
        record_model.id == record_id,
        record_model.deleted_at == None,
        Project.deleted_at == None
    ).options(
        joinedload(record_model.project).joinedload(Project.production),
        joinedload(getattr(record_model, resp_attr))
    ).first()

    if not record:
        return None

    vehicles = get_vehicles()
    vehicle_map = {v["id"]: v.get("fields", {}) for v in vehicles}
    data = _format_base_inspection_admin(record, vehicle_map)

    # Si l'inspection est signée, on récupère les infos du PDF (URL sécurisée, Hash)
    if get_inspection_key(data.get("raw_status")) == "signed":
        doc_info = get_signed_document_info(
            data["inspection_id"], is_checkout=config["is_checkout"])
        if doc_info:
            data.update(doc_info)

    return data


def get_signed_document_info(inspection_id, is_checkout=True):
    """
    Récupère les infos d'un document signé (URL PDF, Hash) et génère un jeton d'accès temporaire.
    """
    model = CheckoutSignedDocument if is_checkout else CheckinSignedDocument
    signed_doc = db.session.get(model, inspection_id)

    if not signed_doc or not signed_doc.pdf_url:
        return None

    pdf_url = signed_doc.pdf_url
    # L'URL peut être un nom de fichier simple ou un chemin complet
    delimiter = "/document/"
    if delimiter not in pdf_url:
        path_part = pdf_url
    else:
        path_part = pdf_url.split(delimiter)[-1].split("?")[0]

    endpoint = "download_checkout_document" if is_checkout else "download_checkin_document"
    token = generate_pdf_access_token(path_part)

    return {
        "hash": getattr(signed_doc, 'hash', None),
        "pdf_url": url_for(endpoint, filepath=path_part, t=token)
    }


def delete_inspection_unified(mode, record_id):
    """
    Supprime génériquement une inspection (Checkout ou Checkin).
    Supprime également les documents signés, les jetons et notifie n8n.
    """
    config = get_inspection_config(mode)
    record = db.session.get(config["model"], record_id)
    if not record or record.deleted_at is not None:
        return False

    from utils.n8n import trigger_n8n_webhook
    insp_id = record.inspection_number

    if insp_id:
        # 1. Nettoyage de la base de données (jetons et documents signés archivés)
        config["token_model"].query.filter_by(inspection_id=insp_id).delete()
        config["signed_model"].query.filter_by(inspection_id=insp_id).delete()

        # 2. Notification n8n de la suppression
        webhook_url = os.getenv(config["webhook_env"])
        if webhook_url:
            trigger_n8n_webhook(
                webhook_url, method="DELETE",
                inspection_id=insp_id,
                project_id=record.project.project_id if record.project else None
            )

    # 3. Suppression des fichiers physiques (photos, PDF)
    _delete_inspection_files(record)

    # 4. Suppression via soft-delete
    record.deleted_at = datetime.utcnow()
    db.session.commit()
    return True


def upload_inspection_photos_shared(mode, record, files):
    """
    Gère l'upload des photos pour n'importe quel type d'inspection.
    Organise les photos dans des dossiers par projet et numéro d'inspection.
    """
    if not files:
        return

    config = get_inspection_config(mode)
    # Import dynamique pour éviter les dépendances circulaires
    import utils.storage as storage
    path_func = getattr(storage, config["photos_path_func"])

    # Assure l'existence du dossier de destination spécifique
    upload_dir = Path(storage.ensure_dir(path_func(
        record.project, record.inspection_number)))

    photo_fields = {
        "exterior_photos": "exterior_photos",
        "interior_photos": "interior_photos",
    }

    output_base = current_app.config.get(
        "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))

    for form_field, model_attr in photo_fields.items():
        uploaded = files.getlist(form_field)
        paths = []
        for f in uploaded:
            if f and f.filename:
                filename = secure_filename(f.filename)
                file_path = upload_dir / filename
                f.save(file_path)
                # Enregistre le chemin relatif par rapport à OUTPUT_FOLDER
                paths.append(os.path.relpath(file_path, output_base))

        if paths:
            # Stockage des chemins sous forme de liste JSON en base de données
            setattr(record, model_attr, json.dumps(paths))

    db.session.commit()


# ── Internal Helpers ───────────────────────────────────────────

def apply_inspection_data(record, form, is_checkout=True):
    """
    Mappe dynamiquement les champs du formulaire aux attributs du modèle basés sur ALL_POSSIBLE_CHECKPOINTS.
    Gère également le niveau de batterie et le calcul de l'état 'prêt' (vehicle_ready).
    """
    vehicle_id = form.get("vehicle_id") or getattr(
        record, 'vehicle_id', None)
    # Récupère uniquement les points de contrôle pertinents pour ce type de véhicule
    checkpoints = get_checkpoints_for_vehicle(vehicle_id)
    pertinent_keys = {cp['key']
                      for cp in checkpoints if cp.get('type') == 'status'}

    def get_val(key):
        """Récupère la clé interne du statut, ou 'not_applicable' si le point n'est pas pertinent."""
        if key not in pertinent_keys:
            return "not_applicable"
        return get_checkpoint_key(form.get(key, "pending"))

    # 1. Mappe tous les points de contrôle de statut standard
    for cp in ALL_POSSIBLE_CHECKPOINTS:
        key = cp['key']
        if cp.get('type') == 'status':
            column = CHECKPOINT_TO_MODEL_MAP.get(key, key)
            if hasattr(record, column):
                setattr(record, column, get_val(key))

    # 2. Gestion du niveau de batterie (valeur numérique)
    battery_val = form.get("battery_level") or form.get("battery")
    if battery_val is not None:
        try:
            record.battery_level = float(battery_val)
        except (ValueError, TypeError):
            pass

    # 3. Calcul de l'état de préparation (si TOUS les points critiques sont conformes)
    if is_checkout:
        record.vehicle_ready = _is_ready(
            form, vehicle_id, is_checkout=True)
    else:
        record.vehicle_ready = _is_ready(
            form, vehicle_id, is_checkout=False)

    record.notes = form.get("notes")


def _format_base_inspection_admin(c, vehicle_map, batch_configs=None):
    """
    Formateur commun pour les objets d'inspection (CheckoutVehicle et CheckinVehicle)
    vers un dictionnaire prêt pour le frontend.
    """
    project_name = c.project.name if c.project else "—"
    v_data = vehicle_map.get(c.vehicle_id, {})
    vehicle_name = v_data.get("name", "—")
    unique_id = v_data.get("unique_id", "—")

    # Utilise la relation standardisée 'controller'
    controller_obj = getattr(c, 'controller', None)
    controller_name = f"{(controller_obj.firstname or '') if controller_obj else ''} {(controller_obj.lastname or '') if controller_obj else ''}".strip() or "—"

    status_id = get_inspection_key(c.status)
    status_label = INSPECTION_STATUS_MAP.get(status_id, status_id)

    ready = "true" if getattr(c, 'vehicle_ready', False) else "false"

    # Formatage des dates pour l'affichage FR
    c_date = format_date_fr(str(c.inspection_date)
                             ) if c.inspection_date else "—"
    d_date = format_date_fr(str(c.project.departure_date)
                             ) if c.project and c.project.departure_date else "—"
    r_date = format_date_fr(str(c.project.return_date)
                             ) if c.project and c.project.return_date else "—"

    data = {
        "id": c.id,
        "inspection_id": c.inspection_number or "—",
        "project": project_name,
        "departure_date": d_date,
        "return_date": r_date,
        "vehicle": {"fields": {"name": vehicle_name, "unique_id": unique_id}},
        "control_date": c_date,
        "status": status_label,
        "raw_status": status_id,
        "status_id": status_id,
        "controller": {
            "id": c.controller_id,
            "name": controller_name
        },
        "created_at": c.created_at.isoformat() if c.created_at else "",
        "ready": ready,
        "controller_id": c.controller_id,
    }

    # Texte de recherche pour le filtrage côté client
    data["search_text"] = f"{data['inspection_id']} {project_name} {controller_name} {status_label}".lower(
    )
    # Récupère la configuration des points de contrôle spécifique au véhicule
    data["check_items"] = get_checkpoints_for_vehicle(
        c.vehicle_id, batch_configs=batch_configs)

    data["control_status"] = status_label

    battery_val = getattr(c, 'battery_level', None)
    data["battery_level"] = battery_val if battery_val is not None else None

    # Mappe dynamiquement tous les points de contrôle pour l'accès direct
    for cp in ALL_POSSIBLE_CHECKPOINTS:
        key = cp['key']
        if cp.get('type') == 'status':
            column = CHECKPOINT_TO_MODEL_MAP.get(key, key)
            data[key] = getattr(c, column, "—") or "—"

    # Calcul centralisé des anomalies et défaillances
    failures = []
    for item in data.get("check_items", []):
        if item.get("type") == "status":
            k = item.get("key")
            val = data.get(k)
            if val and val != "—" and str(val).lower() not in ["ok", "not_applicable"]:
                failures.append(item.get("label") or k)

    is_checkout = isinstance(c, CheckoutVehicle) or getattr(c, "__tablename__", "") == "checkout_vehicles"
    if is_checkout and battery_val is not None and battery_val < 100:
        failures.append("Charge batterie (< 100%)")

    data["failures"] = failures
    data["failure_count"] = len(failures)
    data["has_failures"] = len(failures) > 0

    data["interior_photos"] = _parse_photos_json(c.interior_photos)
    data["exterior_photos"] = _parse_photos_json(c.exterior_photos)
    data["notes"] = c.notes or ""

    if c.project:
        data["production"] = c.project.production.name if c.project.production else "—"
        data["shoot_start"] = format_date_fr(
            str(c.project.shoot_start_date)) if c.project.shoot_start_date else "—"
        data["shoot_end"] = format_date_fr(
            str(c.project.shoot_end_date)) if c.project.shoot_end_date else "—"
        data["vehicle_id"] = c.vehicle_id
        data["project_id"] = str(c.project.id)
        data["project_id_unique"] = c.project.project_id
        data["project_name"] = c.project.name
        data["vehicle_name"] = vehicle_name

    return data


def get_unified_form_context(mode="checkout"):
    """
    Unifie la récupération du contexte pour les formulaires de départ et de retour.
    Gère les blocages (interdire un nouveau départ si un retour n'a pas été effectué).
    """
    projects = Project.query.filter(Project.deleted_at == None).options(joinedload(
        Project.production)).order_by(Project.name).all()
    vehicles = get_vehicles()
    users = User.query.order_by(User.firstname).all()

    checkouts = CheckoutVehicle.query.filter(CheckoutVehicle.deleted_at == None).all()
    checkins = CheckinVehicle.query.filter(CheckinVehicle.deleted_at == None).all()

    # Mapping des noms de projets pour un accès rapide
    project_names = {str(p.id): p.name for p in projects}

    # Mapping des statuts par véhicule et par projet : {vehicule_id: {project_id: status}}
    vehicle_checkout_statuses = {}
    for c in checkouts:
        if c.vehicle_id and c.status and c.project_id:
            vid = c.vehicle_id
            pid = str(c.project_id)
            if vid not in vehicle_checkout_statuses:
                vehicle_checkout_statuses[vid] = {}
            vehicle_checkout_statuses[vid][pid] = c.status

    vehicle_checkin_statuses = {}
    for c in checkins:
        if c.vehicle_id and c.status and c.project_id:
            vid = c.vehicle_id
            pid = str(c.project_id)
            if vid not in vehicle_checkin_statuses:
                vehicle_checkin_statuses[vid] = {}
            vehicle_checkin_statuses[vid][pid] = c.status

    # Spécifiquement pour le départ (checkout) : logique des projets bloquants
    blocking_projects = {}
    if mode == "checkout":
        for vid, p_statuses in vehicle_checkout_statuses.items():
            for pid, status in p_statuses.items():
                if get_inspection_key(status) in ["signed", "completed"]:
                    # Vérifie si le véhicule a été rendu pour ce projet
                    has_checkin = False
                    for ci in checkins:
                        if ci.vehicle_id == vid and str(ci.project_id) == pid and get_inspection_key(ci.status) in ["signed", "completed"]:
                            has_checkin = True
                            break
                    if not has_checkin:
                        # Si non rendu, ce projet bloque un nouveau départ pour ce véhicule
                        blocking_projects[vid] = project_names.get(
                            pid, "Projet inconnu")

    # Enrichissement des données véhicules avec les statuts et blocages
    for v in vehicles:
        vid = v["id"]
        f = v.setdefault("fields", {})
        f["_checkout_statuses"] = vehicle_checkout_statuses.get(vid, {})
        f["_checkin_statuses"] = vehicle_checkin_statuses.get(vid, {})

        if mode == "checkout" and vid in blocking_projects:
            f["_blocked_by"] = blocking_projects[vid]

    # Formatage des projets pour l'affichage dans le sélecteur
    projects_formatted = []
    for p in projects:
        veh_ids = [v.strip() for v in (
            p.vehicles_to_check or "").split(",") if v.strip()]
        v_name = "—"
        if veh_ids:
            # Récupère le nom du premier véhicule associé pour aider l'utilisateur
            for v in vehicles:
                if v["id"] == veh_ids[0]:
                    v_name = v.get("fields", {}).get("name", "—")
                    break

        projects_formatted.append({
            "id": str(p.id),
            "fields": {
                "Nom": p.name,
                "_production_name": p.production.name if p.production else "—",
                "Date de départ": format_date_fr(str(p.departure_date)) if p.departure_date else "—",
                "Date de début de tournage": format_date_fr(str(p.shoot_start_date)) if p.shoot_start_date else "—",
                "Date de fin de tournage": format_date_fr(str(p.shoot_end_date)) if p.shoot_end_date else "—",
                "Véhicules à contrôler": veh_ids,
                "_vehicle_name": v_name
            }
        })

    users_formatted = [{"id": str(u.id), "fields": {
        "firstname": u.firstname, "lastname": u.lastname}} for u in users]

    # Mapping des points de contrôle par véhicule (pour le filtrage dynamique côté frontend)
    checkpoints_mapping = {v["id"]: get_checkpoints_for_vehicle(
        v["id"], vehicle_name=v.get("fields", {}).get("name")) for v in vehicles}

    return {
        "projects": projects_formatted,
        "vehicles": vehicles,
        "users": users_formatted,
        "checkpoints": ALL_POSSIBLE_CHECKPOINTS,
        "checkpoints_config_json": json.dumps(checkpoints_mapping),
        "default_checkpoints_json": json.dumps(BASE_CHECKPOINTS),
    }
