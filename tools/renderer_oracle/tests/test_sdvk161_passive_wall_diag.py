"""CPU-only negative controls for the isolated, nonqualifying wall-sidecar audit."""
import copy
import unittest

from tools.renderer_oracle import sdvk161_passive_wall_diag as passive
from tools.renderer_oracle.common import EvidenceError


def fixture():
    native = {"records": []}
    trace = {"schema": "sdvk161-passive-wall-trace/v1", "qualification": "NONQUALIFYING",
             "capacity": 32768, "total": 2 * 5 + 1, "retained": 2 * 5 + 1,
             "overflow": False, "rows": []}
    for frame in range(1, 97):
        native["records"].extend((
            {"kind": "frame", "frame": frame, "data": {"walls": 1, "vertices": 4}},
            {"kind": "resource", "frame": frame, "data": {
                "light_uploads": {"attempts": 1, "successful": 1, "failed": 0,
                                  "records_used": 0, "uploaded_bytes": 16}}}))
        if frame not in (4, 37):
            continue
        for stage in (2, 3, 4, 5, 6):
            trace["rows"].append({
                "frame": frame, "stage": stage, "seq": len(trace["rows"]),
                "line": 2, "side": 3, "vertices": 4 if stage == 4 else 0,
                "light_index": frame, "normal": 0, "subtractive": 0, "additive": 0})
    trace["rows"].append({
        "frame": 37, "stage": 7, "seq": len(trace["rows"]), "type": 0,
        "portal": 1, "vertices": 12, "light_index": 2,
        "normal": 0, "subtractive": 0, "additive": 0})
    return native, trace


class PassiveTraceTest(unittest.TestCase):
    def test_complete_native_trace_bridge(self):
        native, trace = fixture()
        output = passive.summaries(native, trace)
        self.assertEqual(len(output), 2)
        self.assertEqual(output["37"]["sum_emitted_vertices"], 4)
        self.assertEqual(output["37"]["actual_empty_uploads"], 1)

    def test_synthetic_one_wall_and_one_upload_omission_is_detected(self):
        # Deliberately corrupted *copies* demonstrate the precise missing
        # draw+empty-upload detector; not evidence of the historical cause.
        native, original = fixture()
        mutated = copy.deepcopy(original)
        mutated["rows"] = [
            r for r in mutated["rows"]
            if not (r["frame"] == 37 and r["stage"] in (4, 6))
        ]
        mutated["total"] = mutated["retained"] = len(mutated["rows"])
        difference = passive.compare_traces(original, mutated, 37)
        self.assertEqual(difference["actually-drawn"]["left_only_count"], 1)
        self.assertEqual(difference["successful-light-upload"]["left_only_count"], 1)
        with self.assertRaisesRegex(EvidenceError, "summed real wall draw vertices"):
            passive.summaries(native, mutated)

    def test_worker_gate_missing_fails_closed(self):
        raw, trace = fixture()
        trace["rows"] = [r for r in trace["rows"] if r["stage"] != 7]
        trace["total"] = trace["retained"] = len(trace["rows"])
        with self.assertRaisesRegex(EvidenceError, "worker schedule"):
            passive.summaries(raw, trace)

    def test_impossible_worker_start_before_all_jobs_fails_closed(self):
        raw, trace = fixture()
        next(r for r in trace["rows"] if r["stage"] == 7)["light_index"] = 13
        with self.assertRaisesRegex(EvidenceError, "worker schedule"):
            passive.summaries(raw, trace)

    def test_schedule_only_difference_does_not_forge_wall_delta(self):
        _, trace = fixture()
        alternate = copy.deepcopy(trace)
        schedule = next(r for r in alternate["rows"] if r["stage"] == 7)
        schedule["type"] = 300001
        schedule["light_index"] = schedule["vertices"]
        self.assertEqual(passive.compare_traces(trace, alternate, 37), {})

    def test_wrong_actual_draw_vertices_fails_closed(self):
        native, trace = fixture()
        next(r for r in trace["rows"] if r["frame"] == 37 and r["stage"] == 4)["vertices"] = 8
        with self.assertRaisesRegex(EvidenceError, "summed real wall draw vertices"):
            passive.summaries(native, trace)

    def test_missing_upload_call_fails_closed(self):
        native, trace = fixture()
        trace["rows"] = [r for r in trace["rows"] if not (r["frame"] == 37 and r["stage"] == 6)]
        trace["total"] = trace["retained"] = len(trace["rows"])
        with self.assertRaisesRegex(EvidenceError, "indexed actual upload"):
            passive.summaries(native, trace)

    def test_missing_frame_fails_closed(self):
        native, trace = fixture()
        trace["rows"] = [r for r in trace["rows"] if r["frame"] != 37]
        trace["total"] = trace["retained"] = len(trace["rows"])
        with self.assertRaisesRegex(EvidenceError, "frame census"):
            passive.summaries(native, trace)

    def test_overflow_fails_closed(self):
        native, trace = fixture()
        trace["overflow"] = True
        with self.assertRaisesRegex(EvidenceError, "invalid, truncated"):
            passive.summaries(native, trace)

    def test_falsified_missing_wall_is_located_by_stage(self):
        _, trace = fixture()
        broken = copy.deepcopy(trace)
        broken["rows"] = [r for r in broken["rows"] if not
                          (r["frame"] == 37 and r["stage"] == 4)]
        broken["total"] = broken["retained"] = len(broken["rows"])
        delta = passive.compare_traces(trace, broken, 37)
        self.assertEqual(delta["actually-drawn"]["left_only_count"], 1)
        self.assertNotIn("draw-entry", delta)

    def test_slot_ordinal_does_not_hide_extra_draw(self):
        _, trace = fixture()
        varied = copy.deepcopy(trace)
        next(r for r in varied["rows"] if r["frame"] == 37 and r["stage"] == 4)["light_index"] += 1000
        self.assertEqual(passive.compare_traces(trace, varied, 37), {})
        next(r for r in varied["rows"] if r["frame"] == 37 and r["stage"] == 4)["side"] += 1
        self.assertIn("actually-drawn", passive.compare_traces(trace, varied, 37))


if __name__ == "__main__":
    unittest.main()
