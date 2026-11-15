"""Focused packaging and IWAD compatibility controls, using no game assets."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from tools.dynamic_shadows import build_pr190_materials as materials
from tools.dynamic_shadows import package_windows as packaging
from tools.dynamic_shadows.qualify_material_generator import synthetic_iwad


class IwadValidationTests(unittest.TestCase):
    def test_two_common_doom_map_families_have_no_fixed_hash_whitelist(self):
        with tempfile.TemporaryDirectory() as directory:
            for map_name in ("MAP01", "E1M1"):
                path = Path(directory) / (map_name + ".wad")
                synthetic_iwad(path, map_name)
                self.assertEqual(materials.validate_iwad(path), hashlib.sha256(path.read_bytes()).hexdigest())

    def test_bad_directory_lump_extent_and_missing_material_sources_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.wad"
            synthetic_iwad(path, "MAP01")
            original = path.read_bytes()
            directory_offset = struct.unpack_from("<i", original, 8)[0]
            for offset, replacement in ((8, struct.pack("<i", len(original))),
                                        (directory_offset, struct.pack("<i", -1)),
                                        (directory_offset + 8, b"NOTAPAL\0")):
                changed = bytearray(original)
                changed[offset:offset + len(replacement)] = replacement
                path.write_bytes(changed)
                with self.subTest(offset=offset), self.assertRaises(ValueError):
                    materials.validate_iwad(path)


class WindowsPackageTests(unittest.TestCase):
    def fixture(self, root):
        build = root / "build"
        runtime = build / "RelWithDebInfo"
        for name in packaging.REQUIRED:
            path = runtime / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if name.endswith(".pk3"):
                with ZipFile(path, "w") as archive:
                    archive.writestr("synthetic.txt", name)
            else:
                path.write_bytes(b"synthetic native fixture, never executed")
        flashlight = root / "flashlight.pk3"
        with ZipFile(flashlight, "w") as archive:
            archive.writestr("ZSCRIPT", "synthetic flashlight")
        generator = root / "generator"
        generator.mkdir()
        (generator / "Build-PR190-Materials.exe").write_bytes(b"synthetic, never executed")
        return build, flashlight, generator

    def test_complete_package_has_all_engine_resources_and_local_generator(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build, flashlight, generator = self.fixture(root)
            out = root / "out"
            with patch.object(packaging.subprocess, "check_output", return_value="a" * 40 + "\n"):
                packaging.package(build, flashlight, out, "a" * 40, generator)
            manifest = json.loads((out / "PACKAGE-SHA256.json").read_text())
            self.assertFalse(manifest["game_iwad_included"])
            self.assertTrue(manifest["standalone_material_generator"])
            self.assertTrue((out / "runtime/game_widescreen_gfx.pk3").is_file())
            self.assertTrue(all("runtime/" + name in manifest["files"] for name in packaging.REQUIRED))
            for relative, digest in manifest["files"].items():
                self.assertEqual(packaging.sha256(out / relative), digest)

    def test_missing_lights_cannot_be_replaced_by_unrelated_recursive_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build, flashlight, generator = self.fixture(root)
            (build / "RelWithDebInfo/lights.pk3").unlink()
            stray = build / "fixture/unrelated/lights.pk3"
            stray.parent.mkdir(parents=True)
            stray.write_bytes(b"not the built resource")
            out = root / "out"
            with patch.object(packaging.subprocess, "check_output", return_value="a" * 40 + "\n"):
                with self.assertRaisesRegex(ValueError, "lights.pk3"):
                    packaging.package(build, flashlight, out, "a" * 40, generator)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
