import uuid
from models.db import db, _utcnow


class SqlQueryLog(db.Model):
    """Journal des requêtes SQL (Monitoring de performance)."""
    __tablename__ = "sql_query_logs"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    timestamp = db.Column(db.DateTime(6), default=_utcnow)
    user = db.Column(db.String(255), nullable=False, default='anonymous')
    ip_address = db.Column(db.String(50))
    endpoint = db.Column(db.String(255))
    method = db.Column(db.String(10))
    query = db.Column(db.Text, nullable=False)
    parameters = db.Column(db.Text)
    duration_ms = db.Column(db.Float)

    __table_args__ = (
        db.Index('idx_timestamp_user', 'timestamp', 'user'),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8mb4',
        }
    )

    def __repr__(self):
        return f"<SqlQueryLog {self.id} user={self.user} endpoint={self.endpoint}>"


class CalendarSubscription(db.Model):
    """Abonnement calendrier ICS sécurisé par token unique."""
    __tablename__ = "calendar_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = db.Column(db.String(36), unique=True,
                      nullable=False, default=lambda: str(uuid.uuid4()))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)
    last_accessed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", backref=db.backref("calendar_subscriptions", cascade="all, delete-orphan", passive_deletes=True))

    def to_dict(self):
        """Convertit l'objet en dictionnaire pour les réponses API."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "token": self.token,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_accessed_at": self.last_accessed_at.isoformat() if self.last_accessed_at else None,
        }

    def __repr__(self):
        return f"<CalendarSubscription user={self.user_id} active={self.is_active}>"


class AppSetting(db.Model):
    """Table clé/valeur pour les paramètres globaux de l'application."""
    __tablename__ = "app_settings"

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.String(500), nullable=False)
    updated_at = db.Column(
        db.DateTime, default=_utcnow, onupdate=_utcnow)

    @staticmethod
    def get(key, default=None):
        """
        Récupère une valeur par clé, avec fallback hiérarchique :
        1. Valeur en base de données (si non vide)
        2. Valeur par défaut fournie (si non vide)
        3. Variable d'environnement correspondante (.env)
        4. Chaîne vide
        """
        import os
        from extensions import cache
        cache_key = f"setting:{key}"
        try:
            val = cache.get(cache_key)
            if val is not None and str(val).strip():
                return val
        except Exception:
            pass

        setting = db.session.get(AppSetting, key)
        if setting and setting.value and str(setting.value).strip():
            val = str(setting.value).strip()
        else:
            if default is not None and str(default).strip():
                val = str(default).strip()
            else:
                env_val = os.getenv(key.upper()) or os.getenv(key)
                val = env_val.strip() if env_val else (default or "")

        try:
            cache.set(cache_key, val, timeout=3600)
        except Exception:
            pass
        return val

    @staticmethod
    def get_all_as_dict(keys_defaults: dict) -> dict:
        """Récupère plusieurs paramètres d'un coup de manière optimisée avec fallback env."""
        import os
        from extensions import cache
        keys = list(keys_defaults.keys())

        # 1. Tenter de lire depuis le cache en lot
        cache_keys = [f"setting:{k}" for k in keys]
        cached_results = {}
        try:
            vals = cache.get_many(*cache_keys)
            for k, val in zip(keys, vals):
                if val is not None and str(val).strip():
                    cached_results[k] = str(val).strip()
        except Exception:
            pass

        # 2. S'il manque des clés, les charger de la DB d'un coup
        missing_keys = [k for k in keys if k not in cached_results]
        if missing_keys:
            try:
                db_settings = AppSetting.query.filter(AppSetting.key.in_(missing_keys)).all()
                db_dict = {s.key: str(s.value).strip() for s in db_settings if s.value and str(s.value).strip()}
                for k in missing_keys:
                    val = db_dict.get(k)
                    if not val:
                        d = keys_defaults.get(k)
                        if d is not None and str(d).strip():
                            val = str(d).strip()
                        else:
                            env_val = os.getenv(k.upper()) or os.getenv(k)
                            val = env_val.strip() if env_val else (d or "")
                    cached_results[k] = val
                    try:
                        cache.set(f"setting:{k}", val, timeout=3600)
                    except Exception:
                        pass
            except Exception:
                for k in missing_keys:
                    d = keys_defaults.get(k)
                    env_val = os.getenv(k.upper()) or os.getenv(k)
                    cached_results[k] = env_val.strip() if env_val else (d or "")

        return cached_results

    @staticmethod
    def set(key, value):
        """Crée ou met à jour un paramètre (et met à jour le cache)."""
        from extensions import cache
        setting = db.session.get(AppSetting, key)
        if setting:
            setting.value = str(value)
        else:
            setting = AppSetting(key=key, value=str(value))
            db.session.add(setting)
        db.session.commit()
        try:
            cache.set(f"setting:{key}", str(value), timeout=3600)
        except Exception:
            pass
        return setting

    def __repr__(self):
        return f"<AppSetting {self.key}={self.value}>"
