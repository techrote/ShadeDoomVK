"""Prospective current-source plan controls; no native process is permitted."""
from argparse import Namespace
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.renderer_oracle import prepare, sdvk008_fixtures, sdvk008_physical as target
from tools.renderer_oracle.common import EvidenceError, canonical, pin, sha256


class CurrentSourcePlanTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        for name in ("vkdoom.exe", "vkdoom.pk3", "freedoom2.wad", "license.txt", "vulkan.txt", "owner.txt", "STOP.json"):
            (self.root / name).write_bytes(b"SYNTHETIC CPU input; never executable\n")
        self.renderer = {"commit": "a" * 40, "tree": "b" * 40}
        self.oracle = {"commit": "c" * 40, "tree": "d" * 40}
        stop = pin(self.root / "STOP.json")
        generation = {"schema": "sdvk-physical-prospective-generation/v1",
                      "new_authority": "LATER_DIRECT_OWNER_CORRECTION_FRESH_PROSPECTIVE_EXPERIMENT",
                      "owner_authorization": pin(self.root / "owner.txt"), "source": self.renderer,
                      "historical_stops": [{"path": stop["path"], "sha256": stop["sha256"], "size": stop["bytes"]}]}
        (self.root / "generation.json").write_bytes(canonical(generation))
        self.args = Namespace(exe=self.root / "vkdoom.exe", iwad=self.root / "freedoom2.wad",
                              current_source_plan=self.root / "plan.json", correctness_only=True,
                              software_fixture_control=False, timeout=180, vulkan_summary=self.root / "vulkan.txt",
                              device_name="SYNTHETIC GPU; not enumerated")
        pairs = [row for row in sdvk008_fixtures.CORRECTNESS_PAIRS if row["id"] in target.PARTIAL_PAIRS]
        ids = {row[key] for row in pairs for key in ("off", "on", "background") if key in row}
        self.plan = {"schema": "sdvk008-current-source-plan/v1", "experiment_id": "synthetic-only",
                     "mode": "partial-reference", "renderer_source_root": str(self.root),
                     "renderer_source": self.renderer, "oracle_source": self.oracle,
                     "owner_authorization": pin(self.root / "owner.txt"), "generation": pin(self.root / "generation.json"),
                     "runtime": target.pin_runtime(self.args), "iwad_license": pin(self.root / "license.txt"),
                     "vulkan_summary": pin(self.root / "vulkan.txt"), "device_name": self.args.device_name,
                     "protocol": target.current_protocol(180), "missing_full_gates": list(sdvk008_fixtures.MISSING_GATES),
                     "recipes": {row["id"]: sha256(canonical(row)) for row in prepare.load_catalog()["scenes"] if row["id"] in ids}}

    def seal(self):
        self.args.current_source_plan.write_bytes(canonical(self.plan))
        self.args.current_source_plan_sha256 = pin(self.args.current_source_plan)["sha256"]

    def read(self, *, wrong_source=False):
        sources = [{"commit": "e" * 40, "tree": "f" * 40} if wrong_source else self.renderer, self.oracle]
        with patch.object(target, "source_identity", side_effect=sources), \
             patch.object(target.subprocess, "Popen", side_effect=AssertionError("No native process permitted")):
            return target.current_source_plan(self.args)

    def test_explicit_partial_reference_and_cost_modes_keep_original_budgets(self):
        for mode in ("partial-reference", "partial-reference-and-cost"):
            self.plan["mode"] = mode
            self.args.correctness_only = mode == "partial-reference"
            self.seal()
            result, identity = self.read()
            self.assertEqual(result, self.plan)
            self.assertEqual(identity["sha256"], self.args.current_source_plan_sha256)
        protocol = self.plan["protocol"]
        self.assertEqual(protocol["timing_orders"], [["S0", "SM"], ["SM", "S0"], ["S0", "SM"]])
        self.assertEqual((protocol["warmup_frames"], protocol["timing_frames"]), (120, 120))
        self.assertEqual(len(self.plan["recipes"]), 8)
        with self.assertRaisesRegex(EvidenceError, "Incomplete physical correctness fixtures"):
            target.validate_fixtures(sdvk008_fixtures, prepare.load_catalog())

    def test_wrong_source_mode_or_seal_cannot_admit_a_new_physical_baseline(self):
        self.seal()
        with self.assertRaisesRegex(EvidenceError, "identity mismatch"):
            self.read(wrong_source=True)
        self.args.correctness_only = False
        with self.assertRaisesRegex(EvidenceError, "plan/mode mismatch"):
            self.read()
        self.args.correctness_only = True
        self.args.current_source_plan_sha256 = "0" * 64
        with self.assertRaisesRegex(EvidenceError, "preregistered SHA-256"):
            self.read()

    def test_missing_full_gates_and_historical_stop_cannot_be_erased(self):
        self.plan["missing_full_gates"] = []
        self.seal()
        with self.assertRaisesRegex(EvidenceError, "Missing full-acceptance gates"):
            self.read()
        self.plan["missing_full_gates"] = list(sdvk008_fixtures.MISSING_GATES)
        self.seal()
        (self.root / "STOP.json").write_bytes(b"changed historical failure")
        with self.assertRaisesRegex(EvidenceError, "Historical STOP changed"):
            self.read()


if __name__ == "__main__": unittest.main()
