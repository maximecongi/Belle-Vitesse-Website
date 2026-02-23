import logging
from models import db, User

logger = logging.getLogger(__name__)


def _to_airtable_format(user):
    """
    Helper to return SQLAlchemy objects in the Airtable format 
    expected by the admin templates (id, fields dict).
    """
    if not user:
        return None
    return {
        "id": user.id,
        "fields": {
            "firstname": user.firstname,
            "lastname": user.lastname,
            "mail": user.mail,
            "role": user.role,
            "phone": user.phone
        }
    }


def list_users():
    """
    Fetches all users from the database.
    Sorts by firstname.
    """
    try:
        users = User.query.order_by(User.firstname).all()
        return [_to_airtable_format(u) for u in users]
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        return []


def get_user(record_id):
    """
    Fetches a single user by their ID.
    """
    try:
        user = db.session.get(User, record_id)
        return _to_airtable_format(user)
    except Exception as e:
        logger.error(f"Error fetching user {record_id}: {e}")
        return None


def create_user(data):
    """
    Creates a new user in the database.
    `data` should be a dict containing 'firstname', 'lastname', 'mail', and 'role'.
    """
    try:
        new_user = User(
            firstname=data.get('firstname'),
            lastname=data.get('lastname'),
            mail=data.get('mail'),
            role=data.get('role'),
            phone=data.get('phone')
        )
        db.session.add(new_user)
        db.session.commit()
        logger.info(f"Created new user: {new_user.id} - {new_user.mail}")
        return _to_airtable_format(new_user)
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
        # phone might not be in the form, but just in case
        if 'phone' in data:
            user.phone = data['phone']

        db.session.commit()
        logger.info(f"Updated user: {record_id}")
        return _to_airtable_format(user)
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
        logger.info(f"Deleted user: {record_id}")
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting user {record_id}: {e}")
        return False
