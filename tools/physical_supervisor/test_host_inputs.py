"""CPU/data-only host-input controls. No Vulkan, renderer or DLL is loaded."""
import copy
import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
from unittest.mock import patch

from .common import (DISPLAY_CLASS, Stop, approve, environment_policy,
                     pin, validate_packet, verify_native_device)
from .test_supervisor import TempCase
from .vulkan_inventory import (inspect_registered_manifests, registered_manifests,
                               verify_manifest_closure)


class NativeDeviceInputTests(TempCase):
    def test_physical_uint32_properties_accept_only_the_four_native_fields(self):
        for device_type in (1, 2):
            verify_native_device({"vendor_id": 0, "device_id": 0xffffffff,
                                  "device_type": device_type, "driver_version_raw": 0})

    def test_incomplete_or_inventory_metadata_rejected_before_any_io_or_release(self):
        valid = {"vendor_id": 1, "device_id": 2, "device_type": 2, "driver_version_raw": 3}
        cases = [None, {}, {**valid, "attestation_status": "UNAVAILABLE_NO_VULKAN_INSTANCE"}]
        for key in valid:
            cases.append({k: v for k, v in valid.items() if k != key})
            cases.extend({**valid, key: value} for value in (None, True, "1", 1.0, -1, 0x100000000))
        cases.extend({**valid, "device_type": value} for value in (0, 3, 4, 5))
        # The public execution path calls validate_packet before creating output.
        # Its native-input guard also precedes registry and file reads.
        header = {"schema": "physical-supervisor/packet-v1", "integrity_policy": {},
                  "experiment_id": "CPU-NATIVE-CONTROL", "kind": "diagnostic",
                  "source": {"commit": "1" * 40, "tree": "2" * 40}, "automatic_retries": 0}
        from .common import INTEGRITY_POLICY
        header["integrity_policy"] = dict(INTEGRITY_POLICY)
        for native in cases:
            with self.subTest(native=native), self.assertRaises(Stop):
                verify_native_device(native)
            with patch("tools.physical_supervisor.common.verify_registry", side_effect=AssertionError("No registry IO")), \
                 patch("tools.physical_supervisor.common.read_json", side_effect=AssertionError("No file IO")), \
                 self.assertRaises(Stop):
                validate_packet({**header, "native_device": native})
            with self.assertRaises(Stop):
                approve({"native_device": native}, {}, "a" * 64, object())
            self.assertFalse((self.root / "never-created-stop").exists())


class FrozenCommandInterfaceTests(TempCase):
    def test_real_recipe_positive_and_every_stage_argument_mutation_through_cli(self):
        """Real oracle assets; dummy EXE/device/build and synthetic registry authority."""
        from .__main__ import main
        from functools import lru_cache
        from . import common
        from .common import exclusive, read_json
        from .prepare import frozen_oracle
        from . import test_supervisor as cpu_tests
        packet = cpu_tests.PacketAndApprovalTests.packet(self)
        source = Path(__file__).resolve().parents[2]
        run = frozen_oracle(source)
        prepared = self.root / "real-prepared"
        manifest = run.preparation_module().prepare(prepared, ["compositing", "shadow-boundary"])
        tree = subprocess.check_output([shutil.which("git"), "--no-optional-locks", "-C", str(source),
                                        "rev-parse", "HEAD^{tree}"], text=True).strip()
        packet.update(source={"commit": manifest["source_identity"]["git_commit"], "tree": tree},
                      oracle_source_root=str(source), prepared=str(prepared),
                      stage_output_root=str(self.root / "never-executed-output"))
        inputs = self.root / "isolated-inputs"
        inputs.mkdir()
        iwad = inputs / "cpu-only.wad"
        iwad.write_bytes(b"Synthetic CPU-only IWAD data, never loaded")
        packet["iwad"] = str(iwad)
        packet["files"].append(pin(iwad))
        build = read_json(packet["build_receipt"]["path"])
        build["source"] = {**packet["source"], "dirty": False}
        Path(packet["build_receipt"]["path"]).write_text(json.dumps(build))
        packet["build_receipt"] = pin(packet["build_receipt"]["path"])
        seed = self.root / "synthetic-seed.json"
        target = self.root / "synthetic-packet.json"
        exclusive(seed, packet)
        # Only unrelated source-cleanliness/registry authority is synthetic.
        # Command rederivation, file pins, real oracle and public CLI are intact.
        with patch("tools.physical_supervisor.common.verify_source"), \
             patch("tools.physical_supervisor.common.verify_registry"):
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(main(["prepare", "--seed", str(seed), "--packet", str(target)]), 0, stdout.getvalue())
                self.assertEqual(main(["validate", "--packet", str(target)]), 0, stdout.getvalue())
            original = read_json(target)
            # The positive CLI authenticated every real fixture and file above.
            # Only argv arrays change below. Freeze those unchanged observations
            # to avoid regenerating two scenes hundreds of times in normal CI;
            # keep the public CLI and command checker themselves unmocked.
            scenes = {name: run.prepared_scene(prepared, name) for name in ("compositing", "shadow-boundary")}
            controls = [patch("tools.physical_supervisor.common.verify_pin"),
                        patch("tools.physical_supervisor.common.verify_roots"),
                        patch("tools.physical_supervisor.common.verify_oracle_python_pins"),
                        patch("tools.physical_supervisor.common.normalized", new=lru_cache(maxsize=None)(common.normalized)),
                        patch("tools.physical_supervisor.prepare.frozen_oracle", return_value=run),
                        patch.object(run, "prepared_scene", side_effect=lambda directory, name: scenes[name])]
            for control in controls:
                control.start()
                self.addCleanup(control.stop)
            changed_path = self.root / "mutated-packet.json"
            for index, stage in enumerate(original["stages"]):
                commands = []
                for position in range(1, len(stage["expected_argv"])):
                    argv = list(stage["expected_argv"])
                    argv[position] += "_CPU_MUTATION"
                    commands.append(argv)
                argv = stage["expected_argv"]
                commands += [argv + ["-extra"], argv[:-1], argv[:1] + ["-extra"] + argv[1:],
                             argv[:1] + [argv[2], argv[1]] + argv[3:]]
                for case, command in enumerate(commands):
                    changed = copy.deepcopy(original)
                    changed["stages"][index]["expected_argv"] = command
                    changed_path.write_text(json.dumps(changed))
                    stdout = io.StringIO()
                    with self.subTest(stage=stage["name"], case=case), contextlib.redirect_stdout(stdout):
                        self.assertEqual(main(["validate", "--packet", str(changed_path)]), 1)
                    self.assertIn("Stage command differs", stdout.getvalue())
        self.assertFalse((self.root / "never-executed-output").exists())


