import logging

from extensions import cache
from models import User, db

logger = logging.getLogger(__name__)


def invalidate_user_cache(user_id):
    """Clear cache for a specific user ID."""
    cache.delete(f"user:{user_id}")


def list_users():
    """
    Fetches all users from the database.
    Sorts by firstname.
    """
    try:
        return User.query.order_by(User.firstname).all()
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        return []


def get_user(record_id):
    """
    Fetches a single user by their ID.
    """
    try:
        return db.session.get(User, record_id)
    except Exception as e:
        logger.error(f"Error fetching user {record_id}: {e}")
        return None


def create_user(data):
    """
    Creates a new user in the database.
    `data` should be a dict containing 'firstname', 'lastname', 'mail', 'role', 'job', and 'phone'.
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
        logger.info(f"Created new user: {new_user.id} - {new_user.mail}")
        return new_user
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating user: {e}")
        return None


def update_user(record_id, data):
    """
    Updates an existing user.
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
        logger.info(f"Updated user: {record_id}")
        return user
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating user {record_id}: {e}")
        return None


def delete_user(record_id):
    """
    Deletes a user from the database.
    """
    try:
        user = db.session.get(User, record_id)
        if not user:
            return False

        db.session.delete(user)
        db.session.commit()
        invalidate_user_cache(record_id)
        logger.info(f"Deleted user: {record_id}")
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting user {record_id}: {e}")
        return False
