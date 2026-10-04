"""CPU format/source/owned-child controls only; no native timing or GPU evidence."""
from __future__ import annotations
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

HERE = Path(__file__).resolve()
RUNNER = HERE.with_name("run_freeze_final_dense.py")
if not RUNNER.is_file(): RUNNER = HERE.parents[1] / "run_freeze_final_dense.py"
spec = importlib.util.spec_from_file_location("pf020_final_dense_controls", RUNNER)
runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)


class FinalDenseControls(unittest.TestCase):
    def test_finite_order_native_current_and_actual_reviewed_delta_are_pinned(self):
        self.assertEqual(len(runner.ORDER), 12)
        self.assertEqual(sum(pair > 0 for _, pair in runner.ORDER), 10)
        for pair in range(1, 6):
            variants = [v for v, p in runner.ORDER if p == pair]
            self.assertEqual(variants, ["accepted-master", "final-current"] if pair % 2 else ["final-current", "accepted-master"])
        self.assertEqual(runner.CURRENT_NATIVE, "569bdb118c709dac00dc6543570d6840c88dad12")
        self.assertEqual(len(runner.DELTA_PATHS), 15)
        self.assertIn("src/rendering/r_utility.cpp", runner.DELTA_PATHS)
        self.assertEqual(runner.DELTA_BYTES, 85910)
        self.assertEqual(runner.DELTA_SHA256, "d061eaf9a1b7a5915643691680e2dff2f6fc9eee36737dd3cd14f5b2c0b2db16")

    def test_native_input_predicate_includes_all_static_native_tools_and_recipe_metadata(self):
        self.assertTrue(all(any(root.startswith(prefix) for prefix in runner.NATIVE_ROOTS)
                            for root in runner.PACKAGE_ROOTS.values()))
        for prefix in ("tools/re2c/", "tools/lemon/", "tools/zipdir/", "tools/updaterevision/", "fm_banks/", "soundfont/"):
            self.assertIn(prefix, runner.NATIVE_ROOTS)

    def test_normal_startup_policy_and_script_do_not_enable_correctness_diagnostics_or_clock(self):
        seed = "[GlobalSettings]\n" + "\n".join(k + "=" + v for k, v in {**runner.dense.GLOBAL, "gl_light_shadows": "1"}.items())
        seed += "\n[Doom.ConsoleVariables]\n" + "\n".join(k + "=" + v for k, v in runner.dense.GAME.items()) + "\n"
        config = runner.configuration(seed)
        for line in ("gl_ubershaders=true", "gl_light_shadows=1", "gl_levelmesh=false"):
            self.assertEqual(config.count(line), 1)
        text = runner.script(Path("C:/normal"))
        self.assertNotIn("\n", text[:-1]); self.assertEqual(text.count("; bench;"), 5)
        self.assertIn("wait 350; pause; wait 60", text)
        self.assertNotIn("pf020view", text); self.assertNotIn("pf020vk", text)
        command = runner.command("C:/native/vkdoom.exe", {"iwad": {"path": "C:/inputs/Doom2.wad"}, "fixture": {"path": "C:/inputs/dense.wad"}}, Path("C:/normal"))
        self.assertFalse(any("pf020" in flag.lower() or "cfx" in flag.lower() for flag in command))
        bad = seed.replace("gl_light_shadows=1", "gl_light_shadows=0")
        with self.assertRaisesRegex(ValueError, "shadow policy"): runner.configuration(bad)

    def test_source_text_projection_preserves_binary_and_explicit_nul_nonutf8_bytes(self):
        for source in (b"normal\ntext\n", b"nul\0content\n", b"credits\xff\n"):
            self.assertEqual(runner.package_member_projection(source, source, source, "unset", "i/-text"), "raw-identical")
            self.assertEqual(runner.package_member_projection(source, source.replace(b"\n", b"\r\n"), source, "set", "i/-text"), "git-source-LF-to-CRLF")
        source = b"plain\ntext\n"
        self.assertEqual(runner.package_member_projection(source, source.replace(b"\n", b"\r\n"), source, "auto", "i/lf"), "git-source-LF-to-CRLF")

    def test_binary_semantic_partial_crlf_final_newline_and_current_export_changes_fail(self):
        source = b"one\ntwo\n"; projected = source.replace(b"\n", b"\r\n")
        for older, newer, attr, eol in ((projected, source, "unset", "i/lf"), (projected, source, "unspecified", "i/lf"),
            (projected, source, "auto", "i/-text"), (b"one\r\ntwo\n", source, "set", "i/lf"),
            (projected[:-2], source, "set", "i/lf"), (b"one\rtwo\r", source, "set", "i/lf"),
            (projected.replace(b"two", b"changed"), source, "set", "i/lf"), (source, projected, "set", "i/lf")):
            with self.subTest(older=older, attr=attr, eol=eol), self.assertRaises(ValueError):
                runner.package_member_projection(source, older, newer, attr, eol)

    def package_service(self, root):
        source_root = root / "build/source/current"; source_root.mkdir(parents=True)
        baseline, current, entries = {"artifacts": {}}, {"build": {}, "sourceDirectory": str(source_root)}, []
        for package, prefix in runner.PACKAGE_ROOTS.items():
            source = b"source\n"; path = source_root / prefix / "sample.txt"; path.parent.mkdir(parents=True); path.write_bytes(source)
            entries.append((prefix + "sample.txt", "100644", runner.view.derive.git_blob_id(source)))
            for label, destination, body in (("old", baseline["artifacts"], source.replace(b"\n", b"\r\n")), ("new", current["build"], source)):
                archive = root / "build" / (label + "-" + package)
                with zipfile.ZipFile(archive, "w") as zipper: zipper.writestr("sample.txt", body)
                destination[package] = runner.identity(archive)
        return baseline, current, entries

    def test_complete_package_table_member_and_source_closures_are_required(self):
        for mutation in (None, "missing-table", "missing-package", "extra-member", "duplicate-member", "case-alias", "traversal", "source-blob", "source-mode", "semantic-byte"):
            with tempfile.TemporaryDirectory() as temporary, patch.object(runner, "ROOT", Path(temporary)), patch.object(runner.view, "ROOT", Path(temporary)):
                root = Path(temporary); (root / "build").mkdir(); baseline, current, entries = self.package_service(root)
                attributes = {name: "set" for name, _, _ in entries}; eol = {name: "i/lf" for name, _, _ in entries}
                mappings = dict(runner.PACKAGE_ROOTS)
                package = next(iter(mappings)); archive = Path(current["build"][package]["path"])
                if mutation == "missing-table": mappings.pop(package)
                elif mutation == "missing-package": current["build"].pop(package)
                elif mutation in ("extra-member", "duplicate-member", "case-alias", "traversal"):
                    with zipfile.ZipFile(archive, "a") as zipper:
                        zipper.writestr({"extra-member": "extra.txt", "duplicate-member": "sample.txt", "case-alias": "SAMPLE.TXT", "traversal": "../sample.txt"}[mutation], b"extra\n")
                elif mutation == "source-blob": entries[0] = (entries[0][0], "100644", "f" * 40)
                elif mutation == "source-mode": entries[0] = (entries[0][0], "120000", entries[0][2])
                elif mutation == "semantic-byte":
                    with zipfile.ZipFile(archive, "w") as zipper: zipper.writestr("sample.txt", b"changed\n")
                with patch.object(runner, "PACKAGE_ROOTS", mappings), patch.object(runner.view.derive, "tree_entries", return_value=entries), \
                     patch.object(runner, "text_attributes", return_value=attributes), patch.object(runner, "index_text_classification", return_value=eol):
                    if mutation is None:
                        result = runner.package_equivalence(baseline, current)
                        self.assertEqual(result["memberCount"], 5); self.assertEqual(result["projectedTextMembers"], 5)
                        self.assertFalse(result["strictOneVariableComparison"]); self.assertFalse(result["rawMemberByteIdentical"])
                    else:
                        with self.subTest(mutation=mutation), self.assertRaises((ValueError, KeyError)): runner.package_equivalence(baseline, current)

    def test_quiet_observation_is_bounded_prelaunch_and_never_drops_a_sample(self):
        count = 0
        def sample():
            nonlocal count
            count += 1
            return count * 98, count * 100
        waits = []; result = runner.quiet_host(sample=sample, wait=waits.append)
        self.assertTrue(result["accepted"]); self.assertEqual(len(result["cpuPercent"]), 30); self.assertEqual(waits, [1] * 30)
        count = 0
        def spike():
            nonlocal count
            count += 1
            return count * 70, count * 100
        result = runner.quiet_host(sample=spike, wait=lambda _: None)
        self.assertFalse(result["accepted"]); self.assertEqual(len(result["cpuPercent"]), 30)
        with self.assertRaises(ValueError): runner.quiet_host(sample=lambda: (1, 1), wait=lambda _: None)

    def test_owned_normal_child_token_failure_records_pid_and_kills_only_that_child(self):
        class Child:
            pid = 123; code = None; killed = False; waited = False
            def poll(self): return self.code
            def kill(self): self.killed = True; self.code = -1
            def wait(self, timeout): self.waited = True; return self.code
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary); (out / "work").mkdir()
            c = {"directory": str(out), "argv": ["fixture"]}; receipt = {"output": str(out)}; process = Child()
            def query(pid):
                error = PermissionError("controlled token failure"); error.winerror = 5; raise error
            with self.assertRaises(PermissionError): runner.run_child(c, receipt, {}, popen=lambda *a, **k: process, token_query=query)
            self.assertEqual(c["pid"], 123); self.assertTrue(c["rendererStarted"])
            self.assertEqual(c["nativeTokenQueryError"]["winerror"], 5)
            self.assertTrue(process.killed and process.waited); self.assertEqual(c["exit"], -1)

    def test_owned_normal_child_watchdog_and_log_cap_close_the_actual_owned_handle(self):
        for mode in ("watchdog", "log-cap"):
            class Child:
                pid = 123; code = None; killed = False
                def poll(self): return self.code
                def kill(self): self.killed = True; self.code = -1
                def wait(self, timeout): raise subprocess.TimeoutExpired("fixture", timeout) if self.code is None else RuntimeError("unexpected wait")
            with tempfile.TemporaryDirectory() as temporary:
                out = Path(temporary); (out / "work").mkdir(); c = {"directory": str(out), "argv": ["fixture"]}; process = Child(); ticks = iter((0, 100))
                def popen(*a, **k):
                    if mode == "log-cap": (out / "stdout.log").write_bytes(b"x" * (17 * 1024 * 1024))
                    return process
                process.wait = lambda timeout: -1 if process.code is not None else None
                with self.assertRaisesRegex(ValueError, "watchdog|log cap"):
                    runner.run_child(c, {"output": str(out)}, {}, popen=popen, clock=lambda: next(ticks) if mode == "watchdog" else 0,
                                     token_query=lambda pid: {"pid": pid, "integrityRid": 8192, "elevated": False, "queryOnly": True})
                self.assertTrue(process.killed); self.assertEqual(c["exit"], -1)

    def test_fresh_output_and_mutated_phase_are_rejected_before_process(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(runner.view, "ROOT", Path(temporary)), patch.object(runner, "ROOT", Path(temporary)):
            root = Path(temporary); (root / "build/packet").mkdir(parents=True)
            with patch.object(runner.subprocess, "Popen") as native:
                with self.assertRaises(ValueError): runner.prepare({}, root / "build/packet")
                for status in ("RUNNING", "FAIL", "PASS_EXACT_EQUIVALENCE_WITH_CPU_SNAPSHOTS"):
                    with self.subTest(status=status), self.assertRaises(ValueError): runner.launch({"schema": runner.SCHEMA, "status": status, "rendererStarted": False})
                native.assert_not_called()

    def test_output_inventory_pins_empty_directories_and_rejects_link_aliases(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(runner.view, "ROOT", Path(temporary)):
            root = Path(temporary); out = root / "build/packet"; (out / "work").mkdir(parents=True); (out / "input.txt").write_text("safe")
            inventory = runner.output_inventory(out)
            self.assertEqual(inventory["work"], {"kind": "directory"}); self.assertIn("input.txt", inventory)
            with patch.object(runner.view, "safe_build", side_effect=ValueError("injected junction alias")):
                with self.assertRaises(ValueError): runner.output_inventory(out)

    def test_committed_package_index_identity_precedes_text_classification(self):
        name = "wadsrc/static/sample.txt"; oid = "a" * 40
        expected = {name: {"mode": "100644", "gitBlob": oid}}
        for mutation in (None, "mode", "blob", "stage", "duplicate", "missing-eol", "foreign-eol"):
            mode, actual_oid, stage = "100644", oid, "0"
            if mutation == "mode": mode = "120000"
            if mutation == "blob": actual_oid = "b" * 40
            if mutation == "stage": stage = "1"
            index = f"{mode} {actual_oid} {stage}\t{name}\0".encode()
            if mutation == "duplicate": index += index
            eol = b"" if mutation == "missing-eol" else ("i/lf w/lf attr/text=auto\t" +
                    ("wadsrc/static/other.txt" if mutation == "foreign-eol" else name) + "\0").encode()
            replies = [type("Reply", (), {"stdout": raw})() for raw in (index, eol)]
            with patch.object(runner.subprocess, "run", side_effect=replies):
                if mutation is None: self.assertEqual(runner.index_text_classification(expected), {name: "i/lf"})
                else:
                    with self.subTest(mutation=mutation), self.assertRaises(ValueError): runner.index_text_classification(expected)

    def test_agent_picture_review_requires_exact_actual_files_pixels_and_no_human_claim(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(runner.view, "ROOT", Path(temporary)):
            out = Path(temporary) / "build/packet"; out.mkdir(parents=True)
            receipt = {"output": str(out), "before": {"toolSource": {"commit": "f" * 40}}, "children": []}
            images = []
            for variant in ("accepted-master", "final-current"):
                child_out = out / variant; child_out.mkdir(); png = child_out / "scene.png"; png.write_bytes(b"controlled image bytes")
                receipt["children"].append({"directory": str(child_out), "variant": variant})
                images.append({"variant": variant, "png": runner.identity(png), "decodedRgbSha256": "a" * 64})
            review = {"schema": "pf020-final-dense-warmup-agent-review/v1", "status": "PASS", "inspector": "root-agent",
                      "humanApprovalClaimed": False, "toolHead": "f" * 40, "queryMessagesAbsent": True,
                      "benchmarkOverlayAbsent": True, "healthyFixtureVisible": True, "images": images}
            for mutation in (None, "schema", "status", "inspector", "humanApprovalClaimed", "toolHead", "queryMessagesAbsent",
                             "benchmarkOverlayAbsent", "healthyFixtureVisible", "images", "actual-file", "actual-pixels"):
                changed = copy.deepcopy(review); png = Path(receipt["children"][0]["directory"]) / "scene.png"
                if mutation == "actual-file": png.write_bytes(b"changed actual file")
                elif mutation in changed: changed[mutation] = True if mutation == "humanApprovalClaimed" else "invalid"
                runner.save(out / "warmup-image-review.json", changed)
                rgb = "b" * 64 if mutation == "actual-pixels" else "a" * 64
                with patch.object(runner.dense, "decode_png", return_value=(b"", {"decodedRgbSha256": rgb})):
                    if mutation is None: self.assertFalse(runner.warmup_picture_review(receipt)["humanApprovalClaimed"])
                    else:
                        with self.subTest(mutation=mutation), self.assertRaises(ValueError): runner.warmup_picture_review(receipt)
                png.write_bytes(b"controlled image bytes")

    def test_changed_order_scoring_or_diagnostics_fails_before_identity_and_popen(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(runner.view, "ROOT", Path(temporary)), patch.object(runner, "ROOT", Path(temporary)):
            root = Path(temporary); out = root / "build/packet"; out.mkdir(parents=True)
            recipe = {"schema": runner.SCHEMA, "status": "PREPARED", "rendererStarted": False, "output": str(out), "cwd": str(root),
                      "normalPolicy": runner.NORMAL, "clock": "ordinary-adaptive", "diagnostics": False, "validation": False,
                      "watchdogSeconds": runner.dense.WATCHDOG_SECONDS, "retainedSnapshotsPerScoredChild": 4, "rawBlocks": 60,
                      "scoredSnapshots": 40, "decodedComponentTolerance": 0, "quietPolicy": runner.QUIET_POLICY,
                      "agentWarmupPictureReviewRequired": True, "children": [{"variant": v, "pair": p} for v, p in runner.ORDER], "paths": {}}
            for mutation in (None, "normalPolicy", "clock", "diagnostics", "validation", "watchdogSeconds", "retainedSnapshotsPerScoredChild",
                             "rawBlocks", "scoredSnapshots", "decodedComponentTolerance", "quietPolicy", "agentWarmupPictureReviewRequired", "children"):
                changed = copy.deepcopy(recipe)
                if mutation is not None: changed[mutation] = [] if mutation == "children" else "altered"
                with patch.object(runner, "qualify", side_effect=ValueError("valid preregistration reached identity")) as qualify, \
                     patch.object(runner.subprocess, "Popen") as native:
                    with self.assertRaisesRegex(ValueError, "valid preregistration" if mutation is None else "order/settings/scoring"):
                        runner.launch(changed)
                    self.assertEqual(qualify.call_count, 1 if mutation is None else 0); native.assert_not_called()

    def test_complete_native_bridge_rejects_unreviewed_path_blob_hunk_or_live_byte(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(runner.view, "ROOT", Path(temporary)), patch.object(runner, "ROOT", Path(temporary)):
            root = Path(temporary); name = "src/source.cpp"; body = b"reviewed source\n"; raw = b"reviewed exact diff"
            frozen = root / "build/pf020-native/pf020-view-source-07/current" / name
            frozen.parent.mkdir(parents=True); frozen.write_bytes(body)
            live = root / name; live.parent.mkdir(parents=True); live.write_bytes(body)
            before = {name: {"mode": "100644", "gitBlob": "a" * 40}}
            after = {name: {"mode": "100644", "gitBlob": runner.view.derive.git_blob_id(body)}}
            for mutation in (None, "accepted", "tool", "unreviewed-path", "diff", "frozen", "live"):
                trees = [copy.deepcopy(before), copy.deepcopy(before), copy.deepcopy(after), copy.deepcopy(after)]
                if mutation == "accepted": trees[1][name]["gitBlob"] = "b" * 40
                if mutation == "tool": trees[3][name]["gitBlob"] = "b" * 40
                if mutation == "unreviewed-path":
                    for tree in trees[2:]: tree["tools/zipdir/unreviewed.cpp"] = dict(after[name])
                frozen.write_bytes(b"bad frozen\n" if mutation == "frozen" else body)
                live.write_bytes(b"bad live\n" if mutation == "live" else body)
                with patch.object(runner, "runtime_tree", side_effect=trees), patch.object(runner.view.derive, "git", return_value=b"bad diff" if mutation == "diff" else raw), \
                     patch.object(runner, "DELTA_PATHS", (name,)), patch.object(runner, "DELTA_BYTES", len(raw)), patch.object(runner, "DELTA_SHA256", runner.view.sha(raw)):
                    if mutation is None: self.assertTrue(runner.source_bridge("tool")["liveMatchesCurrentRuntime"])
                    else:
                        with self.subTest(mutation=mutation), self.assertRaises(ValueError): runner.source_bridge("tool")

    def test_pending_child_or_source_mutation_during_quiet_fails_before_popen(self):
        for mutation in ("live-config", "source"):
            with tempfile.TemporaryDirectory() as temporary, patch.object(runner.view, "ROOT", Path(temporary)), patch.object(runner, "ROOT", Path(temporary)):
                root = Path(temporary); (root / "build").mkdir(); seed = root / "build/seed.ini"; seed.write_text("controlled seed")
                before = {"packageEquivalence": {}, "builds": {v: {"artifacts": {"vkdoom.exe": {"path": v}}} for v, _ in runner.ORDER}, "inputs": {}}
                changed = False
                def qualify(paths): return {**before, "changed": True} if changed and mutation == "source" else before
                def quiet():
                    nonlocal changed
                    changed = True
                    if mutation == "live-config":
                        (Path(receipt["children"][0]["directory"]) / "fixture-live.ini").write_text("changed after quiet")
                    return {"accepted": True}
                with patch.object(runner, "qualify", side_effect=qualify), patch.object(runner, "configuration", return_value="controlled config\n"), \
                     patch.object(runner, "command", return_value=["controlled native command"]), patch.object(runner.dense, "health", return_value={}):
                    receipt = runner.prepare({"seed": str(seed)}, root / "build/packet")
                    with patch.object(runner.subprocess, "Popen") as native:
                        code = runner.launch(receipt, popen=native, quiet=quiet,
                                             token_query=lambda pid=None: {"pid": 123, "integrityRid": 8192, "elevated": False, "queryOnly": True})
                    self.assertEqual(code, 1); self.assertEqual(receipt["status"], "FAIL")
                    self.assertIn("Prepared normal child" if mutation == "live-config" else "during quiet", receipt["error"])
                    native.assert_not_called(); self.assertFalse(receipt["rendererStarted"])


if __name__ == "__main__": unittest.main()
