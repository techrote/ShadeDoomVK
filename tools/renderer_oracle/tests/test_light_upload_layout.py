"""Strict byte accounting for historical and source-alpha-sidecar native light records.

These synthetic observations exercise the consumer. They are not Vulkan proof.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common
import validate
from test_validation import observation, recount, row


def packet(*, current=True):
    stride = 80
    uploads = {"available": True, "range_capacity": 16, "record_capacity": 16,
               "range_capacity_bytes": 256, "record_capacity_bytes": 16 * stride,
               "range_entries_used": 2, "records_used": 3, "attempts": 2,
               "successful": 2, "failed": 0, "index_capacity_failures": 0,
               "data_capacity_failures": 0, "normal_records": 2,
               "subtractive_records": 0, "additive_records": 1,
               "uploaded_bytes": 32 + 3 * stride, "peak_records_per_upload": 3,
               "records_per_upload_histogram": {"empty": 1, "1_4": 1, "5_16": 0,
                                                 "17_64": 0, "65_256": 0, "257_plus": 0}}
    if current:
        uploads.update(record_layout="fdynlightinfo-shadow002-sidecar-v1",
                       record_stride_bytes=stride, range_stride_bytes=16)
    resource = {"descriptor_capacity": 128, "descriptor_current": 4,
                "descriptor_high_water": 4, "descriptor_dynamic_start": 16,
                "texture_epoch": 1, "lightmap_epoch": 1, "probe_epoch": 1,
                "async_upload_epoch": 1, "light_uploads": uploads}
    raw = observation()
    raw["records"].append(row("resource", resource))
    return recount(raw), uploads


class LightRecordLayoutTests(unittest.TestCase):
    def test_native_sidecar_layout_and_historical_packets_both_validate(self):
        for current in (False, True):
            with self.subTest(current=current):
                raw, _ = packet(current=current)
                self.assertEqual(validate.observation(raw)["status"], "PASS")

    def test_missing_or_invented_layout_cannot_authorize_larger_records(self):
        for field in ("record_layout", "record_stride_bytes", "range_stride_bytes"):
            raw, uploads = packet()
            del uploads[field]
            with self.subTest(missing=field), self.assertRaises(common.EvidenceError):
                validate.observation(raw)
        raw, uploads = packet()
        for field in ("record_layout", "record_stride_bytes", "range_stride_bytes"):
            del uploads[field]
        uploads["record_capacity_bytes"] = 16 * 544
        with self.assertRaisesRegex(common.EvidenceError, "capacity byte accounting"):
            validate.observation(raw)
        for field, value in (("record_layout", "unregistered"), ("record_stride_bytes", 544),
                             ("record_stride_bytes", 545), ("record_stride_bytes", True),
                             ("range_stride_bytes", 32)):
            raw, uploads = packet()
            uploads[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(common.EvidenceError):
                validate.observation(raw)

    def test_capacity_and_transfer_totals_remain_independently_checked(self):
        for field in ("range_capacity_bytes", "record_capacity_bytes", "uploaded_bytes"):
            raw, uploads = packet()
            uploads[field] += 16
            with self.subTest(field=field), self.assertRaises(common.EvidenceError):
                validate.observation(raw)

    def test_invented_stride_with_consistent_totals_is_rejected(self):
        raw, uploads = packet()
        uploads.update(record_stride_bytes=560, record_capacity_bytes=16 * 560,
                       uploaded_bytes=32 + 3 * 560)
        with self.assertRaisesRegex(common.EvidenceError, "Unrecognized dynamic-light record layout"):
            validate.observation(raw)

    def test_capacity_failures_and_class_accounting_are_still_rejected(self):
        for edits in ({"normal_records": 3}, {"failed": 1, "attempts": 3},
                      {"records_used": 17, "normal_records": 16, "uploaded_bytes": 32 + 17 * 80}):
            raw, uploads = packet()
            uploads.update(edits)
            with self.subTest(edits=edits), self.assertRaises(common.EvidenceError):
                validate.observation(raw)


if __name__ == "__main__":
    unittest.main()
