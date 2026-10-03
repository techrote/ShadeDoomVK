"""Final CFX programme synthesis consistency checks; CPU-only."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
MATRIX = ROOT / "docs/shadedoomvk/evidence/cfx-final-incident-matrix.json"
REPORT = ROOT / "docs/shadedoomvk/CFX-FINAL-PROGRAMME-SYNTHESIS.md"


class CfxFinalProgrammeSynthesis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(MATRIX.read_text(encoding="utf-8"))
        cls.report = REPORT.read_text(encoding="utf-8")

    def test_matrix_has_all_historical_incidents_and_p400_limitation(self):
        ids = {row["incident_id"] for row in self.data["incidents"]}
        expected = {
            "CFX-DBP50-20260920-MAP08",
            "CFX-DBP50-20260923-1824",
            "CFX-DBP50-20260923-2259",
            "CFX-DBP50-V12-20260924-1309",
            "CFX-DBP37-MAP01-20260924",
            "CFX-MAP04-CAPDIAG-20260924",
            "CFX-SUNLUST-MAP24-20260924",
            "CFX-DBP37-P400-CFX005",
        }
        self.assertEqual(ids, expected)
        p400 = next(row for row in self.data["incidents"]
                    if row["incident_id"] == "CFX-DBP37-P400-CFX005")
        self.assertEqual(p400["repaired_build_physical_coverage"], "none")
        self.assertIn("documented residual limitation", p400["categories"])

    def test_categories_are_explicit_and_known(self):
        allowed = set(self.data["allowed_categories"])
        self.assertTrue(allowed)
        for row in self.data["incidents"]:
            self.assertTrue(row["categories"])
            self.assertLessEqual(set(row["categories"]), allowed)

    def test_primary_repair_claim_boundary_is_pinned(self):
        repair = self.data["accepted_primary_repair"]
        self.assertEqual(repair["pr"], 104)
        self.assertEqual(repair["merge_sha"], "d0789c88f88049116022e7b904026cddeaba8ac4")
        self.assertFalse(repair["diagnostic_retention_is_production_fix"])
        self.assertEqual(repair["exact_former_reproducer_successes"]["successes"], 3)
        unsupported = " ".join(repair["not_established"]).lower()
        for phrase in ("shader", "dynamic descriptor", "gpu bytes", "nvidia", "shared mechanism"):
            self.assertIn(phrase, unsupported)

    def test_cross_case_counts_and_exclusions_are_pinned(self):
        cross = self.data["cross_case_qualification"]
        self.assertEqual((cross["processes"], cross["safe_controls"], cross["target_attempts"]), (17, 5, 12))
        self.assertEqual(cross["new_device_loss_or_tdr_events"], 0)
        self.assertEqual(len(cross["routes"]), 3)
        self.assertTrue(all(route["qualified_successes"] == 3 for route in cross["routes"]))
        self.assertEqual(len(cross["excluded_observations"]), 3)

    def test_parent_acceptance_is_complete_without_weakening(self):
        audit = self.data["parent_acceptance"]
        self.assertEqual([row["criterion"] for row in audit], [1, 2, 3, 4, 5, 6])
        self.assertTrue(all(row["result"] == "PASS" for row in audit))
        self.assertFalse(self.data["physical_testing_performed_by_synthesis"])

    def test_pf020_and_vendor_boundaries_fail_closed(self):
        handoff = self.data["pf020_handoff"]
        self.assertFalse(handoff["cfx_blocks_pf020_independently"])
        self.assertIn("repaired P400 behavior untested", handoff["retained_limitations"])
        vendor = self.data["nvidia_disposition"]
        self.assertFalse(vendor["confirmed_nvidia_defect"])
        self.assertFalse(vendor["vendor_package_prepared_by_synthesis"])
        self.assertFalse(vendor["vendor_submission_decision_made"])

    def test_human_report_preserves_required_boundaries(self):
        required = (
            "No repaired-build P400 physical qualification was performed",
            "unique executing shader/SASS",
            "illegal dynamic descriptor access",
            "PASS",
            "PF-020 handoff",
            "NVIDIA / #103 disposition",
            "No new physical GPU run was performed",
        )
        for phrase in required:
            self.assertIn(phrase, self.report)

    def test_canonical_handoff_markers_exist(self):
        expected = {
            "docs/shadedoomvk/DRIVER-CRASH-FORENSICS.md": "CFX-000 final programme synthesis",
            "docs/shadedoomvk/10-EXECUTION-LEDGER.md": "CFX-000 final synthesis",
            "docs/shadedoomvk/issues/PF-020.md": "CFX final handoff",
            "docs/shadedoomvk/rag/02-RENDERER-IDENTITY-LIFETIME.md": "CFX-000 final disposition",
            "docs/shadedoomvk/rag/06-LIGHTMAP-PROBE-PIPELINE.md": "CFX-000 final disposition",
            "docs/shadedoomvk/rag/08-VULKAN-PIPELINE-CAPABILITIES.md": "CFX final diagnostic disposition",
            "docs/shadedoomvk/rag/10-KNOWN-TRAPS-DORMANT-PATHS.md": "CFX descriptor-retirement trap",
        }
        for path, marker in expected.items():
            text = (ROOT / path).read_text(encoding="utf-8")
            self.assertIn(marker, text, path)


if __name__ == "__main__":
    unittest.main()
