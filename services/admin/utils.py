import functools
import json
import logging
import math
import os
from pathlib import Path

from flask import current_app

from models import CheckoutVehicle, db
from utils.checkpoints import get_checkpoints_for_vehicle

logger = logging.getLogger(__name__)


class BusinessIntegrityError(Exception):
    """Exception levée lorsqu'une contrainte métier ou d'intégrité référentielle empêche une action."""
    pass


def format_user_friendly_error(error: Exception, default_message: str = "Une erreur est survenue lors de l'opération.") -> str:
    """
    Traduit les exceptions techniques (IntegrityError, ValueError, etc.) en messages clairs et compréhensibles en français,
    sans afficher de détails Python ou SQL bruts à l'utilisateur.
    """
    if isinstance(error, BusinessIntegrityError):
        return str(error)

    err_str = str(error)

    # Détection des contraintes de clés étrangères (MySQL / SQLite / SQLAlchemy)
    if "foreign key constraint fails" in err_str.lower() or "1451" in err_str:
        return (
            "Impossible de supprimer cet élément car il est actuellement lié à d'autres données "
            "(projets, inspections, décharges, contacts ou rapports). "
            "Veuillez dissocier ou supprimer ces éléments liés avant de réessayer."
        )

    # Détection des contraintes NOT NULL violées lors d'une tentative de suppression/détachement
    if "cannot be null" in err_str.lower() or "1048" in err_str:
        return (
            "Impossible de supprimer cet enregistrement car un ou plusieurs projets ou formulaires en dépendent directement. "
            "Veuillez réassigner ou archiver les éléments associés au préalable."
        )

    # Détection des contraintes d'unicité (Duplicate entry / UNIQUE constraint)
    if "duplicate entry" in err_str.lower() or "unique constraint" in err_str.lower() or "1062" in err_str:
        return "Une entrée portant le même nom, email ou identifiant existe déjà dans le système."

    # Si c'est une ValueError explicite déjà rédigée
    if isinstance(error, ValueError) and err_str and not err_str.startswith("("):
        return err_str

    # Message générique propre pour masquer le bruit technique
    return default_message


