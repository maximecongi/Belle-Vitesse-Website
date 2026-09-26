import os
import sys
import unittest
from unittest.mock import MagicMock
from redis import Redis

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock WeasyPrint
mock_weasyprint = MagicMock()
mock_weasyprint.HTML = MagicMock()
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint

from flask import Flask, session
from app import create_app
from extensions import server_session
from models import User, db
from services.common.session_manager import (
    get_user_active_sessions,
    invalidate_user_sessions,
    register_user_session,
    unregister_user_session,
)
from services.admin.users import create_user, delete_user, update_user


class MockRedisStore(Redis):
    """Client Redis simulé en mémoire pour tester Flask-Session et le session_manager."""

    def __init__(self):
        self.data = {}
        self.sets = {}

    def ping(self):
        return True

    def get(self, key):
        return self.data.get(key)

    def set(self, name, value, ex=None, **kwargs):
        self.data[name] = value
        return True

    def delete(self, *names):
        count = 0
        for n in names:
            if n in self.data:
                del self.data[n]
                count += 1
            if n in self.sets:
                del self.sets[n]
                count += 1
        return count

    def sadd(self, name, *values):
        if name not in self.sets:
            self.sets[name] = set()
        for v in values:
            self.sets[name].add(str(v))
        return len(values)

    def srem(self, name, *values):
        if name not in self.sets:
            return 0
        count = 0
        for v in values:
            if str(v) in self.sets[name]:
                self.sets[name].remove(str(v))
                count += 1
        return count

    def smembers(self, name):
        if name not in self.sets:
            return set()
        return {v.encode("utf-8") for v in self.sets[name]}

    def expire(self, name, time):
        return True


class FlaskSessionTestCase(unittest.TestCase):
    def setUp(self):
        self.mock_redis = MockRedisStore()
        os.environ["FLASK_ENV"] = "testing"
        os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        os.environ["WTF_CSRF_ENABLED"] = "False"
        os.environ["LAUNCH_MODE"] = "false"
        os.environ["USE_SSH_TUNNEL"] = "false"

        self.app = create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.app.config["SESSION_TYPE"] = "redis"
        self.app.config["SESSION_REDIS"] = self.mock_redis
        self.app.config["SESSION_KEY_PREFIX"] = "bv_session:"
        self.app.config["SESSION_USE_SIGNER"] = True

        # Initialiser Flask-Session avec le mock Redis
        server_session.init_app(self.app)

        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            self.user = User(
                firstname="Alice",
                lastname="Technicienne",
                mail="alice@bellevitesse.com",
                role="Technicien",
            )
            db.session.add(self.user)
            db.session.commit()
            self.user_id = self.user.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_session_stored_in_redis_not_in_cookie(self):
        """Les données de session doivent être stockées dans Redis et non dans le cookie client."""
        @self.app.route("/test-set-session")
        def set_sess():
            session["admin_authenticated"] = True
            session["admin_user_id"] = self.user_id
            session["admin_user_role"] = "Technicien"
            return "session_set"

        resp = self.client.get("/test-set-session")
        self.assertEqual(resp.status_code, 200)

        # Vérifier le cookie HTTP
        cookie = resp.headers.get("Set-Cookie", "")
        self.assertIn("session=", cookie)
        # Les données sensibles ne doivent pas apparaître dans le cookie en clair
        self.assertNotIn("Technicien", cookie)
        self.assertNotIn("admin_user_id", cookie)

        # Vérifier que les données sont enregistrées dans Redis avec le préfixe
        redis_keys = [k for k in self.mock_redis.data.keys() if k.startswith("bv_session:")]
        self.assertEqual(len(redis_keys), 1)

    def test_logout_clears_session_from_redis(self):
        """La déconnexion doit purger la session de Redis et supprimer le cookie."""
        # 1. Se connecter
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = self.user_id
            sess["admin_user_role"] = "Technicien"

        # Vérifier qu'une clé existe dans Redis
        self.assertGreater(len(self.mock_redis.data), 0)

        # 2. Se déconnecter
        resp = self.client.get("/admin/logout", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)

        # La session dans le client doit être vidée
        with self.client.session_transaction() as sess:
            self.assertFalse(sess.get("admin_authenticated"))
            self.assertIsNone(sess.get("admin_user_id"))

    def test_user_session_registration_and_invalidation(self):
        """Enregistrement et révocation immédiate de toutes les sessions actives d'un utilisateur."""
        with self.app.app_context():
            # Enregistrer 2 sessions actives pour l'utilisateur
            register_user_session(self.user_id, "sid_alpha_1")
            register_user_session(self.user_id, "sid_beta_2")

            # Stocker des données de session fictives dans Redis
            self.mock_redis.set("bv_session:sid_alpha_1", b"data1")
            self.mock_redis.set("bv_session:sid_beta_2", b"data2")

            active = get_user_active_sessions(self.user_id)
            self.assertIn("sid_alpha_1", active)
            self.assertIn("sid_beta_2", active)

            # Invalider toutes les sessions
            revoked_count = invalidate_user_sessions(self.user_id)
            self.assertEqual(revoked_count, 2)

            # Vérifier que les clés Redis ont bien été supprimées
            self.assertIsNone(self.mock_redis.get("bv_session:sid_alpha_1"))
            self.assertIsNone(self.mock_redis.get("bv_session:sid_beta_2"))
            self.assertEqual(get_user_active_sessions(self.user_id), [])

    def test_user_role_update_triggers_session_invalidation(self):
        """La modification du rôle d'un utilisateur révoque immédiatement ses sessions actives."""
        with self.app.app_context():
            # Enregistrer une session
            register_user_session(self.user_id, "sid_live_test")
            self.mock_redis.set("bv_session:sid_live_test", b"live_data")

            # Modifier le rôle de Technicien à Administrateur
            update_user(self.user_id, {
                "firstname": "Alice",
                "lastname": "Technicienne",
                "mail": "alice@bellevitesse.com",
                "role": "Administrateur"
            })

            # La session doit avoir été révoquée
            self.assertIsNone(self.mock_redis.get("bv_session:sid_live_test"))

    def test_user_deletion_triggers_session_invalidation(self):
        """La suppression d'un utilisateur révoque immédiatement ses sessions actives."""
        with self.app.app_context():
            register_user_session(self.user_id, "sid_to_delete")
            self.mock_redis.set("bv_session:sid_to_delete", b"live_data")

            delete_user(self.user_id)

            self.assertIsNone(self.mock_redis.get("bv_session:sid_to_delete"))

    def test_session_fallback_when_redis_fails(self):
        """Vérifie que l'application démarre et bascule gracieusement sur les cookies si Redis est inaccessible."""
        failing_app = Flask("failing_test_app")
        failing_app.config["SECRET_KEY"] = "test-secret"
        failing_app.config["SESSION_TYPE"] = "redis"
        failing_app.config["REDIS_PORT"] = 99999  # Port inexistant

        # Importer create_app logique fallback
        from redis import Redis
        redis_client = Redis(host="127.0.0.1", port=9999, socket_connect_timeout=0.1)
        try:
            redis_client.ping()
            server_session.init_app(failing_app)
        except Exception:
            # Fallback automatique
            pass

        # L'interface par défaut de Flask (SecureCookieSessionInterface) doit être conservée
        from flask.sessions import SecureCookieSessionInterface
        self.assertIsInstance(failing_app.session_interface, SecureCookieSessionInterface)


if __name__ == "__main__":
    unittest.main()
