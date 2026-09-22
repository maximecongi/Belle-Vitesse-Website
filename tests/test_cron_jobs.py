import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

# Isolation stricte de l'environnement de test
os.environ["FLASK_ENV"] = "testing"
os.environ["TESTING"] = "True"
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
os.environ["WTF_CSRF_ENABLED"] = "False"
os.environ["USE_SSH_TUNNEL"] = "false"

from scripts.verify_cron_jobs import format_timestamp, verify_jobs
from app import create_app


class CronJobsVerificationTest(unittest.TestCase):
    def test_format_timestamp_empty(self):
        self.assertEqual(format_timestamp(None), "Jamais")
        self.assertEqual(format_timestamp(""), "Jamais")

    def test_format_timestamp_summer_paris(self):
        # 16 Septembre (Heure d'été CEST = UTC+2)
        # 02:00:01 UTC -> 04:00:01 Heure de Paris
        iso_str = "2026-09-16T02:00:01.000000+00:00"
        formatted = format_timestamp(iso_str)
        self.assertEqual(formatted, "16/09/2026 à 04:00:01")

    def test_format_timestamp_winter_paris(self):
        # 15 Janvier (Heure d'hiver CET = UTC+1)
        # 03:00:01 UTC -> 04:00:01 Heure de Paris
        iso_str = "2026-01-15T03:00:01.000000+00:00"
        formatted = format_timestamp(iso_str)
        self.assertEqual(formatted, "15/01/2026 à 04:00:01")

    def test_format_timestamp_with_z(self):
        # Format ISO avec 'Z'
        iso_str = "2026-09-16T02:00:01Z"
        formatted = format_timestamp(iso_str)
        self.assertEqual(formatted, "16/09/2026 à 04:00:01")

    def test_format_timestamp_naive_string(self):
        # Timestamp sans offset explicite -> interprété en UTC puis converti en heure de Paris
        iso_str = "2026-09-16T02:00:01"
        formatted = format_timestamp(iso_str)
        self.assertEqual(formatted, "16/09/2026 à 04:00:01")

    @patch("scripts.verify_cron_jobs.load_cron_status")
    def test_verify_jobs(self, mock_load):
        mock_load.return_value = {
            "backup_sql": {
                "last_run": "2026-09-16T02:00:01+00:00",
                "status": "success",
                "error": None,
            }
        }
        jobs, failures, global_status = verify_jobs()
        backup_job = next(j for j in jobs if j["job_name"] == "backup_sql")
        self.assertEqual(backup_job["last_run_display"], "16/09/2026 à 04:00:01")

    def test_cron_report_template_rendering(self):
        app = create_app()
        with app.app_context():
            from flask import render_template

            rendered = render_template(
                "emails/cron_report.html",
                jobs=[
                    {
                        "job_name": "backup_sql",
                        "display_name": "Sauvegarde Base de Données SQL",
                        "expected_freq": "Tous les jours à 4h00",
                        "last_run_display": "16/09/2026 à 04:00:01",
                        "status": "success",
                    }
                ],
                failures=[],
                global_status="OK",
                date_str="16/09/2026",
                time_str="08:00:00",
                now_year=2026,
            )
            # Vérifie qu'il n'y a plus de mention "(UTC)" dans l'en-tête de colonne
            self.assertNotIn("Dernière exécution (UTC)", rendered)
            self.assertIn("Dernière exécution", rendered)
            self.assertIn("16/09/2026 à 04:00:01", rendered)


if __name__ == "__main__":
    unittest.main()
