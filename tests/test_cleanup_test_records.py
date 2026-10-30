import unittest
from datetime import date

from flask import Flask

from models import (
    db,
    CalendarSubscription,
    Contact,
    Incident,
    KDriveObject,
    McpApiToken,
    Project,
    ProjectReport,
    Production,
    SignatureEvent,
    User,
    Vehicle,
)
from scripts.cleanup_test_records import (
    _delete_records,
    discover_cleanup,
    is_test_10,
    is_test_name,
    is_test_user,
)
from sqlalchemy.orm import Session


class TestRecordCleanupTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask("test_record_cleanup_test")
        self.app.config.update(
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SQLALCHEMY_ENGINE_OPTIONS={},
        )
        db.init_app(self.app)
        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.session.remove()

    def test_test_name_matching_is_token_based_and_test10_is_exact(self):
        self.assertTrue(is_test_name("Production TEST - 02"))
        self.assertTrue(is_test_name("test_project"))
        self.assertFalse(is_test_name("Latest Studio"))
        self.assertTrue(is_test_10("  Test   10  "))
        self.assertFalse(is_test_10("TEST 10 — Démo"))

    def test_preview_preserves_test10_group_and_skips_mixed_production(self):
        with self.app.app_context():
            test_production = Production(name="Studio TEST");
            mixed_production = Production(name="TEST production mixte")
            protected_production = Production(name="  TEST   10 ")
            regular_production = Production(name="Studio ordinaire")
            db.session.add_all([test_production, mixed_production, protected_production, regular_production])
            db.session.flush()

            test_contact = Contact(first_name="Test", last_name="Pilote", production_id=test_production.id)
            db.session.add(test_contact)
            db.session.flush()

            removable_project = Project(
                name="Projet test plateau",
                production_id=test_production.id,
                pilot_contact_id=test_contact.id,
            )
            mixed_test_project = Project(name="Project TEST A", production_id=mixed_production.id)
            mixed_live_project = Project(name="Tournage client", production_id=mixed_production.id)
            protected_named_project = Project(name="TEST 10", production_id=protected_production.id)
            protected_other_project = Project(name="Projet lié", production_id=protected_production.id)
            normal_project = Project(name="Tournage normal", production_id=regular_production.id)
            db.session.add_all([
                removable_project,
                mixed_test_project,
                mixed_live_project,
                protected_named_project,
                protected_other_project,
                normal_project,
            ])
            db.session.flush()

            report = ProjectReport(project_id=removable_project.id, content="rapport de test")
            kdrive_object = KDriveObject(
                project_id=removable_project.id,
                entity_type="project",
                entity_id=str(removable_project.id),
                role="test",
                source_key="test-source",
            )
            test_incident = Incident(
                title="Test incident isolé",
                project_id=normal_project.id,
                incident_date=date(2026, 1, 1),
            )
            db.session.add_all([
                report,
                kdrive_object,
                test_incident,
                Vehicle(id="veh-test", fields={"name": "Moto TEST"}),
                Vehicle(id="veh-test-10", fields={"name": "TEST 10"}),
            ])
            db.session.flush()
            signature_event = SignatureEvent(
                document_id=test_incident.incident_number,
                mode="incident",
                event_type="test_created",
            )
            db.session.add(signature_event)
            db.session.commit()

            with Session(db.engine) as session:
                manifest = discover_cleanup(session, "test_db", "bv_mysql", 3306)

            selection = manifest["selection"]
            roots = {(row["table"], row["id"], row["name"]) for row in selection["roots"]}
            deleted_project_ids = {
                row["id"] for row in selection["delete_keys"]["projects"]
            }
            deleted_production_ids = {
                row["id"] for row in selection["delete_keys"]["productions"]
            }
            deleted_contact_ids = {
                row["id"] for row in selection["delete_keys"]["contacts"]
            }

            self.assertIn(removable_project.id, deleted_project_ids)
            self.assertIn(test_production.id, deleted_production_ids)
            self.assertIn(test_contact.id, deleted_contact_ids)
            self.assertIn(mixed_test_project.id, deleted_project_ids)
            self.assertNotIn(mixed_production.id, deleted_production_ids)
            self.assertNotIn(mixed_live_project.id, deleted_project_ids)
            self.assertNotIn(protected_production.id, deleted_production_ids)
            self.assertNotIn(protected_named_project.id, deleted_project_ids)
            self.assertNotIn(protected_other_project.id, deleted_project_ids)
            self.assertNotIn(("vehicles", "veh-test-10", "TEST 10"), roots)
            self.assertIn(("vehicles", "veh-test", "Moto TEST"), roots)
            self.assertIn("mixed_production", {warning["type"] for warning in manifest["warnings"]})
            self.assertIn(report.id, {
                row["id"] for row in selection["delete_keys"]["project_reports"]
            })
            self.assertIn(kdrive_object.id, {
                row["id"] for row in selection["delete_keys"]["kdrive_objects"]
            })
            self.assertEqual(manifest["signature_events_preserved"], 1)

            removable_project_id = removable_project.id
            protected_project_id = protected_named_project.id
            mixed_live_project_id = mixed_live_project.id
            test_production_id = test_production.id
            mixed_production_id = mixed_production.id
            signature_event_id = signature_event.id
            report_id = report.id
            kdrive_object_id = kdrive_object.id

            with db.engine.begin() as connection:
                _delete_records(connection, manifest)

            db.session.expire_all()
            self.assertIsNone(db.session.get(Project, removable_project_id))
            self.assertIsNotNone(db.session.get(Project, protected_project_id))
            self.assertIsNotNone(db.session.get(Project, mixed_live_project_id))
            self.assertIsNone(db.session.get(Production, test_production_id))
            self.assertIsNotNone(db.session.get(Production, mixed_production_id))
            self.assertIsNotNone(db.session.get(SignatureEvent, signature_event_id))
            self.assertIsNone(db.session.get(ProjectReport, report_id))
            self.assertIsNone(db.session.get(KDriveObject, kdrive_object_id))
            self.assertIsNone(db.session.get(Vehicle, "veh-test"))
            self.assertIsNotNone(db.session.get(Vehicle, "veh-test-10"))

    def test_preview_and_cleanup_test_users_and_tokens(self):
        with self.app.app_context():
            real_user = User(id=1, firstname="Maxime", lastname="Congi", mail="maxime@bellevitesse.com", role="administrator")
            test_user1 = User(id=901, firstname="Test", lastname="User901", mail="user901@example.com", role="technicien")
            test_user2 = User(id=902, firstname="Test", lastname="User902", mail="user902@example.com", role="commercial")
            protected_user = User(id=910, firstname="Test", lastname="10", mail="test10@example.com", role="manager")
            db.session.add_all([real_user, test_user1, test_user2, protected_user])
            db.session.flush()

            token1 = McpApiToken(user_id=test_user1.id, name="Com ReadOnly", token_prefix="bv_mcp_1", token_hash="hash_1")
            token_real = McpApiToken(user_id=real_user.id, name="BV ADMIN", token_prefix="bv_mcp_real", token_hash="hash_real")
            cal_sub = CalendarSubscription(user_id=test_user1.id, token="cal_token_123", is_active=True)
            db.session.add_all([token1, token_real, cal_sub])
            db.session.commit()

            with Session(db.engine) as session:
                manifest = discover_cleanup(session, "test_db", "bv_mysql", 3306)

            selection = manifest["selection"]
            deleted_user_ids = {row["id"] for row in selection["delete_keys"]["users"]}
            deleted_token_ids = {row["id"] for row in selection["delete_keys"]["mcp_api_tokens"]}
            deleted_cal_ids = {row["id"] for row in selection["delete_keys"]["calendar_subscriptions"]}

            self.assertIn(test_user1.id, deleted_user_ids)
            self.assertIn(test_user2.id, deleted_user_ids)
            self.assertNotIn(real_user.id, deleted_user_ids)
            self.assertNotIn(protected_user.id, deleted_user_ids)
            self.assertIn(token1.id, deleted_token_ids)
            self.assertNotIn(token_real.id, deleted_token_ids)
            self.assertIn(cal_sub.id, deleted_cal_ids)

            u1_id = test_user1.id
            u2_id = test_user2.id
            real_id = real_user.id
            prot_id = protected_user.id
            t1_id = token1.id
            tr_id = token_real.id
            cal_id = cal_sub.id

            with db.engine.begin() as connection:
                _delete_records(connection, manifest)

            db.session.expire_all()
            self.assertIsNone(db.session.get(User, u1_id))
            self.assertIsNone(db.session.get(User, u2_id))
            self.assertIsNotNone(db.session.get(User, real_id))
            self.assertIsNotNone(db.session.get(User, prot_id))
            self.assertIsNone(db.session.get(McpApiToken, t1_id))
            self.assertIsNotNone(db.session.get(McpApiToken, tr_id))
            self.assertIsNone(db.session.get(CalendarSubscription, cal_id))

    def test_shared_test_user_is_retained_with_warning(self):
        with self.app.app_context():
            retained_production = Production(name="Production Réelle Client")
            db.session.add(retained_production)
            db.session.flush()

            test_user = User(id=903, firstname="Test", lastname="User903", mail="user903@example.com", role="manager")
            db.session.add(test_user)
            db.session.flush()

            retained_project = Project(
                name="Tournage En Cours",
                production_id=retained_production.id,
                last_action_by_id=test_user.id,
            )
            db.session.add(retained_project)
            db.session.commit()

            with Session(db.engine) as session:
                manifest = discover_cleanup(session, "test_db", "bv_mysql", 3306)

            selection = manifest["selection"]
            deleted_user_ids = {row["id"] for row in selection["delete_keys"]["users"]}
            self.assertNotIn(test_user.id, deleted_user_ids)
            self.assertIn("shared_user", {warning["type"] for warning in manifest["warnings"]})


if __name__ == "__main__":
    unittest.main()
