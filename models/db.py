import random
import string
import uuid
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def _utcnow():
    """Retourne la date/heure UTC courante (remplace datetime.utcnow dépréciée)."""
    return datetime.now(timezone.utc)


def generate_inspection_number(prefix):
    """Génère un identifiant unique aléatoire avec un préfixe donné (ex: BVPR-XXXX)."""
    suffix = ''.join(random.choices(
        string.ascii_uppercase + string.digits, k=12))
    return f"{prefix}-{suffix}"
