from tests.base import BaseTestCase
from models import Head, Vehicle, db
from services.admin.equipment_colors import (
    COLOR_KEYS,
    DEFAULT_COLOR,
    EquipmentColorError,
    ensure_equipment_colors,
    set_equipment_color,
)


class EquipmentColorsTest(BaseTestCase):

    def setUp(self):
        super().setUp()
        db.session.add_all([
            Vehicle(id="rec_erider", fields={"name": "eRider"}, display_order=0),
            Vehicle(id="rec_ecar", fields={"name": "eCar"}, display_order=1),
            Head(id="rec_head", fields={"name": "Titan LT"}, display_order=0),
        ])
        db.session.commit()

    def _login(self, role):
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_user_role"] = role

    def test_missing_colors_assigned_and_stable(self):
        colors = ensure_equipment_colors()
        self.assertEqual(colors[("vehicle", "rec_erider")], COLOR_KEYS[0])
        self.assertEqual(colors[("vehicle", "rec_ecar")], COLOR_KEYS[1])
        self.assertEqual(colors[("head", "rec_head")], COLOR_KEYS[2])
        # Stable : un second appel ne change rien
        self.assertEqual(ensure_equipment_colors(), colors)
        self.assertEqual(db.session.get(Vehicle, "rec_ecar").color, COLOR_KEYS[1])

    def test_new_equipment_gets_first_free_color(self):
        ensure_equipment_colors()  # erider = 1re, ecar = 2e, tête = 3e couleur
        set_equipment_color("vehicle", "rec_ecar", COLOR_KEYS[5])  # libère la 2e couleur
        db.session.add(Vehicle(id="rec_new", fields={"name": "Nouveau"}, display_order=5))
        db.session.commit()
        colors = ensure_equipment_colors()
        self.assertEqual(colors[("vehicle", "rec_new")], COLOR_KEYS[1])

    def test_color_cannot_be_given_to_another_equipment(self):
        ensure_equipment_colors()
        with self.assertRaises(EquipmentColorError) as ctx:
            set_equipment_color("head", "rec_head", COLOR_KEYS[0])  # portée par eRider
        self.assertIn("eRider", str(ctx.exception))
        self.assertEqual(db.session.get(Head, "rec_head").color, COLOR_KEYS[2])
        # Réenregistrer sa propre couleur reste possible
        self.assertEqual(set_equipment_color("vehicle", "rec_erider", COLOR_KEYS[0]), COLOR_KEYS[0])

    def test_duplicates_resolved_in_catalog_order(self):
        db.session.get(Vehicle, "rec_erider").color = "red"
        db.session.get(Vehicle, "rec_ecar").color = "red"
        db.session.get(Head, "rec_head").color = "red"
        db.session.commit()
        colors = ensure_equipment_colors()
        self.assertEqual(colors[("vehicle", "rec_erider")], "red")
        self.assertEqual(len(set(colors.values())), 3)
        self.assertNotIn("red", (colors[("vehicle", "rec_ecar")], colors[("head", "rec_head")]))

    def test_palette_exhausted_leaves_equipment_without_color(self):
        for i in range(len(COLOR_KEYS)):
            db.session.add(Vehicle(id=f"rec_extra_{i}", fields={"name": f"Extra {i}"}, display_order=10 + i))
        db.session.commit()
        colors = ensure_equipment_colors()
        assigned = [c for c in colors.values() if c != DEFAULT_COLOR]
        self.assertEqual(len(assigned), len(COLOR_KEYS))
        self.assertEqual(len(set(assigned)), len(COLOR_KEYS))
        self.assertEqual(list(colors.values()).count(DEFAULT_COLOR), 3)

    def test_set_color_validation(self):
        self.assertEqual(set_equipment_color("head", "rec_head", "PINK"), "pink")
        self.assertEqual(db.session.get(Head, "rec_head").color, "pink")
        with self.assertRaises(EquipmentColorError):
            set_equipment_color("vehicle", "rec_erider", "teal")
        with self.assertRaises(EquipmentColorError):
            set_equipment_color("drone", "rec_erider", "pink")
        with self.assertRaises(LookupError):
            set_equipment_color("vehicle", "rec_inconnu", "pink")

    def test_route_permissions(self):
        self._login("commercial")
        resp = self.client.post("/admin/fleet/equipment-color",
                                json={"equipment_type": "vehicle", "equipment_id": "rec_erider", "color": "orange"})
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        self.assertEqual(resp.get_json()["label"], "Orange")
        self.assertEqual(db.session.get(Vehicle, "rec_erider").color, "orange")

        resp = self.client.post("/admin/fleet/equipment-color",
                                json={"equipment_type": "vehicle", "equipment_id": "rec_erider", "color": "nope"})
        self.assertEqual(resp.status_code, 400)

        self._login("technicien")
        resp = self.client.post("/admin/fleet/equipment-color",
                                json={"equipment_type": "vehicle", "equipment_id": "rec_erider", "color": "red"})
        self.assertNotEqual(resp.status_code, 200)
        self.assertEqual(db.session.get(Vehicle, "rec_erider").color, "orange")

    def test_fleet_page_shows_pickers_and_heads(self):
        self._login("commercial")
        resp = self.client.get("/admin/fleet")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("Têtes gyrostabilisées", html)
        self.assertIn('data-equipment-type="head"', html)
        self.assertIn('data-eq-color-toggle', html)

    def test_unset_color_frees_it_and_is_kept(self):
        ensure_equipment_colors()
        freed = COLOR_KEYS[0]  # portée par eRider
        self.assertEqual(set_equipment_color("vehicle", "rec_erider", DEFAULT_COLOR), DEFAULT_COLOR)
        # La couleur libérée peut être reprise par un autre matériel
        self.assertEqual(set_equipment_color("head", "rec_head", freed), freed)
        # « Sans couleur » volontaire : jamais réattribué automatiquement
        colors = ensure_equipment_colors()
        self.assertEqual(colors[("vehicle", "rec_erider")], DEFAULT_COLOR)
        self.assertEqual(db.session.get(Vehicle, "rec_erider").color, DEFAULT_COLOR)

    def test_route_unset_color(self):
        ensure_equipment_colors()
        self._login("commercial")
        resp = self.client.post("/admin/fleet/equipment-color",
                                json={"equipment_type": "vehicle", "equipment_id": "rec_erider", "color": "none"})
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        self.assertEqual(resp.get_json()["label"], "Sans couleur")
