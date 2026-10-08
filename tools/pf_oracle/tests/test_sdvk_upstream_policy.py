"""SDVK-003 selective-upstream import and policy regression checks."""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[3]
CRUSADER = ROOT / "wadsrc/static/zscript/actors/strife/crusader.zs"
EVIDENCE = ROOT / "docs/shadedoomvk/evidence/sdvk003-upstream-tree-differential.json"


def function_body(source, name):
    marker = f"\tvoid {name} ()"
    start = source.index(marker)
    next_start = source.find("\n\tvoid ", start + len(marker))
    return source[start:] if next_start < 0 else source[start:next_start]


class SdvkUpstreamPolicyTests(unittest.TestCase):
    def test_crusader_sweeps_guard_target_before_mutation_and_spawn(self):
        source = CRUSADER.read_text(encoding="utf-8")
        for name in ("A_CrusaderSweepLeft", "A_CrusaderSweepRight"):
            body = function_body(source, name)
            guard = body.index("if (target == null)")
            early_return = body.index("return;", guard)
            angle = body.index("angle ", early_return)
            spawn = body.index("SpawnMissileZAimed", angle)
            self.assertLess(guard, early_return)
            self.assertLess(early_return, angle)
            self.assertLess(angle, spawn)
            self.assertIn("if (misl != null)", body)
            self.assertIn("misl.Vel.Z += 1;", body)

    def test_pinned_tree_receipt_is_complete_and_exact(self):
        data = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(data["schema"], "sdvk-003-upstream-tree-differential/v1")
        self.assertTrue(data["method"]["all_trees_untruncated"])
        refs = {item["name"]: item for item in data["refs"]}
        self.assertEqual(refs["vkdoom"]["commit"], "09634479ab5bf9adf691074fffe85a006a398cd0")
        self.assertEqual(refs["uzdoom"]["commit"], "809e46c25fe2a2f89430de3fbac89626100df384")
        self.assertEqual(refs["gzdoom"]["commit"], "c26ce2e6ca2a0c770f140cb25dde0d30073ca8f7")
        self.assertEqual(refs["shadedoom_master"]["commit"], "1ecc3cf73aa2266a1e741f09078b7d089ba8bf89")
        self.assertEqual(data["deltas_from_vkd_baseline"]["uzdoom"]["counts"]["modified"], 1530)
        self.assertEqual(data["deltas_from_vkd_baseline"]["gzdoom"]["counts"]["modified"], 697)
        self.assertGreaterEqual(data["ownership_overlap"]["uzdoom"]["domains"]["renderer"], 50)
        self.assertGreaterEqual(data["ownership_overlap"]["gzdoom"]["domains"]["renderer"], 40)

    def test_renderer_supersession_fails_closed(self):
        data = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        disposition = data["pf_disposition"]
        self.assertEqual(disposition["confirmed_upstream_supersessions"], [])
        self.assertFalse(disposition["physical_gpu_required_for_this_issue"])
        for path in (
            "src/common/rendering/vulkan/vk_lightmapper.cpp",
            "src/common/rendering/vulkan/vk_lightprober.cpp",
            "src/common/rendering/vulkan/descriptorsets/vk_descriptorset.cpp",
        ):
            row = data["key_capability_paths"][path]
            self.assertIsNotNone(row["shadedoom_master"])
            self.assertIsNone(row["uzdoom"])
            self.assertIsNone(row["gzdoom"])


if __name__ == "__main__":
    unittest.main()
