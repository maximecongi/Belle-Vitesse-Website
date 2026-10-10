import functools
import json
import logging
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


def _is_ready(form_or_statuses, vehicle_id=None, is_checkout=False, battery_val=None):
    """
    Calcule si le véhicule est 'prêt' basé sur les points de contrôle.
    Retourne True si tous les points de contrôle configurés pour ce véhicule sont conformes ('ok' ou 'not_applicable').
    Pour les départs (checkout), exige également une batterie à 100%.
    """
    # 1. Vérification du niveau de batterie pour les départs
    if is_checkout:
        b_val = battery_val
        if b_val is None and hasattr(form_or_statuses, "get"):
            b_val = form_or_statuses.get("battery_level") or form_or_statuses.get("battery")
        try:
            if b_val is not None and float(b_val) < 100:
                return False
        except (ValueError, TypeError):
            pass

    # 2. Vérification des points de contrôle configurés pour ce véhicule
    checkpoints = get_checkpoints_for_vehicle(vehicle_id)
    for cp in checkpoints:
        key = cp['key']
        cp_type = cp.get('type', 'status')
        if cp_type == 'value':
            if key not in ("battery", "battery_level"):
                val = form_or_statuses.get(key) if hasattr(form_or_statuses, "get") else None
                if val is None or str(val).strip() in ("", "—", "None"):
                    return False
        else:
            val = form_or_statuses.get(key) if hasattr(form_or_statuses, "get") else None
            val_clean = str(val).lower().strip() if val is not None else ""
            if val_clean not in ("ok", "non_applicable", "not_applicable"):
                return False
    return True


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
