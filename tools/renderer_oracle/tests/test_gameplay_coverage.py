"""CPU replay of the retained FAILED_STOP capture; never a new native result."""
import copy
import gzip
import hashlib
import json
from pathlib import Path
import unittest

from tools.renderer_oracle import gameplay_smoke as smoke, prepare, run, validate


class GameplayCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = Path(__file__).with_name("fixtures") / "gameplay-motion-4be.renderer.json.gz"
        payload = gzip.decompress(fixture.read_bytes())
        assert hashlib.sha256(payload).hexdigest() == "c0ea2fa0cceb3c4a51d4ac4b110b4c9649afeb6eaf900d647265428a88148468"
        cls.captured = json.loads(payload)
        cls.scene = next(scene for scene in prepare.load_catalog()["scenes"] if scene["id"] == smoke.SCENE)
        cls.required = [run.CHANNEL_KIND.get(name, name) for name in cls.scene["required_state_channels"]]

    def admission(self, raw, **kwargs):
        return validate.observation(raw, expected_map=run.observation_map(self.scene),
            expected_frames=smoke.FRAMES, expected_extent=[640, 480],
            required_kinds=kwargs.pop("required_kinds", self.required),
            gameplay_recipe=kwargs.pop("gameplay_recipe", self.scene), **kwargs)

    def test_real_capture_exposes_old_full_detail_rule_and_passes_exact_scoped_coverage(self):
        raw = self.captured
        # This is the actual failed admission, not a native rerun or changed receipt.
        with self.assertRaisesRegex(ValueError, "Frame 1 is missing a required observation channel"):
            self.admission(raw, gameplay_recipe=None)
        result = self.admission(raw)
        self.assertEqual((result["status"], result["frames"], result["records"]), ("PASS", 128, 8105))
        self.assertFalse(result["native_acceptance_awarded"])
        self.assertEqual(raw["limits"]["retained_bytes"], 12252105)
        self.assertEqual(smoke.observation_detail_frames(raw, self.scene), {8, 24, 40, 41, 56, 80, 81, 96, 120})
        run._scene_assertions(raw, self.scene)
        played = smoke.validate_records(raw, self.scene["native"])
        self.assertTrue(played["movement"] and played["turn"] and played["ammo_depletion_both_maps"])
        self.assertEqual(played["fresh_levelmesh_owners"], [3, 5, 7])
        self.assertTrue(played["muzzle_light_reset"])

    def test_missing_detail_or_any_unsampled_critical_channel_still_fails(self):
        for kind, frame in [(kind, 41) for kind in sorted(smoke.DETAIL_KINDS)] + [
                (kind, 1) for kind in ("frame", "gameplay", "resource", "viewmodel", "context")]:
            raw = copy.deepcopy(self.captured)
            raw["records"] = [row for row in raw["records"] if (row["kind"], row["frame"]) != (kind, frame)]
            raw["limits"]["retained_records"] = len(raw["records"])
            # Only test rows change; the retained capture and its original pins do not.
            # An omitted caller requirement cannot turn off the four critical channels.
            required = [] if kind in ("frame", "gameplay", "resource", "viewmodel") else self.required
            with self.subTest(kind=kind, frame=frame), self.assertRaises(ValueError):
                self.admission(raw, required_kinds=required)

    def test_arbitrary_flag_or_later_muzzle_cannot_authorize_coverage_and_other_recipes_are_denied(self):
        for defect in ("flag", "first-muzzle", "duplicate-player", "extra-detail", "wrong-recipe", "wrong-mode"):
            raw = copy.deepcopy(self.captured)
            scene = copy.deepcopy(self.scene)
            if defect in ("flag", "first-muzzle"):
                player = next(row["data"] for row in raw["records"] if row["kind"] == "gameplay" and row["frame"] == 41)
                player["detail_selected" if defect == "flag" else "extra_light"] = False if defect == "flag" else 0
            elif defect == "duplicate-player":
                raw["records"].append(copy.deepcopy(next(row for row in raw["records"] if row["kind"] == "gameplay")))
            elif defect == "extra-detail":
                extra = copy.deepcopy(next(row for row in raw["records"] if row["kind"] == "material"))
                extra["frame"] = 42
                raw["records"].append(extra)
            elif defect == "wrong-recipe":
                scene["id"] = "viewmodel-pbr"
            elif defect == "wrong-mode":
                scene["native"]["gameplay_smoke"]["frames"] = 127
            raw["limits"]["retained_records"] = len(raw["records"])
            with self.subTest(defect=defect), self.assertRaises(ValueError):
                self.admission(raw, gameplay_recipe=scene)


if __name__ == "__main__":
    unittest.main()
