import logging
from utils.checkout import TABLE_USERS

logger = logging.getLogger(__name__)


def list_users():
    """
    Fetches all users from the Airtable users table.
    Sorts by firstname.
    """
    try:
        users = TABLE_USERS.all(sort=["firstname"])
        return users
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        return []


def get_user(record_id):
    """
    Fetches a single user by their Airtable record ID.
    """
    try:
        user = TABLE_USERS.get(record_id)
        return user
    except Exception as e:
        logger.error(f"Error fetching user {record_id}: {e}")
        return None


def create_user(data):
    """
    Creates a new user in Airtable.
    `data` should be a dict containing 'firstname', 'lastname', 'mail', and 'role'.
    """
    try:
        record = TABLE_USERS.create(data)
        logger.info(f"Created new user: {record['id']} - {data.get('mail')}")
        return record
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return None


def update_user(record_id, data):
    """
    Updates an existing user.
    """
    try:
        record = TABLE_USERS.update(record_id, data)
        logger.info(f"Updated user: {record_id}")
        return record
    except Exception as e:
        logger.error(f"Error updating user {record_id}: {e}")
        return None


def delete_user(record_id):
    """
    Deletes a user from Airtable.
    """
    try:
        TABLE_USERS.delete(record_id)
        logger.info(f"Deleted user: {record_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting user {record_id}: {e}")
        return False
