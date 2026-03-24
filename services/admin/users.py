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
        logger.info(f"Utilisateur mis à jour : {record_id}")
        return user
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erreur lors de la mise à jour de l'utilisateur {record_id} : {e}")
        return None


def delete_user(record_id):
    """
    Supprime un utilisateur de la base de données.
    """
    try:
        user = db.session.get(User, record_id)
        if not user:
            return False

        db.session.delete(user)
        db.session.commit()
        invalidate_user_cache(record_id)
        logger.info(f"Utilisateur supprimé : {record_id}")
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erreur lors de la suppression de l'utilisateur {record_id} : {e}")
        return False
