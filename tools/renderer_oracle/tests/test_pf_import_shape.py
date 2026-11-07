"""Synthetic PF source-index admission, independent of original PF qualification."""
import json
from pathlib import Path
import tempfile
import unittest
import adapters
import common

SPECS = {
    "pf020-native-scene-observation/v1": ("COLLECTED_STATE_ONLY", "records"),
    "shadedoomvk-pf020-vulkan-observation/v1": ("COLLECTED_PENDING_VALIDATION", "keyLookups"),
    "shadedoomvk-pf110-native-indexed/v1": ("PASS", "cases"),
    "shadedoomvk-pf113-startup-observer/v1": ("PASS", "draws"),
    "shadedoomvk-pf113-native-probe-controls/v1": ("PASS", "cases"),
}


class PFImportShapeTests(unittest.TestCase):
    def _adapt(self, value):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            return adapters.adapt(path)

    def test_scalar_and_wrong_container_cannot_claim_observations(self):
        for schema, (status, field) in SPECS.items():
            for value in ("fake", 1, False, {"fake": "record"}, ["fake"], [0], [{}]):
                with self.subTest(schema=schema, field=field, value=value):
                    with self.assertRaises(common.EvidenceError):
                        self._adapt({"schema": schema, "status": status, field: value})

    def test_optional_field_wrong_type_does_not_hide_behind_a_valid_channel(self):
        cases = [
            ("shadedoomvk-pf020-vulkan-observation/v1", "COLLECTED_PENDING_VALIDATION",
             {"keyLookups": [{"count": 1}], "workerState": [1]}),
            ("shadedoomvk-pf020-vulkan-observation/v1", "COLLECTED_PENDING_VALIDATION",
             {"workerState": {"queued": 1}, "images": ["fake"]}),
            ("shadedoomvk-pf113-startup-observer/v1", "PASS",
             {"draws": [{"kind": "actual"}], "events": False}),
            ("shadedoomvk-pf113-native-probe-controls/v1", "PASS",
             {"cases": [{"name": "actual"}], "resources": [1]}),
        ]
        for schema, status, fields in cases:
            with self.subTest(schema=schema, fields=fields):
                with self.assertRaises(common.EvidenceError):
                    self._adapt({"schema": schema, "status": status, **fields})

    def test_positive_indexing_retains_source_and_qualification_limits(self):
        cases = [
            ("pf020-native-scene-observation/v1", "COLLECTED_STATE_ONLY", {"records": [{"event": "scene"}]},
             "context", ["/records"]),
            ("shadedoomvk-pf020-vulkan-observation/v1", "COLLECTED_PENDING_VALIDATION",
             {"workerState": {"queued": 0}}, "pipeline", ["/workerState"]),
            ("shadedoomvk-pf110-native-indexed/v1", "PASS", {"cases": [{"token": {"index": 5}}]},
             "resources", ["/cases/0/token"]),
            ("shadedoomvk-pf113-startup-observer/v1", "PASS",
             {"draws": [{"kind": "actual"}], "events": [{"kind": "published"}]},
             "probe", ["/draws", "/events"]),
            ("shadedoomvk-pf113-native-probe-controls/v1", "PASS",
             {"cases": [{"name": "actual"}], "resources": {"pairA": 1}}, "resources", ["/resources"]),
        ]
        for schema, status, fields, channel, pointers in cases:
            with self.subTest(schema=schema):
                source = {"schema": schema, "status": status, **fields}
                result = self._adapt(source)
                self.assertEqual(result["original"], source)
                self.assertEqual(result["channels"][channel]["json_pointers"], pointers)
                self.assertEqual(result["validation"].split(";")[0], "indexed_only")
                self.assertFalse(result["fresh_execution"])
                self.assertFalse(result["current_build_equivalence_established"])

    def test_empty_observations_and_unhashable_schema_fail_as_evidence_error(self):
        for payload in ({"schema": ["pf020-native-scene-observation/v1"], "status": "COLLECTED_STATE_ONLY"},
                        {"schema": {"value": "pf020-native-scene-observation/v1"}, "status": "COLLECTED_STATE_ONLY"},
                        {"schema": "pf020-native-scene-observation/v1", "status": "COLLECTED_STATE_ONLY", "records": []}):
            with self.subTest(payload=payload), self.assertRaises(common.EvidenceError):
                self._adapt(payload)


if __name__ == "__main__":
    unittest.main()
