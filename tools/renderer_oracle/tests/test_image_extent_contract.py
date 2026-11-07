"""Synthetic RGB8 extent admission controls; no renderer or native capture is run."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common
import images


class RGBExtentContractTests(unittest.TestCase):
    POLICY = {"metric": "exact-rgb8"}

    def test_negative_extents_cannot_become_matching_positive_pixel_counts(self):
        for extent in ((-1, -1), (-4, -2)):
            with self.subTest(extent=extent):
                raw = bytes(extent[0] * extent[1] * 3)
                with self.assertRaisesRegex(common.EvidenceError, "Invalid RGB extent"):
                    images.compare_rgb(raw, raw, extent, self.POLICY)

    def test_dimensions_must_respect_native_png_bounds(self):
        for extent in ((1921, 1), (1, 1081)):
            with self.subTest(extent=extent):
                raw = bytes(extent[0] * extent[1] * 3)
                with self.assertRaisesRegex(common.EvidenceError, "Invalid RGB extent"):
                    images.compare_rgb(raw, raw, extent, self.POLICY)

    def test_bool_float_zero_and_malformed_extents_are_rejected(self):
        for extent in ((True, 1), (1.0, 1.0), (0, 1), (1, 0), (), (1,), (1, 1, 1), None, "1x1"):
            with self.subTest(extent=extent):
                with self.assertRaisesRegex(common.EvidenceError, "Invalid RGB extent"):
                    images.compare_rgb(bytes(3), bytes(3), extent, self.POLICY)

    def test_valid_extents_preserve_exact_and_tolerant_metrics(self):
        left = bytes(6)
        right = bytes([1, 0, 0, 0, 0, 0])
        for extent in ((2, 1), [2, 1]):
            with self.subTest(extent=extent):
                equal = images.compare_rgb(left, left, extent, self.POLICY)
                self.assertTrue(equal["passed"])
                self.assertEqual(equal["changed_pixels"], 0)
                different = images.compare_rgb(left, right, extent, self.POLICY)
                self.assertFalse(different["passed"])
                self.assertEqual(different["max_channel_error"], 1)
                self.assertEqual(different["changed_pixel_fraction"], .5)
                tolerant = images.compare_rgb(left, right, extent, {
                    "metric": "rgb8-absolute", "max_channel_error": 1,
                    "mean_channel_error": .2, "changed_pixel_fraction": .5})
                self.assertTrue(tolerant["passed"])
                self.assertAlmostEqual(tolerant["mean_channel_error"], 1 / 6)

    def test_native_boundary_dimensions_remain_accepted(self):
        for extent in ((1920, 1), (1, 1080)):
            with self.subTest(extent=extent):
                raw = bytes(extent[0] * extent[1] * 3)
                self.assertTrue(images.compare_rgb(raw, raw, extent, self.POLICY)["passed"])


if __name__ == "__main__":
    unittest.main()
