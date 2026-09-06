import os
import random
import string
import uuid
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy


class SafeSQLAlchemy(SQLAlchemy):
    """Extension sécurisée de SQLAlchemy empêchant tout drop_all accidentel hors SQLite."""

    def drop_all(self, *args, **kwargs):
        try:
            uri = str(self.engine.url) if self.engine else ""
        except Exception:
            uri = ""
        if uri and "sqlite" not in uri and os.getenv("ALLOW_DROP_ALL") != "true":
            raise RuntimeError(
                f"🚨 SÉCURITÉ : Appel db.drop_all() INTERDIT sur une base non-SQLite ({uri}) !"
            )
        return super().drop_all(*args, **kwargs)


db = SafeSQLAlchemy()


def _utcnow():
    """Retourne la date/heure UTC courante (remplace datetime.utcnow dépréciée)."""
    return datetime.now(timezone.utc)


def generate_inspection_number(prefix):
    """Génère un identifiant unique aléatoire avec un préfixe donné (ex: BVPR-XXXX)."""
    suffix = ''.join(random.choices(
        string.ascii_uppercase + string.digits, k=12))
    return f"{prefix}-{suffix}"
