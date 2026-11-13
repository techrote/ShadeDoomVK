"""Copyright-free regression checks for the optional add-on builder."""

from pathlib import Path
import re
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

import numpy as np
from PIL import Image

import build
from dbp50_effective import reconstruct_rows
import gallery
from material_profiles_v2 import cpu_controls
from sprite_materials import maps_for


def switch_fixture():
    palette = bytearray(768)
    palette[3:9] = bytes((64, 64, 64, 192, 20, 12))
    texture = struct.pack("<8sIhhIh", b"SW1TEST", 0, 2, 2, 0, 1)
    texture += struct.pack("<hhhhh", 0, 0, 0, 0, 0)
    original = {
        "PLAYPAL": bytes(palette),
        "PNAMES": struct.pack("<i8s", 1, b"SWPATCH"),
        "TEXTURE1": struct.pack("<ii", 1, 8) + texture,
        "SWPATCH": patch(1),
    }
    entries = [dict(name="SW1TEST", kind="wall", family="metal", id=1)]
    return original, entries


def patch(color):
    column = bytes((0, 2, 0, color, color, 0, 255))
    return struct.pack("<hhhhII", 2, 2, 0, 0, 16, 23) + column * 2


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

    def test_palette_only_change_selects_override(self):
        original, entries = switch_fixture()
        palette = bytearray(original["PLAYPAL"])
        palette[3:6] = bytes((136, 25, 18))
        replacement = {"PLAYPAL": bytes(palette)}
        rows = reconstruct_rows(original, replacement, {}, entries)
        self.assertTrue(rows[0]["rgba_changed"])
        self.assertFalse(rows[0]["pattern_changed"])
        [(row, context)] = build.dbp50_material_inputs(rows, original, replacement)
        self.assertEqual(tuple(row["pixels"][0, 0]), (136, 25, 18, 255))
        self.assertTrue(np.all(context["switch_mask"] == 1))
        unchanged = reconstruct_rows(original, {}, {}, entries)
        self.assertEqual(list(build.dbp50_material_inputs(unchanged, original, {})), [])

    def test_switch_patch_uses_inherited_definition(self):
        original, entries = switch_fixture()
        replacement = {"SWPATCH": patch(2)}
        rows = reconstruct_rows(original, replacement, {}, entries)
        self.assertTrue(rows[0]["pattern_changed"])
        [(row, context)] = build.dbp50_material_inputs(rows, original, replacement)
        self.assertEqual(tuple(row["pixels"][0, 0]), (192, 20, 12, 255))
        self.assertTrue(np.all(context["switch_mask"] == 1))

    def test_gallery_archive_resources_and_navigation(self):
        with TemporaryDirectory() as scratch:
            out = Path(scratch)
            channels = ("albedo", "normal", "specular", "metallic", "roughness", "ao")
            files = {}
            for channel in channels:
                filename = f"{channel}.png"
                Image.new("RGBA", (16, 16), (120, 96, 48, 255)).save(out / filename)
                files[channel] = filename
            entry = dict(
                name="SW1TEST",
                kind="wall",
                family="metal",
                width=16,
                height=16,
                files=files,
                aliases={"legacy": "L0000001", "normal": "N0000001", "pbr": "P0000001"},
            )
            gallery.build(
                {"entries": [entry], "iwad": "synthetic", "iwad_sha256": "synthetic"},
                out,
                ["SW1TEST"],
                [("SGSWITCH", "Switches", ["SW1TEST"])],
            )
            with ZipFile(out / "DoomII-Material-Gallery.pk3") as package:
                self.assertIsNone(package.testzip())
                names = set(package.namelist())
                mapinfo = package.read("MAPINFO").decode()
                maps = re.findall(r"(?m)^map (\w+)", mapinfo)
                self.assertEqual(maps, ["SGSHOW", "SGSWITCH", "SG0002"])
                self.assertEqual(
                    re.findall(r'(?m)^  next = "(\w+)"', mapinfo), maps[1:] + maps[:1]
                )
                self.assertEqual(
                    re.findall(r'(?m)^  secretnext = "(\w+)"', mapinfo),
                    maps[-1:] + maps[:-1],
                )
                menu = package.read("MENUDEF").decode()
                for name in maps:
                    self.assertIn(f'"map {name}"', menu)
                    data = package.read(f"maps/{name}.wad")
                    self.assertEqual(data[:4], b"PWAD")
                    self.assertIn(b"TEXTMAP", data)
                    self.assertIn(b"ENDMAP", data)
                gldefs = package.read("GLDEFS").decode()
                self.assertTrue(set(re.findall(r'"([^"]+)"', gldefs)) <= names)
                for alias in entry["aliases"].values():
                    self.assertIn(f"textures/{alias}.png", names)
                self.assertIn("MaterialGalleryMenu", package.read("KEYCONF").decode())
            self.assertIn("SW1TEST", (out / "INDEX.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
