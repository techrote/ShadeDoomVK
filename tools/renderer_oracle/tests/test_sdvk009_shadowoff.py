"""Prepared quality equivalence only; these controls never render."""
import unittest

from tools.renderer_oracle import prepare, sdvk009_shadowoff as scaling


class ShadowoffRecipeTests(unittest.TestCase):
    def test_sparse_variants_preserve_actual_scene_payloads_and_all_other_quality(self):
        catalog = prepare.load_catalog()
        prepare.validate_catalog(catalog)
        scenes = {scene["id"]: scene for scene in catalog["scenes"]}
        for original_id in ("lights-one", "lights-many"):
            original, variant = scenes[original_id], scenes[original_id + "-shadow-off"]
            with self.subTest(scene=original_id):
                self.assertEqual(original["native"]["settings"]["gl_light_shadows"], 2)
                self.assertEqual(variant, scaling.shadowoff_variant(original))
                self.assertNotIn("shadow", variant["required_state_channels"])
                before, after = prepare.scene_assets(original), prepare.scene_assets(variant)
                self.assertEqual(set(before[1]), set(after[1]))
                changed = {name for name in before[1] if before[1][name] != after[1][name]}
                self.assertEqual(changed, {"MAPINFO"})
                self.assertEqual(before[1]["MAPINFO"].replace(
                    ('"SDVK ' + original_id + '"').encode(), ('"SDVK ' + variant["id"] + '"').encode()), after[1]["MAPINFO"])
                for name in before[1]:
                    if name != "MAPINFO": self.assertEqual(before[1][name], after[1][name], name)
                self.assertEqual(prepare.configuration(original).replace(b"gl_light_shadows=2", b"gl_light_shadows=0"),
                                 prepare.configuration(variant))
                self.assertEqual(prepare.capture_script(original).replace(b"gl_light_shadows 2", b"gl_light_shadows 0"),
                                 prepare.capture_script(variant))
        self.assertEqual(scenes["shadow-boundary"]["native"]["authored_light_count"], 1025)
        self.assertEqual(scenes["shadow-boundary"]["native"]["settings"]["gl_light_shadows"], 2)

    def test_fixed_orders_are_twelve_independent_timings_after_eight_state_captures(self):
        rows = scaling.capture_specs({scene: "a" * 64 for scene in scaling.SCENES})
        self.assertEqual(len({row["name"] for row in rows}), 20)
        self.assertEqual([row["scene"] for row in rows[8:]], [scene for order in scaling.TIMING_ORDERS for scene in order])
        self.assertTrue(all(row["warmup"] == 120 and row["extent"] == [1904, 1001] and row["deadline_seconds"] == 180 for row in rows))
        self.assertTrue(all(row["frames"] == 120 and row["compare_with"] is None for row in rows[8:]))
        self.assertTrue(all(row["mode"] == "state" and row["frames"] == 1 for row in rows[:8]))


if __name__ == "__main__":
    unittest.main()
