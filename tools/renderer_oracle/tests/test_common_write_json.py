"""CPU-only regression controls for fresh renderer evidence JSON receipts.

No native renderer, Vulkan device or physical campaign is used.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from pathlib import Path
import tempfile
import unittest

from tools.renderer_oracle import common


class WriteJsonPreflightTests(unittest.TestCase):
    def test_nonfinite_payload_does_not_reserve_an_artifact(self):
        for bad in (float("nan"), {"nested": [1, float("inf")]},
                    {"nested": {"bad": float("-inf")}}):
            with self.subTest(bad=repr(bad)), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "attempt.json"
                with self.assertRaises(common.EvidenceError):
                    common.write_json(path, {"evidence": bad})
                self.assertFalse(path.exists(), "Invalid JSON must not leave an empty immutable receipt")

    def test_unserializable_payload_does_not_reserve_an_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "attempt.json"
            with self.assertRaises(TypeError):
                common.write_json(path, {"bad": object()})
            self.assertFalse(path.exists())

    def test_invalid_payload_does_not_create_evidence_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "attempt" / "steps"
            with self.assertRaises(common.EvidenceError):
                common.write_json(directory / "receipt.json", {"bad": float("nan")})
            self.assertFalse(directory.parent.exists())

    def test_valid_payload_remains_canonical_and_write_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "attempt" / "receipt.json"
            value = {"z": [1, 2], "a": "complete"}
            common.write_json(path, value)
            original = path.read_bytes()
            self.assertEqual(original, common.canonical(value))
            self.assertEqual(common.read_json(path), value)
            with self.assertRaises(FileExistsError):
                common.write_json(path, {"new": True})
            self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
