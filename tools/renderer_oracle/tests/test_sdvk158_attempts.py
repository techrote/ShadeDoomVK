"""Execute capture's actual receipt-admission path and SDVK-158 stop ordering.

CPU only. The post-process portion of capture, its exception/finally handlers,
native_ci.attempt and qualify are real. Host/preparation/process services and
the final independent comparison are doubles; no renderer or Vulkan is run.
"""
from __future__ import annotations

import argparse
import ast
import copy
from contextlib import ExitStack, redirect_stdout
import inspect
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.renderer_oracle import common, native_ci, prepare, run, sdvk010_sun_native
from tools.renderer_oracle import sdvk158_lightmap_transition as target
from tools.renderer_oracle.tests.test_sdvk158_repeatability import envelope, png, recipe
from tools.renderer_oracle.tests.test_sdvk158_lightmap_transition import stdout


def assigns(node, name):
    return isinstance(node, ast.Assign) and any(
        isinstance(value, ast.Name) and value.id == name for value in node.targets)


def capture_admission(*, original=False):
    """Slice complete actual post-process flow, preserving exception/exit paths."""
    function = ast.parse(inspect.getsource(run.capture)).body[0]
    tries = [(index, node) for index, node in enumerate(function.body) if isinstance(node, ast.Try)]
    if len(tries) != 1:
        raise AssertionError("Expected one capture operation/retention boundary")
    try_index, operation = tries[0]
    starts = [index for index, node in enumerate(operation.body) if assigns(node, "raw")]
    if len(starts) != 1:
        raise AssertionError("Expected one capture raw-receipt admission boundary")
    operation = copy.deepcopy(operation)
    operation.body = operation.body[starts[0]:]
    if original:
        gates = [node for node in operation.body if isinstance(node, ast.If) and any(
            isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
            and child.func.id == "validate_transition_records" for child in ast.walk(node))]
        if len(gates) != 1:
            raise AssertionError("Expected one new capture-time transition gate")
        operation.body.remove(gates[0])
    initial = [node for node in function.body[:try_index] if assigns(node, "result")]
    tail = function.body[try_index + 1:]
    if len(initial) != 1 or not isinstance(tail[-1], ast.Return):
        raise AssertionError("Expected capture result initialization and returned receipt")
    # Execute as a module with captured service values. The source return is
    # represented by reading result afterward; no admission condition changes.
    module = ast.Module(body=copy.deepcopy(initial) + [operation] + copy.deepcopy(tail[:-1]),
                        type_ignores=[])
    return compile(ast.fix_missing_locations(module), str(Path(run.__file__)), "exec")


