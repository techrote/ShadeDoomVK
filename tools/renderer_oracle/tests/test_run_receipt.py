"""Synthetic end-to-end receipt controls; no executable/rendering evidence.

Preparation uses the real authored lights-zero fixture. The executable, IWAD,
engine package, logs, observations and PNG are explicitly synthetic test data.
Only that synthetic executable is mocked; real Git verification still runs.
"""
import argparse
import copy
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
sys.path.insert(0, str(TESTS.parent))
import common
import prepare
import run
from test_evidence import png
from test_validation import observation, recount, row


class SyntheticRunReceiptTests(unittest.TestCase):
    def test_device_errors_in_either_stream_override_successful_completion(self):
        complete = "SDVK_OBSERVATION_COLLECTED: native.renderer.json\n"
        for marker in ("[vulkan error] invalid descriptor", "Validation Error: VUID-123",
                       "[fault] type=4 address=0x123", "VK_ERROR_DEVICE_LOST",
                       "device lost", "device-lost", "Fatal error: stopped"):
            for stream in ("stdout", "stderr"):
                with self.subTest(marker=marker, stream=stream), self.assertRaisesRegex(common.EvidenceError, stream):
                    run.completion_log(complete + (marker if stream == "stdout" else ""),
                                       marker if stream == "stderr" else "")
        run.completion_log(complete + "[vulkan warning] advisory\n", "[vulkan info] diagnostic\n")

    def test_native_version_accepts_lf_and_crlf_but_rejects_ambiguous_identity(self):
        lines = ["ShadeDoomVK synthetic", "Commit: " + "a" * 40, "Working tree: clean"]
        for newline in ("\n", "\r\n"):
            with self.subTest(newline=repr(newline)):
                self.assertEqual(run.version_identity((newline.join(lines) + newline).encode()), ("a" * 40, "clean"))
        invalid = [lines + [lines[1]], lines + [lines[2]],
                   [lines[0], "Commit: " + "a" * 39, lines[2]],
                   [lines[0], lines[1], "Working tree: unknown"],
                   ["Other engine", lines[1], lines[2]]]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(common.EvidenceError):
                run.version_identity(("\r\n".join(value) + "\r\n").encode())

    def test_extent_override_is_bounded_and_rewrites_only_native_extent_flags(self):
        native = {"extent": [640, 480]}
        args = argparse.Namespace(extent=None)
        self.assertEqual(run.capture_extent(args, native, "timing"), [640, 480])
        args.extent = "1904x1001"
        self.assertEqual(run.capture_extent(args, native, "timing"), [1904, 1001])
        argv = run.apply_extent(["engine", "-width", "640", "-height", "480", "+map", "X"], [1904, 1001])
        self.assertEqual(argv[argv.index("-width") + 1], "1904")
        self.assertEqual(argv[argv.index("-height") + 1], "1001")
        for invalid in ("0x480", "1921x1080", "1920x1081", "640,480", "640x"):
            args.extent = invalid
            with self.subTest(invalid=invalid), self.assertRaises(common.EvidenceError):
                run.capture_extent(args, native, "timing")

        profile = {"extent": [1904, 1001], "reference_extent": [640, 480]}
        argv = ["engine", "-width", "1904", "-height", "1001"]
        self.assertEqual(run.validated_extent(profile, native, argv), [1904, 1001])
        bad_argv = ["engine", "-width", "640", "-height", "480"]
        with self.assertRaisesRegex(common.EvidenceError, "extent disagrees"):
            run.validated_extent(profile, native, bad_argv)
        legacy_override = {"extent": [1904, 1001]}
        with self.assertRaises(common.EvidenceError):
            run.validated_extent(legacy_override, native, argv)

    def test_material_semantic_custom_layers_require_explicit_assertion(self):
        authored = [
            {"binding": i, "semantic": semantic, "role": "authored-layer",
             "source": {"lump": 20 + i, "width": 16, "height": 16}}
            for i, semantic in enumerate(
                ["albedo", "normal", "metallic", "roughness", "ambient-occlusion"])
        ]
        placeholders = [
            {"binding": 5 + i, "semantic": semantic, "role": "fallback-placeholder",
             "source": {"lump": 0, "width": 1, "height": 1}}
            for i, semantic in enumerate(("brightmap-emissive", "detail", "glow"))
        ]
        custom = {"binding": 8, "semantic": "custom", "role": "authored-layer",
                  "custom_index": 0, "requested_sampling": 1,
                  "source": {"lump": 99, "width": 16, "height": 16}}
        value = {"layers": authored + placeholders + [custom]}
        expected = ["albedo", "normal", "metallic", "roughness", "ambient-occlusion"]

        self.assertFalse(run._material_semantics_match(value, expected))
        self.assertTrue(run._material_semantics_match(value, expected, allow_custom=True))
        self.assertTrue(run._material_custom_layers_match(
            value, [{"binding": 8, "custom_index": 0, "requested_sampling": 1}]))
        wrong = copy.deepcopy(value)
        wrong["layers"][-1]["requested_sampling"] = 0
        self.assertFalse(run._material_custom_layers_match(
            wrong, [{"binding": 8, "custom_index": 0, "requested_sampling": 1}]))
        reordered = {"layers": authored + [custom] + placeholders}
        self.assertFalse(run._material_semantics_match(
            reordered, expected, allow_custom=True))

        height = {"binding": 9, "semantic": "height", "role": "authored-layer",
                  "requested_sampling": 1,
                  "sampler": {"min_filter": 1, "mag_filter": 1, "mipmap_mode": 1},
                  "source": {"lump": 100, "width": 16, "height": 16}}
        with_height = {"layers": authored + placeholders + [custom, height], "height_texture_index": 9}
        self.assertTrue(run._material_semantics_match(
            with_height, expected, allow_custom=True, allow_height=True))
        self.assertTrue(run._material_height_layer_match(
            with_height, {"binding": 9, "requested_sampling": 1}))
        self.assertTrue(run._material_layer_sampling_match(with_height, [
            {"semantic": "height", "binding": 9, "requested_sampling": 1,
             "min_filter": 1, "mag_filter": 1, "mipmap_mode": 1}]))
        wrong_index = copy.deepcopy(with_height)
        wrong_index["height_texture_index"] = 8
        self.assertFalse(run._material_height_layer_match(
            wrong_index, {"binding": 9, "requested_sampling": 1}))

    def test_capture_validate_and_rehashed_packet_negatives(self):
        original_subprocess_run = subprocess.run
        with tempfile.TemporaryDirectory(prefix="sdvk-synthetic-receipt-") as temporary:
            root = Path(temporary).resolve()
            exe, iwad = root / "synthetic-engine", root / "synthetic.wad"
            exe.write_bytes(b"SYNTHETIC executable placeholder; never launched\n")
            iwad.write_bytes(b"SYNTHETIC IWAD placeholder; never rendered\n")
            (root / "vkdoom.pk3").write_bytes(b"SYNTHETIC engine package\n")
            out, prepared = root / "attempt", root / "prepared"
            calls, delegated_git = [], []
            scene = next(s for s in prepare.load_catalog()["scenes"] if s["id"] == "lights-zero")
            native = scene["native"]
            commit = None
            version_state = "clean"
            stdout_error, stderr_error = "", ""

            def synthetic_engine(argv, *positional, **kwargs):
                if str(argv[0]) != str(exe):
                    if argv[0] == "git":
                        delegated_git.append(list(argv))
                    return original_subprocess_run(argv, *positional, **kwargs)
                calls.append(list(argv))
                if argv[1:] == ["--version"]:
                    # Windows CRT uses CRLF even when stdout is a binary pipe.
                    version = f"ShadeDoomVK SYNTHETIC receipt test\r\nCommit: {commit}\r\nWorking tree: {version_state}\r\n"
                    return subprocess.CompletedProcess(argv, 0, version.encode(), b"")
                request = common.read_json(out / "request.json")
                self.assertEqual(Path(kwargs["cwd"]), out)
                self.assertEqual(argv, request["argv"])
                self.assertIn("-sdvkobservequit", argv)
                self.assertEqual(argv[argv.index("-rngseed") + 1], str(native["seed"]))
                data = observation()
                data["warmup_frames"] = int(argv[argv.index("-sdvkobservewarmup") + 1])
                self.assertEqual(int(argv[argv.index("-sdvkobserveframes") + 1]), 1)
                data["build"].update(commit=commit, application_cache={
                    "available": True, "path": str(out / "cache"), "policy": "SYNTHETIC isolated cache"})
                data["screenshot"]["path"] = str(out / "native.png")
                for record in data["records"]:
                    value = record["data"]
                    if "context" in value:
                        value["context"].update(map=native["map"], type="main", root_type="main",
                                                position=list(native["camera"]["position"]))
                    if record["kind"] == "frame":
                        value.update(map=native["map"], width=640, height=480, settings=copy.deepcopy(native["settings"]))
                        value["camera"].update(position=list(native["camera"]["position"]), angles=[0, 0, 0])
                        for counter, bounds in native["frame_assertions"].items():
                            value[counter] = bounds["minimum"]
                context = copy.deepcopy(data["records"][0]["data"]["context"])
                data["records"] += [row("pipeline", {"context": context, "key": {"shader": {"UseShadowmap": 0}},
                                                     "draw_count": 6, "basis": "SYNTHETIC test pipeline"}),
                                    row("resource", {"descriptor_capacity": 64, "descriptor_current": 1,
                                                     "descriptor_high_water": 1, "descriptor_dynamic_start": 16,
                                                     "texture_epoch": 1, "lightmap_epoch": 1, "probe_epoch": 1,
                                                     "async_upload_epoch": 1, "scope": "SYNTHETIC owner snapshot"})]
                common.write_json(out / "native.renderer.json", recount(data))
                (out / "native.png").write_bytes(png(bytes(640 * 480 * 3), width=640, height=480))
                lines = ["SYNTHETIC engine output; no runtime was executed", "W_Init: Init WADfiles."]
                lines += [f"adding {path}, 1 lumps" for path in request["packages"]]
                lines += [f'"{key}" is "{str(value).lower()}" (default: "synthetic")'
                          for key, value in native["settings"].items()]
                lines.append("SDVK_OBSERVATION_COLLECTED: " + str(out / "native.renderer.json"))
                kwargs["stdout"].write(("\n".join(lines) + "\n" + stdout_error).encode())
                kwargs["stderr"].write(stderr_error.encode())
                return subprocess.CompletedProcess(argv, 0)

            args = argparse.Namespace(exe=exe, iwad=iwad, prepared=prepared, scene="lights-zero", out=out,
                                      mode="state", frames=1, warmup=3, timeout=10, gpu=False,
                                      include_stress=False, image_policy="exact")
            with mock.patch.object(run.subprocess, "run", side_effect=synthetic_engine):
                manifest = prepare.prepare(prepared, ["lights-zero"])
                commit = manifest["source_identity"]["git_commit"]
                pins = {"executable": common.pin(exe), "iwad": common.pin(iwad),
                        "engine_packages": {"vkdoom.pk3": common.pin(root / "vkdoom.pk3")}}
                for field in ("executable", "package"):
                    args.runtime_pins = copy.deepcopy(pins)
                    target = args.runtime_pins["executable"] if field == "executable" else args.runtime_pins["engine_packages"]["vkdoom.pk3"]
                    target["sha256"] = "0" * 64
                    args.out = root / ("changed-" + field)
                    with self.assertRaisesRegex(common.EvidenceError, "changed after physical preregistration"):
                        run.capture(args)
                    self.assertEqual(calls, [])  # reject bytes before even --version
                    self.assertEqual(common.read_json(args.out / "run.json")["status"], "FAIL")
                args.runtime_pins = pins
                args.expected_commit = "f" * 40 if commit != "f" * 40 else "e" * 40
                args.require_clean = True
                args.out = root / "wrong-source"
                with self.assertRaisesRegex(common.EvidenceError, "commit differs"):
                    run.capture(args)
                self.assertEqual(len(calls), 1)  # --version only, no renderer launch
                self.assertEqual(common.read_json(args.out / "run.json")["status"], "FAIL")
                args.expected_commit = commit
                version_state = "modified"
                args.out = root / "dirty-source"
                with self.assertRaisesRegex(common.EvidenceError, "clean renderer build"):
                    run.capture(args)
                self.assertEqual(len(calls), 2)  # another --version only
                self.assertEqual(common.read_json(args.out / "run.json")["status"], "FAIL")
                version_state = "clean"
                args.out = out
                collected = run.capture(args)
                successful_out = out
                for stream, marker in (("stdout", "[fault] type=4 address=0x123\n"),
                                       ("stderr", "[vulkan error] Validation Error: invalid descriptor\n")):
                    out = root / ("failed-" + stream)
                    args.out = out
                    stdout_error = marker if stream == "stdout" else ""
                    stderr_error = marker if stream == "stderr" else ""
                    with self.assertRaisesRegex(common.EvidenceError, "Native process error in " + stream):
                        run.capture(args)
                    failed = common.read_json(out / "run.json")
                    self.assertEqual(failed["status"], "FAIL")
                    self.assertIn("SDVK_OBSERVATION_COLLECTED:", (out / "stdout.log").read_text())
                    self.assertIn(marker.strip(), (out / (stream + ".log")).read_text())
                    self.assertTrue({"stdout.log", "stderr.log", "native.renderer.json"} <= set(failed["artifacts"]))
                out = successful_out
                args.out = out
            self.assertEqual(len(calls), 8)  # two rejected versions, one success, two retained severity failures.
            self.assertTrue(any(command[1:3] == ["cat-file", "-e"] for command in delegated_git))
            self.assertEqual(collected["status"], "COLLECTED")
            validated_root, receipt, raw, result = run.validate_run(out)
            self.assertEqual(validated_root, out)
            self.assertEqual(result["status"], "PASS")
            self.assertFalse(receipt["native_acceptance_awarded"])
            self.assertEqual(receipt["console_settings"], native["settings"])
            self.assertTrue(set(scene["required_state_channels"]).issubset(result["kinds"]))

            # Two paths must not turn one process into repeatability evidence.
            # A copied packet remains independently readable for archival use.
            with self.assertRaisesRegex(common.EvidenceError, "independent"):
                run.compare_runs(out, out)
            copied = root / "copied-attempt"
            shutil.copytree(out, copied)
            self.assertEqual(run.validate_run(copied)[3]["status"], "PASS")
            with self.assertRaisesRegex(common.EvidenceError, "same process"):
                run.compare_runs(out, copied)

            names = ("input/scene.pk3", "input/fixture.ini", "capture.cfg", "request.json", "native.renderer.json", "run.json",
                     "stdout.log", "stderr.log")
            originals = {name: (out / name).read_bytes() for name in names}

            def repin(changed_receipt, name, payload):
                (out / name).write_bytes(payload)
                changed_receipt["artifacts"][name] = common.pin(out / name, relative_to=out)

            def assert_packet_rejected(changed_receipt, message):
                (out / "run.json").write_bytes(common.canonical(changed_receipt))
                try:
                    with self.assertRaisesRegex(common.EvidenceError, message):
                        run.validate_run(out)
                finally:
                    for name, payload in originals.items():
                        (out / name).write_bytes(payload)

            changed = copy.deepcopy(receipt)
            repin(changed, "stderr.log", b"[vulkan error] retained validation failure\n")
            assert_packet_rejected(changed, "Native process error in stderr")

            # Rehashing a mutable packet entry cannot replace its preregistered input.
            for name in ("input/scene.pk3", "input/fixture.ini", "capture.cfg"):
                with self.subTest(rehashed_input=name):
                    changed = copy.deepcopy(receipt)
                    repin(changed, name, originals[name] + b"\nSYNTHETIC tampering\n")
                    assert_packet_rejected(changed, "Input identity differs")

            # Even agreeing run/request profiles cannot relabel the observed interval.
            changed = copy.deepcopy(receipt)
            request = common.read_json(out / "request.json")
            request["reproduction"]["warmup_frames"] += 1
            changed["reproduction"] = copy.deepcopy(request["reproduction"])
            repin(changed, "request.json", common.canonical(request))
            assert_packet_rejected(changed, "warmup/GPU mode differs")

            # Matching rewritten run/raw build fields still conflict with startup identity.
            changed = copy.deepcopy(receipt)
            contradictory = copy.deepcopy(raw)
            contradictory["build"]["commit"] = "f" * 40 if commit != "f" * 40 else "e" * 40
            changed["build"] = copy.deepcopy(contradictory["build"])
            repin(changed, "native.renderer.json", common.canonical(contradictory))
            assert_packet_rejected(changed, "Runtime and preregistered source identities disagree")


if __name__ == "__main__":
    unittest.main()
