"""Bounded CPU restart parser/child controls; never native or GPU evidence."""
from __future__ import annotations

import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle import run_indexed_material_restart as runner
from tools.pf_oracle import run_indexed_material_runtime as base
from tools.pf_oracle.tests import test_indexed_runtime_runner as controls


class IndexedRestartRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.out = Path(self.temporary.name).resolve()
        self.addCleanup(patch.stopall)
        patch.object(runner.subprocess, "Popen", side_effect=AssertionError("CPU tests must never launch a real child")).start()
        self.case = {"rendererMode": 4, "globalFilter": 0, "extent": [640, 480]}

    def write_log(self, text, name="stdout.log"):
        (self.out / name).write_text(text, encoding="utf-8")

    def package_fixture(self):
        build, inputs, paths = {}, {}, []
        for name in ("vkdoom.pk3", "game_support.pk3", "lights.pk3", "brightmaps.pk3", "game_widescreen_gfx.pk3"):
            path = self.out / name
            path.write_bytes(name.encode())
            build[name] = base.identity(path)
            paths.append(path)
        for name, filename in (("iwad", "doom2.wad"), ("mod", "synthetic.pk3")):
            path = self.out / filename
            path.write_bytes(filename.encode())
            inputs[name] = base.identity(path)
            paths.append(path)
        return {"build": build, "inputs": inputs}, paths

    @staticmethod
    def startup(paths):
        return "W_Init: Init WADfiles.\n" + "\n".join(f"adding {path.as_posix()}, {i + 1} lumps" for i, path in enumerate(paths)) + "\n"

    def test_exact_two_startups_independently_require_all_seven_pinned_packages(self):
        before, paths = self.package_fixture()
        self.write_log(self.startup(paths) + "PF110_RESTART_BEFORE PASS\n" + self.startup(paths))
        evidence = runner.package_startups(self.out, before)
        self.assertEqual(evidence["startupCount"], 2)
        self.assertEqual([block["packageCount"] for block in evidence["blocks"]], [7, 7])
        self.assertFalse(base.loaded_package_evidence(self.out, before)["verified"])

    def test_no_one_or_three_startups_are_rejected(self):
        before, paths = self.package_fixture()
        for count in (0, 1, 3):
            self.write_log(self.startup(paths) * count)
            with self.assertRaisesRegex(ValueError, "exactly two"):
                runner.package_startups(self.out, before)

    def test_missing_duplicate_extra_packages_in_either_startup_fail(self):
        before, paths = self.package_fixture()
        extra = self.out / "unapproved-extras.wad"
        extra.write_bytes(b"unknown")
        for bad in (paths[:-1], paths + paths[:1], paths + [extra]):
            for stage in (0, 1):
                self.write_log(self.startup(bad if stage == 0 else paths) + self.startup(bad if stage == 1 else paths))
                with self.assertRaises(ValueError):
                    runner.package_startups(self.out, before)

    def test_package_outside_startup_blocks_is_rejected(self):
        before, paths = self.package_fixture()
        self.write_log(f"adding {paths[0].as_posix()}, 1 lumps\n" + self.startup(paths) * 2)
        with self.assertRaisesRegex(ValueError, "outside"):
            runner.package_startups(self.out, before)

    def validation_fixture(self):
        self.write_log("Vulkan device: synthetic CPU control\nVulkan version: 1.2.3 (api) 4.5.6 (driver)\n")
        self.write_log('[Vulkan Loader] INFO | LAYER: Insert instance layer "VK_LAYER_KHRONOS_validation" (pinned.dll)\n'
                       '[Vulkan Loader] INFO | LAYER: Inserted device layer "VK_LAYER_KHRONOS_validation" (pinned.dll)\n', "stderr.log")
        self.write_log("Validation Information: [ CURRENT-VALIDATION-ENABLED ]\n"
                       "vkCreateInstance(): Current Validaiton Enabled:\n  - Core Checks\n"
                       "Objects: 1\n    [0] VkInstance 0x10203\n", "validation.log")

    def test_one_actual_vulkan_activation_and_instance_are_required(self):
        self.validation_fixture()
        evidence = runner.persistent_vulkan(self.out, "core")
        self.assertEqual(evidence["observedVkInstance"], "0x10203")
        self.assertEqual(len(evidence["instanceInsertionLines"]), 1)

    def test_second_instance_device_or_activation_and_validation_error_fail(self):
        for name, append in (("stderr.log", 'Insert instance layer "VK_LAYER_KHRONOS_validation" (new.dll)\n'),
                             ("stderr.log", 'Inserted device layer "VK_LAYER_KHRONOS_validation" (new.dll)\n'),
                             ("stdout.log", "Vulkan device: second\n"),
                             ("validation.log", "Validation Information: [ CURRENT-VALIDATION-ENABLED ]\n  - Core Checks\nVkInstance 0x445566\n"),
                             ("validation.log", "Validation Error: actual synthetic VUID\n")):
            self.validation_fixture()
            with (self.out / name).open("a", encoding="utf-8") as stream:
                stream.write(append)
            with self.assertRaises(ValueError):
                runner.persistent_vulkan(self.out, "core")

    def native_fixture(self):
        before, _ = self.package_fixture()
        for phase in ("before", "after"):
            (self.out / phase).mkdir(exist_ok=True)
        stats = {"activations": 20, "retirements": 10, "resets": 0, "staleRejects": 1,
                 "invalidRetires": 0, "duplicateActivations": 0}
        first = {"schema": runner.NATIVE_SCHEMA, "schemaVersion": 1, "stage": "before", "status": "PASS", "error": "",
            "prefix": str(self.out / "before/native"), "nativeReceipt": str(self.out / "before/native.json"),
            "beforeNativePrefix": str(self.out / "before/native"), "afterNativePrefix": str(self.out / "after/native"),
            "afterExec": str(self.out / "after/execute.cfg"), "beforeCounter": 0, "actualCounter": 0,
            "managerIdentity": "1001", "actualManagerIdentity": "1001", "deviceIdentity": "1002", "actualDeviceIdentity": "1002",
            "framebufferIdentity": "1003", "actualFramebufferIdentity": "1003", "beforeLifetime": stats, "actualLifetime": dict(stats),
            "iwad": before["inputs"]["iwad"]["path"], "mod": before["inputs"]["mod"]["path"], "rendererMode": 4, "globalTextureFilter": 0,
            "tokens": [{"index": 12, "generation": 2, "epoch": 3, "span": 2}, {"index": 14, "generation": 2, "epoch": 3, "span": 2}],
            "oldTokensLive": [True, True], "valueOnlyCheckpoint": True, "oldResourcePointersDereferenced": False,
            "paletteAddressInequalityRequired": False, "oldTokensCheckedBeforeProducer": False}
        second = copy.deepcopy(first)
        second.update(stage="after", prefix=str(self.out / "after/native"), nativeReceipt=str(self.out / "after/native.json"),
                      actualCounter=1, oldTokensLive=[False, False], oldTokensCheckedBeforeProducer=True)
        second["actualLifetime"].update(retirements=15, staleRejects=3)
        self.write_log("PF110_RESTART_BEFORE PASS counter=0 blocks=2; native.restart-before.json\n"
                       "PF110_RESTART_AFTER PASS counter=1 old_blocks_stale=2; native.restart-after.json\n")
        return before, first, second

    def save_native(self, first, second):
        for phase, data in (("before", first), ("after", second)):
            base.save(self.out / phase / ("native.restart-" + phase + ".json"), data)

    def test_live_before_stale_after_same_value_checkpoint_and_counter_pass(self):
        before, first, second = self.native_fixture()
        self.save_native(first, second)
        evidence = runner.restart_evidence(self.out, self.case, before)
        self.assertEqual(evidence["status"], "PASS")
        self.assertEqual(evidence["phases"]["after"]["actualJson"]["oldTokensLive"], [False, False])

    def test_new_manager_device_counter_or_checkpoint_cannot_fake_in_process_restart(self):
        before, first, good = self.native_fixture()
        for mutate in (lambda d: d.update(actualManagerIdentity="2001"), lambda d: d.update(actualDeviceIdentity="2002"),
                       lambda d: d.update(actualFramebufferIdentity="2003"), lambda d: d.update(actualCounter=0),
                       lambda d: d.update(actualCounter=2), lambda d: d.update(beforeCounter=1, actualCounter=2),
                       lambda d: d["tokens"][0].update(generation=8)):
            second = copy.deepcopy(good)
            mutate(second)
            self.save_native(first, second)
            with self.assertRaises(ValueError):
                runner.restart_evidence(self.out, self.case, before)

    def test_one_old_token_live_missing_pair_or_checks_after_producer_fail(self):
        before, first, good = self.native_fixture()
        for mutate in (lambda d: d.update(oldTokensLive=[False, True]), lambda d: d.update(tokens=[]),
                       lambda d: d["tokens"][1].update(index=12), lambda d: d.update(oldTokensCheckedBeforeProducer=False),
                       lambda d: d.update(oldResourcePointersDereferenced=True), lambda d: d.update(oldTokensLive=[0, 0])):
            second = copy.deepcopy(good)
            mutate(second)
            self.save_native(first, second)
            with self.assertRaises(ValueError):
                runner.restart_evidence(self.out, self.case, before)

    def test_missing_retirements_allocator_reset_invalid_free_or_stale_counter_fail(self):
        before, first, good = self.native_fixture()
        for field, value in (("retirements", 11), ("resets", 1), ("invalidRetires", 1), ("duplicateActivations", 1), ("staleRejects", 1)):
            second = copy.deepcopy(good)
            second["actualLifetime"][field] = value
            self.save_native(first, second)
            with self.assertRaises(ValueError):
                runner.restart_evidence(self.out, self.case, before)

    def test_protocol_before_is_terminal_and_after_explicitly_loads_map(self):
        before, after = runner.scripts(self.out)
        commands = controls.IndexedRuntimeRunnerTests.exec_line_commands(before)
        self.assertEqual(len(before.splitlines()), 1)
        self.assertEqual(commands[-1], ["pf_indexedmaterial_restart_before", runner.protocol_path(self.out / "before/native"),
                                       runner.protocol_path(self.out / "after/native"), runner.protocol_path(self.out / "after/execute.cfg")])
        self.assertTrue(all(command[0] in ("wait", "vid_setsize") for command in commands[:-1]))
        after_commands = controls.IndexedRuntimeRunnerTests.exec_line_commands(after)
        self.assertEqual(after_commands[:5], [["wait", "35"], ["map", "PF110"], ["wait", "105"], ["vid_setsize", "640", "480"], ["wait", "35"]])
        self.assertEqual(after_commands[5], ["pf_indexedmaterial_restart_after", runner.protocol_path(self.out / "after/native")])
        self.assertEqual(after_commands[-2:], [["wait", "5"], ["quit"]])

    def test_source_linked_actual_restart_and_static_startup_log_are_not_substituted(self):
        main = (ROOT / "src/d_main.cpp").read_text(encoding="utf-8")
        renderer = (ROOT / "src/common/rendering/vulkan/vk_renderdevice.cpp").read_text(encoding="utf-8")
        seam = (ROOT / "src/common/rendering/vulkan/textures/vk_indexedmaterialdiagnostics.cpp").read_text(encoding="utf-8")
        self.assertIn("UNSAFE_CCMD(debug_restart)", main)
        self.assertIn("restart++;", main)
        self.assertIn("static bool first = true;", renderer)
        self.assertIn('Printf("Vulkan device: ', renderer)
        self.assertIn('Args->TakeValue("+exec");', seam)
        self.assertIn('Args->TakeValue("+map");', seam)
        self.assertIn('"debug_restart -iwad "', seam)
        self.assertIn("oldTokensCheckedBeforeProducer", seam)

    def test_watchdog_kills_only_own_fake_child_without_a_second_process(self):
        clock, receipt = [0.], {}
        child = controls.FakeChild(clock)
        with patch.object(base.time, "monotonic", side_effect=lambda: clock[0]):
            with self.assertRaisesRegex(ValueError, "90-second"):
                base.wait_child(child, self.out, receipt, "synthetic.pk3")
        self.assertEqual(child.kills, 1)
        self.assertEqual(receipt["watchdogAction"]["pid"], child.pid)
        self.assertEqual(clock[0], 90.)

    def test_launch_routes_exactly_one_fake_popen_child_and_retains_its_pid(self):
        before = {"stable": True}
        receipt = {"before": before, "generated": {}, "configLiveBefore": {}, "argv": ["fake-staged.exe"],
                   "validationMode": "core", "status": "PREPARED"}
        fake = controls.FakeChild([0.], exit_code=0)
        def fake_collect(record, out, case, manifest):
            for name in ("beforeRawReadback", "afterRawReadback", "restart", "loadedPackages", "validation"):
                record[name] = {"status": "PASS"}
            record["exitSettings"] = {"verified": True}
            record["presentation"] = {"status": "PASS"}
        with patch.object(runner, "snapshot", return_value=before), patch.object(runner, "generated_identity", return_value={}), \
             patch.object(base, "identity", return_value={}), patch.object(base, "environment", return_value=({}, {})), \
             patch.object(runner, "collect_evidence", side_effect=fake_collect), \
             patch.object(runner.subprocess, "Popen", return_value=fake) as popen:
            code = runner.launch(receipt, {"mod": {"path": "synthetic.pk3"}}, self.case,
                                 Path("manifest"), Path("fake-staged.exe"), self.out, "core", Path("layer"))
        self.assertEqual(code, 0)
        self.assertEqual(popen.call_count, 1)
        self.assertEqual(receipt["process"]["launchCount"], 1)
        self.assertEqual(receipt["process"]["pid"], fake.pid)

    def test_final_output_hash_or_stat_failure_writes_durable_fail_receipt(self):
        bad_output = self.out / "unreadable-native.bin"
        bad_output.write_bytes(b"synthetic observer output")
        original_is_file = Path.is_file
        def fake_collect(record, out, case, manifest):
            for name in ("beforeRawReadback", "afterRawReadback", "restart", "loadedPackages", "validation"):
                record[name] = {"status": "PASS"}
            record["exitSettings"] = {"verified": True}
            record["presentation"] = {"status": "PASS"}
        for operation in ("hash", "stat"):
            receipt = {"before": {"stable": True}, "generated": {}, "configLiveBefore": {}, "argv": ["fake-staged.exe"],
                       "validationMode": "core", "status": "PREPARED"}
            fake = controls.FakeChild([0.], exit_code=0)
            def identity(path):
                if operation == "hash" and Path(path) == bad_output:
                    raise PermissionError("synthetic output read denied")
                return {}
            def is_file(path):
                if operation == "stat" and path == bad_output:
                    raise OSError("synthetic output stat failed")
                return original_is_file(path)
            with self.subTest(operation=operation), patch.object(runner, "snapshot", return_value={"stable": True}), \
                 patch.object(runner, "generated_identity", return_value={}), patch.object(base, "identity", side_effect=identity), \
                 patch.object(base, "environment", return_value=({}, {})), patch.object(Path, "is_file", is_file), \
                 patch.object(runner, "collect_evidence", side_effect=fake_collect), \
                 patch.object(runner.subprocess, "Popen", return_value=fake) as popen:
                code = runner.launch(receipt, {"mod": {"path": "synthetic.pk3"}}, self.case,
                                     Path("manifest"), Path("fake-staged.exe"), self.out, "core", Path("layer"))
            self.assertEqual(code, 1)
            saved = base.read_json(self.out / "receipt.json")
            self.assertEqual(saved["status"], "FAIL")
            self.assertIn("artifactError", saved)
            self.assertEqual(saved["beforeRawReadback"]["status"], "PASS")
            self.assertEqual(popen.call_count, 1)
            self.assertEqual(saved["process"]["pid"], fake.pid)
            if operation == "hash":
                self.assertIn(bad_output.name, saved["outputUnavailable"])


if __name__ == "__main__":
    unittest.main()
