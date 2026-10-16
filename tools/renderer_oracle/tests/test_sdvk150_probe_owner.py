"""Adversarial controls for SDVK-150 probe-owner lifecycle acceptance."""
from __future__ import annotations

import copy
import unittest

from tools.renderer_oracle.common import EvidenceError
from tools.renderer_oracle.sdvk150_probe_owner import validate_lifecycle_records
from tools.renderer_oracle.run import _sdvk150_repeatability_projection

SPEC = {
    "owners": [
        {"map": "SDV15A", "authored_count": 2},
        {"map": "SDV15B", "authored_count": 2},
    ],
    "passes_per_owner": 5,
}


def event(kind: str, map_name: str, revision: int, epoch: int, iteration: int,
          authored: int = 2) -> dict:
    return {
        "event": kind,
        "map": map_name,
        "owner_revision": revision,
        "authored_count": authored,
        "iteration": iteration,
        "next_index": 0 if kind == "owner-reset" else 2,
        "collected": 0,
        "light_probe_epoch": epoch,
        "irradiance_count": 2,
        "prefilter_count": 2,
    }


def records() -> list[dict]:
    events = [event("owner-reset", "SDV15A", 11, 3, 0)]
    events += [event("pass-published", "SDV15A", 11, 3, i) for i in range(1, 6)]
    events += [event("owner-reset", "SDV15B", 19, 5, 0)]
    events += [event("pass-published", "SDV15B", 19, 5, i) for i in range(1, 6)]
    return [{
        "kind": "probe-builder",
        "frame": 1,
        "count": 1,
        "data": {
            "scope": "actual incremental builder reset/publication callbacks across observer warmup",
            "events": events,
        },
    }]


class ProbeOwnerLifecycleValidationTests(unittest.TestCase):
    def test_complete_same_count_transition_passes(self):
        result = validate_lifecycle_records(records(), SPEC)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["actual_publication_callbacks"], 10)
        self.assertFalse(result["count_fallback_used"])

    def test_reused_owner_revision_is_rejected(self):
        value = records()
        for row in value[0]["data"]["events"]:
            if row["map"] == "SDV15B":
                row["owner_revision"] = 11
        with self.assertRaises(EvidenceError):
            validate_lifecycle_records(value, SPEC)

    def test_missing_final_publication_is_rejected(self):
        value = records()
        value[0]["data"]["events"] = [
            row for row in value[0]["data"]["events"]
            if not (row["map"] == "SDV15B" and row["event"] == "pass-published"
                    and row["iteration"] == 5)
        ]
        with self.assertRaises(EvidenceError):
            validate_lifecycle_records(value, SPEC)

    def test_count_reset_fallback_is_rejected(self):
        value = records()
        rows = value[0]["data"]["events"]
        rows.insert(7, event("count-reset", "SDV15B", 19, 5, 0))
        with self.assertRaises(EvidenceError):
            validate_lifecycle_records(value, SPEC)

    def test_mixed_publication_revision_is_rejected(self):
        value = records()
        for row in value[0]["data"]["events"]:
            if row["map"] == "SDV15B" and row["event"] == "pass-published" and row["iteration"] == 3:
                row["owner_revision"] = 20
                break
        with self.assertRaises(EvidenceError):
            validate_lifecycle_records(value, SPEC)

    def test_nonadvancing_resource_epoch_is_rejected(self):
        value = records()
        for row in value[0]["data"]["events"]:
            if row["map"] == "SDV15B":
                row["light_probe_epoch"] = 3
        with self.assertRaises(EvidenceError):
            validate_lifecycle_records(value, SPEC)

    def test_repeatability_normalizes_only_owner_revision_labels(self):
        left = records()
        right = copy.deepcopy(left)
        for row in right[0]["data"]["events"]:
            row["owner_revision"] += 100
        self.assertNotEqual(left, right)
        self.assertEqual(
            _sdvk150_repeatability_projection(left, "probe-owner-transition"),
            _sdvk150_repeatability_projection(right, "probe-owner-transition"),
        )
        strict = copy.deepcopy(right)
        strict[0]["data"]["events"][-1]["light_probe_epoch"] += 1
        self.assertNotEqual(
            _sdvk150_repeatability_projection(left, "probe-owner-transition"),
            _sdvk150_repeatability_projection(strict, "probe-owner-transition"),
        )

    def test_partial_publication_and_stale_reset_progress_are_rejected(self):
        cases = (
            ("partial-collected", -1, "collected", 1, "not completed producer state"),
            ("wrong-next-index", -1, "next_index", 0, "not completed producer state"),
            ("reset-iteration", 6, "iteration", 5, "reset retained old progress"),
            ("reset-next-index", 6, "next_index", 2, "reset retained old progress"),
            ("reset-collected", 6, "collected", 2, "reset retained old progress"),
            ("boolean-progress", -1, "collected", False, "not a nonnegative integer"),
        )
        for name, index, field, replacement, reason in cases:
            with self.subTest(case=name):
                value = records()
                value[0]["data"]["events"][index][field] = replacement
                with self.assertRaisesRegex(EvidenceError, reason):
                    validate_lifecycle_records(value, SPEC)

    def test_wrong_count_or_undeclared_events_cannot_be_filtered_away(self):
        for kind in ("owner-reset", "count-reset", "pass-published"):
            with self.subTest(kind=kind):
                value = records()
                value[0]["data"]["events"].insert(7, event(kind, "SDV15B", 19, 5, 0, authored=1))
                with self.assertRaisesRegex(EvidenceError, "wrong authored count"):
                    validate_lifecycle_records(value, SPEC)
        value = records()
        value[0]["data"]["events"].insert(7, event("owner-reset", "SDV15C", 23, 6, 0))
        with self.assertRaisesRegex(EvidenceError, "undeclared map"):
            validate_lifecycle_records(value, SPEC)
        value = records()
        value[0]["data"]["events"].insert(7, event("empty-reset", "SDV15B", 19, 5, 0))
        with self.assertRaisesRegex(EvidenceError, "not a declared reset/publication"):
            validate_lifecycle_records(value, SPEC)

    def test_half_pair_family_is_rejected(self):
        value = records()
        for row in value[0]["data"]["events"]:
            if row["map"] == "SDV15B" and row["event"] == "pass-published":
                row["prefilter_count"] = 1
                break
        with self.assertRaises(EvidenceError):
            validate_lifecycle_records(value, SPEC)


if __name__ == "__main__":
    unittest.main()
