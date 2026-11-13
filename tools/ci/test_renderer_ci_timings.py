"""Focused regression checks for the read-only hosted publication timing report."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.ci import renderer_ci_timings as timing


class TimingReportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "steps").mkdir()
        (self.root / "qualification.json").write_text('{"status": "FAIL"}', encoding="utf-8")

    def receipt(self, name, started, finished, status="PASS"):
        (self.root / "steps" / (name + ".json")).write_text(
            json.dumps({"name": name, "status": status,
                        "started_utc": started, "finished_utc": finished}),
            encoding="utf-8")

    def test_preserves_each_capture_and_missing_steps(self):
        self.receipt("shadow-control", "2026-11-06T13:06:13+00:00",
                     "2026-11-06T13:47:13+00:00")
        report = timing.summarize(self.root, host={"runner_environment": "github-hosted"})
        self.assertEqual(report["qualification_status"], "FAIL")
        self.assertEqual(report["capture_duration_seconds_sum"], 2460.0)
        self.assertEqual([r["status"] for r in report["actual_processes"]],
                         ["NOT_RUN", "PASS", "NOT_RUN", "NOT_RUN"])
        self.assertFalse(report["physical_gpu_qualified"])
        self.assertFalse(report["performance_accepted"])
        self.assertIn("41.00 min", timing.markdown(report))

    def test_rejects_misnamed_receipt_and_invalid_clock(self):
        name = "compositing-control"
        self.receipt(name, "2026-11-06T13:07:00+00:00", "2026-11-06T13:06:00+00:00")
        with self.assertRaisesRegex(ValueError, "backwards"):
            timing.summarize(self.root, host={})
        self.receipt(name, "2026-11-06T13:06:00+00:00", "2026-11-06T13:07:00+00:00")
        receipt = self.root / "steps" / (name + ".json")
        data = json.loads(receipt.read_text(encoding="utf-8"))
        data["name"] = "unrelated"
        receipt.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "name mismatch"):
            timing.summarize(self.root, host={})

    def test_rejects_timezone_less_receipts(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            timing.duration_seconds({"started_utc": "2026-11-06T13:00:00",
                                     "finished_utc": "2026-11-06T13:01:00"})


if __name__ == "__main__":
    unittest.main()
