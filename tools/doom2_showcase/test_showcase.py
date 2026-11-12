"""Copyright-free regression checks for the optional add-on builder."""

from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

import numpy as np

import build
from material_profiles_v2 import cpu_controls
from sprite_materials import maps_for


class ShowcaseTests(unittest.TestCase):
    def test_flashlight_package_contains_only_addon_sources(self):
        with TemporaryDirectory() as scratch:
            out = Path(scratch)
            build.build_flashlight(out)
            with ZipFile(out / "Local-Flashlight.pk3") as package:
                self.assertEqual(tuple(package.namelist()), build.FLASHLIGHT_FILES)
                self.assertIsNone(package.testzip())

    def test_wrong_iwad_leaves_no_output(self):
        with TemporaryDirectory() as scratch:
            source = Path(scratch) / "doom2.wad"
            source.write_bytes(b"not the supported WAD")
            out = Path(scratch) / "output"
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    build.__file__,
                    "--doom2",
                    str(source),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Unexpected WAD identity", result.stderr)
            self.assertFalse(out.exists())

    def test_material_semantics(self):
        self.assertEqual(cpu_controls()["status"], "PASS")
        pixels = np.full((16, 24, 4), (96, 96, 96, 255), dtype=np.uint8)
        pixels[:, :3, 3] = 0
        pixels[4:8, 8:16, :3] = 144
        gun = maps_for(pixels, "weapon", "PISGA0")
        flesh = maps_for(pixels, "flesh", "TROOA1")
        self.assertGreater(gun["metallic"][6, 10], 150)
        self.assertLess(flesh["metallic"][6, 10], 15)
        self.assertLess(gun["roughness"][6, 10], flesh["roughness"][6, 10])
        self.assertEqual(gun["normal"].shape, (16, 24, 3))
        length = np.linalg.norm(gun["normal"].astype(float) / 127.5 - 1, axis=2)
        self.assertTrue(np.all(np.abs(length - 1) < 0.015))


if __name__ == "__main__":
    unittest.main()
