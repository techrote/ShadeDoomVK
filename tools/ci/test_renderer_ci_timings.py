"""Focused regression checks for the read-only hosted publication timing report."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.ci import renderer_ci_timings as timing


class TimingReportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "renderer-sdvk009-publication"
        (self.root / "steps").mkdir(parents=True)
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

    def test_observed_overlap_is_distinct_from_both_topology_models(self):
        intervals = [(0, 2), (2, 12), (1, 11), (3, 13)]
        for name, (start, finish) in zip(timing.CAPTURES, intervals):
            self.receipt(name, f"2026-11-06T13:00:{start:02}+00:00",
                         f"2026-11-06T13:00:{finish:02}+00:00")
        report = timing.summarize(self.root, host={})
        observed = report["capture_observation"]
        model = report["topology_model"]
        self.assertEqual(observed["observed_span_seconds"], 13)
        self.assertEqual(observed["summed_capture_seconds"], 32)
        self.assertEqual(observed["peak_overlapping_capture_steps"], 3)
        self.assertEqual(observed["sum_to_observed_span_ratio"], round(32 / 13, 6))
        self.assertTrue(observed["all_expected_captures_timed"])
        self.assertTrue(observed["all_expected_captures_passed"])
        self.assertEqual(model["ideal_parallel_capture_seconds"], 12)
        self.assertEqual(model["ideal_control_gated_capture_seconds"], 22)
        self.assertFalse(model["measured_alternative_execution"])
        self.assertIn("Modeled scheduling only", timing.markdown(report))
        self.assertIn("not end-to-end workflow speedup", timing.markdown(report))

    def test_touching_boundaries_are_serial_and_zero_length_has_no_overlap(self):
        for index, name in enumerate(timing.CAPTURES):
            self.receipt(name, f"2026-11-06T13:00:0{index}+00:00",
                         f"2026-11-06T13:00:0{index + 1}+00:00")
        report = timing.summarize(self.root, host={})
        self.assertEqual(report["capture_observation"]["peak_overlapping_capture_steps"], 1)
        self.assertEqual(report["capture_observation"]["sum_to_observed_span_ratio"], 1)
        for name in timing.CAPTURES:
            self.receipt(name, "2026-11-06T13:00:00+00:00", "2026-11-06T13:00:00+00:00")
        observed = timing.summarize(self.root, host={})["capture_observation"]
        self.assertEqual(observed["peak_overlapping_capture_steps"], 0)
        self.assertEqual(observed["observed_span_seconds"], 0)
        self.assertIsNone(observed["sum_to_observed_span_ratio"])

    def test_incomplete_or_failed_attempt_is_not_a_full_scheduling_estimate(self):
        self.receipt("shadow-control", "2026-11-06T13:00:00+00:00",
                     "2026-11-06T13:02:00+00:00", status="FAIL")
        report = timing.summarize(self.root, host={})
        self.assertEqual(report["capture_observation"]["timed_captures"], 1)
        self.assertFalse(report["capture_observation"]["all_expected_captures_timed"])
        self.assertFalse(report["capture_observation"]["all_expected_captures_passed"])
        self.assertFalse(report["topology_model"]["available"])
        self.assertIn("partial capture evidence", timing.markdown(report))

    def test_failed_assembly_retains_new_four_worker_capture_timings(self):
        workers = [{"worker": name} for name in timing.WORKERS]
        (self.root / "qualification.json").write_text(json.dumps({"status": "FAIL", "workers": workers}))
        intervals = [(3, 5), (0, 10), (0, 10), (0, 10)]
        for name, (start, finish) in zip(timing.CAPTURES, intervals):
            self.receipt(name, f"2026-11-06T13:00:{start:02}+00:00",
                         f"2026-11-06T13:00:{finish:02}+00:00")
        report = timing.summarize(self.root, host={})
        self.assertEqual(report["qualification_status"], "FAIL")
        self.assertEqual(report["workers"], workers)
        self.assertEqual(report["capture_observation"]["peak_overlapping_capture_steps"], 4)
        self.assertEqual(report["capture_duration_seconds_sum"], 32)
        model = report["topology_model"]
        self.assertEqual(model["ideal_parallel_capture_seconds"], 10)
        self.assertEqual(model["ideal_control_gated_capture_seconds"], 20)
        self.assertIn("compositing on publication worker", model["capture_assignment"])
        self.assertIn("six short publication modules preceding the independent compositing capture", model["excludes"])
        self.assertIn("**FAIL**", timing.markdown(report))

    def test_authenticated_partial_restore_without_assembly_has_no_qualification(self):
        (self.root / "qualification.json").unlink()
        report = timing.summarize(self.root, host={})
        self.assertEqual(report["qualification_status"], "NOT_ASSEMBLED")
        self.assertFalse(report["capture_observation"]["all_expected_captures_passed"])
        self.assertFalse(report["topology_model"]["available"])

    def test_worker_identity_profiles_and_inputs_remain_immutable(self):
        worker = {"worker": "controls", "worker_execution_id": "capture-worker", "hosted_run": {"RUNNER_NAME": "hosted-2"},
                  "host_identity": {"boot_id": "separate-boot"},
                  "started_utc": "2026-11-06T13:00:00+00:00", "finished_utc": "2026-11-06T13:01:00+00:00"}
        (self.root / "qualification.json").write_text(json.dumps({"status": "PASS", "workers": [worker]}))
        profile = {"worker": "controls", "cpu_model": "capture CPU", "logical_processors": 4,
                   "affinity_processors": 4, "cgroup_cpu_max": "max 100000", "mesa_vulkan_drivers_version": "test-version"}
        directory = self.base / "renderer-ci-controls"
        directory.mkdir()
        (directory / "profile.json").write_text(json.dumps(profile))
        def hashes():
            return {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in self.base.rglob('*') if path.is_file()}
        before = hashes()
        report = timing.summarize(self.root, host={"cpu_model": "aggregation CPU"})
        timing.markdown(report)
        self.assertEqual(hashes(), before)
        self.assertEqual(report["workers"], [worker])
        self.assertEqual(report["worker_profiles"]["controls"]["profile"], profile)
        self.assertEqual(report["host"]["cpu_model"], "aggregation CPU")
        self.assertEqual(report["missing_capture_worker_profiles"], [])
        self.assertIn("capture CPU", timing.markdown(report))

    def test_cross_wired_profiles_and_duplicate_worker_names_are_rejected(self):
        directory = self.base / "renderer-ci-controls"
        directory.mkdir()
        (directory / "profile.json").write_text('{"worker":"witness-1"}')
        with self.assertRaisesRegex(ValueError, "Cross-wired"):
            timing.summarize(self.root, host={})
        (directory / "profile.json").unlink()
        (self.root / "qualification.json").write_text(json.dumps({"status": "PASS", "workers": [
            {"worker": "controls"}, {"worker": "controls"}]}))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            timing.summarize(self.root, host={})

    def test_two_plus_one_placement_and_probe_cost_are_separate_from_three_way_model(self):
        assignments = ("publication", "controls", "witness-1", "controls")
        allocation = {"schema": "sdvk009-cohort-allocation/v1", "cohort": ["controls", "witness-1"],
                      "captures": [{"name": name, "worker": worker}
                                   for name, worker in zip(timing.CAPTURES, assignments)]}
        allocation["placement"] = {"candidates": [
            {"cohort": ["controls", "witness-1"], "compatible": True,
             "score_milliseconds": 2500, "within_near_minimum": True}],
            "minimum_score_milliseconds": 2500, "selected_score_milliseconds": 2500}
        qualification = {"status": "PASS", "workers": [{"worker": name} for name in timing.WORKERS],
                         "cohort_allocation": allocation, "cohort_allocation_sha256": "a" * 64}
        (self.root / "qualification.json").write_text(json.dumps(qualification))
        for name, (start, finish) in zip(timing.CAPTURES, ((3, 5), (0, 10), (0, 10), (10, 20))):
            self.receipt(name, f"2026-11-06T13:00:{start:02}+00:00",
                         f"2026-11-06T13:00:{finish:02}+00:00")
        for worker in timing.WORKERS[1:]:
            name = "cohort-probe-" + worker
            path = self.root / "distributed-probes" / worker / "steps" / (name + ".json")
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"name": name, "status": "PASS",
                "started_utc": "2026-11-06T12:59:50+00:00", "finished_utc": "2026-11-06T12:59:52+00:00",
                "result": {"elapsed_seconds": 1.25}}))
        barrier = self.base / "renderer-ci-controls/cohort-barrier.json"
        barrier.parent.mkdir()
        barrier.write_text('{"status":"PASS","elapsed_seconds":3}')
        before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in self.base.rglob('*') if path.is_file()}
        report = timing.summarize(self.root, host={})
        cohort = report["cohort_scheduling"]
        self.assertEqual(cohort["allocated_capture_lower_bound_seconds"], 20)
        self.assertEqual(cohort["worker_capture_seconds"],
                         {"publication": 2, "controls": 20, "witness-1": 10, "witness-2": 0})
        self.assertEqual(cohort["probe_attempt_seconds_sum"], 6)
        self.assertEqual(cohort["probe_native_seconds_sum"], 3.75)
        self.assertEqual(cohort["barrier_reports"]["controls"]["elapsed_seconds"], 3)
        self.assertEqual(cohort["placement_model"], allocation["placement"])
        self.assertTrue(cohort["all_probe_receipts_retained"])
        self.assertFalse(cohort["qualification_authority"])
        self.assertEqual(report["capture_duration_seconds_sum"], 32)
        self.assertEqual(report["capture_observation"]["observed_span_seconds"], 20)
        self.assertEqual(report["topology_model"]["ideal_parallel_capture_seconds"], 10)
        self.assertIn("unconstrained three-way model", timing.markdown(report))
        self.assertIn("not predicted full-capture durations", timing.markdown(report))
        after = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in self.base.rglob('*') if path.is_file()}
        self.assertEqual(before, after)

    def test_cohort_report_rejects_cross_wired_assignment_and_invalid_native_time(self):
        allocation = {"schema": "sdvk009-cohort-allocation/v1", "cohort": ["controls"],
                      "captures": [{"name": name, "worker": worker} for name, worker in
                                   zip(timing.CAPTURES, ("publication", "controls", "controls", "witness-2"))]}
        (self.root / "qualification.json").write_text(json.dumps({"status": "FAIL", "cohort_allocation": allocation}))
        with self.assertRaisesRegex(ValueError, "Cross-wired cohort"):
            timing.summarize(self.root, host={})
        for value in (True, -1, float('nan'), float('inf')):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "native elapsed"):
                timing.native_elapsed({"result": {"elapsed_seconds": value}})


if __name__ == "__main__":
    unittest.main()
