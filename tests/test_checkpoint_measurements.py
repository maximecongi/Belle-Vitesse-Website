import unittest
from unittest.mock import patch

from services.admin.checkpoint_measurements import (
    normalize_measurement_rules,
    validate_measurement,
    format_rule_decimal,
    snapshot_rules,
)
from services.admin.utils import compute_inspection_readiness


class CheckpointMeasurementRulesTests(unittest.TestCase):
    def setUp(self):
        self.rules = {"minimum": "0", "maximum": "100", "goal": "100", "tolerance": "5", "unit": "%"}

    def test_checkout_tolerance_is_clamped_to_range(self):
        self.assertEqual(validate_measurement("95", self.rules, True), ("95", None))
        self.assertEqual(validate_measurement("95.5", self.rules, True), ("95.5", None))
        self.assertEqual(validate_measurement("100", self.rules, True), ("100", None))
        self.assertIn("objectif", validate_measurement("94.9", self.rules, True)[1])
        self.assertIn("plage", validate_measurement("100.1", self.rules, True)[1])
        self.assertIn("une décimale", validate_measurement("95.55", self.rules, True)[1])

    def test_checkin_only_requires_value_inside_range(self):
        self.assertEqual(validate_measurement("42", self.rules, False), ("42", None))
        self.assertIn("plage", validate_measurement("-0.1", self.rules, False)[1])

    def test_rejects_non_finite_measurements(self):
        self.assertIn("finis", validate_measurement("NaN", self.rules, True)[1])
        self.assertIn("finis", validate_measurement("Infinity", self.rules, False)[1])

    def test_configuration_requires_ordered_bounds_and_nonnegative_tolerance(self):
        with self.assertRaisesRegex(ValueError, "objectif"):
            normalize_measurement_rules({"minimum": 0, "maximum": 100, "goal": 101, "tolerance": 5})
        with self.assertRaisesRegex(ValueError, "tolérance"):
            normalize_measurement_rules({"minimum": 0, "maximum": 100, "goal": 100, "tolerance": -1})
        with self.assertRaisesRegex(ValueError, "une décimale"):
            normalize_measurement_rules({"minimum": 0, "maximum": 100, "goal": 100, "tolerance": 0.25})

    def test_format_rule_decimal_limits_to_one_decimal(self):
        self.assertEqual(format_rule_decimal("100.000000"), "100.0")
        self.assertEqual(format_rule_decimal("0.000000"), "0.0")
        self.assertEqual(format_rule_decimal("5.000000"), "5.0")
        self.assertEqual(format_rule_decimal("95.5"), "95.5")
        self.assertEqual(format_rule_decimal(100), "100.0")
        self.assertIsNone(format_rule_decimal(None))
        self.assertIsNone(format_rule_decimal(""))

    def test_snapshot_rules_enforces_one_decimal(self):
        raw_config = {
            "minimum": "0.000000",
            "maximum": "100.000000",
            "goal": "100.000000",
            "tolerance": "5.000000",
            "unit": "%",
        }
        snap = snapshot_rules(raw_config)
        self.assertEqual(snap["minimum"], "0.0")
        self.assertEqual(snap["maximum"], "100.0")
        self.assertEqual(snap["goal"], "100.0")
        self.assertEqual(snap["tolerance"], "5.0")
        self.assertEqual(snap["unit"], "%")

    @patch("services.admin.utils.is_known_vehicle", return_value=True)
    @patch("services.admin.utils.get_checkpoints_for_vehicle")
    def test_readiness_uses_goal_for_checkout_and_range_for_checkin(self, checkpoints, _known_vehicle):
        checkpoints.return_value = [{"key": "battery", "label": "Charge", "type": "value", **self.rules}]
        checkout_ready, _ = compute_inspection_readiness(
            {"vehicle_id": "veh-1", "battery_level": "95"}, vehicle_id="veh-1", is_checkout=True
        )
        checkout_rejected, _ = compute_inspection_readiness(
            {"vehicle_id": "veh-1", "battery_level": "94"}, vehicle_id="veh-1", is_checkout=True
        )
        checkin_ready, _ = compute_inspection_readiness(
            {"vehicle_id": "veh-1", "battery_level": "40"}, vehicle_id="veh-1", is_checkout=False
        )
        self.assertTrue(checkout_ready)
        self.assertFalse(checkout_rejected)
        self.assertTrue(checkin_ready)


if __name__ == "__main__":
    unittest.main()
