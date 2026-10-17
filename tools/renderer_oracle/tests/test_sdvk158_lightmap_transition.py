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


def resource(frame: int, *, epoch: int = 3, updates: int = 0, completions: int = 0,
             initial_dirty: int = 0, geometry_dirty: int = 0, light_dirty: int = 0,
             pages=(3, 3), retained: int = 2, invalid: int = 0):
    state = {
        "available": True, "map": target.MAP, "texture_size": 1024,
        "texture_count": len(pages), "vulkan_page_count": len(pages),
        "used_tiles": sum(pages), "retained_tiles_loaded": retained,
        "frame_tile_updates": updates, "frame_tile_completions": completions,
        "live_tiles": sum(pages),
        "valid_live_tiles": sum(pages) - invalid, "invalid_live_tiles": invalid,
        "initial_dirty": initial_dirty, "geometry_dirty": geometry_dirty, "light_dirty": light_dirty,
        "all_clean": initial_dirty == 0 and geometry_dirty == 0 and light_dirty == 0,
        "page_count_match": True,
        "sampling_page_bounds_ok": invalid == 0, "page_live_tiles": list(pages),
        "scope": "fixture",
    }
    return {"kind": "resource", "frame": frame, "data": {
        "lightmap_epoch": epoch, "lightmap_state": state,
    }}


def levelmesh_draw(frame: int, surface: str):
    return {"kind": "pipeline", "frame": frame, "count": 1, "data": {
        "producer": "levelmesh-indexed-range", "surface": surface,
        "indexed": True, "first_index": 0 if surface == "side" else 18, "draw_count": 6,
        "key": {"shader": {"UseLevelMesh": 1}},
        "context": {"available": True, "map": target.MAP, "type": "main", "root_type": "main",
                    "depth": 0, "parent_identity": 0},
    }}


def good_raw():
    rows = []
    for frame in range(1, target.FRAMES + 1):
        if frame <= 8:
            rows.append(resource(frame, epoch=3, light_dirty=2))
        elif frame <= 24:
            rows.append(resource(
                frame, epoch=3,
                updates=1 if frame == 9 else 0,
                completions=1 if frame == 9 else 0,
                initial_dirty=5 if frame == 9 else 0,
                light_dirty=5 if frame == 9 else 0))
        elif frame <= 40:
            rows.append(resource(
                frame, epoch=4,
                updates=1 if frame == 25 else 0,
                completions=1 if frame == 25 else 0,
                initial_dirty=3 if frame == 25 else 0,
                light_dirty=2))
        else:
            rows.append(resource(
                frame, epoch=4,
                updates=1 if frame == 41 else 0,
                completions=1 if frame == 41 else 0,
                initial_dirty=5 if frame == 41 else 0,
                light_dirty=5 if frame == 41 else 0))
    rows.extend(levelmesh_draw(frame, surface)
                for frame in range(1, target.FRAMES + 1) for surface in ("side", "flat"))
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
        self.assertEqual(result["levelmesh_draws"]["minimum_side_ranges_per_frame"], 1)
        self.assertEqual(result["levelmesh_draws"]["minimum_flat_ranges_per_frame"], 1)

    def test_each_frame_requires_actual_side_and_flat_submissions(self):
        for surface in ("side", "flat"):
            raw = good_raw()
            raw["records"] = [row for row in raw["records"]
                              if not (row["frame"] == 24 and row["data"].get("surface") == surface)]
            with self.subTest(surface=surface), self.assertRaisesRegex(EvidenceError, "no actual LevelMesh"):
                target.validate_transition_records(raw, stdout(), native_recipe())

    def test_immediate_empty_unbound_or_foreign_draws_cannot_cover_mesh(self):
        mutations = (
            lambda row: row.pop("producer"),
            lambda row: row.update(indexed=False),
            lambda row: row.update(draw_count=0),
            lambda row: row.update(first_index=-1),
            lambda row: row["key"]["shader"].update(UseLevelMesh=0),
            lambda row: row["context"].update(available=False),
            lambda row: row["context"].update(type="portal", depth=1, parent_identity=1),
            lambda row: row["context"].update(root_type="camera-texture"),
            lambda row: row["context"].update(map="OTHER"),
        )
        for mutation in mutations:
            raw = good_raw()
            mutation(next(row["data"] for row in raw["records"]
                          if row["frame"] == 41 and row["data"].get("surface") == "flat"))
            with self.subTest(mutation=mutation), self.assertRaises(EvidenceError):
                target.validate_transition_records(raw, stdout(), native_recipe())

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
            if record["kind"] == "resource" and 9 <= record["frame"] <= 24:
                record["data"]["lightmap_state"]["frame_tile_completions"] = 0
        with self.assertRaisesRegex(EvidenceError, "real lightmap tile work"):
            target.validate_transition_records(raw, stdout(), native_recipe())

        raw = good_raw()
        raw["records"][23]["data"]["lightmap_state"].update(
            all_clean=False, light_dirty=1)
        with self.assertRaisesRegex(EvidenceError, "dirty/completion"):
            target.validate_transition_records(raw, stdout(), native_recipe())

    def test_reload_requires_new_resource_epoch_and_retained_admission(self):
        raw = good_raw()
        for record in raw["records"]:
            if record["kind"] == "resource":
                record["data"]["lightmap_epoch"] = 3
        with self.assertRaisesRegex(EvidenceError, "resource epoch"):
            target.validate_transition_records(raw, stdout(), native_recipe())

        raw = good_raw()
        raw["records"][30]["data"]["lightmap_state"]["retained_tiles_loaded"] = 0
        with self.assertRaisesRegex(EvidenceError, "provenance"):
            target.validate_transition_records(raw, stdout(), native_recipe())

    def test_driver_markers_are_exact_and_outcome_independent(self):
        bad = stdout().replace("after_main_views=56", "after_main_views=57")
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
