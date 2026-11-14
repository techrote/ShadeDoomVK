"""CPU-only positive and falsifying controls for startup lifetime trace admission."""
from __future__ import annotations

import copy
from pathlib import Path
import unittest

from tools.renderer_oracle import sdvk161_texture_epoch_diagnostic as diag
from tools.renderer_oracle.common import EvidenceError


def event(index, action, before, after, hw, pp, owner=-1, seen=0):
    return {"ordinal": index, "event": action, "owner_kind":
            ("hardware" if action.startswith("hw-") else
             "postprocess" if action.startswith("pp-") else "manager"),
            "manager_id": 1, "owner_id": owner,
            "before": before, "after": after,
            "hardware_count": hw, "pp_count": pp,
            "presented_view_ordinal": seen,
            "stack": ["vkdoom(+0x100)", "vkdoom(+0x200)"],
            "pc_offsets": [{"module": "vkdoom", "offset": 256},
                           {"module": "vkdoom", "offset": 512}]}


def specimen():
    events = [
        event(0, "manager-create", 1, 1, 0, 0),
        event(1, "hw-add", 1, 1, 1, 0, owner=1),
        event(2, "hw-remove", 1, 2, 1, 0, owner=1),
        event(3, "manager-deinit", 2, 3, 0, 0),
    ]
    trace = {"schema": "sdvk161-texture-epoch-startup/v1",
             "status": "NONQUALIFYING_DIAGNOSTIC",
             "default_off": True, "snapshot_frozen": True,
             "capacity": 256, "recorded": len(events), "overflow": False,
             "first_retained_manager_id": 1,
             "first_retained_texture_epoch": 3,
             "events": events}
    raw = {"records": [{"frame": 1, "kind": "resource",
                        "data": {"texture_epoch": 3}}]}
    return trace, raw


class EpochTraceAdmission(unittest.TestCase):
    def test_exact_pre_frame_chain(self):
        trace, raw = specimen()
        result = diag.validate_trace(trace, raw)
        self.assertEqual(result["first_retained_texture_epoch"], 3)
        self.assertEqual(result["increments"], 2)

    def test_missing_retirement_event(self):
        trace, raw = specimen()
        del trace["events"][2]
        trace["recorded"] -= 1
        trace["events"][2]["ordinal"] = 2
        with self.assertRaisesRegex(EvidenceError, "Epoch chain is broken"):
            diag.validate_trace(trace, raw)

    def test_stale_resource_owner(self):
        trace, raw = specimen()
        trace["events"][2]["owner_id"] = 77
        with self.assertRaisesRegex(EvidenceError, "retirement is detached"):
            diag.validate_trace(trace, raw)

    def test_missing_epoch_increment(self):
        trace, raw = specimen()
        trace["events"][2]["after"] = 1
        with self.assertRaisesRegex(EvidenceError, "failed to advance"):
            diag.validate_trace(trace, raw)

    def test_unlogged_epoch_increment(self):
        trace, raw = specimen()
        trace["events"][3]["before"] = 3
        with self.assertRaisesRegex(EvidenceError, "Epoch chain is broken"):
            diag.validate_trace(trace, raw)

    def test_wrong_manager_counts(self):
        trace, raw = specimen()
        trace["events"][2]["hardware_count"] = 0
        with self.assertRaisesRegex(EvidenceError, "manager counts"):
            diag.validate_trace(trace, raw)

    def test_inconsistent_first_retained_native_state(self):
        trace, raw = specimen()
        raw["records"][0]["data"]["texture_epoch"] = 4
        with self.assertRaisesRegex(EvidenceError, "Original retained native texture epoch"):
            diag.validate_trace(trace, raw)

    def test_overflow_fail_closed(self):
        trace, raw = specimen()
        trace["overflow"] = True
        with self.assertRaisesRegex(EvidenceError, "overflowed"):
            diag.validate_trace(trace, raw)

    def test_missing_caller_stack_fail_closed(self):
        trace, raw = specimen()
        trace["events"][2]["pc_offsets"] = []
        with self.assertRaisesRegex(EvidenceError, "callstack"):
            diag.validate_trace(trace, raw)

    def test_extra_real_retirement_detectable(self):
        a, _ = specimen()
        b = copy.deepcopy(a)
        b["events"].insert(2, event(2, "pp-add", 1, 1, 1, 1, owner=2))
        b["events"].insert(3, event(3, "pp-remove", 1, 2, 1, 1, owner=2))
        b["events"][4] = event(4, "hw-remove", 2, 3, 1, 0, owner=1)
        b["events"][5] = event(5, "manager-deinit", 3, 4, 0, 0)
        b["recorded"] = len(b["events"])
        b["first_retained_texture_epoch"] = 4
        raw = {"records": [{"frame": 1, "kind": "resource",
                            "data": {"texture_epoch": 4}}]}
        diag.validate_trace(b, raw)
        differences = diag.delta(a, b)
        self.assertGreaterEqual(len(differences), 1)
        self.assertTrue(any(any(e["event"] == "pp-remove" for e in chunk["right"])
                            for chunk in differences))

    def test_all_producer_sites_are_instrumented(self):
        root = Path(__file__).resolve().parents[3]
        c = (root / "src/common/rendering/vulkan/textures/vk_texture.cpp").read_text()
        self.assertEqual(c.count("TextureEpoch.Invalidate();"), 3)
        for function, category in (
                ("void VkTextureManager::RemoveTexture(", '"hw-remove"'),
                ("void VkTextureManager::RemovePPTexture(", '"pp-remove"'),
                ("void VkTextureManager::Deinit(", '"manager-deinit"')):
            region = c[c.index(function):]
            region = region[:region.index("\n}\n") + 3]
            self.assertIn("TextureEpoch.Invalidate();", region)
            self.assertIn(category, region)


if __name__ == "__main__":
    unittest.main()
