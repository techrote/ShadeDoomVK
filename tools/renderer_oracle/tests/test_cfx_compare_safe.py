"""CPU-only regression for the CFX-002 matched safe-run equivalence gate."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from tools import cfx_compare_safe


class SafeCompareExitStatusTests(unittest.TestCase):
    def compare(self, outcomes):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            argv = ["cfx_compare_safe.py"]
            for name, (status, exit_status) in zip(("off", "capture", "repeat"), outcomes):
                directory = root / name
                (directory / "work").mkdir(parents=True)
                (directory / "work" / "levelmesh.obj").write_text(
                    "# same mesh\n# revision\no sector\nv 0 0 0\nvt 0 0\nf 1 1 1\n",
                    encoding="utf-8")
                (directory / "manifest.json").write_text(json.dumps({
                    "run_id": "synthetic-" + name,
                    "source": {"exe": {"sha256": "a" * 64}, "local_patch_sha256": "b" * 64},
                    "content": [{"sha256": "c" * 64}],
                    "run": {"config_sha256": "d" * 64,
                            "map": "MAP01", "actual_resolution": [2, 2]},
                    "status": status, "exit_status": exit_status,
                }), encoding="utf-8")
                picture = root / (name + ".png")
                Image.new("RGB", (2, 2), (12, 34, 56)).save(picture)
                argv.extend((f"--{name}-run", str(directory),
                             f"--{name}-image", str(picture)))
            output = root / "result.json"
            argv.extend(("--out", str(output)))
            with patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
                rc = cfx_compare_safe.main()
            return rc, json.loads(output.read_text(encoding="utf-8"))

    def test_three_successful_runs_are_admitted(self):
        rc, result = self.compare([("EXITED", 0)] * 3)
        self.assertEqual(rc, 0)
        self.assertTrue(result["pass"])
        self.assertTrue(result["state_assertions"]["exit_zero"])

    def test_three_matching_nonzero_exits_are_not_admitted(self):
        rc, result = self.compare([("EXITED", 1)] * 3)
        self.assertEqual(rc, 1)
        self.assertFalse(result["pass"])
        self.assertFalse(result["state_assertions"]["exit_zero"])

    def test_three_matching_non_exit_states_are_not_admitted(self):
        rc, result = self.compare([("TIMEOUT", 0)] * 3)
        self.assertEqual(rc, 1)
        self.assertFalse(result["pass"])
        self.assertFalse(result["state_assertions"]["exit_zero"])

    def test_one_failed_capture_is_not_admitted(self):
        rc, result = self.compare([("EXITED", 0), ("EXITED", 2), ("EXITED", 0)])
        self.assertEqual(rc, 1)
        self.assertFalse(result["pass"])
        self.assertFalse(result["state_assertions"]["exit_zero"])


if __name__ == "__main__":
    unittest.main()
