"""Pure CPU custody and independent support-declaration validation controls."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .common import Stop, pin, verify_iwad_support
from .supervisor import validate_stage


class SupportCustodyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.runtime = self.root / "runtime"
        self.runtime.mkdir()
        self.exe = self.runtime / "SYNTHETIC_NEVER_EXECUTED.exe"
        self.iwad = self.root / "synthetic.wad"
        self.support = self.runtime / "support.wad"
        for path, data in ((self.exe, b"not executable"), (self.iwad, b"synthetic IWAD"),
                           (self.support, b"synthetic support WAD")):
            path.write_bytes(data)
        self.packet = {"iwad": str(self.iwad), "renderer": str(self.exe),
                       "oracle_source_root": str(Path(__file__).resolve().parents[2]),
                       "files": [pin(p) for p in (self.exe, self.iwad, self.support)]}
        def oracle_pin(path):
            row = pin(path)
            return {"path": row["path"], "sha256": row["sha256"], "bytes": row["size"]}
        self.packet["iwad_support"] = {"iwad": oracle_pin(self.iwad), "packages": [oracle_pin(self.support)]}

    def test_real_oracle_validates_exact_support_without_any_process(self):
        with patch("subprocess.Popen", side_effect=AssertionError("No native process permitted")) as native:
            verify_iwad_support(self.packet)
            verify_iwad_support(self.packet, check_files=False)
            native.assert_not_called()

    def test_unpinned_changed_or_wrong_iwad_support_fails(self):
        mutations = [lambda p: p["files"].pop(),
                     lambda p: p["iwad_support"]["iwad"].update(sha256="0" * 64),
                     lambda p: p["iwad_support"]["packages"][0].update(sha256="0" * 64),
                     lambda p: p["iwad_support"]["packages"].append(copy.deepcopy(p["iwad_support"]["packages"][0])),
                     lambda p: p["iwad_support"].update(packages=[])]
        for mutate in mutations:
            packet = copy.deepcopy(self.packet)
            mutate(packet)
            # frozen_oracle intentionally reloads its module-local EvidenceError;
            # use the stable ValueError base rather than a stale class object.
            with self.subTest(packet=packet), self.assertRaises((Stop, ValueError)):
                verify_iwad_support(packet, check_files=False)
        self.support.write_bytes(b"changed after preregistration")
        with self.assertRaises((Stop, ValueError)):
            verify_iwad_support(self.packet)

    def test_supervisor_requires_request_to_match_prospective_packet(self):
        out = self.root / "capture"
        control = self.root / "control"
        out.mkdir()
        control.mkdir()
        owner = {"synthetic_owned_target": True}
        packet = {**self.packet, "source": {"commit": "a" * 40}, "native_device": {"vendor_id": 1}}
        stage = {"capture": {"out": str(out)}}
        (out / "native.renderer.json").write_text(json.dumps({"build": {
            "commit": "a" * 40, "working_tree": "clean", "vulkan": {"vendor_id": 1}}}))
        for name in ("target-resumed.json", "target-exit.json"):
            (control / name).write_text(json.dumps({"identity": owner, "returncode": 0}))
        class CPUOracle:
            @staticmethod
            def validate_run(path):
                return {"synthetic_cpu_validation": True}
        with patch("tools.physical_supervisor.prepare.frozen_oracle", return_value=CPUOracle), \
             patch("subprocess.Popen", side_effect=AssertionError("No native process permitted")) as native:
            (out / "request.json").write_text(json.dumps({"iwad_support": packet["iwad_support"]}))
            self.assertEqual(validate_stage(packet, stage, control, owner)["validation"], "PASS")
            for value in ({}, {"iwad_support": {"iwad": {}, "packages": []}}):
                (out / "request.json").write_text(json.dumps(value))
                with self.assertRaises(Stop):
                    validate_stage(packet, stage, control, owner)
            native.assert_not_called()


if __name__ == "__main__":
    unittest.main()
