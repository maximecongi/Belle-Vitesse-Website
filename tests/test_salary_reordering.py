import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import db, SalaryPosition, SalaryRate
from services.admin.pricing import (
    reorder_salary_rates,
    normalize_salary_positions_order,
    list_salary_rates_grouped
)


class SalaryReorderingTest(unittest.TestCase):
    def setUp(self):
        os.environ["FLASK_ENV"] = "testing"
        os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        os.environ["WTF_CSRF_ENABLED"] = "False"
        os.environ["USE_SSH_TUNNEL"] = "false"

        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False

        with self.app.app_context():
            db.create_all()

            # Création de positions de test
            pos1 = SalaryPosition(group_name="Pilote", position="Pilote A", display_order=14)
            pos2 = SalaryPosition(group_name="Pilote", position="Pilote B", display_order=22)
            pos3 = SalaryPosition(group_name="Cadreur", position="Cadreur A", display_order=40)
            db.session.add_all([pos1, pos2, pos3])
            db.session.commit()

            # Création de taux (annexes) pour chaque position
            for pos in [pos1, pos2, pos3]:
                for annexe in ["Annexe 1", "USPA", "Facture"]:
                    rate = SalaryRate(
                        position_id=pos.id,
                        annexe=annexe,
                        base_hourly=30.0,
                        inter_8h=240.0,
                        inter_10h=360.0
                    )
                    db.session.add(rate)
            db.session.commit()

            self.pos1_id = pos1.id
            self.pos2_id = pos2.id
            self.pos3_id = pos3.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_reorder_salary_rates_with_position_ids(self):
        """Vérifie que le réordonnancement par position_id génère des display_order séquentiels propres (0, 1, 2...)."""
        with self.app.app_context():
            # Inverser Pilote B avant Pilote A, puis Cadreur A
            groups_order = {
                "Pilote": [self.pos2_id, self.pos1_id],
                "Cadreur": [self.pos3_id]
            }
            res = reorder_salary_rates(groups_order)
            self.assertTrue(res)

            p2 = db.session.get(SalaryPosition, self.pos2_id)
            p1 = db.session.get(SalaryPosition, self.pos1_id)
            p3 = db.session.get(SalaryPosition, self.pos3_id)

            self.assertEqual(p2.display_order, 0)
            self.assertEqual(p1.display_order, 1)
            self.assertEqual(p3.display_order, 2)

    def test_reorder_salary_rates_move_across_groups(self):
        """Vérifie que déplacer une position d'un groupe à un autre met à jour son group_name et son ordre."""
        with self.app.app_context():
            # Déplacer Pilote A dans le groupe Cadreur
            groups_order = {
                "Pilote": [self.pos2_id],
                "Cadreur": [self.pos3_id, self.pos1_id]
            }
            reorder_salary_rates(groups_order)

            p1 = db.session.get(SalaryPosition, self.pos1_id)
            self.assertEqual(p1.group_name, "Cadreur")
            self.assertEqual(p1.display_order, 2)

    def test_reorder_salary_rates_backward_compatibility(self):
        """Vérifie que reorder_salary_rates accepte toujours les rate_id sans dupliquer ou incrémenter de 8 en 8."""
        with self.app.app_context():
            # Récupérer les rate_ids pour pos1 et pos2
            rates_p1 = SalaryRate.query.filter_by(position_id=self.pos1_id).all()
            rates_p2 = SalaryRate.query.filter_by(position_id=self.pos2_id).all()
            all_rate_ids = [r.id for r in rates_p1] + [r.id for r in rates_p2]

            groups_order = {
                "Pilote": all_rate_ids
            }
            reorder_salary_rates(groups_order)

            p1 = db.session.get(SalaryPosition, self.pos1_id)
            p2 = db.session.get(SalaryPosition, self.pos2_id)

            # Doit attribuer 0 et 1 (et NON 0 et 3 suite aux 3 taux par position)
            self.assertEqual(p1.display_order, 0)
            self.assertEqual(p2.display_order, 1)

    def test_normalize_salary_positions_order(self):
        """Vérifie que normalize_salary_positions_order réindexe de 0 à N."""
        with self.app.app_context():
            count = normalize_salary_positions_order()
            self.assertEqual(count, 3)

            positions = SalaryPosition.query.order_by(SalaryPosition.display_order.asc()).all()
            self.assertEqual([p.display_order for p in positions], [0, 1, 2])

    def test_list_salary_rates_grouped_ordered_strictly(self):
        """Vérifie que list_salary_rates_grouped respecte strictement display_order."""
        with self.app.app_context():
            # Pilote B (0), Cadreur A (1), Pilote A (2)
            p2 = db.session.get(SalaryPosition, self.pos2_id)
            p2.display_order = 0
            p3 = db.session.get(SalaryPosition, self.pos3_id)
            p3.display_order = 1
            p1 = db.session.get(SalaryPosition, self.pos1_id)
            p1.display_order = 2
            db.session.commit()

            grouped = list_salary_rates_grouped()
            group_keys = list(grouped.keys())

            # Pilote apparaît en premier car son premier élément a display_order=0, Cadreur en second
            self.assertEqual(group_keys, ["Pilote", "Cadreur"])

            # Dans Pilote, Pilote B (0) doit être avant Pilote A (2)
            pilote_positions = [r["position"] for r in grouped["Pilote"] if r["annexe"] == "Annexe 1"]
            self.assertEqual(pilote_positions, ["Pilote B", "Pilote A"])


if __name__ == "__main__":
    unittest.main()

