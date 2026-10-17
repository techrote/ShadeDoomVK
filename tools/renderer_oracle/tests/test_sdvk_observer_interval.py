"""Execute production observer intervals and bounds without a renderer or GPU.

The actual Observer, frame/collection methods, VulkanDraw gate and RecordStore
run unchanged. Engine data, draw payloads and Vulkan resource snapshots are
small CPU services; they are not native rendering or image evidence.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import block

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
DIAGNOSTICS = ROOT / "src/rendering/hwrenderer/diagnostics"
SOURCE = DIAGNOSTICS / "hw_sdvkdiagnostics.cpp"
VULKAN = ROOT / "src/common/rendering/vulkan/textures/vk_sdvkdiagnostics.cpp"
FIXTURE = HERE / "sdvk_observer_interval_fixture.cpp"
RESET = "StateFlag.store(false, std::memory_order_relaxed);"


def definition(source: str, signature: str) -> str:
    # Source-scoped extraction avoids unrelated C++ digit separators/raw strings.
    if source.count(signature) != 1:
        raise AssertionError("Expected unique observer definition: " + signature)
    return block(source[source.index(signature):], signature)


def build(directory: Path, *, original: bool = False):
    directory.mkdir(parents=True, exist_ok=True)
    source = SOURCE.read_text()
    state = definition(source, "struct Observer\n") + ";\n"
    state += "\n".join(definition(source, signature) for signature in (
        "Observer& Get()", "void Require(", "template<class V> std::string Vector("))
    (directory / "observer_state.inc").write_text("namespace {\n" + state + "\n}\n")
    (directory / "observer_dump.inc").write_text(
        "namespace {\n" + definition(source, "void Dump(bool complete)") + "\n}\n")
    methods = []
    for signature in (
        "void Fail(", "void ProbeBuilderLifecycle(", "void Emit(",
        "void BeginFrame()", "void EndFrame()", "void FramePresented()",
        "void GpuGroup(", "void GpuUnavailable(",
    ):
        method = definition(source, signature)
        if original and signature == "void EndFrame()":
            # Preserve the failing pre-fix behavior by removing only the new
            # state-interval close; all other production decisions stay live.
            if method.count(RESET) != 1:
                raise AssertionError("Expected one EndFrame state interval close")
            method = method.replace(RESET, "", 1)
        methods.append(method)
    methods.append(definition(VULKAN.read_text(), "void VulkanDraw("))
    (directory / "observer_methods.inc").write_text(
        "namespace SdvkDiagnostics {\n" + "\n".join(methods) + "\n}\n")
    return compile_fixture(FIXTURE, output_dir=directory,
                           includes=[directory, DIAGNOSTICS])


class ObserverIntervalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="sdvk-observer-interval-")
        cls.directory = Path(cls.temp.name)
        cls.current = build(cls.directory / "current")
        cls.original = build(cls.directory / "pre-fix", original=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def execute(self, scenario: str, *, original: bool = False):
        executable = self.original if original else self.current
        prefix = self.directory / (self.id().split(".")[-1] + ("-old" if original else ""))
        result = subprocess.run([str(executable), scenario, str(prefix)],
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        summary = json.loads(result.stdout)
        envelope = json.loads(prefix.with_suffix(".renderer.json").read_text())
        return summary, envelope

    def assert_complete(self, summary, envelope, requested=3):
        self.assertEqual(envelope["status"], "COLLECTED_PENDING_VALIDATION")
        self.assertEqual(envelope["observed_frames"], requested)
        self.assertEqual(envelope["dropped_records"], 0)
        self.assertEqual(envelope["error"], "")
        self.assertEqual(summary["late_draw_payloads"], 0)
        self.assertFalse(summary["enabled_after_presentation"])
        self.assertFalse(summary["state_after_presentation"])
        self.assertFalse(summary["gpu_after_presentation"])
        self.assertEqual(envelope["limits"]["max_records"], 65536)
        self.assertEqual(envelope["limits"]["max_retained_bytes"], 16 * 1024 * 1024)

    def test_post_view_flood_is_excluded_and_next_views_reopen_collection(self):
        summary, envelope = self.execute("state")
        self.assert_complete(summary, envelope)
        self.assertEqual(summary["warmup_draw_payloads"], 0)
        self.assertEqual(summary["main_draw_payloads"], 3)
        self.assertEqual(summary["canvas_draw_payloads"], 3)
        rows = [r for r in envelope["records"] if r["kind"] == "pipeline"]
        self.assertEqual([(r["frame"], r["data"]["phase"]) for r in rows],
                         [(frame, phase) for frame in (1, 2, 3)
                          for phase in ("canvas", "main")])

    def test_pre_fix_interval_leak_exhausts_the_unchanged_record_store(self):
        summary, envelope = self.execute("state", original=True)
        self.assertEqual(envelope["status"], "FAIL")
        self.assertEqual(envelope["observed_frames"], 1)
        self.assertGreater(envelope["dropped_records"], 0)
        self.assertGreater(summary["late_draw_payloads"], 0)
        self.assertLess(envelope["limits"]["retained_records"], 65536)
        self.assertGreater(envelope["limits"]["retained_bytes"], 16 * 1024 * 1024 - 16384)
        self.assertIn("record/byte limit reached", envelope["error"])

    def test_resources_and_delayed_gpu_results_keep_their_frame_identity(self):
        summary, envelope = self.execute("state")
        self.assert_complete(summary, envelope)
        resources = [r for r in envelope["records"] if r["kind"] == "resource"]
        self.assertEqual([r["frame"] for r in resources], [1, 2, 3])
        self.assertTrue(all(r["data"]["state_enabled"] for r in resources))
        timing = [r for r in envelope["records"] if r["kind"] == "timing"]
        self.assertEqual([r["frame"] for r in timing], [1, 2, 3])
        self.assertTrue(all(r["data"]["name"] == "after-render-view" for r in timing))
        self.assertEqual(envelope["availability"]["gpu_timing"]["groups"], 3)

    def test_lifecycle_trace_spans_warmup_and_between_view_callbacks(self):
        summary, envelope = self.execute("state")
        self.assert_complete(summary, envelope)
        rows = [r for r in envelope["records"] if r["kind"] == "probe-builder"]
        events = [(r["frame"], e["event"]) for r in rows for e in r["data"]["events"]]
        self.assertEqual(events, [(1, "warmup-reset"), (2, "between-view-publication")])
        self.assertEqual(summary["lifecycle_events_after_close"], 0)

    def test_timing_mode_excludes_state_and_retains_gpu_after_end(self):
        summary, envelope = self.execute("timing")
        self.assert_complete(summary, envelope)
        self.assertEqual(summary["warmup_draw_payloads"], 0)
        self.assertEqual(summary["main_draw_payloads"], 0)
        self.assertEqual(summary["canvas_draw_payloads"], 0)
        self.assertEqual({r["kind"] for r in envelope["records"]},
                         {"frame", "resource", "timing"})
        self.assertFalse(envelope["availability"]["state"]["available"])
        resources = [r for r in envelope["records"] if r["kind"] == "resource"]
        self.assertTrue(all(not r["data"]["state_enabled"] for r in resources))
        self.assertEqual(envelope["availability"]["gpu_timing"]["groups"], 3)

    def test_real_in_scope_overflow_still_fails_closed(self):
        summary, envelope = self.execute("overflow")
        self.assertEqual(envelope["status"], "FAIL")
        self.assertGreater(envelope["dropped_records"], 0)
        self.assertIn("record/byte limit reached", envelope["error"])
        self.assertEqual(summary["late_draw_payloads"], 0)
        self.assertFalse(summary["enabled_after_presentation"])
        self.assertFalse(summary["state_after_presentation"])

    def test_resource_snapshot_exception_also_closes_state_interval(self):
        summary, envelope = self.execute("snapshot-failure")
        self.assertEqual(envelope["status"], "FAIL")
        self.assertEqual(envelope["error"], "fixture resource snapshot failure")
        self.assertEqual(envelope["dropped_records"], 1)  # delayed GPU result rejected
        self.assertEqual(summary["late_draw_payloads"], 0)
        self.assertFalse(summary["enabled_after_presentation"])
        self.assertFalse(summary["state_after_presentation"])


if __name__ == "__main__":
    unittest.main()
