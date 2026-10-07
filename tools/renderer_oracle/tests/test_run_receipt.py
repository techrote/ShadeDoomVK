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

            def synthetic_engine(argv, *positional, **kwargs):
                if str(argv[0]) != str(exe):
                    if argv[0] == "git":
                        delegated_git.append(list(argv))
                    return original_subprocess_run(argv, *positional, **kwargs)
                calls.append(list(argv))
                if argv[1:] == ["--version"]:
                    version = f"ShadeDoomVK SYNTHETIC receipt test\nCommit: {commit}\nWorking tree: clean\n"
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
                kwargs["stdout"].write(("\n".join(lines) + "\n").encode())
                return subprocess.CompletedProcess(argv, 0)

            args = argparse.Namespace(exe=exe, iwad=iwad, prepared=prepared, scene="lights-zero", out=out,
                                      mode="state", frames=1, warmup=3, timeout=10, gpu=False,
                                      include_stress=False, image_policy="exact")
            with mock.patch.object(run.subprocess, "run", side_effect=synthetic_engine):
                manifest = prepare.prepare(prepared, ["lights-zero"])
                commit = manifest["source_identity"]["git_commit"]
                collected = run.capture(args)
            self.assertEqual(len(calls), 2)  # --version and the synthetic producer.
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

            names = ("input/scene.pk3", "input/fixture.ini", "capture.cfg", "request.json", "native.renderer.json", "run.json")
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
