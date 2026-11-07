"""Actual recipe/preparer controls; renderer and Vulkan are never executed."""
import copy
import datetime as dt
import json
from pathlib import Path
import shutil
import subprocess
import types
import unittest
from unittest.mock import patch

from .common import Stop, exclusive, pin, utc, validate_packet
from .conditional_grant import Ledger, authority, check_budget, digest, initialize_ledger
from .prepare import frozen_oracle, registered_packet
from .registered import PROFILE, SCHEMA, definition, validate
from . import test_supervisor as fixtures
from .test_integration import synthetic_source_checks


class RegisteredWorkloadTests(fixtures.TempCase):
    # Reuse only the host/registry/build CPU seed.
    def seed_and_registration(self, scenes=("viewmodel-legacy", "viewmodel-model-normal"), *, purpose="sdvk011-viewmodel"):
        seed = fixtures.PacketAndApprovalTests.packet(self)
        (Path(seed["renderer"]).parent / "vkdoom.pk3").write_bytes(b"SYNTHETIC engine package, NEVER LOADED")
        source = Path(__file__).resolve().parents[2]
        run = frozen_oracle(source)
        prepared = self.root / "real-prepared"
        manifest = run.preparation_module().prepare(prepared, list(scenes))
        commit = manifest["source_identity"]["git_commit"]
        tree = subprocess.check_output([shutil.which("git"), "rev-parse", "HEAD^{tree}"], cwd=source).decode().strip()
        seed.update(source={"commit": commit, "tree": tree}, oracle_source_root=str(source),
                    prepared=str(prepared), git=shutil.which("git"), stage_output_root=str(self.root / "captures"))
        content = self.root / "content"
        content.mkdir()
        iwad = content / "synthetic.wad"
        iwad.write_bytes(b"SYNTHETIC IWAD, NEVER LOADED")
        seed["iwad"] = str(iwad)
        build = self.root / "real-source-synthetic-build.json"
        snapshot = self.root / "snapshot.json"
        exclusive(build, {"schema": "synthetic-build/v1", "source": {**seed["source"], "dirty": False},
                          "executable": pin(seed["renderer"]), "configuration": "synthetic", "toolchain": "synthetic",
                          "flags": [], "source_snapshot": pin(snapshot)})
        seed["build_receipt"] = pin(build)
        captures = []
        for index, scene in enumerate(scenes):
            _, _, recipe = run.prepared_scene(prepared, scene)
            for attempt in ((1,) if purpose == "sdvk009-fault-discriminator" else (1, 2)):
                captures.append({"name": f"scene-{index}-{attempt}", "scene": scene,
                    "recipe_sha256": run.sha256(run.canonical(recipe)), "mode": "state", "frames": 1,
                    "warmup": 240, "extent": [640, 480], "deadline_seconds": 180,
                    "compare_with": f"scene-{index}-1" if attempt == 2 else None})
                if purpose == "sdvk009-fault-discriminator":
                    captures[-1]["collision_snapshot"] = True
                if purpose == "sdvk014-lifecycle":
                    captures[-1].update(frames=96, warmup=32)
        document = {"schema": SCHEMA, "profile": PROFILE, "purpose": purpose,
            "scope": "PARTIAL_COLLECTION_ONLY", "renderer_source": seed["source"], "oracle_source": seed["source"],
            "build_receipt": seed["build_receipt"], "renderer": pin(seed["renderer"]), "iwad": pin(iwad),
            "prepared_manifest": pin(prepared / "prepared.json"), "output_root": seed["stage_output_root"], "captures": captures}
        registration = self.root / "registration.json"
        exclusive(registration, document)
        grant = {"schema": "sdvk009-conditional-renderer-grant/v1", "grant_id": "CPU-REGISTERED-ONLY", "owner": "CPU fixture",
            "max_renderer_launches": len(captures), "max_retries_per_test": 0,
            "user_instruction_verbatim": "Synthetic CPU-only instruction", "user_addendum_verbatim": "Zero retries",
            "tests": [r["name"] for r in captures], "ledger_root": str(self.root / "ledger"), "recorded_utc": utc(),
            "expires_utc": (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).isoformat(), "conditions": ["review"],
            "registered_workload": {"profile": PROFILE, "registration": pin(registration)}}
        grant_pin = initialize_ledger(grant)
        seed["conditional_grant"] = grant_pin
        seed["files"].append(grant_pin)
        return seed, registration, grant

    def prepare_actual(self, scenes=("viewmodel-legacy",), **kwargs):
        seed, registration, grant = self.seed_and_registration(scenes, **kwargs)
        # Registry/source reads alone are synthetic. All actual recipe/member,
        # input/hash, derived command and conditional budget checks run normally.
        with patch("tools.physical_supervisor.common.verify_registry"), \
             patch("tools.physical_supervisor.common.verify_source"):
            packet = registered_packet(seed, registration)
        return packet, grant

    def assert_real_capture_boundary(self, packet, stage):
        from .collector import run_oracle
        class NoTarget(RuntimeError):
            pass
        packet["packet_sha256"] = "a" * 64
        stop = Path(packet["stop_root"])
        if not stop.exists():
            stop.mkdir()
            exclusive(stop / "HELD.json", {"status": "HELD"})
            exclusive(stop / ("release-" + "a" * 64 + ".json"), {"packet_sha256": "a" * 64, "expires_utc": packet["expires_utc"]})
        control = self.root / ("adapter-control-" + stage["name"])
        control.mkdir()
        identity = {"explicitly_synthetic_CPU_parent": True}
        exclusive(control / "supervisor-identity.json", identity)
        exclusive(control / "source-preflight.json", {"schema": "physical-supervisor/source-preflight-v1",
            "packet_sha256": "a" * 64, "stage": stage["name"], "source": packet["source"],
            "root": packet["oracle_source_root"], "git": pin(packet["git"]), "supervisor": identity,
            "checks": synthetic_source_checks(packet), "utc": utc()})
        frozen_oracle(packet["oracle_source_root"]).host_profile()
        def target(*args, **kwargs):
            self.assertEqual(args[3], stage["expected_argv"])
            raise NoTarget("Actual capture reached CPU boundary; no renderer created")
        with patch.object(subprocess, "Popen", side_effect=AssertionError("No child inside capture CPU control")) as native, \
             patch("tools.physical_supervisor.collector.gated_target", side_effect=target) as boundary:
            with self.assertRaises(NoTarget):
                run_oracle(packet, stage, control, pin(control / "source-preflight.json"))
        native.assert_not_called()
        boundary.assert_called_once()

    def test_actual_viewmodel_preparer_derives_repeat_and_model_captures_without_launch(self):
        packet, grant = self.prepare_actual(("viewmodel-legacy", "viewmodel-model-normal"))
        self.assertEqual(len(packet["stages"]), 4)
        self.assertEqual(authority(packet), grant)
        self.assertFalse(Path(packet["stages"][0]["capture"]["out"]).exists())
        self.assertEqual(packet["stages"][1]["compare_with"], packet["stages"][0]["capture"]["out"])
        for stage in packet["stages"]:
            self.assertEqual(stage["capture"]["warmup"], 240)
            self.assertEqual(stage["expected_argv"][stage["expected_argv"].index("-sdvkobservewarmup") + 1], "240")
            self.assertFalse(stage["capture"]["gpu"])
        self.assertIn("viewmodel-model-normal", [s["capture"]["scene"] for s in packet["stages"]])
        self.assert_real_capture_boundary(packet, packet["stages"][0])
        self.assert_real_capture_boundary(packet, packet["stages"][2])

    def test_fault_discriminator_has_one_typed_cpu_snapshot_capture(self):
        packet, grant = self.prepare_actual(("compositing",), purpose="sdvk009-fault-discriminator")
        self.assertEqual(len(packet["stages"]), 1)
        stage = packet["stages"][0]
        self.assertTrue(stage["capture"]["collision_snapshot"])
        self.assertEqual(stage["expected_argv"][-2:], ["-sdvkcollisionsnapshot", str(Path(stage["capture"]["out"]) / "collision").replace("\\", "/")])
        self.assertIn("collision-1.bin", stage["required_outputs"])
        self.assert_real_capture_boundary(packet, stage)
        changed = copy.deepcopy(packet)
        document = definition(changed)
        document["captures"].append({**document["captures"][0], "name": "forbidden-second-creation"})
        path = self.root / "two-discriminator-captures.json"
        exclusive(path, document)
        changed["workload_registration"] = pin(path)
        changed["files"].append(pin(path))
        with self.assertRaises(Stop):
            definition(changed)

    def test_special_surface_preparer_retains_real_lifecycle_flags_and_frames(self):
        packet, _ = self.prepare_actual(("special-surface-lifecycle",), purpose="sdvk014-lifecycle")
        self.assertIn("-sdvk161surfacedriver", packet["stages"][0]["expected_argv"])
        self.assertEqual(packet["stages"][0]["capture"]["frames"], 96)
        self.assert_real_capture_boundary(packet, packet["stages"][0])

    def test_wrong_command_order_recipe_output_and_frame_controls_are_rejected(self):
        packet, _ = self.prepare_actual()
        changes = [lambda p: p["stages"].reverse(), lambda p: p["stages"].pop(),
            lambda p: p["stages"][0]["expected_argv"].append("+quit"),
            lambda p: p["stages"][0]["capture"].update(frames=2),
            lambda p: p["stages"][0]["capture"].update(gpu=True),
            lambda p: p["stages"][1].pop("compare_with"),
            lambda p: p["stages"][0].update(required_outputs=["run.json"]),
            lambda p: p["stages"][0]["generated_pins"].pop(),
            lambda p: p["stages"][1]["capture"].update(out=p["stages"][0]["capture"]["out"])]
        for mutate in changes:
            changed = copy.deepcopy(packet)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(Stop):
                validate(changed, check_files=True)

    def test_registration_seal_and_exact_source_cannot_be_rewritten(self):
        packet, _ = self.prepare_actual()
        for key in ("renderer_source", "oracle_source"):
            changed = copy.deepcopy(packet)
            document = definition(changed)
            document[key]["commit"] = "a" * 40
            path = self.root / (key + ".json")
            exclusive(path, document)
            changed["files"].append(pin(path))
            changed["workload_registration"] = pin(path)
            with self.subTest(key=key), self.assertRaises(Stop):
                validate(changed, check_files=False)
        Path(packet["workload_registration"]["path"]).write_text("{}")
        with self.assertRaises(Stop):
            definition(packet)

    def test_registered_budget_has_exact_order_zero_retry_and_all_stage_fences(self):
        packet, grant = self.prepare_actual()
        for key, value in (("max_renderer_launches", len(grant["tests"]) + 1), ("max_renderer_launches", 1),
                           ("max_retries_per_test", 1), ("tests", list(reversed(grant["tests"])))):
            changed = copy.deepcopy(grant)
            changed[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(Stop):
                check_budget(changed, [], grant["tests"][0], "a" * 64)
        sha, stop = digest(packet), packet["stop_root"]
        with Ledger(grant) as ledger:
            ledger.start(sha, stop, {})
            with self.assertRaises(Stop):
                ledger.reserve(sha, grant["tests"][1], stop)
            for index, name in enumerate(grant["tests"]):
                ledger.reserve(sha, name, stop)
                if index + 1 < len(grant["tests"]):
                    with self.assertRaises(Stop):
                        ledger.reserve(sha, grant["tests"][index + 1], stop)
                ledger.complete(sha, name)
            with self.assertRaises(Stop):
                ledger.reserve(sha, grant["tests"][0], stop)
            result = self.root / "result.json"
            exclusive(result, {"status": "COLLECTED_PENDING_ACCEPTANCE"})
            ledger.finish(sha, "COLLECTED_PENDING_ACCEPTANCE", pin(result))
            self.assertEqual(len(ledger.charges()), len(grant["tests"]))

    def test_legacy_grant_cannot_admit_registered_or_full_campaign(self):
        packet, grant = self.prepare_actual()
        changed = copy.deepcopy(packet)
        changed["kind"] = "diagnostic"
        with self.assertRaises(Stop):
            authority(changed)
        changed["kind"] = "campaign"
        with self.assertRaises(Stop):
            validate_packet(changed, check_files=False)


class RegisteredAdmissionTests(fixtures.TempCase):
    def test_twenty_six_creations_require_exact_registered_zero_retry_budget(self):
        names = [f"capture-{index:02d}" for index in range(26)]
        registration = self.root / "synthetic-budget-only.json"
        exclusive(registration, {"schema": SCHEMA, "profile": PROFILE, "purpose": "sdvk008-partial-reference-and-cost",
            "scope": "PARTIAL_COLLECTION_ONLY", "captures": [{"name": name} for name in names]})
        grant = {"schema": "sdvk009-conditional-renderer-grant/v1", "max_renderer_launches": 26,
            "max_retries_per_test": 0, "tests": names, "user_instruction_verbatim": "Synthetic CPU allowance",
            "user_addendum_verbatim": "Zero retry", "registered_workload": {"profile": PROFILE, "registration": pin(registration)}}
        self.assertEqual(check_budget(grant, [], names[0], "a" * 64)["attempt"], 0)
        for mutate in (lambda g: g.pop("registered_workload"), lambda g: g.update(max_renderer_launches=27),
                       lambda g: g.update(max_retries_per_test=1), lambda g: g["tests"].reverse()):
            changed = copy.deepcopy(grant)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(Stop):
                check_budget(changed, [], names[0], "a" * 64)

    def test_pom_reference_gate_requires_pass_before_first_timing_creation(self):
        from .registered import before_capture, reference_gate
        pairs = [{"id": name, "off": f"off-{index}", "on": f"on-{index}", "oracle": {}}
                 for index, name in enumerate(("default-off", "heightless", "single-m", "alpha"))]
        stages = []
        for pair in pairs:
            for scene in (pair["off"], pair["on"]):
                for attempt in (1, 2):
                    out = self.root / f"{scene}-{attempt}"
                    out.mkdir()
                    exclusive(out / "run.json", {"explicitly_synthetic_CPU_fixture": True})
                    stages.append({"name": out.name, "capture": {"scene": scene, "extent": "640x480", "mode": "state", "out": str(out)}})
        timing = {"name": "first-timing", "capture": {"mode": "timing"}}
        stages.append(timing)
        contract = types.SimpleNamespace(CORRECTNESS_PAIRS=pairs, MISSING_GATES=["full-acceptance-held"],
                                         source_projected_marker_direction=True)
        state = {"image": "PASS", "direction": "PASS"}
        validations = []
        driver = types.SimpleNamespace(fixture_contract=lambda: contract,
            PARTIAL_PAIRS=tuple(p["id"] for p in pairs), continuity=lambda a, b: None,
            controlled_pair=lambda a, b: ({}, {}),
            image_pair=lambda *a, **k: {"status": state["image"]},
            source_projected_direction_witness=lambda *a, **k: {"status": state["direction"]})
        run = types.SimpleNamespace(validate_run=lambda path: validations.append(path), compare_runs=lambda *a: {"status": "PASS"})
        packet = {"kind": "registered-workload", "stages": stages}
        with patch("tools.physical_supervisor.registered.definition", return_value={"purpose": "sdvk008-partial-reference-and-cost"}), \
             patch("tools.physical_supervisor.registered.importlib.import_module", return_value=driver), \
             patch.object(subprocess, "Popen", side_effect=AssertionError("No native process in reference gate")) as native:
            self.assertEqual(before_capture(packet, timing, run)["status"], "PASS")
            self.assertEqual(len(validations), 16)
            for key in ("image", "direction"):
                for value in ("FAIL", "INCONCLUSIVE"):
                    state[key] = value
                    with self.subTest(key=key, value=value), self.assertRaises(Stop):
                        before_capture(packet, timing, run)
                state[key] = "PASS"
            state["direction"] = "INCONCLUSIVE"
            self.assertEqual(reference_gate(packet, run, require_pass=False)["status"], "INCONCLUSIVE")
            state["direction"] = "FAIL"
            with self.assertRaises(Stop):
                reference_gate(packet, run, require_pass=False)
            native.assert_not_called()


if __name__ == "__main__":
    unittest.main()