class ManifestClosureTests(TempCase):
    def fixture(self):
        library = self.root / "cpu-only-layer.dll"
        library.write_bytes(b"CPU test data, never a loaded library")
        manifest = self.root / "cpu-only-layer.json"
        manifest.write_text(json.dumps({"layer": {"library_path": "./" + library.name,
            "disable_environment": {"SYNTHETIC_LAYER_DISABLE": "1"}}}))
        registry = [{"hive": "HKLM", "key": "SOFTWARE\\Khronos\\Vulkan\\ImplicitLayers",
                     "present": True, "values": [{"name": str(manifest), "type": 4, "value": 0}]}]
        return {"files": [pin(manifest), pin(library)], "registry_policy": registry,
                "environment_policy": environment_policy(["SYNTHETIC_LAYER_DISABLE"]),
                "module_policy": {"required_paths": [], "optional_paths": [str(library)]}}

    def test_dword_zero_is_discoverable_and_nonzero_is_disabled_without_children(self):
        packet = self.fixture()
        with patch("subprocess.Popen", side_effect=AssertionError("No process")), \
             patch("ctypes.CDLL", side_effect=AssertionError("No library load")):
            self.assertEqual(len(registered_manifests(packet["registry_policy"])), 1)
            verify_manifest_closure(packet)
            result = inspect_registered_manifests(packet["registry_policy"])
        self.assertEqual(result[0]["environment_keys"], ["SYNTHETIC_LAYER_DISABLE"])
        self.assertEqual(result[0]["selection"], "REGISTERED_STATIC_CANDIDATE_NOT_LOADER_READBACK")
        packet["registry_policy"][0]["values"][0]["value"] = 1
        self.assertEqual(registered_manifests(packet["registry_policy"]), [])

    def test_device_registration_is_independent_of_missing_legacy_keys(self):
        packet = self.fixture()
        path = packet["files"][0]["path"]
        absent = {"hive": "HKLM", "key": "SOFTWARE\\Khronos\\Vulkan\\Drivers", "present": False, "values": []}
        device = {"hive": "HKLM", "key": DISPLAY_CLASS + "\\0006", "present": True,
                  "values": [{"name": "VulkanDriverName", "type": 1, "value": path},
                             {"name": "VulkanImplicitLayers", "type": 7, "value": [path]},
                             {"name": "VulkanDriverNameWoW", "type": 1, "value": "uninspected-32-bit"}]}
        packet["registry_policy"] = [absent, device]
        entries = registered_manifests(packet["registry_policy"])
        self.assertEqual(len(entries), 1)
        self.assertEqual(len(entries[0]["registrations"]), 2)
        verify_manifest_closure(packet)

    def test_missing_manifest_library_module_or_environment_pin_fails_closed(self):
        packet = self.fixture()
        mutations = [lambda p: p["files"].pop(0), lambda p: p["files"].pop(1),
                     lambda p: p["module_policy"]["optional_paths"].clear(),
                     lambda p: p["environment_policy"].pop("SYNTHETIC_LAYER_DISABLE")]
        for mutation in mutations:
            changed = copy.deepcopy(packet)
            mutation(changed)
            with self.subTest(mutation=mutation), self.assertRaises(Stop):
                verify_manifest_closure(changed)

    def test_changed_manifest_and_library_bytes_are_not_new_authority(self):
        packet = self.fixture()
        from pathlib import Path
        for row in packet["files"]:
            path = Path(row["path"])
            original = path.read_bytes()
            path.write_bytes(original + b" changed")
            try:
                with self.subTest(path=path), self.assertRaises(Stop):
                    verify_manifest_closure(packet)
            finally:
                path.write_bytes(original)

    def test_bare_library_search_name_requires_resolution_evidence(self):
        packet = self.fixture()
        from pathlib import Path
        path = Path(packet["files"][0]["path"])
        path.write_text(json.dumps({"ICD": {"library_path": "unresolved.dll"}}))
        with self.assertRaisesRegex(Stop, "separately resolved"):
            inspect_registered_manifests(packet["registry_policy"])
