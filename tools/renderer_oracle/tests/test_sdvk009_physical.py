"""Host-only controls for the preregistered SDVK-009 physical campaign driver."""
from argparse import Namespace
from pathlib import Path
import tempfile
import unittest
import copy
import json
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.renderer_oracle import sdvk009_physical as physical
from tools.renderer_oracle.common import EvidenceError


class PhysicalCampaignControls(unittest.TestCase):
    @staticmethod
    def _result(device_type=2):
        return {"status": "COLLECTED", "build": {"working_tree": "clean", "commit": physical.EXPECTED_RENDERER_COMMIT,
                "device": "physical-test", "vulkan": {"available": True, "device_type": device_type}},
                "executable": {"sha256": "a" * 64}, "reproduction": {"iwad_sha256": "b" * 64},
                "loaded_packages": [{"path": "runtime/vkdoom.pk3", "sha256": "c" * 64, "bytes": 12, "lumps": 1}]}

    def _run(self, root, *, device_type=2, compare_status="PASS", mutate=None):
        args = Namespace(exe=Path("engine"), iwad=Path("iwad"), out=root / "campaign", timeout=600, execute=True)
        captures = []

        def capture(ns):
            ns.out.mkdir(parents=True, exist_ok=False)
            captures.append(ns)
            result = self._result(device_type)
            if mutate:
                mutate(result, len(captures))
            return result

        summary = {"schema": "sdvk-renderer-baseline/v1", "status": "DESCRIPTIVE", "runs": []}
        with patch.object(physical.prepare, "prepare", return_value={"status": "prepared_only"}), \
             patch.object(physical, "_pin_runtime", return_value={"synthetic": True}), \
             patch.object(physical, "_timing_integrity", return_value={"status": "COMPLETE_GROUPS_SCOPE_UNQUALIFIED"}), \
             patch.object(physical.run, "capture", side_effect=capture), \
             patch.object(physical.run, "compare_runs", return_value={"status": compare_status}), \
             patch.object(physical.run, "summarize_runs", return_value=summary), \
             patch.object(physical.run, "comparable_build", side_effect=lambda value: value):
            result = physical.campaign(args)
        return captures, result

    def test_exact_process_matrix_and_extent_policy(self):
        with tempfile.TemporaryDirectory(prefix="sdvk009-physical-unit-") as directory:
            captures, result = self._run(Path(directory))
        self.assertEqual(result["status"], "COLLECTED_PENDING_SDVK009_DECISION")
        self.assertTrue(result["physical_gpu_evidence_collected"])
        self.assertFalse(result["physical_gpu_qualified"])
        self.assertFalse(result["performance_accepted"])
        self.assertEqual(len(captures), 41)
        reference = captures[:20]
        highres = captures[20:26]
        timing = captures[26:]
        self.assertTrue(all(call.mode == "state" and call.extent is None and call.frames == 1 for call in reference))
        self.assertTrue(all(call.mode == "state" and call.extent == physical.ARCHITECTURE_EXTENT for call in highres))
        self.assertTrue(all(call.mode == "timing" and call.extent == physical.ARCHITECTURE_EXTENT
                            and call.frames == 120 and call.warmup == 120 and call.gpu for call in timing))
        self.assertEqual([call.scene for call in timing], [scene for order in physical.TIMING_ORDER for scene in order])

    def test_cpu_device_is_rejected_before_timing(self):
        with tempfile.TemporaryDirectory(prefix="sdvk009-physical-unit-") as directory:
            args = Namespace(exe=Path("engine"), iwad=Path("iwad"), out=Path(directory) / "campaign", timeout=600, execute=True)
            def capture(ns):
                ns.out.mkdir(parents=True, exist_ok=False)
                return {"status": "COLLECTED", "build": {"vulkan": {"available": True, "device_type": 4}}}
            with patch.object(physical.prepare, "prepare", return_value={"status": "prepared_only"}), \
                 patch.object(physical, "_pin_runtime", return_value={"synthetic": True}), \
                 patch.object(physical.run, "capture", side_effect=capture):
                with self.assertRaisesRegex(EvidenceError, "physical campaign failed"):
                    physical.campaign(args)
            self.assertTrue((args.out / "sdvk009-physical-campaign.json").is_file())

    def test_comparison_failure_stops_before_timing(self):
        with tempfile.TemporaryDirectory(prefix="sdvk009-physical-unit-") as directory:
            root = Path(directory)
            args = Namespace(exe=Path("engine"), iwad=Path("iwad"), out=root / "campaign", timeout=600, execute=True)
            calls = []
            def capture(ns):
                ns.out.mkdir(parents=True, exist_ok=False)
                calls.append(ns)
                return self._result()
            with patch.object(physical.prepare, "prepare", return_value={"status": "prepared_only"}), \
                 patch.object(physical, "_pin_runtime", return_value={"synthetic": True}), \
                 patch.object(physical.run, "capture", side_effect=capture), \
                 patch.object(physical.run, "compare_runs", return_value={"status": "FAIL"}), \
                 patch.object(physical.run, "comparable_build", side_effect=lambda value: value):
                with self.assertRaisesRegex(EvidenceError, "physical campaign failed"):
                    physical.campaign(args)
            self.assertEqual(len(calls), 2)
            self.assertTrue(all(call.mode == "state" for call in calls))
            self.assertTrue((args.out / "reference-compositing-comparison.json").is_file())

    def test_cross_scene_and_reference_to_timing_byte_changes_stop_and_retain_failure(self):
        # A different executable with the same embedded Git identity, a changed
        # engine PK3 or another IWAD must not slip through per-scene summaries.
        for boundary in (3, 27):
            for field in ("exe", "package", "iwad"):
                with self.subTest(boundary=boundary, field=field), tempfile.TemporaryDirectory() as directory:
                    def mutate(result, ordinal):
                        if ordinal == boundary:
                            if field == "exe":
                                result["executable"]["sha256"] = "d" * 64
                            elif field == "package":
                                result["loaded_packages"][0]["sha256"] = "d" * 64
                            else:
                                result["reproduction"]["iwad_sha256"] = "d" * 64
                    root = Path(directory)
                    with self.assertRaisesRegex(EvidenceError, "physical campaign failed"):
                        self._run(root, mutate=mutate)
                    receipt = json.loads((root / "campaign/sdvk009-physical-campaign.json").read_text())
                    self.assertEqual(receipt["status"], "FAIL")
                    self.assertIn("bytes changed", receipt["error"])
                    self.assertFalse(receipt["physical_gpu_evidence_collected"])
                    captures = [s for s in receipt["steps"] if s["name"].startswith(("reference-", "highres-", "timing-r"))
                                and not s["name"].endswith("compare")]
                    self.assertEqual(len(captures), boundary - 1)

    def test_wrong_source_or_dirty_build_stops_on_first_capture(self):
        for field, value in (("commit", "f" * 40), ("working_tree", "modified")):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                def mutate(result, ordinal):
                    result["build"][field] = value
                root = Path(directory)
                with self.assertRaisesRegex(EvidenceError, "physical campaign failed"):
                    self._run(root, mutate=mutate)
                receipt = json.loads((root / "campaign/sdvk009-physical-campaign.json").read_text())
                self.assertEqual(len(receipt["steps"]), 1)

    def test_scene_package_changes_are_expected_but_engine_package_changes_are_not(self):
        reference = self._result()
        candidate = copy.deepcopy(reference)
        candidate["loaded_packages"].append({"path": "input/scene.pk3", "sha256": "e" * 64,
                                              "bytes": 40, "lumps": 3})
        self.assertEqual(physical._runtime_identity(reference), physical._runtime_identity(candidate))

    def test_timing_group_gaps_are_inconclusive_and_complete_postprocess_is_not_scene_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            raw = {"mode": "timing", "observed_frames": 120, "records": []}
            def check():
                (path / "native.renderer.json").write_text(json.dumps(raw))
                return physical._timing_integrity(path)
            self.assertEqual(check()["status"], "INCONCLUSIVE")
            raw["records"] = [{"kind": "timing", "frame": frame,
                               "data": {"clock": "gpu", "name": "tonemap", "milliseconds": 0.1}}
                              for frame in range(1, 121)]
            self.assertEqual(check()["status"], "COMPLETE_GROUPS_SCOPE_UNQUALIFIED")
            raw["records"].pop()
            self.assertEqual(check()["status"], "INCONCLUSIVE")
            raw["records"].append({"kind": "timing", "frame": 120,
                                   "data": {"available": False, "reason": "query unavailable"}})
            self.assertEqual(check()["status"], "INCONCLUSIVE")

    def test_execute_flag_is_mandatory(self):
        with tempfile.TemporaryDirectory(prefix="sdvk009-physical-unit-") as directory:
            args = Namespace(exe=Path("engine"), iwad=Path("iwad"), out=Path(directory) / "campaign", timeout=600, execute=False)
            with self.assertRaisesRegex(EvidenceError, "explicit --execute"):
                physical.campaign(args)


if __name__ == "__main__":
    unittest.main(verbosity=2)
