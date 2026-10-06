import logging

from extensions import cache
from models import User, db

logger = logging.getLogger(__name__)


def invalidate_user_cache(user_id):
    """Efface le cache pour un identifiant utilisateur spécifique."""
    cache.delete(f"user:{user_id}")


def list_users():
    """
    Récupère tous les utilisateurs de la base de données.
    Trié par prénom.
    """
    try:
        return User.query.order_by(User.firstname).all()
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des utilisateurs : {e}")
        return []


def get_user(record_id):
    """
    Récupère un utilisateur unique par son ID.
    """
    try:
        return db.session.get(User, record_id)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'utilisateur {record_id} : {e}")
        return None


def create_user(data):
    """
    Crée un nouvel utilisateur dans la base de données.
    `data` doit être un dictionnaire contenant 'firstname', 'lastname', 'mail', 'role', 'job' et 'phone'.
    """
    try:
        new_user = User(
            firstname=data.get('firstname'),
            lastname=data.get('lastname'),
            mail=data.get('mail'),
            role=data.get('role'),
            phone=data.get('phone'),
            job=data.get('job')
        )
        db.session.add(new_user)
        db.session.commit()
        invalidate_user_cache(new_user.id)
        logger.info(f"Nouvel utilisateur créé : {new_user.id} - {new_user.mail}")
        return new_user
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erreur lors de la création de l'utilisateur : {e}")
        return None


def update_user(record_id, data):
    """
    Met à jour un utilisateur existant.
    """
    try:
        user = db.session.get(User, record_id)
        if not user:
            return None

        old_role = user.role
        user.firstname = data.get('firstname', user.firstname)
        user.lastname = data.get('lastname', user.lastname)
        user.mail = data.get('mail', user.mail)
        user.role = data.get('role', user.role)

        if 'phone' in data:
            user.phone = data['phone']
        if 'job' in data:
            user.job = data['job']

        db.session.commit()
        invalidate_user_cache(record_id)

        # Si le rôle a changé, révoquer immédiatement toutes les sessions actives
        if user.role != old_role:
            try:
                from services.common.session_manager import invalidate_user_sessions
                invalidate_user_sessions(record_id)
            except Exception as sess_err:
                logger.warning(f"Erreur lors de l'invalidation des sessions pour {record_id}: {sess_err}")

        logger.info(f"Utilisateur mis à jour : {record_id}")
        return user
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erreur lors de la mise à jour de l'utilisateur {record_id} : {e}")
        return None


def delete_user(record_id):
    """
    Supprime un utilisateur de la base de données après vérification de ses dépendances.
    """
    from services.admin.utils import BusinessIntegrityError

    user = db.session.get(User, record_id)
    if not user:
        return False

    user_name = f"{user.firstname} {user.lastname}".strip() or f"Utilisateur #{record_id}"

    # 1. Vérification des départs (checkouts) contrôlés par cet utilisateur
    from models import CheckoutVehicle
    checkouts = CheckoutVehicle.query.filter_by(controller_id=record_id).all()
    if checkouts:
        count = len(checkouts)
        raise BusinessIntegrityError(
            f"Impossible de supprimer le compte de « {user_name} » : "
            f"il est enregistré en tant que contrôleur sur {count} fiche(s) de départ (check-out). "
            "Afin de préserver l'historique réglementaire des contrôles, ce compte ne peut pas être supprimé."
        )

    # 2. Vérification des incidents signalés par cet utilisateur
    from models import Incident
    incidents = Incident.query.filter_by(reported_by_id=record_id).all()
    if incidents:
        count = len(incidents)
        raise BusinessIntegrityError(
            f"Impossible de supprimer le compte de « {user_name} » : "
            f"il est auteur de {count} déclaration(s) d'incident / dommage. "
            "Pour des raisons de traçabilité, ce compte ne peut être supprimé."
        )

    # 3. Vérification des rapports de tournage rédigés par cet utilisateur
    from models import ProjectReport
    reports = ProjectReport.query.filter_by(user_id=record_id).all()
    if reports:
        count = len(reports)
        raise BusinessIntegrityError(
            f"Impossible de supprimer le compte de « {user_name} » : "
            f"il est rattaché à {count} rapport(s) de tournage. "
            "Pour préserver l'historique des tournages, ce compte ne peut être supprimé."
        )

    try:
        # Nettoyage des relations autorisées en cascade (ex: abonnements calendrier, tokens MCP)
        # Note: calendar_subscriptions et mcp_tokens sont en cascade delete-orphan sur le modèle User.
        db.session.delete(user)
        db.session.commit()
        invalidate_user_cache(record_id)

        try:
            from services.common.session_manager import invalidate_user_sessions
            invalidate_user_sessions(record_id)
        except Exception as sess_err:
            logger.warning(f"Erreur lors de l'invalidation des sessions pour {record_id}: {sess_err}")

        logger.info(f"Utilisateur supprimé : {record_id}")
        return True
    except BusinessIntegrityError:
        raise
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erreur lors de la suppression de l'utilisateur {record_id} : {e}")
        from services.admin.utils import format_user_friendly_error
        raise BusinessIntegrityError(format_user_friendly_error(e, "Erreur lors de la suppression de l'utilisateur."))
