"""Bounded #110 runner controls; temporary files and fake children, never launches."""
from __future__ import annotations

from pathlib import Path
import configparser
import copy
import math
import re
import shlex
import subprocess
import struct
import sys
import tempfile
import unittest
import zlib
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle import run_indexed_material_runtime as runner
from tools.pf_oracle import prepare_indexed_material_runtime as generator


class FakeChild:
    pid = 41020

    def __init__(self, clock, exit_code=None, exit_on_wait=False):
        self.clock, self.exit_code, self.exit_on_wait = clock, exit_code, exit_on_wait
        self.kills = 0

    def poll(self):
        return self.exit_code

    def kill(self):
        self.kills += 1
        self.exit_code = 1

    def wait(self, timeout):
        if self.exit_code is not None:
            return self.exit_code
        if self.exit_on_wait:
            self.exit_code = 0
            return 0
        self.clock[0] += timeout
        raise subprocess.TimeoutExpired(["fake-owned-child"], timeout)


class IndexedRuntimeRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.out = Path(self.temporary.name)
        self.clock = [0.0]
        self.addCleanup(patch.stopall)
        patch.object(runner.time, "monotonic", side_effect=lambda: self.clock[0]).start()
        patch.object(runner.subprocess, "Popen", side_effect=AssertionError("Tests must never launch a child")).start()

    def logs(self, text, name="stdout.log"):
        (self.out / name).write_text(text, encoding="utf-8")

    def test_client_size_precedes_native_and_preview(self):
        script = runner.execution_script(self.out)
        self.assertLess(script.index("wait 105"), script.index("vid_setsize 640 480; wait 5"))
        self.assertLess(script.index("vid_setsize"), script.index("pf_indexedmaterial_validate"))
        self.assertLess(script.index("pf_indexedmaterial_validate"), script.index("pf110_overlay true"))
        self.assertLess(script.index("pf110_overlay true"), script.index("screenshot"))

    @staticmethod
    def exec_line_commands(line):
        # Syntax adapter only: native execution/ticks/GPU effects are not modelled.
        lexer = shlex.shlex(line, posix=True, punctuation_chars=";")
        lexer.whitespace_split = True
        lexer.commenters = ""
        commands = [[]]
        for token in lexer:
            if token == ";":
                commands.append([])
            else:
                commands[-1].append(token)
        return [command for command in commands if command]

    def test_waits_have_same_physical_line_continuations_including_queued_screenshot(self):
        lines = runner.execution_script(self.out).splitlines()
        self.assertEqual(len(lines), 1)
        commands = self.exec_line_commands(lines[0])
        waits = [(i, command) for i, command in enumerate(commands) if command[0] == "wait"]
        self.assertEqual([int(command[1]) for _, command in waits], [105, 5, 35, 35, 5])
        self.assertTrue(all(i < len(commands) - 1 for i, _ in waits))
        screenshot = next(i for i, command in enumerate(commands) if command[0] == "screenshot")
        self.assertEqual(commands[screenshot + 1:], [["wait", "5"], ["quit"]])
        self.assertEqual(commands[screenshot][1], runner.safe_console_path(self.out / "presentation.png"))

    def test_original_multiline_waits_do_not_have_deferred_remainders(self):
        original = 'pf110_overlay false\nwait 105\npf_indexedmaterial_validate "native"\nwait 5\n'
        original += 'pf110_overlay true\nwait 5\nscreenshot "presentation.png"\nwait 5\nquit\n'
        wait_lines = [self.exec_line_commands(line) for line in original.splitlines() if line.startswith("wait ")]
        self.assertEqual(len(wait_lines), 4)
        self.assertTrue(all(len(commands) == 1 for commands in wait_lines))

    def test_native_source_requires_wait_remainders_and_queues_screenshot(self):
        dispatch = (ROOT / "src/common/console/c_dispatch.cpp").read_text(encoding="utf-8")
        self.assertRegex(dispatch, re.compile(r"void FExecList::ExecCommands\(\) const\s*\{.*?"
                         r"for \(.*?Commands.Size\(\).*?AddCommandString\(Commands\[i\].GetChars\(\)\);", re.S))
        start = dispatch.index("if (tics > 0)")
        wait_branch = dispatch[start:dispatch.index("return;", start)]
        self.assertRegex(wait_branch, re.compile(r"if \(more\).*?new FWaitingCommand\(brkpt, tics, UnsafeExecutionContext\)", re.S))
        misc = (ROOT / "src/m_misc.cpp").read_text(encoding="utf-8")
        self.assertRegex(misc, re.compile(r"UNSAFE_CCMD \(screenshot\).*?G_ScreenShot \(argv\[1\]\);", re.S))
        game = (ROOT / "src/g_game.cpp").read_text(encoding="utf-8")
        self.assertRegex(game, re.compile(r"void G_ScreenShot \(const char \*filename\).*?"
                         r"if \(gameaction == ga_nothing\).*?shotfile = filename;.*?gameaction = ga_screenshot;", re.S))
        self.assertRegex(game, re.compile(r"case ga_screenshot:\s*M_ScreenShot \(shotfile.GetChars\(\)\);", re.S))

    def test_exec_line_bound_and_quoted_semicolon_path(self):
        with patch.object(runner, "safe_console_path", return_value="C:/fresh/quoted; path/result.png"):
            commands = self.exec_line_commands(runner.execution_script(self.out).strip())
        self.assertEqual(next(command[1] for command in commands if command[0] == "screenshot"),
                         "C:/fresh/quoted; path/result.png")
        with patch.object(runner, "safe_console_path", return_value="C:/" + "x" * 4096):
            with self.assertRaisesRegex(ValueError, "native parser's single-line bound"):
                runner.execution_script(self.out)

    def test_known_fixture_compile_error_aborts_only_own_child(self):
        self.logs('Script error, "pf110-indexed-material.pk3:zscript" line 1:\nUnexpected \';\'\n')
        child, receipt = FakeChild(self.clock), {}
        with self.assertRaisesRegex(ValueError, "fixture script compilation failed"):
            runner.wait_child(child, self.out, receipt, "pf110-indexed-material.pk3")
        self.assertEqual(child.kills, 1)
        self.assertEqual(receipt["startupAbort"]["pid"], child.pid)
        self.assertEqual(receipt["startupAbort"]["log"], "stdout.log")
        self.assertNotIn("watchdogAction", receipt)
        self.assertEqual(self.clock[0], 0)

    def test_error_header_across_chunk_boundary_on_exited_child(self):
        self.logs("x" * (64 * 1024 - 12) + '\nScript error, "pf110-indexed-material.pk3:zscript" line 9:\n')
        child, receipt = FakeChild(self.clock, exit_code=1), {}
        with self.assertRaisesRegex(ValueError, "compilation failed"):
            runner.wait_child(child, self.out, receipt, "pf110-indexed-material.pk3")
        self.assertEqual(child.kills, 0)
        self.assertEqual(receipt["startupAbort"]["action"], "own child already exited")

    def test_unrelated_errors_and_validation_messages_do_not_kill(self):
        self.logs('Script error, "other.pk3:zscript" line 1:\nValidation Error: synthetic VUID\n')
        child, receipt = FakeChild(self.clock, exit_on_wait=True), {}
        runner.wait_child(child, self.out, receipt, "pf110-indexed-material.pk3")
        self.assertEqual(child.kills, 0)
        self.assertEqual(receipt["exitCode"], 0)
        self.assertNotIn("startupAbort", receipt)

    def test_stderr_fixture_error_is_retained(self):
        self.logs('Script error, "PF110-INDEXED-MATERIAL.pk3:zscript" line 2:\n', "stderr.log")
        child, receipt = FakeChild(self.clock), {}
        with self.assertRaises(ValueError):
            runner.wait_child(child, self.out, receipt, "pf110-indexed-material.pk3")
        self.assertEqual(receipt["startupAbort"]["log"], "stderr.log")

    def test_watchdog_still_kills_only_own_child_at_limit(self):
        child, receipt = FakeChild(self.clock), {}
        with self.assertRaisesRegex(ValueError, "90-second child watchdog expired"):
            runner.wait_child(child, self.out, receipt, "pf110-indexed-material.pk3")
        self.assertEqual(self.clock[0], 90)
        self.assertEqual(child.kills, 1)
        self.assertEqual(receipt["watchdogAction"]["pid"], child.pid)
        self.assertNotIn("startupAbort", receipt)

    def package_fixture(self):
        build, inputs, paths = {}, {}, []
        for name in ("vkdoom.pk3", "game_support.pk3", "lights.pk3", "brightmaps.pk3", "game_widescreen_gfx.pk3"):
            path = self.out / name
            path.write_bytes(name.encode("ascii"))
            build[name] = runner.identity(path)
            paths.append(path)
        for key, name in (("iwad", "doom2.wad"), ("mod", "fixture.pk3")):
            path = self.out / name
            path.write_bytes(name.encode("ascii"))
            inputs[key] = runner.identity(path)
            paths.append(path)
        return {"build": build, "inputs": inputs}, paths

    def package_log(self, paths):
        self.logs("\n".join(f"adding {path.as_posix()}, {i + 1} lumps" for i, path in enumerate(paths)) + "\n")

    def test_actual_package_order_counts_and_hashes_are_verified(self):
        before, paths = self.package_fixture()
        self.package_log(paths)
        result = runner.loaded_package_evidence(self.out, before)
        self.assertTrue(result["verified"], result["errors"])
        self.assertEqual(result["packageCount"], 7)
        self.assertEqual([row["lumps"] for row in result["orderedPackages"]], list(range(1, 8)))
        self.assertEqual([row["path"] for row in result["orderedPackages"]], [str(path) for path in paths])
        self.assertTrue(all(row["pinned"] and len(row["sha256"]) == 64 for row in result["orderedPackages"]))

    def test_unpinned_sidecar_is_hashed_and_rejected(self):
        before, paths = self.package_fixture()
        sidecar = self.out / "extras.wad"
        sidecar.write_bytes(b"unapproved-sidecar")
        self.package_log(paths + [sidecar])
        result = runner.loaded_package_evidence(self.out, before)
        self.assertFalse(result["verified"])
        self.assertTrue(any("Unpinned loaded package" in error for error in result["errors"]))
        self.assertFalse(result["orderedPackages"][-1]["pinned"])
        self.assertEqual(result["orderedPackages"][-1]["sha256"], runner.digest(sidecar))

    def test_duplicate_package_is_rejected(self):
        before, paths = self.package_fixture()
        self.package_log(paths + paths[:1])
        result = runner.loaded_package_evidence(self.out, before)
        self.assertFalse(result["verified"])
        self.assertTrue(any("Duplicate loaded package" in error for error in result["errors"]))

    def test_supplied_startup_text_is_explicit_and_default_keeps_whole_log_duplicate_rejection(self):
        before, paths = self.package_fixture()
        one = "\n".join(f"adding {path.as_posix()}, {i + 1} lumps" for i, path in enumerate(paths)) + "\n"
        self.logs(one + one)
        self.assertFalse(runner.loaded_package_evidence(self.out, before)["verified"])
        self.assertTrue(runner.loaded_package_evidence(self.out, before, startup_text=one)["verified"])
        self.assertFalse(runner.loaded_package_evidence(self.out, before, startup_text=one + one)["verified"])

    def test_missing_required_package_is_rejected(self):
        before, paths = self.package_fixture()
        self.package_log(paths[1:])
        result = runner.loaded_package_evidence(self.out, before)
        self.assertFalse(result["verified"])
        self.assertTrue(any("not observed loading" in error for error in result["errors"]))

    def test_changed_loaded_bytes_are_rejected(self):
        before, paths = self.package_fixture()
        paths[-1].write_bytes(b"changed after preparation")
        self.package_log(paths)
        result = runner.loaded_package_evidence(self.out, before)
        self.assertFalse(result["verified"])
        self.assertTrue(any("differs from its pinned identity" in error for error in result["errors"]))

    def test_native_filter_requires_actual_integer_selected_case(self):
        case = {"globalFilter": 0}
        self.assertTrue(runner.native_filter_evidence({"globalTextureFilter": 0}, case)["verified"])
        for observed in (2, None, "0", False):
            self.assertFalse(runner.native_filter_evidence({"globalTextureFilter": observed}, case)["verified"])

    def test_saved_exit_settings_are_observed_and_checked(self):
        (self.out / "fixture-live.ini").write_text("[GlobalSettings]\nvid_rendermode=4\ngl_texture_filter=2\n", encoding="utf-8")
        case = {"rendererMode": 4, "globalFilter": 2}
        result = runner.exit_settings_evidence(self.out, case)
        self.assertTrue(result["verified"])
        self.assertEqual(result["observed"], {"vid_rendermode": 4, "gl_texture_filter": 2})
        self.assertFalse(runner.exit_settings_evidence(self.out, {**case, "globalFilter": 0})["verified"])
        self.assertIn("does not prove per-draw", result["scope"])

    def test_missing_or_duplicate_saved_settings_fail_closed(self):
        path = self.out / "fixture-live.ini"
        path.write_text("[GlobalSettings]\nvid_rendermode=4\n", encoding="utf-8")
        with self.assertRaises(configparser.NoOptionError):
            runner.exit_settings_evidence(self.out, {"rendererMode": 4, "globalFilter": 0})
        path.write_text("[GlobalSettings]\nvid_rendermode=4\ngl_texture_filter=0\ngl_texture_filter=2\n", encoding="utf-8")
        with self.assertRaises(configparser.DuplicateOptionError):
            runner.exit_settings_evidence(self.out, {"rendererMode": 4, "globalFilter": 0})

    def test_engine_repeated_search_paths_do_not_hide_actual_global_settings(self):
        path = self.out / "fixture-live.ini"
        path.write_text("[IWADSearch.Directories]\nPath=.\nPath=$DOOMWADDIR\nPath=$HOME\n"
                        "[FileSearch.Directories]\nPath=$PROGDIR\nPath=.\n"
                        "[GlobalSettings]\nvid_rendermode=4\ngl_texture_filter=0\n"
                        "[GlobalSettings.Unknown]\nvid_rendermode=0\ngl_texture_filter=2\n",
                        encoding="utf-8")
        result = runner.exit_settings_evidence(self.out, {"rendererMode": 4, "globalFilter": 0})
        self.assertTrue(result["verified"])
        self.assertEqual(result["observed"], {"vid_rendermode": 4, "gl_texture_filter": 0})

    def test_critical_duplicates_and_duplicate_global_sections_are_rejected(self):
        path = self.out / "fixture-live.ini"
        case = {"rendererMode": 4, "globalFilter": 0}
        path.write_text("[GlobalSettings]\nvid_rendermode=4\nVID_RENDERMODE=4\ngl_texture_filter=0\n", encoding="utf-8")
        with self.assertRaises(configparser.DuplicateOptionError):
            runner.exit_settings_evidence(self.out, case)
        path.write_text("[GlobalSettings]\nvid_rendermode=4\ngl_texture_filter=0\n"
                        "[GlobalSettings]\nvid_rendermode=4\ngl_texture_filter=0\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate saved GlobalSettings section"):
            runner.exit_settings_evidence(self.out, case)

    def test_default_or_other_section_values_cannot_supply_missing_globals(self):
        path = self.out / "fixture-live.ini"
        path.write_text("[DEFAULT]\nvid_rendermode=4\ngl_texture_filter=0\n[GlobalSettings]\n", encoding="utf-8")
        with self.assertRaises(configparser.NoOptionError):
            runner.exit_settings_evidence(self.out, {"rendererMode": 4, "globalFilter": 0})

    def test_information_statuspath_is_not_a_validation_error(self):
        self.logs("Validation Layer Info - Logging validation error to C:/fresh/validation.log\n")
        self.logs('[Vulkan Loader] INFO | LAYER: Insert instance layer "VK_LAYER_KHRONOS_validation"\n'
                  '[Vulkan Loader] WARNING | LAYER: Registry lookup failed to get layer manifest files.\n', "stderr.log")
        self.logs("Validation Information: [ CURRENT-VALIDATION-ENABLED ] | MessageID = 0xfd7b2292\n"
                  "vkCreateInstance(): Current Validaiton Enabled:\n  - Core Checks\n\n", "validation.log")
        result = runner.validation_evidence(self.out, "core")
        self.assertTrue(result["requestedModeVerified"])
        self.assertEqual(result["errorCount"], 0)
        self.assertEqual(result["warningCount"], 0)

    def test_actual_layer_errors_and_warnings_remain_failures(self):
        self.logs("Validation Layer Info - Logging validation error to C:/fresh/validation.log\n"
                  "[vulkan error] a definite callback error with no VUID\n"
                  "Validation Layer Warning - actual warning\n")
        self.logs("Validation Error: [ VUID-vkCmdCopyImage-imageLayout-00128 ] | invalid layout\n"
                  "Validation Warning: [ UNASSIGNED-CoreValidation-Shader-OutputNotConsumed ] | unused output\n"
                  "ERROR: non-VUID validation error\nWARNING: non-VUID validation warning\n", "validation.log")
        self.logs("ERROR | SYNC-HAZARD-WRITE-AFTER-READ actual hazard\n", "stderr.log")
        result = runner.validation_evidence(self.out, "core")
        self.assertEqual(result["errorCount"], 4)
        self.assertEqual(result["warningCount"], 3)
        self.assertFalse(any("Logging validation error to" in row["line"] for row in result["errors"]))

    def test_severity_must_be_a_header_not_information_body_text(self):
        for line in ("Validation Information: previously observed ERROR VUID-example",
                     "Validation Layer Info - Logging validation error to path/WARNING-VUID-example",
                     "INFO: example text Validation Error: [VUID-example]"):
            self.assertIsNone(runner.validation_severity(line, "stdout.log"))

    @staticmethod
    def material_controls():
        rows = [{"name": name, "control": control, "indexed": True, "pixelOracleApplied": True, "pixelMismatches": 0}
                for name, control in (("indexed-alpha-half-opaque", "public-alpha-half-inherited-opaque"),
                    ("indexed-colour-tag", "public-colour-command-luminance-white-vertex"),
                    ("indexed-object-add-colour", "actual-getTexel-add-object-before-palette"))]
        rows[0].update(publicAlpha=0.5, whiteVertexColour=True)
        rows[1].update(publicColor=0xff285aaa, whiteVertexColour=True)
        rows[2].update(addRedByte=16, objectRedByte=128, changedPixels=40, rejectedOrderingPixels=30)
        return rows

    def test_actual_material_mode_and_controls_are_required(self):
        rows, case = self.material_controls(), {"rendererMode": 4}
        result = runner.native_participation_evidence({"rendererMode": 4}, case, rows)
        self.assertEqual(result["rendererMode"], 4)
        with self.assertRaisesRegex(ValueError, "renderer mode differs"):
            runner.native_participation_evidence({"rendererMode": 0}, case, rows)
        with self.assertRaisesRegex(ValueError, "missing or failed"):
            runner.native_participation_evidence({"rendererMode": 4}, case, rows[:-1])
        rows[-1]["rejectedOrderingPixels"] = 0
        with self.assertRaisesRegex(ValueError, "ordering witness"):
            runner.native_participation_evidence({"rendererMode": 4}, case, rows)

    def test_hardware_case_cannot_claim_software_producers(self):
        data = {"softwareCanvas": {"required": False, "observed": False, "actualMode": 4}}
        case = {"rendererMode": 4, "extent": [640, 480]}
        self.assertEqual(runner.software_canvas_evidence(self.out, data, case, [])["artifacts"], {})
        data["softwareCanvas"]["observed"] = True
        with self.assertRaisesRegex(ValueError, "unexpectedly claimed"):
            runner.software_canvas_evidence(self.out, data, case, [])

    def software_fixture(self):
        # Parser-only synthetic bytes, never presented as real software/GPU output.
        records = []
        for i in range(2):
            stem = self.out / f"native-software-existing-swcanvas-{i}"
            record = {"ownerPointer": str(100 + i), "materialPointer": str(200 + i),
                "sourceName": "", "sourceScaleFlags": 0, "wrapperColorFormat": 0, "layerCount": 2,
                "width": 640, "height": 480, "indexImage": str(300 + i), "indexView": str(400 + i),
                "paletteImage": "500", "paletteView": "600", "trackedBaseLayout": 1, "trackedPaletteLayout": 5,
                "nativeOffsetBytes": 0, "nativeRowPitchBytes": 640, "producerPitchBytes": 640,
                "pitchMatchesProducer": True, "mappedReadAfterNormalFence": True, "mappedImageTransferred": False,
                "indexedAuxiliaryImagesAbsent": True, "indexedPaletteDescriptorAbsent": True,
                "artifactStem": str(stem), "mappedBytes": 640 * 480, "paletteBytes": 1024,
                "tokens": [{"index": 3000 + 2 * i, "generation": 1, "epoch": 2, "span": 2, "live": True}]}
            Path(str(stem) + ".mapped-r8").write_bytes(bytes(record["mappedBytes"]))
            Path(str(stem) + ".resident-palette-bgra8").write_bytes(bytes(1024))
            records.append(record)
        counts = {"materials": 4, "hardwareTextures": 8, "gameTextures": 12, "descriptorEntries": 6}
        software = {"required": True, "observed": True, "actualMode": 0, "ownerCount": 2, "registryUnchanged": True,
            "hostPixelsWritten": False, "producerCreationPerformed": False, "softwareDrawPerformedByDiagnostic": False,
            "before": counts, "after": dict(counts), "mappedMemoryContract": "producer flags are not independently queried",
            "records": records}
        observer = {"name": "software-existing-swcanvas", "descriptorOnly": True,
                    "shaderResultClaimed": False, "observerOnly": True, **software}
        return {"softwareCanvas": software}, {"rendererMode": 0, "extent": [640, 480]}, [observer]

    def test_mode0_observer_hashes_both_actual_record_artifact_shapes(self):
        data, case, cases = self.software_fixture()
        result = runner.software_canvas_evidence(self.out, data, case, cases)
        self.assertEqual(len(result["artifacts"]), 4)
        self.assertTrue(all(len(row["sha256"]) == 64 for row in result["artifacts"].values()))
        self.assertIn("no software shader-result equivalence", result["scope"])
        self.assertIn("tracked CPU state", result["scope"])

    def test_mode0_missing_or_fabricated_producer_state_fails(self):
        data, case, cases = self.software_fixture()
        mutations = (
            lambda software: software.update(observed=False),
            lambda software: software["after"].update(hardwareTextures=9),
            lambda software: software.update(producerCreationPerformed=True),
            lambda software: software["records"][0].update(mappedImageTransferred=True),
            lambda software: software["records"][0].update(nativeOffsetBytes=16),
            lambda software: software["records"][0].update(nativeRowPitchBytes=1024),
            lambda software: software["records"][0].update(sourceScaleFlags=4),
            lambda software: software["records"][0]["tokens"][0].update(live=False),
            lambda software: software["records"][1].update(ownerPointer=software["records"][0]["ownerPointer"]),
        )
        for mutate in mutations:
            candidate = copy.deepcopy(data)
            mutate(candidate["softwareCanvas"])
            observer = {**cases[0], **candidate["softwareCanvas"]}
            with self.assertRaises(ValueError):
                runner.software_canvas_evidence(self.out, candidate, case, [observer])
        with self.assertRaisesRegex(ValueError, "metadata is inconsistent"):
            runner.software_canvas_evidence(self.out, data, case, [])

    def test_mode0_missing_or_wrong_size_artifacts_fail(self):
        data, case, cases = self.software_fixture()
        path = Path(data["softwareCanvas"]["records"][0]["artifactStem"] + ".mapped-r8")
        path.write_bytes(b"short")
        with self.assertRaisesRegex(ValueError, "artifact size"):
            runner.software_canvas_evidence(self.out, data, case, cases)
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            runner.software_canvas_evidence(self.out, data, case, cases)

    @staticmethod
    def png_chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xffffffff)

    @classmethod
    def png_bytes(cls, pixels, modes=(0,), compression=6, extra=b"", ihdr=None):
        # Independent PNG writer used for CPU decoder controls, never native evidence.
        ihdr = ihdr or struct.pack(">IIBBBBB", 640, 480, 8, 2, 0, 0, 0)
        rows, previous = bytearray(), bytes(640 * 3)
        for y in range(480):
            row = pixels[y * 1920:(y + 1) * 1920]
            mode = modes[y % len(modes)]
            encoded = bytearray()
            for i, value in enumerate(row):
                a, b, c = (row[i - 3] if i >= 3 else 0), previous[i], (previous[i - 3] if i >= 3 else 0)
                if mode == 4:
                    p = a + b - c
                    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                    predictor = a if pa <= pb and pa <= pc else b if pb <= pc else c
                else:
                    predictor = (0, a, b, (a + b) // 2)[mode]
                encoded.append((value - predictor) % 256)
            rows.extend(bytes((mode,)) + encoded)
            previous = row
        return (b"\x89PNG\r\n\x1a\n" + cls.png_chunk(b"IHDR", ihdr)
                + cls.png_chunk(b"IDAT", zlib.compress(rows, compression)) + cls.png_chunk(b"IEND", b"") + extra)

    def presentation_fixture(self):
        # Synthetic parser/relationship positive: colours are generated locally,
        # contain no IWAD bytes, and are not presented as GPU or visual evidence.
        manifest = {"rois": generator.roi_metadata(), "scene": {"roomStrip": [0, 404, 640, 76]},
                    "syntheticInput": {"width": generator.WIDTH, "height": generator.HEIGHT,
                                       "rowMajorIndices": list(generator.INDEX_ROW) * generator.HEIGHT}}
        case = {"rendererMode": 4, "globalFilter": 0}
        pixels = bytearray(bytes((16, 16, 16)) * (640 * 480))
        indices = generator.INDEX_ROW
        a = tuple(generator.REMAP_A.get(n, n) for n in indices)
        b = tuple(generator.REMAP_B.get(n, n) for n in indices)
        inverse = tuple(255 - n for n in a)
        rejected = tuple(generator.REMAP_A.get(255 - n, 255 - n) for n in indices)
        rows = {"neutral-indexed": indices, "neutral-ordinary": indices, "neutral-flat": indices,
                "a-first-A": a, "a-first-B": b, "a-repeat-A": a, "b-first-B": b, "b-first-A": a, "b-repeat-B": b,
                "inverse-A": inverse, "inverse-reference": inverse, "rejected-row-order-model": rejected,
                "tinted-indexed-A": a, "tinted-reference": a, "ordinary-red-is-alpha": indices,
                "boundary-indexed-A": a, "boundary-reference": a, "boundary-flat": indices,
                "ordinary-translation-A": a, "indexed-translucent-A": a}

        def colour(n):
            return bytes((40 + n * 53 % 200, 40 + n * 71 % 200, 40 + n * 97 % 200))

        for roi in manifest["rois"]:
            name = roi["name"]
            if name == "missing-input":
                continue
            x, y, _, height = roi["rect"]
            source_width = 64 if name in ("neutral-flat", "boundary-flat") else 16
            origin, width = (x + .25, 127.5) if name.startswith("boundary-") else (x, 128)
            for yy in range(y, y + height):
                for xx in range(x, x + 128):
                    lane = int((xx + .5 - origin) * source_width / width) % 16
                    offset = (yy * 640 + xx) * 3
                    pixels[offset:offset + 3] = colour(rows[name][lane])
        ack = "PF110_OVERLAY_READY mode=4 filter=0 extent=640x480 frames=2\n"
        return manifest, case, pixels, ack

    def presentation(self, pixels, manifest, case, ack):
        path = self.out / "presentation.png"
        path.write_bytes(self.png_bytes(pixels))
        return runner.screenshot_evidence(path, manifest, case, ack)

    def test_source_linked_rgb_png_and_roi_contract(self):
        png_source = (ROOT / "src/common/textures/m_png.cpp").read_text(encoding="utf-8")
        render_source = (ROOT / "src/common/rendering/vulkan/vk_renderdevice.cpp").read_text(encoding="utf-8")
        self.assertIn("ihdr->BitDepth = 8;", png_source)
        self.assertIn("color_type == SS_PAL ? 3 : 2", png_source)
        self.assertIn("ihdr->Interlace = 0;", png_source)
        self.assertIn("color_type = SS_RGB;", render_source)
        manifest, _, _, _ = self.presentation_fixture()
        self.assertEqual(len(runner.presentation_contract(manifest)), 21)
        # The production flat repeats the16-index row four times across64 texels.
        flat = generator.members()["flats/PF110FL.lmp"]
        self.assertEqual(flat[:64], bytes(generator.INDEX_ROW * 4))
        self.assertEqual(len(flat), 64 * 64)

    def test_source_linked_batch_boundary_and_overlay_acknowledgement(self):
        constants = (ROOT / "src/common/engine/i_net.h").read_text(encoding="utf-8")
        net = (ROOT / "src/d_net.cpp").read_text(encoding="utf-8")
        self.assertRegex(constants, r"BACKUPTICS\s*=\s*36\s*,")
        self.assertIn("(maketic - gametic) / ticdup >= BACKUPTICS/2-1", net)
        self.assertIn("pf110_overlay_frames", generator.zscript())
        self.assertIn("PF110_OVERLAY_READY mode=%d filter=%d extent=640x480 frames=2", generator.zscript())
        commands = self.exec_line_commands(runner.execution_script(self.out))
        raw = next(i for i, command in enumerate(commands) if command[0] == "pf_indexedmaterial_validate")
        enabled = commands.index(["pf110_overlay", "true"])
        self.assertEqual(commands[raw + 1], ["wait", "35"])
        self.assertEqual(commands[enabled + 1], ["wait", "35"])

    def test_repeat_inset_catches_wrong_pixel_between_declared_sample_centres(self):
        manifest, case, pixels, ack = self.presentation_fixture()
        # Centre lanes/vertical probes remain untouched; a corrupted repeat's
        # actual inset is still rejected instead of accepting only16 samples.
        offset = (110 * 640 + 450) * 3
        pixels[offset:offset + 3] = bytes((255, 0, 0))
        evidence = self.presentation(pixels, manifest, case, ack)
        self.assertEqual(evidence["status"], "FAIL")
        comparison = next(check for check in evidence["checks"] if check["name"] == "a-first-A==a-repeat-A")
        self.assertFalse(comparison["pass"])
        self.assertTrue(comparison["fullInsetCompared"])

    def test_true_png_compression_and_all_five_filter_types_decode_exactly(self):
        _, _, pixels, _ = self.presentation_fixture()
        path = self.out / "presentation.png"
        for compression, modes in ((0, (0,)), (9, (0, 1, 2, 3, 4))):
            with self.subTest(compression=compression):
                path.write_bytes(self.png_bytes(pixels, modes, compression))
                decoded, evidence = runner.decode_screenshot_png(path)
                self.assertEqual(decoded, bytes(pixels))
                self.assertEqual(evidence["rowFiltersObserved"], sorted(set(modes)))
                self.assertEqual(evidence["decodedBytes"], 640 * 480 * 3)

    def test_png_rejects_header_only_truncated_crc_invalid_and_trailing_data(self):
        _, _, pixels, _ = self.presentation_fixture()
        good = self.png_bytes(pixels)
        bad_crc = bytearray(good)
        bad_crc[29] ^= 1
        bad_zlib = good[:33] + self.png_chunk(b"IDAT", b"not-zlib") + self.png_chunk(b"IEND", b"")
        for data in (good[:24], good[:-12], bytes(bad_crc), bad_zlib, good + b"trailing"):
            with self.subTest(length=len(data)):
                path = self.out / "presentation.png"
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    runner.decode_screenshot_png(path)

    def test_png_rejects_expansion_extra_stream_interlace_and_invalid_filter(self):
        _, _, pixels, _ = self.presentation_fixture()
        header = b"\x89PNG\r\n\x1a\n" + self.png_chunk(b"IHDR", struct.pack(">IIBBBBB", 640, 480, 8, 2, 0, 0, 0))
        trailer = self.png_chunk(b"IEND", b"")
        count = 480 * 1921
        variants = (header + self.png_chunk(b"IDAT", zlib.compress(bytes(count + 1))) + trailer,
                    header + self.png_chunk(b"IDAT", zlib.compress(bytes(count)) + zlib.compress(b"extra")) + trailer,
                    self.png_bytes(pixels, ihdr=struct.pack(">IIBBBBB", 640, 480, 8, 2, 0, 0, 1)),
                    header + self.png_chunk(b"IDAT", zlib.compress(bytes((5,)) + bytes(count - 1))) + trailer)
        for data in variants:
            path = self.out / "presentation.png"
            path.write_bytes(data)
            with self.assertRaises(ValueError):
                runner.decode_screenshot_png(path)

    def test_valid_source_declared_presentation_passes_all_six_mode_filter_cases(self):
        manifest, _, pixels, _ = self.presentation_fixture()
        for mode in (4, 2, 0):
            for filtering in (0, 2):
                case = {"rendererMode": mode, "globalFilter": filtering}
                ack = f"PF110_OVERLAY_READY mode={mode} filter={filtering} extent=640x480 frames=2\n"
                with self.subTest(mode=mode, filtering=filtering):
                    evidence = self.presentation(pixels, manifest, case, ack)
                    self.assertEqual(evidence["status"], "PASS", [check for check in evidence["checks"] if not check["pass"]])
                    self.assertEqual(len(evidence["rois"]), 21)
                    self.assertTrue(all(len(roi["rgbSha256"]) == 64 for roi in evidence["rois"].values()))
                    self.assertIn("no raw-to-presentation", evidence["scope"])

    def test_blank_and_room_like_wrong_screenshots_fail_presence_not_only_equalities(self):
        manifest, case, _, ack = self.presentation_fixture()
        for pixels in (bytes((16, 16, 16)) * (640 * 480), bytes((80, 35, 20)) * (640 * 480)):
            evidence = self.presentation(pixels, manifest, case, ack)
            self.assertEqual(evidence["status"], "FAIL")
            self.assertTrue(any(not check["pass"] and "lane-shape" in check["name"] for check in evidence["checks"]))

    def test_wrong_roi_first_use_inverse_colour_and_alpha_mutants_fail(self):
        manifest, case, good, ack = self.presentation_fixture()
        rectangles = {roi["name"]: roi["rect"] for roi in manifest["rois"]}
        for target, source in (("a-repeat-A", "a-first-B"), ("inverse-A", "rejected-row-order-model"),
                               ("tinted-reference", "a-first-B"), ("indexed-translucent-A", "a-first-B"),
                               ("missing-input", "a-first-A"), ("neutral-flat", "neutral-indexed")):
            pixels = bytearray(good)
            x, y, width, height = rectangles[target]
            sx, sy, _, _ = rectangles[source]
            for dy in range(height):
                pixels[((y + dy) * 640 + x) * 3:((y + dy) * 640 + x + width) * 3] = good[((sy + dy) * 640 + sx) * 3:((sy + dy) * 640 + sx + width) * 3]
            with self.subTest(target=target):
                evidence = self.presentation(pixels, manifest, case, ack)
                self.assertEqual(evidence["status"], "FAIL")

    def test_ack_missing_duplicate_or_wrong_case_rejects_valid_pixels(self):
        manifest, case, pixels, ack = self.presentation_fixture()
        for observed in ("", ack + ack, ack.replace("mode=4", "mode=0"), ack.replace("frames=2", "frames=1")):
            evidence = self.presentation(pixels, manifest, case, observed)
            self.assertEqual(evidence["status"], "FAIL")
            self.assertFalse(evidence["acknowledgement"]["verified"])

    def test_roi_metadata_cannot_hide_missing_or_changed_panel(self):
        manifest, case, pixels, ack = self.presentation_fixture()
        for mutate in (lambda m: m["rois"].pop(), lambda m: m["rois"][0]["rect"].__setitem__(0, 121),
                       lambda m: m["syntheticInput"]["rowMajorIndices"].__setitem__(0, 6)):
            candidate = copy.deepcopy(manifest)
            mutate(candidate)
            with self.assertRaises(ValueError):
                self.presentation(pixels, candidate, case, ack)

    def filtered_ordinary_fixture(self):
        manifest, case, good, _ = self.presentation_fixture()
        pixels = bytearray(good)
        # CPU texture-sampling control: standard linear interpolation between
        # neighbouring source texel centres, only for production ordinary panels.
        # This models the retained sampler semantics, not native image evidence.
        for roi in manifest["rois"]:
            if roi["name"] not in runner.PRESENTATION_ORDINARY:
                continue
            x, y, width, height = roi["rect"]
            origin, extent = (x + .25, 127.5) if roi["name"] == "boundary-reference" else (x, 128)
            colours = [good[(y * 640 + x + 4 + i * 8) * 3:(y * 640 + x + 4 + i * 8) * 3 + 3] for i in range(16)]
            for xx in range(x, x + width):
                u = (xx + .5 - origin) * 16 / extent - .5
                lane = math.floor(u)
                fraction = u - lane
                left, right = colours[max(0, min(15, lane))], colours[max(0, min(15, lane + 1))]
                rgb = bytes(round(a * (1 - fraction) + b * fraction) for a, b in zip(left, right))
                for yy in range(y, y + height):
                    offset = (yy * 640 + xx) * 3
                    pixels[offset:offset + 3] = rgb
        case["globalFilter"] = 2
        return manifest, case, pixels, "PF110_OVERLAY_READY mode=4 filter=2 extent=640x480 frames=2\n"

    def test_source_linked_linear_ordinary_and_discrete_inverse_reference_contract(self):
        samplers = (ROOT / "src/common/rendering/vulkan/samplers/vk_samplers.cpp").read_text(encoding="utf-8")
        material = (ROOT / "src/common/rendering/vulkan/textures/vk_hwtexture.cpp").read_text(encoding="utf-8")
        self.assertIn(".MagFilter(TexFilter[filter].magFilter)", samplers)
        nearest = samplers[samplers.index("for (int i = CLAMP_NOFILTER;"):samplers.index("mSamplers[CLAMP_CAMTEX]")]
        self.assertIn(".MagFilter(VK_FILTER_NEAREST)", nearest)
        self.assertIn(".MinFilter(VK_FILTER_NEAREST)", nearest)
        self.assertIn("if (state.mPaletteMode || indexedMaterial)", material)
        self.assertIn("clampmode = CLAMP_NOFILTER_XY", material)
        self.assertIn('Panel("PF110IA", 284, 204, true, 0);', generator.zscript())
        self.assertNotIn("inverse-reference", runner.PRESENTATION_ORDINARY)

    def test_filtered_ordinary_samples_reproduce_old_false_gate_without_weakening_indexed(self):
        manifest, case, pixels, ack = self.filtered_ordinary_fixture()
        old_case = {**case, "globalFilter": 0}
        old = self.presentation(pixels, manifest, old_case, ack.replace("filter=2", "filter=0"))
        self.assertEqual(old["status"], "FAIL")
        self.assertTrue(any(not check["pass"] and check.get("equalPairedLanes") is False for check in old["checks"]))
        self.assertTrue(any(not check["pass"] and check.get("maximumDifference", 0) > 1 for check in old["checks"]))
        corrected = self.presentation(pixels, manifest, case, ack)
        self.assertEqual(corrected["status"], "PASS", [item for item in corrected["checks"] if not item["pass"]])
        self.assertEqual(corrected["maximumRgbDifference"], 1)
        self.assertEqual(len(corrected["ordinaryFilteredObservations"]), 3)
        self.assertTrue(all(row["maximumDifference"] > 1 for row in corrected["ordinaryFilteredObservations"]))
        inverse = next(row for row in corrected["checks"] if row["name"] == "inverse-A==inverse-reference")
        self.assertTrue(inverse["pass"])

    def test_linear_ordinary_diversity_and_vertical_still_reject_blank_and_wrong_rows(self):
        manifest, case, good, ack = self.filtered_ordinary_fixture()
        for blank in (True, False):
            pixels = bytearray(good)
            for yy in (range(54, 74) if blank else (58,)):
                for xx in range(284, 412):
                    offset = (yy * 640 + xx) * 3
                    pixels[offset:offset + 3] = bytes((16, 16, 16))
            evidence = self.presentation(pixels, manifest, case, ack)
            self.assertEqual(evidence["status"], "FAIL")
            control = next(item for item in evidence["checks"] if item["name"] == "neutral-ordinary-authored-lane-shape")
            self.assertFalse(control["pass"])

    def test_linear_filter_keeps_indexed_first_use_and_inverse_mutants_hard_failures(self):
        manifest, case, good, ack = self.filtered_ordinary_fixture()
        rectangles = {roi["name"]: roi["rect"] for roi in manifest["rois"]}
        for target, source in (("a-repeat-A", "a-first-B"), ("inverse-A", "rejected-row-order-model")):
            pixels = bytearray(good)
            x, y, width, height = rectangles[target]
            sx, sy, _, _ = rectangles[source]
            for dy in range(height):
                pixels[((y + dy) * 640 + x) * 3:((y + dy) * 640 + x + width) * 3] = good[((sy + dy) * 640 + sx) * 3:((sy + dy) * 640 + sx + width) * 3]
            self.assertEqual(self.presentation(pixels, manifest, case, ack)["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
