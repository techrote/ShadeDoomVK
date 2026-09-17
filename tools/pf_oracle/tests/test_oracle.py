from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


RUN_PATH = Path(__file__).resolve().parents[1] / "run.py"
SPEC = importlib.util.spec_from_file_location("pf_oracle_run", RUN_PATH)
assert SPEC and SPEC.loader
oracle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(oracle)


class OracleTests(unittest.TestCase):
    def make_repo(self, files: dict[str, str]) -> Path:
        root = Path(self.tempdir.name)
        for relpath, content in files.items():
            path = root / relpath
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
        return root

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    @staticmethod
    def manifest(probes):
        return {
            "schema_version": 1,
            "programme": "PF-001-test",
            "baseline_lineage": "fixture",
            "probes": probes,
        }

    def test_invariant_and_known_defect_are_classified(self):
        root = self.make_repo({"source.txt": "stable marker\nknown bad marker\n"})
        result = oracle.evaluate_manifest(
            root,
            self.manifest(
                [
                    {
                        "id": "stable",
                        "category": "test",
                        "kind": "invariant",
                        "owner": "PF-X",
                        "paths": ["source.txt"],
                        "required": ["stable marker"],
                    },
                    {
                        "id": "known",
                        "category": "test",
                        "kind": "known_defect",
                        "owner": "PF-Y",
                        "paths": ["source.txt"],
                        "required": ["known bad marker"],
                    },
                ]
            ),
        )
        self.assertEqual(result["summary"]["unexpected"], 0)
        by_id = {item["id"]: item for item in result["probes"]}
        self.assertEqual(by_id["stable"]["classification"], "invariant_passed")
        self.assertEqual(by_id["known"]["classification"], "known_defect_reproduced")

    def test_known_defect_disappearing_requires_deliberate_baseline_update(self):
        root = self.make_repo({"source.txt": "fixed now\n"})
        result = oracle.evaluate_manifest(
            root,
            self.manifest(
                [
                    {
                        "id": "known",
                        "category": "test",
                        "kind": "known_defect",
                        "owner": "PF-Y",
                        "paths": ["source.txt"],
                        "required": ["known bad marker"],
                    }
                ]
            ),
        )
        self.assertEqual(result["summary"]["unexpected"], 1)
        self.assertEqual(result["probes"][0]["classification"], "known_defect_changed")

    def test_forbidden_pattern_breaks_invariant(self):
        root = self.make_repo({"source.txt": "good marker\nforbidden marker\n"})
        result = oracle.evaluate_manifest(
            root,
            self.manifest(
                [
                    {
                        "id": "stable",
                        "category": "test",
                        "kind": "invariant",
                        "owner": "PF-X",
                        "paths": ["source.txt"],
                        "required": ["good marker"],
                        "forbidden": ["forbidden marker"],
                    }
                ]
            ),
        )
        self.assertEqual(result["summary"]["unexpected"], 1)
        self.assertEqual(result["probes"][0]["classification"], "invariant_broken")

    def test_results_are_deterministic_and_sorted(self):
        root = self.make_repo({"source.txt": "a b\n"})
        probes = [
            {
                "id": "z-last",
                "category": "test",
                "kind": "invariant",
                "owner": "PF-X",
                "paths": ["source.txt"],
                "required": ["b"],
            },
            {
                "id": "a-first",
                "category": "test",
                "kind": "invariant",
                "owner": "PF-X",
                "paths": ["source.txt"],
                "required": ["a"],
            },
        ]
        one = oracle.evaluate_manifest(root, self.manifest(probes))
        two = oracle.evaluate_manifest(root, self.manifest(list(reversed(probes))))
        self.assertEqual(one, two)
        self.assertEqual([p["id"] for p in one["probes"]], ["a-first", "z-last"])
        self.assertEqual(oracle._canonical_json(one), oracle._canonical_json(two))

    def test_duplicate_probe_ids_are_rejected(self):
        root = self.make_repo({"source.txt": "a\n"})
        duplicate = {
            "id": "same",
            "category": "test",
            "kind": "invariant",
            "owner": "PF-X",
            "paths": ["source.txt"],
            "required": ["a"],
        }
        with self.assertRaises(oracle.OracleError):
            oracle.evaluate_manifest(root, self.manifest([duplicate, dict(duplicate)]))

    def test_canonical_json_ignores_object_key_input_order(self):
        a = {"b": 2, "a": {"y": 2, "x": 1}}
        b = json.loads('{"a":{"x":1,"y":2},"b":2}')
        self.assertEqual(oracle._canonical_json(a), oracle._canonical_json(b))


if __name__ == "__main__":
    unittest.main()
