"""Native fixture authoring and deliberately falsified image-gate controls.

Synthetic RGB here tests only the checker. It cannot be submitted as a native
rendered result; native_capture additionally requires actual source identity,
engine completion, Vulkan observation, upload state and original screenshots.
"""
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.dynamic_shadows import native_capture, native_scene
from tools.pf_oracle.fixture_runner import run_fixture


class NativeActorShadowContracts(unittest.TestCase):
    def test_actual_cpp_alpha_filter(self):
        result = run_fixture("tools/pf_oracle/tests/actor_shadowmask_fixture.cpp",
            includes=["src/common/rendering/hwrenderer/data"], capture_output=True)
        self.assertIn("negative controls PASS", result.stdout)

    def test_original_fixture_is_deterministic_and_has_both_light_channels(self):
        first = native_scene.archive()
        self.assertEqual(first, native_scene.archive())
        with zipfile.ZipFile(io.BytesIO(first)) as archive:
            names = set(archive.namelist())
            self.assertIn("sprites/SH02A0.png", names)
            self.assertIn("maps/SDVSHD.wad", names)
            self.assertNotIn("PLAYPAL", names)
            self.assertIn(b"SH002Caster", archive.read("ZSCRIPT"))
        self.assertTrue(native_scene.opaque(10, 66))
        self.assertFalse(native_scene.opaque(31, 66))
        self.assertFalse(native_scene.opaque(31, 26))
        self.assertFalse(native_scene.opaque(50, 45))
        self.assertTrue(native_scene.opaque(13, 45))
        self.assertFalse(native_scene.opaque(0, 0, solid=True))

    def test_changed_camera_does_not_redefine_receiver_world_points(self):
        a, b = native_scene.witnesses(), native_scene.witnesses("orbit")
        for name in ("floor_opaque", "floor_hole", "wall_opaque", "wall_hole", "floor_notch"):
            self.assertEqual(a[name]["world"], b[name]["world"])
            self.assertNotEqual(a[name]["pixel"], b[name]["pixel"])
            point = a[name]["world"]
            if name.startswith("floor_"):
                self.assertAlmostEqual(point[2], 0.)
            else:
                self.assertAlmostEqual(point[1], native_scene.WALL_Y)

    def test_receiver_patch_excludes_foreground_card_with_pixel_margin(self):
        for variant in ("base", "orbit"):
            origin, yaw = native_scene.camera(variant)
            for name, sample in native_scene.witnesses(variant).items():
                if not name.startswith("sprite_"):
                    self.assertTrue(native_scene.receiver_patch_is_clear(sample, origin, yaw), name)
        # Retained native failure: the old left-side camera sampled the visible
        # sprite at (370,331), not the intended floor behind it. The source and
        # world receiver are unchanged; this camera must fail authoring checks.
        old = dict(native_scene.witnesses()["floor_opaque"],
                   pixel=[369.74181950256633, 330.69994281677447])
        self.assertFalse(native_scene.receiver_patch_is_clear(old, (-64, -256, 96), 80))
        # Its center ray clears the card, but the complete
        # 3x3 pixel patch overlaps. A center-only visibility test is insufficient.
        edge = dict(native_scene.witnesses()["floor_opaque"], pixel=[358, 335])
        self.assertFalse(native_scene.receiver_patch_is_clear(edge, (0, -280, 96), 90))

    def test_animation_replaces_only_the_notch_and_uses_real_tic_pacing(self):
        members = native_scene.members(variant="animated")
        self.assertIn(b"SH02 A 10; SH02 B -1", members["ZSCRIPT"])
        self.assertNotEqual(members["sprites/SH02A0.png"], members["sprites/SH02B0.png"])
        self.assertTrue(native_scene.recipe(variant="animated")["settings"]["cl_capfps"])

    @staticmethod
    def images(*, corrupt=None, flip=False, solid=False, variant="base"):
        off = bytes((160, 70, 120)) * (640 * 480)
        on = bytearray(off)
        for name, sample in native_scene.witnesses(variant).items():
            blocked = name.endswith("opaque") or (flip and name.endswith("notch"))
            blocked = blocked or (solid and name.endswith(("hole", "notch")))
            if corrupt == "solid" and name.endswith("hole"):
                blocked = True
            if corrupt == "self" and name.startswith("sprite_"):
                blocked = True
            cx, cy = (round(x) for x in sample["pixel"])
            for y in range(cy - 1, cy + 2):
                for x in range(cx - 1, cx + 2):
                    at = (y * 640 + x) * 3
                    if blocked:
                        on[at] -= 40
                        if corrupt == "ambient": on[at + 1] -= 20
                        if corrupt == "other_light": on[at + 2] -= 20
        return off, bytes(on)

    def test_discriminates_source_specific_alpha_shadow(self):
        native_capture.assess_pair(*self.images())
        native_capture.assess_pair(*self.images(flip=True), variant="flip")
        native_capture.assess_pair(*self.images(flip=True), variant="animated")

    def test_unchanged_or_black_output_cannot_pass(self):
        original, _ = self.images()
        for rgb in (original, bytes(len(original))):
            with self.assertRaisesRegex(ValueError, "shadow missing|control is absent"):
                native_capture.assess_pair(rgb, rgb)

    def test_rejects_global_darkening_filled_holes_self_shadow_and_wrong_flip(self):
        for mutation in ("ambient", "other_light", "solid", "self"):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                native_capture.assess_pair(*self.images(corrupt=mutation))
        with self.assertRaisesRegex(ValueError, "shadow missing"):
            native_capture.assess_pair(*self.images(), variant="flip")

    def test_failed_pair_keeps_later_measurements_and_fails_overall(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decoded = {}
            for case in native_capture.CASES:
                material, variant, enabled = case
                out = root / native_capture.case_name(*case)
                out.mkdir()
                off, on = self.images(variant=variant, solid=variant == "solid",
                                      flip=variant in ("flip", "animated"))
                # A real missing red shadow must fail, while later successful
                # controls remain inspectable in the same bounded run.
                if material == "pbr" or variant == "invisible":
                    on = off
                decoded[out / "native.png"] = (native_scene.EXTENT, on if enabled else off)
            with patch.object(native_capture.images, "decode", side_effect=decoded.__getitem__):
                result = native_capture.assess(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(set(result["errors"]), {"pbr-base"})
            self.assertEqual(len(result["witnesses"]), 8)
            self.assertTrue(result["witnesses"]["invisible_off_on_identical"])
            self.assertGreater(result["witnesses"]["normal-animated"]["floor_notch"]["red_loss"], 8)
            self.assertTrue((root / "normal-animated-on" / "image-acceptance.json").is_file())


if __name__ == "__main__":
    unittest.main()
