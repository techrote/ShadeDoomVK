"""CPU controls for SDVK-158 clock-only comparison differences.

All envelopes, capture receipts and PNGs are synthetic. The production state
validator, transition validator, semantic comparator and RGB decoder run; only
the external capture-receipt service is replaced. No renderer is executed.
"""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_evidence import png
from test_validation import observation, recount, row
from tools.renderer_oracle import common, prepare, run, sdvk158_lightmap_transition as transition
from tools.renderer_oracle.tests.test_sdvk158_lightmap_transition import good_raw, levelmesh_draw, stdout

SCENE = "lightmap-retained-transition"
CLOCK = "ordinary_engine_clock_with_fixed_presented-view_input_schedule"


def recipe():
    return next(scene for scene in prepare.load_catalog()["scenes"] if scene["id"] == SCENE)


def envelope(*, start_tic=100, tics_per_view=1, fraction=0.125):
    """Same submitted/completed work by view; independently paced ordinary tics."""
    scene = recipe()
    native = scene["native"]
    result = observation()
    template = result["records"]
    result["records"] = []
    result.update(requested_frames=transition.FRAMES, observed_frames=transition.FRAMES,
                  warmup_frames=transition.WARMUP)
    for resource in (record for record in good_raw()["records"] if record["kind"] == "resource"):
        frame = resource["frame"]
        # Same-map reload starts a new simulation-time interval. Neither its
        # elapsed tics nor interpolation fraction schedules the view driver.
        tic = start_tic + (frame if frame <= 24 else frame - 24) * tics_per_view
        records = copy.deepcopy(template)
        for record in records:
            record["frame"] = frame
            value = record["data"]
            if "context" in value:
                value["context"].update(map=native["map"], gametic=tic, fraction=fraction,
                                        position=list(native["camera"]["position"]))
            if record["kind"] == "frame":
                value.update(map=native["map"], gametic=tic, settings=copy.deepcopy(native["settings"]))
                value["camera"].update(position=list(native["camera"]["position"]), fraction=fraction)
        context = copy.deepcopy(records[0]["data"]["context"])
        records.insert(2, row("pipeline", {
            "context": context, "key": {"shader": {"UseLevelMesh": 1}},
            "draw_count": 6, "basis": "SYNTHETIC emitted pipeline"}, frame=frame))
        for surface in ("side", "flat"):
            submitted = levelmesh_draw(frame, surface)
            submitted["data"]["context"] = copy.deepcopy(context)
            records.insert(-1, submitted)
        resource["count"] = 1
        resource["data"].update(
            descriptor_capacity=64, descriptor_current=1, descriptor_high_water=1,
            descriptor_dynamic_start=16, texture_epoch=1, probe_epoch=1, async_upload_epoch=1,
            levelmesh={"epoch": 10 if frame <= 24 else 11, "geometry": 1,
                       "surface": 1, "lights": 1, "query": 1})
        result["records"].extend(records + [resource])
    result["limits"]["retained_bytes"] = sum(
        len(common.canonical(record["data"])) + len(record["kind"]) for record in result["records"])
    return recount(result)


