import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from redis import Redis

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock WeasyPrint
mock_weasyprint = MagicMock()
mock_weasyprint.HTML = MagicMock()
mock_weasyprint.CSS = MagicMock()
sys.modules["weasyprint"] = mock_weasyprint

from app import create_app
from models import User, db
from services.common.auth import (
    get_auth_serializer,
    is_jti_consumed,
    mark_jti_consumed,
    request_magic_link,
    verify_magic_link,
)


class MagicLinksSecurityTestCase(unittest.TestCase):
    def setUp(self):
        os.environ["FLASK_ENV"] = "testing"
        os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        os.environ["WTF_CSRF_ENABLED"] = "False"
        os.environ["LAUNCH_MODE"] = "false"
        os.environ["USE_SSH_TUNNEL"] = "false"

        self.app = create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            self.user = User(
                firstname="Maxime",
                lastname="Congi",
                mail="maxime@bellevitesse.com",
                role="Super Administrateur",
            )
            db.session.add(self.user)
            db.session.commit()
            self.user_id = self.user.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_magic_link_single_use_jti_invalidation(self):
        """Un lien magique ne doit être utilisable qu'une seule et unique fois (JTI invalidé dès le premier usage)."""
        with self.app.app_context():
            with patch("services.common.auth.send_magic_link_email") as mock_send:
                mock_send.return_value = True
                success = request_magic_link("maxime@bellevitesse.com")
                self.assertTrue(success)

                # Récupérer l'URL envoyée par email
                self.assertTrue(mock_send.called)
                args, _ = mock_send.call_args
                magic_link_url = args[2]
                token = magic_link_url.split("/admin/auth/")[-1]

            # 1er usage : validation réussie
            user_data = verify_magic_link(token)
            self.assertIsNotNone(user_data)
            self.assertEqual(user_data["email"], "maxime@bellevitesse.com")
            self.assertEqual(user_data["id"], self.user_id)

            # 2ème usage : tentative de rejeu immédiatement rejetée
            second_attempt = verify_magic_link(token)
            self.assertIsNone(second_attempt, "Le jeton ne doit pas être réutilisable après consommation.")

    def test_magic_link_http_flow_and_replay_protection(self):
        """Test du flux HTTP complet de connexion par lien magique et rejet du rejeu."""
        # 1. Demande de lien magique via POST /admin/login
        with patch("services.common.auth.send_magic_link_email") as mock_send:
            mock_send.return_value = True
            resp = self.client.post("/admin/login", data={"email": "maxime@bellevitesse.com"})
            self.assertEqual(resp.status_code, 200)

            self.assertTrue(mock_send.called)
            args, _ = mock_send.call_args
            token = args[2].split("/admin/auth/")[-1]

        # 2. Premier clic sur le lien magique -> authentification et redirection vers dashboard
        click1 = self.client.get(f"/admin/auth/{token}", follow_redirects=False)
        self.assertEqual(click1.status_code, 302)
        self.assertIn("/admin/dashboard", click1.location)

        # Vérifier que la session est bien authentifiée
        with self.client.session_transaction() as sess:
            self.assertTrue(sess.get("admin_authenticated"))
            self.assertEqual(sess.get("admin_user_id"), self.user_id)

        # 3. Déconnexion
        self.client.get("/admin/logout")

        # 4. Deuxième clic sur le même lien magique -> rejet immédiat et redirection vers login
        click2 = self.client.get(f"/admin/auth/{token}", follow_redirects=False)
        self.assertEqual(click2.status_code, 302)
        self.assertIn("/admin/login", click2.location)

        # La session ne doit pas être authentifiée
        with self.client.session_transaction() as sess:
            self.assertFalse(sess.get("admin_authenticated"))

    def test_debug_mode_does_not_auto_login_on_admin_login(self):
        """Le mode DEBUG=True en environnement de développement ne doit plus jamais authentifier automatiquement l'utilisateur anonyme."""
        self.app.config["FLASK_ENV"] = "development"
        self.app.config["DEBUG"] = True

        resp = self.client.get("/admin/login")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Dashboard Admin", resp.get_data(as_text=True))

        # Vérifier qu'aucune session n'a été créée
        with self.client.session_transaction() as sess:
            self.assertFalse(sess.get("admin_authenticated"))
            self.assertIsNone(sess.get("admin_user_id"))

    def test_debug_mode_does_not_auto_login_on_protected_routes(self):
        """L'accès à une route protégée par @require_roles sans session doit rediriger vers login même avec DEBUG=True."""
        self.app.config["FLASK_ENV"] = "development"
        self.app.config["DEBUG"] = True

        resp = self.client.get("/admin/dashboard", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/admin/login", resp.location)

        # Vérifier qu'aucune session n'a été forgée
        with self.client.session_transaction() as sess:
            self.assertFalse(sess.get("admin_authenticated"))

    def test_expired_magic_link_rejected(self):
        """Un jeton dont la durée dépasse 900s doit être rejeté."""
        from itsdangerous import SignatureExpired
        with self.app.app_context():
            with patch("services.common.auth.get_auth_serializer") as mock_get_ser:
                mock_ser = MagicMock()
                mock_ser.loads.side_effect = SignatureExpired("Token expired")
                mock_get_ser.return_value = mock_ser
                result = verify_magic_link("dummy-token")
                self.assertIsNone(result)

    def test_tampered_magic_link_rejected(self):
        """Un jeton altéré ou falsifié doit être rejeté."""
        with self.app.app_context():
            result = verify_magic_link("forged-invalid-token-content")
            self.assertIsNone(result)

    def test_magic_link_jti_invalidation_with_redis(self):
        """Vérifie l'enregistrement et le rejet d'un JTI consommé via le backend Redis."""
        class MockRedisAuth(Redis):
            def __init__(self):
                self.data = {}
            def get(self, key):
                return self.data.get(key)
            def set(self, name, value, ex=None, **kwargs):
                self.data[name] = value
                return True
            def setex(self, name, time, value):
                self.data[name] = value
                return True
            def exists(self, *names):
                return sum(1 for n in names if n in self.data)
            def delete(self, *names):
                return sum(1 for n in names if self.data.pop(n, None) is not None)

        mock_redis = MockRedisAuth()
        with self.app.app_context():
            with patch("services.common.auth._get_auth_redis_client", return_value=mock_redis):
                with patch("services.common.auth.send_magic_link_email", return_value=True):
                    request_magic_link("maxime@bellevitesse.com")

                # Récupérer la clé pending
                pending_keys = [k for k in mock_redis.data if k.startswith("bv_magic_link_pending:")]
                self.assertEqual(len(pending_keys), 1)
                jti = pending_keys[0].split("bv_magic_link_pending:")[-1]

                # Simuler le jeton
                serializer = get_auth_serializer()
                token = serializer.dumps({"email": "maxime@bellevitesse.com", "jti": jti}, salt="magic-link-salt")

                # 1ère validation
                res1 = verify_magic_link(token)
                self.assertIsNotNone(res1)
                self.assertIn(f"bv_magic_link_used:{jti}", mock_redis.data)

                # 2ème validation -> rejet immédiat
                res2 = verify_magic_link(token)
                self.assertIsNone(res2)


if __name__ == "__main__":
    unittest.main()

