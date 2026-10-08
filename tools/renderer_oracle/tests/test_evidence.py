"""Evidence integrity/metric controls; all constructed records are synthetic."""
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import adapters
import benchmark
import common
import images


def png(rgb, width=2, height=1, compression=9):
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))
    rows = b"".join(b"\0" + rgb[y*width*3:(y+1)*width*3] for y in range(height))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + \
        chunk(b"IDAT", zlib.compress(rows, compression)) + chunk(b"IEND", b"")


class EvidenceIntegrityTests(unittest.TestCase):
    def test_reject_duplicate_nonfinite_and_numeric_overflow_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "input.json"
            for raw in ('{"a":1,"a":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e9999}'):
                path.write_text(raw)
                with self.subTest(raw=raw), self.assertRaises(common.EvidenceError):
                    common.read_json(path)

    def test_artifacts_have_exact_bytes_and_no_path_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "a").write_bytes(b"retained")
            identity = common.pin(root / "a", relative_to=root)
            self.assertEqual(common.checked(root, identity), root / "a")
            for name in ("../a", "/a", "x/../a", "a\\b", "C:/a", "./a", "a//b"):
                with self.subTest(name=name), self.assertRaises(common.EvidenceError):
                    common.artifact_path(root, name)
            (root / "a").write_bytes(b"modified")
            with self.assertRaises(common.EvidenceError):
                common.checked(root, identity)

    def test_an_existing_attempt_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "result.json"
            common.write_json(path, {"retained": True})
            with self.assertRaises(FileExistsError):
                common.write_json(path, {"retained": False})
            self.assertTrue(common.read_json(path)["retained"])


class ImagePolicyTests(unittest.TestCase):
    def test_pixel_identity_is_independent_of_png_compression(self):
        with tempfile.TemporaryDirectory() as temporary:
            left, right = Path(temporary) / "a.png", Path(temporary) / "b.png"
            rgb = bytes([0, 100, 255, 7, 11, 19])
            left.write_bytes(png(rgb, compression=0))
            right.write_bytes(png(rgb, compression=9))
            self.assertNotEqual(left.read_bytes(), right.read_bytes())
            result = images.compare(left, right, {"metric": "exact-rgb8"})
            self.assertTrue(result["passed"])
            self.assertEqual(result["changed_pixels"], 0)

    def test_small_global_mean_cannot_hide_a_large_local_error(self):
        left = bytes(300)
        right = bytes([255]) + bytes(299)
        result = images.compare_rgb(left, right, (100, 1), {
            "metric": "rgb8-absolute", "max_channel_error": 8,
            "mean_channel_error": 1, "changed_pixel_fraction": .02})
        self.assertFalse(result["passed"])
        self.assertEqual(result["max_channel_error"], 255)

    def test_crc_truncation_extent_and_non_rgb_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "input.png"
            good = png(bytes(6))
            for raw in (good[:-1], good + b"trailing", good[:-5] + b"wrong", png(bytes(6), width=0)):
                path.write_bytes(raw)
                with self.assertRaises(common.EvidenceError):
                    images.decode(path)

    def test_all_tolerances_must_be_explicit_and_bounded(self):
        for policy in ({"metric": "unknown"}, {"metric": "rgb8-absolute"},
                       {"metric": "exact-rgb8", "tolerance": 1},
                       {"metric": "rgb8-absolute", "max_channel_error": True,
                        "mean_channel_error": 1, "changed_pixel_fraction": 1}):
            with self.assertRaises(common.EvidenceError):
                images.validate_policy(policy)


class BenchmarkTests(unittest.TestCase):
    def test_known_percentiles_and_raw_sample_count(self):
        summary = benchmark.distribution([1, 2, 3, 4], minimum_samples=4)
        self.assertEqual(summary["p50"], 2.5)
        self.assertAlmostEqual(summary["p95"], 3.85)
        self.assertAlmostEqual(summary["p99"], 3.97)
        self.assertEqual(summary["count"], 4)

    def test_missing_negative_nonfinite_and_boolean_samples_fail(self):
        for samples in ([], [1, -1], [1, math.nan], [1, math.inf], [True]):
            with self.assertRaises(common.EvidenceError):
                benchmark.distribution(samples, minimum_samples=1)
        with self.assertRaises(common.EvidenceError):
            benchmark.distribution([1] * 29)

    def test_state_capture_cannot_be_relabelled_as_ordinary_timing(self):
        with self.assertRaises(common.EvidenceError):
            benchmark.summarize({"mode": "state", "records": []})

    def test_gpu_nested_groups_stay_separate(self):
        records = [{"kind": "frame", "data": {"cpu_render_view_ms": 2}}] * 30
        records += [{"kind": "timing", "data": {"clock": "gpu", "name": name, "milliseconds": value}}
                    for name, value in (("Scene", 10), ("Scene/Opaque", 8))]
        summary = benchmark.summarize({"mode": "timing", "records": records})
        self.assertNotIn("gpu_frame_ms", summary)
        self.assertEqual(set(summary["gpu_groups"]), {"Scene", "Scene/Opaque"})


class PFImportTests(unittest.TestCase):
    def test_indexed_resource_tokens_are_indexed_at_their_actual_case_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic-pf110.json"
            common.write_json(path, {"schema": "shadedoomvk-pf110-native-indexed/v1", "status": "PASS",
                                   "cases": [{"token": {"index": 5, "generation": 1, "epoch": 1, "span": 2}}]})
            result = adapters.adapt(path)
            self.assertEqual(result["channels"]["resources"]["json_pointers"], ["/cases/0/token"])

    def test_import_preserves_raw_scope_and_does_not_invent_channels(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic-pf.json"
            data = {"schema": "pf020-native-scene-observation/v1", "status": "COLLECTED_STATE_ONLY",
                    "error": "", "records": [{"event": "scene", "semanticKey": "synthetic"}]}
            common.write_json(path, data)
            result = adapters.adapt(path)
            self.assertEqual(result["original"], data)
            self.assertFalse(result["fresh_execution"])
            self.assertFalse(result["current_build_equivalence_established"])
            self.assertEqual(result["channels"]["timing"]["status"], "not_collected")

    def test_failed_empty_unknown_producer_cannot_be_promoted(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "input.json"
            for data in ({"schema": "unknown", "status": "PASS"},
                         {"schema": "pf020-native-scene-observation/v1", "status": "FAIL"},
                         {"schema": "pf020-native-scene-observation/v1", "status": "COLLECTED_STATE_ONLY", "records": []}):
                path.write_text(json.dumps(data))
                with self.assertRaises(common.EvidenceError):
                    adapters.adapt(path)


if __name__ == "__main__":
    unittest.main()