def handle_admin_service_error(func):
    """Décorateur pour centraliser la gestion des erreurs dans les services admin (rollback et log)."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erreur dans {func.__name__} : {e}")
            raise e
    return wrapper


def _parse_photos_json(text):
    """Analyse une chaîne JSON de chemins de photos et retourne une liste de dictionnaires (URL, label)."""
    if not text:
        return []
    try:
        paths = json.loads(text)
        return [{"url": f"/files/{p}", "label": p.split("/")[-1]} for p in paths]
    except Exception:
        return [{"url": f"/files/{text}", "label": "File"}]


def _delete_inspection_files(record):
    """
    Supprime tous les fichiers physiques associés à un enregistrement de départ ou de retour.
    Inclut les photos intérieures/extérieures et le PDF signé.
    """

    output_base = current_app.config.get(
        "OUTPUT_FOLDER", os.path.join(current_app.root_path, "output"))

    # 1. Photos (Hierarchical: output/YEAR/MONTH/.../PHOTOS/ID)
    if record.project and record.inspection_number:
        import shutil

        from utils.storage import get_checkin_photos_path, get_checkout_photos_path

        if isinstance(record, CheckoutVehicle):
            hierarchical_photo_dir = get_checkout_photos_path(
                record.project, record.inspection_number)
        else:
            hierarchical_photo_dir = get_checkin_photos_path(
                record.project, record.inspection_number)

        if hierarchical_photo_dir.exists():
            try:
                shutil.rmtree(hierarchical_photo_dir)
                logger.info(
                    f"🗑️ Dossier PHOTOS supprimé : {hierarchical_photo_dir}")
            except Exception as e:
                logger.error(
                    f"❌ Échec de la suppression du dossier PHOTOS {hierarchical_photo_dir}: {e}")

    # 2. Signed PDF
    if record.signed_pdf_path:
        # signed_pdf_path is usually a URL or relative path: http://.../checkout/document/filepath
        path_part = record.signed_pdf_path.split(
            "/document/")[-1].split("?")[0]
        pdf_path = Path(output_base) / path_part
        if pdf_path.exists():
            try:
                os.remove(pdf_path)
                logger.info(f"🗑️ PDF supprimé : {pdf_path}")
            except Exception as e:
                logger.error(
                    f"❌ Échec de la suppression du PDF {pdf_path}: {e}")


def is_known_vehicle(v_id) -> bool:
    """
    Vérifie si le véhicule correspond exactement à un véhicule reconnu dans le parc (get_vehicles).
    Respecte les formats ID (id en base ou Airtable) et nom de véhicule (fields.name) réellement utilisés.
    """
    if not v_id:
        return False
    from utils.database import get_vehicles
    try:
        vehicles = get_vehicles() or []
        str_v_id = str(v_id).strip()
        for v in vehicles:
            v_real_id = str(v.get("id", "")).strip()
            if v_real_id and v_real_id == str_v_id:
                return True
            v_name = str((v.get("fields") or {}).get("name", "")).strip()
            if v_name and v_name == str_v_id:
                return True
        return False
    except Exception:
        return False


def compute_inspection_readiness(form_or_statuses, vehicle_id=None, is_checkout=False, battery_val=None) -> tuple[bool, list[str]]:
    """
    Source unique de vérité pour le calcul de conformité et préparation d'un véhicule.
    Retourne un tuple (is_ready: bool, failures: list[str]).
    
    Règles strictes :
    1. Pour le check-out : un véhicule doit être obligatoirement sélectionné et reconnu dans le parc (get_vehicles).
    2. La batterie doit être un nombre fini compris entre 0 et 100. Pour checkout, elle doit être égale à 100%.
    3. Tous les points de contrôle configurés pour ce véhicule doivent être renseignés et conformes ('ok' ou 'not_applicable').
    """
    failures = []

    # 1. Validation rigoureuse de la batterie
    b_val = battery_val
    if b_val is None:
        if hasattr(form_or_statuses, "get"):
            b_val = form_or_statuses.get("battery_level")
            if b_val is None:
                b_val = form_or_statuses.get("battery")
        elif hasattr(form_or_statuses, "battery_level"):
            b_val = getattr(form_or_statuses, "battery_level")

    if b_val is None or str(b_val).strip() in ("", "—", "None"):
        if is_checkout:
            failures.append("Charge batterie (non renseignée)")
    else:
        try:
            val_float = float(b_val)
            if not math.isfinite(val_float) or math.isnan(val_float):
                failures.append("Niveau de batterie non numérique ou infini")
            elif val_float < 0 or val_float > 100:
                failures.append(f"Niveau de batterie hors limites ({val_float}%)")
            elif is_checkout and val_float < 100:
                failures.append("Charge batterie (< 100%)")
        except (ValueError, TypeError):
            failures.append("Niveau de batterie invalide")

    # 2. Validation des points de contrôle du véhicule
    v_id = vehicle_id
    if not v_id:
        if hasattr(form_or_statuses, "vehicle_id"):
            v_id = getattr(form_or_statuses, "vehicle_id", None)
        elif hasattr(form_or_statuses, "get"):
            v_id = form_or_statuses.get("vehicle_id")

    if is_checkout:
        # Check-out est strictement fail-closed : il exige impérativement un véhicule identifié
        # et reconnu dans le parc (get_vehicles), disposant d'un profil de points de contrôle.
        # Le chemin utils/checkpoints.py pouvant renvoyer des checkpoints génériques même pour un
        # véhicule inventé, nous vérifions expressément la présence du véhicule dans get_vehicles().
        if not v_id:
            failures.append("Véhicule non sélectionné")
            checkpoints = []
        elif not is_known_vehicle(v_id):
            failures.append("Véhicule non reconnu")
            checkpoints = []
        else:
            checkpoints = get_checkpoints_for_vehicle(v_id)
            if not checkpoints:
                failures.append("Profil de points de contrôle introuvable")
    else:
        checkpoints = get_checkpoints_for_vehicle(v_id) if v_id else []

    if checkpoints:
        for cp in checkpoints:
            key = cp['key']
            label = cp.get('label') or key
            cp_type = cp.get('type', 'status')
            if hasattr(form_or_statuses, "get"):
                val = form_or_statuses.get(key)
            elif hasattr(form_or_statuses, "get_checkpoint_status"):
                val = form_or_statuses.get_checkpoint_status(key, default=None)
            elif hasattr(form_or_statuses, "checkpoint_statuses"):
                val_statuses = getattr(form_or_statuses, "checkpoint_statuses", {})
                val = val_statuses.get(key) if isinstance(val_statuses, dict) else None
            else:
                val = None

            if cp_type == 'value':
                if key not in ("battery", "battery_level"):
                    if val is None or str(val).strip() in ("", "—", "None"):
                        failures.append(f"{label} (non renseigné)")
            else:
                val_clean = str(val).lower().strip() if val is not None else ""
                if val_clean not in ("ok", "non_applicable", "not_applicable"):
                    failures.append(label)
    elif not is_checkout:
        if isinstance(form_or_statuses, dict) and form_or_statuses:
            # Fallback pour validation directe de statuts uniquement HORS check-out
            for key, val in form_or_statuses.items():
                if key in ("battery", "battery_level", "vehicle_id"):
                    continue
                val_clean = str(val).lower().strip() if val is not None else ""
                if val_clean not in ("ok", "non_applicable", "not_applicable"):
                    failures.append(key)
        else:
            if v_id:
                failures.append("Profil de points de contrôle introuvable")
            else:
                failures.append("Véhicule non sélectionné")

    is_ready = (len(failures) == 0)
    return is_ready, failures


def _is_ready(form_or_statuses, vehicle_id=None, is_checkout=False, battery_val=None) -> bool:
    """
    Calcule si le véhicule est 'prêt' basé sur les points de contrôle.
    Délègue à la source unique de vérité compute_inspection_readiness.
    """
    is_ready, _ = compute_inspection_readiness(
        form_or_statuses,
        vehicle_id=vehicle_id,
        is_checkout=is_checkout,
        battery_val=battery_val
    )
    return is_ready


# ── Aides CRUD Génériques ──────────────────────────────────────────


def generic_list_records(model, fields_map, order_by_attr=None, default_empty=None):
    """
    Récupérateur générique qui retourne une liste d'enregistrements formattés.

    Args:
        model: Classe du modèle SQLAlchemy.
        fields_map: Dict mappant les clés frontend aux attributs du modèle ou callables.
        order_by_attr: Attribut optionnel pour le tri.
        default_empty: Valeur par défaut pour les champs vides ou None (None par défaut).
    """
    query = model.query
    if order_by_attr is not None:
        query = query.order_by(order_by_attr)

    records = query.all()
    result = []

    for r in records:
        formatted = {"id": r.id}
        for key, attr in fields_map.items():
            if callable(attr):
                val = attr(r)
                formatted[key] = val if val is not None and val != "" and val != "—" else default_empty
            else:
                val = getattr(r, attr, None)
                formatted[key] = val if val is not None and val != "" and val != "—" else default_empty
        result.append(formatted)

    return result


def format_contact_for_list(c): return {
    "id": c.id,
    "name": f"{c.first_name} {c.last_name}",
    "production": c.production_rel.name if c.production_rel else "Indépendant",
    "job": c.job_title or "—",
    "phone": c.phone or "—",
    "mail": c.mail or "—"
}


def format_production_for_list(p): return {
    "id": p.id,
    "name": p.name,
    "address": p.address or "—",
    "contacts_count": len(p.contacts),
    "projects_count": len(p.projects)
}


def generic_get_record_for_edit(model, record_id, fields_list):
    """
    Récupérateur générique pour les données d'édition de formulaire.

    Args:
        model: Classe du modèle SQLAlchemy.
        record_id: ID de l'enregistrement.
        fields_list: Liste des attributs du modèle à inclure.
    """
    record = db.session.get(model, record_id)
    if not record:
        return None

    return {field: getattr(record, field) or "" for field in fields_list}


@handle_admin_service_error
def generic_delete_record(model, record_id):
    """
    Suppression d'enregistrement générique.
    """
    record = db.session.get(model, record_id)
    if record:
        db.session.delete(record)
        db.session.commit()
    return True


@handle_admin_service_error
def generic_find_or_create(model, lookup_filter, attributes, order_by=None, enrich_existing=True):
    """
    Recherche un enregistrement selon un filtre ou le crée de manière atomique.
    
    Si l'enregistrement existe déjà : enrichit automatiquement ses attributs vides
    avec les nouvelles valeurs fournies dans attributes sans écraser les données existantes.
    Si l'enregistrement n'existe pas : l'instancie avec attributes et l'insère en base.
    
    Retourne:
        tuple (instance, created: bool)
    """
    query = model.query.filter(lookup_filter)
    if order_by is not None:
        query = query.order_by(order_by)
    instance = query.first()

    if instance:
        if enrich_existing:
            updated = False
            for attr, val in attributes.items():
                if val is not None and val != "" and not getattr(instance, attr, None):
                    setattr(instance, attr, val)
                    updated = True
            if updated:
                db.session.commit()
        return instance, False

    instance = model(**attributes)
    db.session.add(instance)
    db.session.commit()
    return instance, True

