"""CPU controls for SDVK-161 fresh-attempt ordering and fail-closed admission.

No renderer/device is invoked. External capture/receipt services are doubles;
qualification stop ordering and exact comparison policy execute production code.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, redirect_stdout
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.renderer_oracle import native_ci, prepare, run, sdvk010_sun_native
from tools.renderer_oracle import sdvk161_special_surfaces as gate
from tools.renderer_oracle.common import EvidenceError, read_json, write_json


class SpecialSurfaceAttemptTests(unittest.TestCase):
    def exercise(self, directory, *, capture_failure=None, receipt_failure=None,
                 semantic_failure=None, negative_failure=None, checkpoint_failure=None, comparison_status="PASS", commit="a" * 40):
        calls = []
        admissions = []
        comparisons = []
        args = argparse.Namespace(exe=Path("UNUSED-engine"), iwad=Path("UNUSED-iwad"),
                                  iwad_license=None, expected_commit=commit,
                                  out=Path(directory) / "qualification")
        native = {"synthetic": True}

        def capture(options):
            calls.append(options)
            options.out.mkdir()
            (options.out / "stdout.log").write_text("synthetic log")
            receipt = {"status": "FAIL" if capture_failure == len(calls) else "COLLECTED"}
            write_json(options.out / "run.json", receipt)
            write_json(options.out / "native.renderer.json", {"attempt": len(calls)})
            return receipt

        def validate(path):
            admissions.append(path)
            if receipt_failure == len(admissions):
                raise EvidenceError("synthetic corrupt receipt")
            return path, {}, {"attempt": len(admissions)}, {}

        def semantic(raw, stdout, observed_native):
            self.assertEqual(observed_native, native)
            self.assertEqual(stdout, "synthetic log")
            if semantic_failure == raw["attempt"]:
                raise EvidenceError("synthetic wrong draw path")
            return {"status": "PASS"}

        def negatives(raw, stdout, native):
            if negative_failure == raw["attempt"]:
                raise EvidenceError("synthetic captured control accepted wrong path")
            return {"status": "PASS", "synthetic": True}

        def checkpoints(root, raw):
            if checkpoint_failure == raw["attempt"]:
                raise EvidenceError("SDVK-161 lifecycle equivalent-state RGB differs: synthetic one-channel phase mutation")
            return {"status": "PASS", "synthetic": True}

        def compare(left, right):
            comparisons.append((left, right))
            return {"status": comparison_status, "state_equal": comparison_status == "PASS",
                    "image": {"passed": comparison_status == "PASS", "changed_pixels": 0}}

        with ExitStack() as stack, redirect_stdout(io.StringIO()):
            stack.enter_context(patch.dict(os.environ, {}, clear=True))
            stack.enter_context(patch.object(sdvk010_sun_native, "software_host_guard", return_value={"synthetic": True}))
            stack.enter_context(patch.object(native_ci, "preflight", return_value={"status": "PASS"}))
            stack.enter_context(patch.object(prepare, "prepare", return_value={"scenes": [{"id": gate.SCENE, "native": native}]}))
            stack.enter_context(patch.object(run, "capture", side_effect=capture))
            stack.enter_context(patch.object(run, "validate_run", side_effect=validate))
            stack.enter_context(patch.object(gate, "validate_transition_records", side_effect=semantic))
            stack.enter_context(patch.object(gate, "validate_checkpoint_images", side_effect=checkpoints))
            stack.enter_context(patch.object(gate, "captured_negatives", side_effect=negatives))
            stack.enter_context(patch.object(gate, "compare_checkpoint_images", return_value={"status": "PASS", "synthetic": True}))
            stack.enter_context(patch.object(run, "compare_runs", side_effect=compare))
            result = gate.qualify(args)
        return args, calls, admissions, comparisons, result

    def test_first_failed_capture_receipt_or_semantics_stops_dependent_process(self):
        for failure in ("capture_failure", "receipt_failure", "semantic_failure", "negative_failure", "checkpoint_failure"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                args, calls, admissions, comparisons, result = self.exercise(directory, **{failure: 1})
                self.assertEqual(result["status"], "FAIL")
                self.assertEqual([call.out.name for call in calls], ["lifecycle-1"])
                self.assertEqual(comparisons, [])
                self.assertEqual(len(admissions), 0 if failure == "capture_failure" else 1)
                self.assertFalse((args.out / "lifecycle-2").exists())
                self.assertTrue((args.out / "lifecycle-1/run.json").is_file())
                self.assertTrue((args.out / "steps/lifecycle-1.traceback.txt").is_file())
                self.assertEqual(read_json(args.out / "qualification.json")["status"], "FAIL")

    def test_lifecycle_rgb_mismatch_stops_before_the_second_native_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            args, calls, admissions, comparisons, result = self.exercise(directory, checkpoint_failure=1)
            self.assertEqual((len(calls), len(admissions), len(comparisons)), (1, 1, 0))
            self.assertEqual(result["status"], "FAIL")
            self.assertFalse((args.out / "lifecycle-2").exists())
            detail = read_json(args.out / "steps/lifecycle-1.json")
            self.assertIn("lifecycle equivalent-state RGB", detail["error"])

    def test_second_semantic_failure_stops_comparison(self):
        with tempfile.TemporaryDirectory() as directory:
            _, calls, admissions, comparisons, result = self.exercise(directory, semantic_failure=2)
            self.assertEqual((len(calls), len(admissions), len(comparisons)), (2, 2, 0))
            self.assertEqual(result["status"], "FAIL")

    def test_two_admitted_independent_attempts_use_exact_state_rgb_comparison(self):
        with tempfile.TemporaryDirectory() as directory:
            _, calls, admissions, comparisons, result = self.exercise(directory)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(len(admissions), 2)
            self.assertEqual(len(comparisons), 1)
            self.assertNotEqual(calls[0].out, calls[1].out)
            for call in calls:
                self.assertEqual((call.scene, call.mode, call.frames, call.warmup, call.timeout),
                                 (gate.SCENE, "state", gate.FRAMES, gate.WARMUP, gate.DEADLINE))
                self.assertFalse(call.gpu)
                self.assertEqual(call.image_policy, "exact")
                self.assertTrue(call.require_clean)
            self.assertEqual(result["automatic_retries"], 0)
            self.assertTrue(result["physical_stop_active"])
            self.assertFalse(result["physical_gpu_qualified"])
            self.assertFalse(result["performance_accepted"])
            self.assertEqual(result["historical_physical_root_cause"], "UNDETERMINED")

    def test_comparison_failure_is_never_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            _, calls, _, comparisons, result = self.exercise(directory, comparison_status="FAIL")
            self.assertEqual(len(calls), 2)
            self.assertEqual(len(comparisons), 1)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("exact semantic state/RGB", result["error"])

    def test_nonexact_build_identity_stops_before_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            _, calls, _, comparisons, result = self.exercise(directory, commit="130d09ac")
            self.assertEqual(calls, [])
            self.assertEqual(comparisons, [])
            self.assertEqual(result["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
