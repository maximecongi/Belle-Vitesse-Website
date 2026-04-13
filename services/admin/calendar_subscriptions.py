"""
Service de gestion des abonnements calendrier ICS.
Permet de créer, révoquer et régénérer les tokens pour les utilisateurs.
"""
import logging
import uuid
from models import CalendarSubscription, User, db

logger = logging.getLogger(__name__)


def list_all_subscriptions():
    """
    Récupère tous les abonnements calendrier avec les informations utilisateur.
    Retourne une liste de dictionnaires enrichis.
    """
    try:
        subs = (
            CalendarSubscription.query
            .join(User)
            .order_by(User.firstname)
            .all()
        )
        return subs
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des abonnements calendrier : {e}")
        return []


def get_subscription_for_user(user_id):
    """Récupère l'abonnement actif d'un utilisateur (s'il existe)."""
    try:
        return CalendarSubscription.query.filter_by(
            user_id=user_id, is_active=True
        ).first()
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'abonnement pour user {user_id} : {e}")
        return None


def create_subscription(user_id):
    """
    Crée un nouvel abonnement calendrier pour un utilisateur.
    Si un abonnement actif existe déjà, le retourne sans en créer un nouveau.
    """
    try:
        # Vérifier s'il existe déjà un abonnement actif
        existing = CalendarSubscription.query.filter_by(
            user_id=user_id, is_active=True
        ).first()
        if existing:
            logger.info(f"Abonnement calendrier déjà actif pour user {user_id}")
            return existing

        sub = CalendarSubscription(
            user_id=user_id,
            token=str(uuid.uuid4()),
        )
        db.session.add(sub)
        db.session.commit()
        logger.info(f"Abonnement calendrier créé pour user {user_id} : token={sub.token[:8]}...")
        return sub
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erreur lors de la création de l'abonnement pour user {user_id} : {e}")
        return None


def revoke_subscription(user_id):
    """
    Révoque (désactive) l'abonnement calendrier actif d'un utilisateur.
    L'URL cessera de fonctionner immédiatement.
    """
    try:
        sub = CalendarSubscription.query.filter_by(
            user_id=user_id, is_active=True
        ).first()
        if not sub:
            return False

        sub.is_active = False
        db.session.commit()
        logger.info(f"Abonnement calendrier révoqué pour user {user_id}")
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erreur lors de la révocation de l'abonnement pour user {user_id} : {e}")
        return False


def regenerate_subscription(user_id):
    """
    Régénère l'abonnement calendrier : révoque l'ancien token et en crée un nouveau.
    Retourne le nouvel abonnement ou None en cas d'erreur.
    """
    try:
        # Désactiver tous les tokens existants
        CalendarSubscription.query.filter_by(
            user_id=user_id, is_active=True
        ).update({"is_active": False})

        # Créer un nouveau token
        sub = CalendarSubscription(
            user_id=user_id,
            token=str(uuid.uuid4()),
        )
        db.session.add(sub)
        db.session.commit()
        logger.info(f"Abonnement calendrier régénéré pour user {user_id} : token={sub.token[:8]}...")
        return sub
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erreur lors de la régénération de l'abonnement pour user {user_id} : {e}")
        return None
