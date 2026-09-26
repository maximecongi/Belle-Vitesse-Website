import time
import unittest
from unittest.mock import patch
from app import create_app
from models import NewsletterSubscriber, db
from services.public.newsletter import (
    generate_newsletter_token,
    validate_newsletter_submission,
)
from itsdangerous import URLSafeTimedSerializer


class NewsletterAntiSpamTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        db.session.rollback()
        # Nettoyage des abonnés créés pendant les tests
        NewsletterSubscriber.query.filter(
            NewsletterSubscriber.email.like("test_antispam_%")
        ).delete()
        db.session.commit()
        self.ctx.pop()

    def test_token_generation(self):
        """Vérifie que la génération du jeton produit un token valide et décodable."""
        token = generate_newsletter_token()
        self.assertTrue(bool(token))

        secret = self.app.config.get("SECRET_KEY", "bv_newsletter_default_secret")
        serializer = URLSafeTimedSerializer(secret, salt="newsletter-anti-bot")
        timestamp = serializer.loads(token, max_age=10, salt="newsletter-anti-bot")
        self.assertAlmostEqual(timestamp, time.time(), delta=2.0)

    def test_honeypot_triggered(self):
        """Vérifie que le remplissage du honeypot déclenche un silent drop."""
        form_data = {
            "email": "test_antispam_hp@example.com",
            "website_hp": "http://spambot.com",
            "subscribe_token": generate_newsletter_token(),
        }
        is_valid, reason, detail = validate_newsletter_submission(
            form_data, email=form_data["email"]
        )
        self.assertFalse(is_valid)
        self.assertEqual(reason, "honeypot_triggered")

        # Test via l'endpoint HTTP /subscribe
        with patch("utils.mailer.send_subscription_email") as mock_mail:
            resp = self.client.post("/subscribe", data=form_data)
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertEqual(data["status"], "success")

            # Vérifie qu'aucun email n'a été envoyé et rien en base
            mock_mail.assert_not_called()
            sub = NewsletterSubscriber.query.filter_by(
                email=form_data["email"]
            ).first()
            self.assertIsNone(sub)

    def test_dot_stuffing_detection(self):
        """Vérifie que les adresses artificiellement truffées de points sont neutralisées."""
        fake_email = "a.w.e.s.o.m.e.bot@gmail.com"
        form_data = {
            "email": fake_email,
            "website_hp": "",
            "subscribe_token": generate_newsletter_token(),
        }
        is_valid, reason, _ = validate_newsletter_submission(form_data, email=fake_email)
        self.assertFalse(is_valid)
        self.assertEqual(reason, "dot_stuffing")

        with patch("utils.mailer.send_subscription_email") as mock_mail:
            resp = self.client.post("/subscribe", data=form_data)
            self.assertEqual(resp.status_code, 200)
            mock_mail.assert_not_called()
            self.assertIsNone(
                NewsletterSubscriber.query.filter_by(email=fake_email).first()
            )

    def test_disposable_domain_detection(self):
        """Vérifie le blocage silencieux des domaines d'emails jetables."""
        disposable_email = "spammer@mailinator.com"
        form_data = {
            "email": disposable_email,
            "website_hp": "",
            "subscribe_token": generate_newsletter_token(),
        }
        is_valid, reason, _ = validate_newsletter_submission(
            form_data, email=disposable_email
        )
        self.assertFalse(is_valid)
        self.assertEqual(reason, "disposable_domain")

    def test_gov_institution_detection(self):
        """Vérifie le blocage silencieux des domaines institutionnels ciblés par flood."""
        victim_email = "target@state.gov"
        form_data = {
            "email": victim_email,
            "website_hp": "",
            "subscribe_token": generate_newsletter_token(),
        }
        is_valid, reason, _ = validate_newsletter_submission(
            form_data, email=victim_email
        )
        self.assertFalse(is_valid)
        self.assertEqual(reason, "gov_mil_blocked")

    def test_too_fast_submission_time_trap(self):
        """Vérifie qu'une soumission en moins de 1.5s est détectée comme bot."""
        # Pour tester le time-trap, on simule un environnement non-testing
        secret = self.app.config.get("SECRET_KEY", "bv_newsletter_default_secret")
        serializer = URLSafeTimedSerializer(secret, salt="newsletter-anti-bot")
        # Token créé il y a 0.2 seconde
        fast_token = serializer.dumps(time.time() - 0.2)

        self.app.config["TESTING"] = False
        try:
            form_data = {
                "email": "test_antispam_fast@example.com",
                "website_hp": "",
                "subscribe_token": fast_token,
            }
            is_valid, reason, _ = validate_newsletter_submission(
                form_data, email=form_data["email"]
            )
            self.assertFalse(is_valid)
            self.assertEqual(reason, "submitted_too_fast")
        finally:
            self.app.config["TESTING"] = True

    def test_legit_user_submission_succeeds(self):
        """Vérifie qu'un humain normal (token valide, délai normal, champ vide) est bien inscrit."""
        legit_email = "test_antispam_legit@example.com"
        secret = self.app.config.get("SECRET_KEY", "bv_newsletter_default_secret")
        serializer = URLSafeTimedSerializer(secret, salt="newsletter-anti-bot")
        token = serializer.dumps(time.time() - 3.0)

        form_data = {
            "email": legit_email,
            "website_hp": "",
            "subscribe_token": token,
            "lang": "fr",
        }

        with patch("utils.mailer.send_subscription_email") as mock_mail:
            resp = self.client.post("/subscribe", data=form_data)
            self.assertEqual(resp.status_code, 200)
            mock_mail.assert_called_once_with(legit_email)

            sub = NewsletterSubscriber.query.filter_by(email=legit_email).first()
            self.assertIsNotNone(sub)


if __name__ == "__main__":
    unittest.main()