class LightmapRepeatabilityTests(unittest.TestCase):
    def compare(self, left, right, *, scene=SCENE, clock=CLOCK, changed_image=False):
        # Structural/lifecycle validation is real, including 48 exact frame
        # identities and the preregistered input markers and phase windows.
        for data in (left, right):
            run.validate.observation(data, required_kinds=["context", "pipeline", "resource"],
                                     expected_frames=transition.FRAMES, expected_map=transition.MAP)
            transition.validate_transition_records(data, stdout(), recipe()["native"])
        with tempfile.TemporaryDirectory(prefix="sdvk158-compare-") as directory:
            roots = [Path(directory) / name for name in ("left", "right")]
            for index, root in enumerate(roots):
                root.mkdir()
                rgb = bytes([1 if changed_image and index else 0]) + bytes(5)
                (root / "native.png").write_bytes(png(rgb))
                common.write_json(root / "run.json", {"synthetic": True})
                common.write_json(root / "request.json", {"cwd": str(root)})
            receipt = {
                "scene": scene, "mode": "state",
                "reproduction": {"clock": clock, "image_policy": {"metric": "exact-rgb8"}},
                "build": left["build"], "executable": {"sha256": "a" * 64}, "loaded_packages": [],
            }
            with mock.patch.object(run, "validate_run", side_effect=[
                (roots[0], receipt, left, {}), (roots[1], receipt, right, {}),
            ]):
                return run.compare_runs(*roots)

    def test_declared_fixed_view_scene_compares_equal_with_independent_tic_pacing(self):
        left = envelope()
        right = envelope(start_tic=300, tics_per_view=4, fraction=0.875)
        original = copy.deepcopy((left, right))
        result = self.compare(left, right)
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["state_equal"])
        self.assertTrue(result["image"]["passed"])
        self.assertIn("SDVK-158 fixed-presented-view schedule", result["normalization"])
        self.assertEqual((left, right), original)  # raw clock evidence stays intact

    def test_old_clock_selection_reproduces_only_tic_and_fraction_mismatch(self):
        left = envelope()
        right = envelope(start_tic=300, tics_per_view=4, fraction=0.875)
        # This is the old compare_runs predicate applied to the actual recipe,
        # then the unchanged production projection it selected.
        old_static = recipe()["native"]["clock"]["state"] == "static_after_initialization"
        self.assertFalse(old_static)
        x = run.validate.state_projection(left, static_scene=old_static)
        y = run.validate.state_projection(right, static_scene=old_static)
        differences = run.differences(x, y)
        self.assertTrue(differences)
        self.assertTrue(all(item["path"].endswith(("/gametic", "/fraction")) for item in differences))
        self.assertNotEqual(x, y)

    def test_projection_requires_exact_scene_and_declared_clock(self):
        left = envelope()
        right = envelope(start_tic=300, tics_per_view=4, fraction=0.875)
        for scene, clock in (("another-transition", CLOCK), (SCENE, "ordinary_engine_clock"),
                             (SCENE, CLOCK + "-unregistered")):
            with self.subTest(scene=scene, clock=clock):
                result = self.compare(left, right, scene=scene, clock=clock)
                self.assertEqual(result["status"], "FAIL")
                self.assertFalse(result["state_equal"])
                self.assertNotIn("SDVK-158 fixed-presented-view schedule", result["normalization"])
        self.assertEqual(self.compare(left, right, scene="ordinary-static-scene",
                                      clock="static_after_initialization")["status"], "PASS")

    def test_phase_resource_completion_and_geometry_differences_remain_exact(self):
        for mutation in ("lightmap-epoch", "levelmesh-epoch", "completion-count", "dirty-state",
                         "phase-view", "camera-position", "camera-angle", "camera-fov", "settings", "pipeline",
                         "levelmesh-first-index", "levelmesh-multiplicity"):
            left = envelope()
            right = envelope(start_tic=300, tics_per_view=4, fraction=0.875)
            resources = {record["frame"]: record["data"] for record in right["records"]
                         if record["kind"] == "resource"}
            if mutation == "lightmap-epoch":
                resources[25]["lightmap_epoch"] += 1
            elif mutation == "levelmesh-epoch":
                resources[25]["levelmesh"]["epoch"] += 1
            elif mutation == "completion-count":
                resources[9]["lightmap_state"].update(frame_tile_updates=2, frame_tile_completions=2)
            elif mutation == "dirty-state":
                resources[10]["lightmap_state"].update(light_dirty=1, all_clean=False)
            elif mutation == "phase-view":
                # Still completes in the admitted phase, but changes its exact
                # view association. The semantic comparator must reject this.
                resources[9]["lightmap_state"], resources[10]["lightmap_state"] = (
                    resources[10]["lightmap_state"], resources[9]["lightmap_state"])
            else:
                for record in right["records"]:
                    if record["frame"] != 12:
                        continue
                    value = record["data"]
                    if (mutation == "pipeline" and record["kind"] == "pipeline"
                            and "producer" not in value):
                        value["key"]["shader"]["UseLevelMesh"] = 0
                    if value.get("producer") == "levelmesh-indexed-range" and value.get("surface") == "side":
                        if mutation == "levelmesh-first-index":
                            value["first_index"] += 3
                        elif mutation == "levelmesh-multiplicity":
                            record["count"] += 1
                    if mutation == "camera-position" and "context" in value:
                        value["context"]["position"][0] += 1
                    if record["kind"] == "frame":
                        if mutation == "camera-position":
                            value["camera"]["position"][0] += 1
                        elif mutation == "camera-angle":
                            value["camera"]["angles"][0] += 1
                        elif mutation == "camera-fov":
                            value["camera"]["fov"] += 1
                        elif mutation == "settings":
                            value["settings"]["gl_levelmesh"] = False
            with self.subTest(mutation=mutation):
                result = self.compare(left, right)
                self.assertEqual(result["status"], "FAIL")
                self.assertFalse(result["state_equal"])
                self.assertTrue(result["image"]["passed"])

    def test_exact_rgb_difference_is_not_hidden_by_matching_semantic_state(self):
        result = self.compare(envelope(), envelope(start_tic=300, tics_per_view=4, fraction=0.875),
                              changed_image=True)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(result["state_equal"])
        self.assertFalse(result["image"]["passed"])
        self.assertEqual(result["image"]["changed_pixels"], 1)


if __name__ == "__main__":
    unittest.main()
