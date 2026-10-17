"""SDVK-158 retained multi-page lightmap transition oracle controls."""
from __future__ import annotations

import hashlib
import struct
import unittest
import zlib

from tools.renderer_oracle import prepare, sdvk158_lightmap_transition as target
from tools.renderer_oracle.common import EvidenceError


def native_recipe():
    return {
        "generator": "lightmap_transition", "map": target.MAP,
        "recommended_warmup_frames": target.WARMUP,
        "lightmap_transition_schedule": target.SCHEDULE,
        "settings": {"gl_levelmesh": True, "lm_dynlights": False},
    }


def resource(frame: int, *, epoch: int = 3, updates: int = 0, clean: bool = True,
             pages=(3, 3), retained: int = 2, invalid: int = 0):
    dirty = 0 if clean else 3
    state = {
        "available": True, "map": target.MAP, "texture_size": 1024,
        "texture_count": len(pages), "vulkan_page_count": len(pages),
        "used_tiles": sum(pages), "retained_tiles_loaded": retained,
        "frame_tile_updates": updates, "live_tiles": sum(pages),
        "valid_live_tiles": sum(pages) - invalid, "invalid_live_tiles": invalid,
        "initial_dirty": dirty, "geometry_dirty": 0, "light_dirty": 0,
        "all_clean": clean, "page_count_match": True,
        "sampling_page_bounds_ok": invalid == 0, "page_live_tiles": list(pages),
        "scope": "fixture",
    }
    return {"kind": "resource", "frame": frame, "data": {
        "lightmap_epoch": epoch, "lightmap_state": state,
    }}


def good_raw():
    rows = []
    for frame in range(1, target.FRAMES + 1):
        if frame <= 24:
            rows.append(resource(frame, epoch=3, clean=True))
        elif frame <= 56:
            rows.append(resource(frame, epoch=3, updates=1 if frame == 25 else 0,
                                 clean=frame != 25))
        elif frame <= 88:
            rows.append(resource(frame, epoch=4, updates=1 if frame == 57 else 0,
                                 clean=frame != 57))
        else:
            rows.append(resource(frame, epoch=4, updates=1 if frame == 89 else 0,
                                 clean=frame != 89))
    return {"observed_frames": target.FRAMES, "records": rows}


def stdout():
    return "\n".join(
        f"SDVK158_LIGHTMAP_INPUT phase={phase['phase']} after_main_views={phase['after_main_views']}"
        for phase in target.SCHEDULE
    )


class LightmapTransitionOracleTests(unittest.TestCase):
    def test_positive_repeated_multi_page_cycles(self):
        result = target.validate_transition_records(good_raw(), stdout(), native_recipe())
        self.assertEqual(result["status"], "PASS")
        self.assertGreaterEqual(result["minimum_pages"], 2)
        self.assertTrue(result["final_all_clean"])

    def test_single_page_or_invalid_live_receipt_rejects(self):
        for edit in ("single-page", "invalid"):
            raw = good_raw()
            row = raw["records"][40]["data"]["lightmap_state"]
            if edit == "single-page":
                row.update(texture_count=1, vulkan_page_count=1, page_live_tiles=[6])
            else:
                row.update(invalid_live_tiles=1, valid_live_tiles=5,
                           sampling_page_bounds_ok=False)
            with self.subTest(edit=edit), self.assertRaises(EvidenceError):
                target.validate_transition_records(raw, stdout(), native_recipe())

    def test_missing_completed_work_or_clean_convergence_rejects(self):
        raw = good_raw()
        for record in raw["records"]:
            if 25 <= record["frame"] <= 56:
                record["data"]["lightmap_state"]["frame_tile_updates"] = 0
        with self.assertRaisesRegex(EvidenceError, "real lightmap tile work"):
            target.validate_transition_records(raw, stdout(), native_recipe())

        raw = good_raw()
        raw["records"][55]["data"]["lightmap_state"].update(
            all_clean=False, initial_dirty=1)
        with self.assertRaisesRegex(EvidenceError, "dirty/completion"):
            target.validate_transition_records(raw, stdout(), native_recipe())

    def test_reload_requires_new_resource_epoch_and_retained_admission(self):
        raw = good_raw()
        for record in raw["records"]:
            record["data"]["lightmap_epoch"] = 3
        with self.assertRaisesRegex(EvidenceError, "resource epoch"):
            target.validate_transition_records(raw, stdout(), native_recipe())

        raw = good_raw()
        raw["records"][70]["data"]["lightmap_state"]["retained_tiles_loaded"] = 0
        with self.assertRaisesRegex(EvidenceError, "provenance"):
            target.validate_transition_records(raw, stdout(), native_recipe())

    def test_driver_markers_are_exact_and_outcome_independent(self):
        bad = stdout().replace("after_main_views=88", "after_main_views=89")
        with self.assertRaisesRegex(EvidenceError, "driver order"):
            target.validate_transition_records(good_raw(), bad, native_recipe())

    def test_authored_v5_lump_digest_is_exact_textmap_md5(self):
        textmap = b'namespace = "ZDoom";\nsector { heightfloor = 0; heightceiling = 160; }\n'
        payload, digest = prepare._sdvk158_lightmap_lump(textmap, width=513, height=513)
        raw = zlib.decompress(payload)
        version, count, pixels, source = struct.unpack("<III16s", raw[:28])
        self.assertEqual((version, count, pixels), (5, 2, 513 * 513 * 2))
        self.assertEqual(source, hashlib.md5(textmap).digest())
        self.assertEqual(digest, hashlib.md5(textmap).hexdigest())


if __name__ == "__main__":
    unittest.main()
