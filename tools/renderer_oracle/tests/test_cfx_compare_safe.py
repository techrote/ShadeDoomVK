"""CPU-only regression for the CFX-002 matched safe-run equivalence gate."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class CPUImage:
    """Fixed RGB input for the exit gate; image decoding is outside this test."""
    size = (2, 2)

    def __init__(self, path):
        self.pixels = Path(path).read_bytes()

    def convert(self, mode):
        assert mode == "RGB"
        return self

    def tobytes(self):
        return self.pixels


# The historical comparison tool requires Pillow at execution time. The CPU
# contract suite does not: isolate its image dependency while exercising its
# actual manifest, mesh, pixel-metric and admission code, without a global stub.
spec = importlib.util.spec_from_file_location(
    "cfx_compare_safe_exit_fixture", Path(__file__).resolve().parents[2] / "cfx_compare_safe.py")
cfx_compare_safe = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"PIL": SimpleNamespace(Image=SimpleNamespace(open=CPUImage))}):
    spec.loader.exec_module(cfx_compare_safe)


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
                picture = root / (name + ".rgb")
                picture.write_bytes(bytes((12, 34, 56)) * 4)
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
