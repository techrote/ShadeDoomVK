"""CPU-only production snapshot serialization and immutable-output contract."""
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import compile_fixture

ROOT = Path(__file__).resolve().parents[3]


class CollisionSnapshotWriterTests(unittest.TestCase):
    def test_little_endian_defined_fields_and_no_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="collision-writer-") as directory:
            destination = Path(directory) / "snapshot.bin"
            executable = compile_fixture(
                ROOT / "tools/pf_oracle/tests/collision_snapshot_writer_fixture.cpp",
                includes=[ROOT / "src/common/rendering/hwrenderer/data"], output_dir=directory)
            subprocess.run([str(executable), str(destination)], check=True, timeout=30)
            self.assertEqual(destination.read_bytes(), b"SDVKCL01" +
                             struct.pack("<IIff4sIIii", 0x12345678, 0xffffffff,
                                         -0.0, 1.5, b"TEST", 2, 4, -2147483647, 2147483647))


if __name__ == "__main__":
    unittest.main()
