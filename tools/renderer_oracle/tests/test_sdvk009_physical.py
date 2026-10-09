"""Host-only controls for the preregistered SDVK-009 physical campaign driver."""
from argparse import Namespace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.renderer_oracle import sdvk009_physical as physical
from tools.renderer_oracle.common import EvidenceError


class PhysicalCampaignControls(unittest.TestCase):
    def _run(self, root, *, device_type=2, compare_status="PASS"):
        args = Namespace(exe=Path("engine"), iwad=Path("iwad"), out=root / "campaign", timeout=600, execute=True)
        captures = []

        def capture(ns):
            ns.out.mkdir(parents=True, exist_ok=False)
            captures.append(ns)
            return {"status": "COLLECTED", "build": {"working_tree": "clean", "commit": "a" * 40,
                    "device": "physical-test", "vulkan": {"available": True, "device_type": device_type}}}

        summary = {"schema": "sdvk-renderer-baseline/v1", "status": "DESCRIPTIVE", "runs": []}
        with patch.object(physical.prepare, "prepare", return_value={"status": "prepared_only"}), \
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
                return {"status": "COLLECTED", "build": {"working_tree": "clean", "commit": "a" * 40,
                        "device": "physical-test", "vulkan": {"available": True, "device_type": 2}}}
            with patch.object(physical.prepare, "prepare", return_value={"status": "prepared_only"}), \
                 patch.object(physical.run, "capture", side_effect=capture), \
                 patch.object(physical.run, "compare_runs", return_value={"status": "FAIL"}), \
                 patch.object(physical.run, "comparable_build", side_effect=lambda value: value):
                with self.assertRaisesRegex(EvidenceError, "physical campaign failed"):
                    physical.campaign(args)
            self.assertEqual(len(calls), 2)
            self.assertTrue(all(call.mode == "state" for call in calls))

    def test_execute_flag_is_mandatory(self):
        with tempfile.TemporaryDirectory(prefix="sdvk009-physical-unit-") as directory:
            args = Namespace(exe=Path("engine"), iwad=Path("iwad"), out=Path(directory) / "campaign", timeout=600, execute=False)
            with self.assertRaisesRegex(EvidenceError, "explicit --execute"):
                physical.campaign(args)


if __name__ == "__main__":
    unittest.main(verbosity=2)