class LightmapAttemptTests(unittest.TestCase):
    def exercise(self, directory, *, invalid=None, original=False):
        admission = capture_admission(original=original)
        args = argparse.Namespace(
            exe=Path("UNUSED-synthetic-engine"), iwad=Path("UNUSED-synthetic-iwad"), iwad_license=None,
            expected_commit="a" * 40, out=Path(directory) / "qualification")
        calls = []
        scene = recipe()

        def capture(options):
            calls.append(options)
            options.out.mkdir()
            raw = envelope()
            text = stdout()
            if len(calls) == 1:
                if invalid == "missing-flat":
                    raw["records"] = [record for record in raw["records"] if not (
                        record["frame"] == 9 and record["data"].get("surface") == "flat")]
                    raw["limits"]["retained_records"] = len(raw["records"])
                elif invalid == "no-completion":
                    for record in raw["records"]:
                        if record["kind"] == "resource" and 9 <= record["frame"] <= 24:
                            record["data"]["lightmap_state"]["frame_tile_completions"] = 0
                elif invalid == "wrong-marker":
                    text = text.replace("after_main_views=56", "after_main_views=57")
            common.write_json(options.out / "native.renderer.json", raw)
            (options.out / "native.png").write_bytes(png(bytes(6)))
            (options.out / "stdout.log").write_text(text)
            namespace = dict(vars(run))
            namespace.update(
                args=options, scene=scene, native=scene["native"], out=options.out,
                mode=options.mode, frames=options.frames, warmup=options.warmup, extent=[2, 1],
                source_commit=args.expected_commit, working_tree="clean", text=text,
                diagnostics=None, profile={"extent": [2, 1]}, executable={}, packages=[],
                readbacks=scene["native"]["settings"], elapsed=0,
                process=argparse.Namespace(returncode=0), started=run.utc())
            exec(admission, namespace)
            return namespace["result"]

        with ExitStack() as stack, redirect_stdout(io.StringIO()):
            stack.enter_context(patch.dict(os.environ, {}, clear=True))
            stack.enter_context(patch.object(sdvk010_sun_native, "software_host_guard",
                                             return_value={"status": "PASS", "synthetic": True}))
            stack.enter_context(patch.object(native_ci, "preflight", return_value={"status": "PASS"}))
            stack.enter_context(patch.object(prepare, "prepare", return_value={"scenes": [scene]}))
            stack.enter_context(patch.object(run, "capture", side_effect=capture))
            comparison = stack.enter_context(patch.object(run, "compare_runs",
                                                          return_value={"status": "PASS", "synthetic": True}))
            result = target.qualify(args)
        return args, calls, result, comparison.call_count

    def test_first_invalid_receipt_stops_before_any_dependent_capture(self):
        for invalid, reason in (("missing-flat", "no actual LevelMesh flat"),
                                ("no-completion", "did not complete real lightmap tile work"),
                                ("wrong-marker", "driver order/count")):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory(prefix="sdvk158-attempt-") as directory:
                args, calls, result, comparisons = self.exercise(directory, invalid=invalid)
                self.assertEqual(result["status"], "FAIL")
                self.assertEqual([call.out.name for call in calls], ["transition-1"])
                self.assertEqual(comparisons, 0)
                self.assertEqual([(step["name"], step["status"]) for step in result["steps"]],
                                 [("transition-1", "FAIL")])
                receipt = common.read_json(args.out / "transition-1/run.json")
                self.assertEqual(receipt["status"], "FAIL")
                self.assertIn(reason, receipt["error"])
                self.assertIn("native.renderer.json", receipt["artifacts"])
                self.assertIn("stdout.log", receipt["artifacts"])
                self.assertTrue((args.out / "steps/transition-1.traceback.txt").is_file())
                self.assertFalse((args.out / "transition-2").exists())

    def test_pre_fix_admission_incorrectly_allows_dependent_capture(self):
        with tempfile.TemporaryDirectory(prefix="sdvk158-pre-fix-attempt-") as directory:
            args, calls, result, comparisons = self.exercise(directory, invalid="missing-flat", original=True)
            self.assertEqual([call.out.name for call in calls], ["transition-1", "transition-2"])
            self.assertEqual(comparisons, 1)
            self.assertEqual(result["status"], "PASS")  # comparison service is an explicit double
            first = common.read_json(args.out / "transition-1/run.json")
            self.assertEqual(first["status"], "COLLECTED")
            raw = common.read_json(args.out / "transition-1/native.renderer.json")
            with self.assertRaisesRegex(common.EvidenceError, "no actual LevelMesh flat"):
                target.validate_transition_records(raw, stdout(), recipe()["native"])

    def test_valid_attempts_reach_exactly_two_independent_captures(self):
        with tempfile.TemporaryDirectory(prefix="sdvk158-valid-attempt-") as directory:
            args, calls, result, comparisons = self.exercise(directory)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual([call.out.name for call in calls], ["transition-1", "transition-2"])
            self.assertEqual(comparisons, 1)
            self.assertEqual(result["automatic_retries"], 0)
            for call in calls:
                self.assertEqual((call.frames, call.warmup, call.timeout),
                                 (target.FRAMES, target.WARMUP, target.DEADLINE))
                self.assertFalse(call.gpu)
                self.assertEqual(common.read_json(call.out / "run.json")["status"], "COLLECTED")
            self.assertTrue((args.out / "qualification.json").is_file())


if __name__ == "__main__":
    unittest.main()
