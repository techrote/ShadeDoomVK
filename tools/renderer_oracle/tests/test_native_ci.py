"""Host-only CI controls; synthetic/mocked outputs never qualify native rendering.

SPDX-License-Identifier: GPL-3.0-or-later
"""
from argparse import Namespace
from contextlib import ExitStack, redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.renderer_oracle import native_ci
from tools.renderer_oracle.common import EvidenceError

class Controls(unittest.TestCase):
    def setUp(self):
        self.summary = '''GPU0:
    deviceType = PHYSICAL_DEVICE_TYPE_CPU
    deviceName = llvmpipe (synthetic unit fixture)
    driverName = llvmpipe
    driverID = DRIVER_ID_MESA_LLVMPIPE
    driverInfo = synthetic unit fixture
    apiVersion = 1.3.0
    driverVersion = 0.0.0
'''
        self.full = self.summary + '\n'.join(name + ' = true' for name in native_ci.FEATURES)

    def test_device_feature_probe_is_headless_without_mutating_parent_environment(self):
        with patch.dict(os.environ, {"DISPLAY": ":99", "WAYLAND_DISPLAY": "wayland-0", "KEEP": "yes"}, clear=True):
            child = native_ci.device_feature_probe_environment()
            self.assertNotIn("DISPLAY", child)
            self.assertNotIn("WAYLAND_DISPLAY", child)
            self.assertEqual(child["KEEP"], "yes")
            self.assertEqual(os.environ["DISPLAY"], ":99")
            self.assertEqual(os.environ["WAYLAND_DISPLAY"], "wayland-0")

    def test_synthetic_identity_and_each_missing_or_false_feature(self):
        value = native_ci.device_evidence(self.summary, self.full)
        self.assertEqual(len(value['required_features']), 5)
        for name in native_ci.FEATURES:
            for replace in ('false', None):
                with self.subTest(name=name, replace=replace):
                    import re
                    expression = r'(?m)^\s*' + re.escape(name) + r'\s*=\s*true$'
                    changed = re.sub(expression, '' if replace is None else name + ' = false', self.full)
                    with self.assertRaises(EvidenceError):
                        native_ci.device_evidence(self.summary, changed)

    def test_extra_device_and_wrong_driver_rejected(self):
        variants = [self.summary + '\nGPU1:\n', self.summary.replace('PHYSICAL_DEVICE_TYPE_CPU', 'PHYSICAL_DEVICE_TYPE_DISCRETE_GPU'),
                    self.summary.replace('driverName = llvmpipe', 'driverName = other'),
                    self.summary.replace('DRIVER_ID_MESA_LLVMPIPE', 'DRIVER_ID_NVIDIA_PROPRIETARY')]
        for summary in variants:
            with self.subTest(summary=summary[-200:]), self.assertRaises(EvidenceError):
                native_ci.device_evidence(summary, self.full)
        with self.assertRaises(EvidenceError):
            native_ci.device_evidence(self.summary, self.full + '\nGPU1:\n')

    def test_full_report_driver_and_api_identity_must_match_summary(self):
        # Two independent vulkaninfo calls can no longer be combined into one
        # apparently qualified host receipt when their provenance disagrees.
        properties = {"driverInfo": "synthetic unit fixture", "apiVersion": "1.3.0",
                      "driverVersion": "0.0.0"}
        for name, original in properties.items():
            mutations = {
                "conflicting": self.full.replace(f"{name} = {original}", f"{name} = mismatched"),
                "missing": self.full.replace(f"    {name} = {original}\n", ""),
                "contradictory_duplicate": self.full + f"\n{name} = mismatched",
            }
            for kind, mutated in mutations.items():
                with self.subTest(property=name, mutation=kind):
                    with self.assertRaises(EvidenceError):
                        native_ci.device_evidence(self.summary, mutated)
        # Identical repeated fields remain harmless; do not tighten the device
        # inventory or driver-property output policy beyond identity equality.
        full = self.full + "\napiVersion = 1.3.0"
        self.assertEqual(native_ci.device_evidence(self.summary, full)["device"]["apiVersion"],
                         "1.3.0")


    def test_full_report_packed_versions_match_and_check_packed_values(self):
        # Retained hosted #182 evidence: summary versions 1.4.318 / 25.2.8,
        # full vulkaninfo versions 1.4.318 (4211006) / 25.2.8 (104865800).
        summary = (self.summary.replace("apiVersion = 1.3.0", "apiVersion = 1.4.318")
                   .replace("driverVersion = 0.0.0", "driverVersion = 25.2.8"))
        full = (self.full.replace("apiVersion = 1.3.0", "apiVersion = 1.4.318 (4211006)")
                .replace("driverVersion = 0.0.0", "driverVersion = 25.2.8 (104865800)"))
        self.assertEqual(native_ci.device_evidence(summary, full)["device"]["apiVersion"],
                         "1.4.318")
        self.assertEqual(native_ci.device_evidence(summary, full)["device"]["driverVersion"],
                         "25.2.8")
        variants = {
            "api-packed-mismatch": full.replace("(4211006)", "(4211007)"),
            "driver-packed-mismatch": full.replace("(104865800)", "(104865801)"),
            "api-dotted-mismatch": full.replace("1.4.318 (4211006)", "1.4.319 (4211006)"),
            "driver-dotted-mismatch": full.replace("25.2.8 (104865800)",
                                                    "25.2.9 (104865800)"),
            "api-nonnumeric": full.replace("(4211006)", "(not-a-number)"),
            "driver-nonnumeric": full.replace("(104865800)", "(invalid)"),
            "contradictory-duplicate": full + "\napiVersion = 1.4.319 (4211007)\n",
            "invalid-component": full.replace("1.4.318 (4211006)",
                                              "1.4.4096 (4214784)"),
        }
        for kind, bad_full in variants.items():
            with self.subTest(kind=kind), self.assertRaises(EvidenceError):
                native_ci.device_evidence(summary, bad_full)
        # Legitimate repetitions with consistent packed representation are valid.
        repeated = full + "\napiVersion = 1.4.318 (4211006)\n"
        self.assertEqual(native_ci.device_evidence(summary, repeated)["device"]["driverName"],
                         "llvmpipe")

    def fake_summary(self, gpu=True):
        return {'status': 'DESCRIPTIVE', 'repeatability_evidence': True,
                'runs': [{'summary': {'gpu_groups': {'Opaque': {'samples_ms': [0.1]}} if gpu else {}}} for _ in range(3)]}

    def scenario(self, base, *, full=False, bad_capture=False, bad_compare=False, gpu=True, preflight=True):
        args = Namespace(exe=Path('unused-exe'), iwad=Path('unused-iwad'), out=base/'out',
                         iwad_license=None, scene=None, full=full)
        calls = []
        def capture(args):
            args.out.mkdir(parents=True, exist_ok=False)
            calls.append(args)
            if bad_capture and len(calls) == 1:
                (args.out/'unit-only-failure.txt').write_text('Injected capture failure; not native evidence')
                raise EvidenceError('injected capture failure')
            return {'status': 'COLLECTED', 'unit_test_only': True}
        with ExitStack() as stack, redirect_stdout(io.StringIO()):
            preflight_mock = stack.enter_context(patch.object(native_ci, 'preflight', return_value={'status': 'PASS' if preflight else 'FAIL'}))
            prep = stack.enter_context(patch.object(native_ci.prepare, 'prepare', return_value={'status': 'prepared_only'}))
            stack.enter_context(patch.object(native_ci.run, 'capture', side_effect=capture))
            comparison = stack.enter_context(patch.object(native_ci.run, 'compare_runs', side_effect=lambda *p: {'status': 'FAIL' if bad_compare and 'compositing' in str(p[0]) else 'PASS'}))
            summary = stack.enter_context(patch.object(native_ci.run, 'summarize_runs', return_value=self.fake_summary(gpu)))
            result = native_ci.qualify(args)
        return args, calls, result, prep, comparison, summary, preflight_mock

    def test_default_and_full_process_counts_exact_policy_and_fresh_outputs(self):
        for full, count, scenes, summaries in ((False, 7, 2, 1), (True, 55, 20, 5)):
            with self.subTest(full=full), tempfile.TemporaryDirectory(prefix='sdvk-native-ci-unit-') as directory:
                args, calls, result, prep, comparison, summary, _ = self.scenario(Path(directory), full=full)
                self.assertEqual(result['status'], 'PASS')
                self.assertEqual(len(calls), count)
                self.assertEqual(len({str(call.out) for call in calls}), count)
                self.assertEqual(comparison.call_count, scenes)
                self.assertTrue(all(not call.kwargs for call in comparison.call_args_list))
                self.assertEqual(summary.call_count, summaries)
                minimums = [call.kwargs['minimum_samples'] for call in summary.call_args_list]
                self.assertEqual(minimums, [120] if not full else [120, 30, 30, 30, 30])
                self.assertTrue(all(len(call.args[0]) == 3 for call in summary.call_args_list))
                for call in calls:
                    self.assertEqual(call.image_policy, 'exact')
                    if call.mode == 'state':
                        self.assertEqual(call.frames, 1)
                    elif call.scene in native_ci.SDVK009_SCALE_TIMING_SCENES:
                        self.assertEqual(call.frames, 30)
                        self.assertEqual(call.warmup, 20)
                    else:
                        self.assertEqual(call.frames, 120)
                    self.assertEqual(call.gpu, call.mode == 'timing')
                self.assertEqual(result['sdvk009_scale_timing_scenes'],
                                 list(native_ci.SDVK009_SCALE_TIMING_SCENES) if full else [])
                if full:
                    for scene in ("viewmodel-model-legacy", "viewmodel-model-normal",
                                  "viewmodel-model-pbr", "viewmodel-model-fallback"):
                        self.assertEqual(sum(call.scene == scene and call.mode == "state"
                                             for call in calls), 2, scene)
                before = (args.out/'native-ci.json').read_bytes()
                with self.assertRaises(FileExistsError):
                    native_ci.qualify(args)
                self.assertEqual(before, (args.out/'native-ci.json').read_bytes())

    def test_capture_failure_and_comparison_failure_do_not_stop_independent_work(self):
        with tempfile.TemporaryDirectory(prefix='sdvk-native-ci-unit-') as directory:
            args, calls, result, _, comparison, summary, _ = self.scenario(Path(directory), bad_capture=True, bad_compare=True)
            self.assertEqual(result['status'], 'FAIL')
            self.assertEqual(len(calls), 7)
            self.assertEqual(comparison.call_count, 2)
            self.assertEqual(summary.call_count, 1)
            failed = [row['name'] for row in result['steps'] if row['status'] == 'FAIL']
            self.assertEqual(failed, ['compositing-state-1', 'compositing-compare'])
            self.assertTrue((args.out/'state/compositing/1/unit-only-failure.txt').is_file())
            comparison_receipt = json.loads((args.out/'steps/compositing-compare.json').read_text())
            self.assertEqual(comparison_receipt['result']['status'], 'FAIL')

    def test_no_gpu_baseline_is_retained_and_fails(self):
        with tempfile.TemporaryDirectory(prefix='sdvk-native-ci-unit-') as directory:
            args, calls, result, *_ = self.scenario(Path(directory), gpu=False)
            self.assertEqual(result['status'], 'FAIL')
            self.assertEqual(result['steps'][-1]['name'], 'baseline')
            self.assertEqual(result['steps'][-1]['status'], 'FAIL')
            self.assertTrue((args.out/'baseline.json').is_file())

    def test_preflight_failure_blocks_engine_and_preparation(self):
        with tempfile.TemporaryDirectory(prefix='sdvk-native-ci-unit-') as directory:
            _, calls, result, prep, comparison, summary, _ = self.scenario(Path(directory), preflight=False)
            self.assertEqual(result['status'], 'FAIL')
            self.assertEqual(calls, [])
            prep.assert_not_called()
            comparison.assert_not_called()
            summary.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
