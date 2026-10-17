"""Exercise actual LevelMesh draw observation against CPU command services.

The production submission loop, diagnostic callback and canonical serializers
run unchanged. Pipeline application and command buffers are explicit doubles;
these tests create no renderer, Vulkan device or native rendering evidence.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import block

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
VULKAN = ROOT / "src/common/rendering/vulkan"
DIAGNOSTICS = ROOT / "src/rendering/hwrenderer/diagnostics"
RENDERSTATE = VULKAN / "vk_renderstate.cpp"
OBSERVER = VULKAN / "textures/vk_sdvkdiagnostics.cpp"
HEADER = ROOT / "src/common/rendering/hwrenderer/data/hw_renderstate.h"
FIXTURE = HERE / "sdvk_levelmesh_draw_fixture.cpp"


def definition(source: str, signature: str) -> str:
    if source.count(signature) != 1:
        raise AssertionError("Expected unique LevelMesh definition: " + signature)
    return block(source[source.index(signature):], signature)


def build(directory: Path, *, missing_hook: bool = False):
    directory.mkdir(parents=True, exist_ok=True)
    source = RENDERSTATE.read_text()
    method = definition(source, "void VkRenderState::DrawLevelMeshList(")
    (directory / "levelmesh_declaration.inc").write_text(
        method.split("{", 1)[0].replace("VkRenderState::", "") + ";\n")
    if missing_hook:
        # Preserve the previous unobserved producer: only its new callback is
        # removed. The submitted commands, keys and loop decisions stay live.
        hook = re.compile(
            r"if \(range.Count\(\) > 0 && SdvkDiagnostics::StateEnabled\(\)\)\s*"
            r"SdvkDiagnostics::VulkanLevelMeshDraw\(this, range.Start, range.Count\(\), surface\);")
        method, count = hook.subn("(void)surface;", method)
        if count != 1:
            raise AssertionError("Expected one actual LevelMesh draw hook")
    (directory / "levelmesh_loop.inc").write_text(method + "\n")
    (directory / "levelmesh_surface.inc").write_text(
        definition(HEADER.read_text(), "enum class LevelMeshDrawSurface") + ";\n")
    observer = OBSERVER.read_text()
    (directory / "levelmesh_serializers.inc").write_text(
        "namespace {\n" + "\n".join(definition(observer, signature) for signature in (
            "std::string Shader(", "std::string Pipeline(")) + "\n}\n")
    (directory / "levelmesh_access.inc").write_text(
        "struct FSdvkDiagnosticAccess {\n" +
        "static void LevelMeshSurfaces(VkRenderState*, int, int) { throw std::logic_error(\"SDVK-161 was not requested\"); }\n" +
        definition(observer, "static void LevelMeshDraw(") + "\n};\n")
    (directory / "levelmesh_callback.inc").write_text(
        "namespace SdvkDiagnostics {\n" +
        definition(observer, "void VulkanLevelMeshDraw(") + "\n}\n")
    return compile_fixture(FIXTURE, output_dir=directory,
                           includes=[directory, DIAGNOSTICS, VULKAN])


class LevelMeshDrawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="sdvk-levelmesh-draw-")
        directory = Path(cls.temp.name)
        cls.current = build(directory / "current")
        cls.previous = build(directory / "missing-hook", missing_hook=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def execute(self, scenario, *, missing_hook=False):
        executable = self.previous if missing_hook else self.current
        result = subprocess.run([str(executable), scenario], text=True,
                                capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_submitted_ranges_keep_final_keys_context_and_post_draw_order(self):
        result = self.execute("side")
        self.assertEqual(result["error"], "")
        self.assertEqual(result["pipeline_ids"], [1, 3])
        self.assertEqual([event["event"] for event in result["events"]],
                         ["apply", "draw", "observe", "draw", "observe",
                          "apply", "draw", "observe"])
        draws = [event for event in result["events"] if event["event"] == "draw"]
        rows = result["records"]
        self.assertEqual(len(rows), 3)
        self.assertEqual([(row["data"]["first_index"], row["data"]["draw_count"])
                          for row in rows], [(7, 6), (40, 3), (90, 12)])
        for row, draw in zip(rows, draws):
            data = row["data"]
            self.assertEqual(row["kind"], "pipeline")
            self.assertTrue(row["deduplicate"])
            self.assertTrue(data["indexed"])
            self.assertEqual(data["producer"], "levelmesh-indexed-range")
            self.assertEqual(data["surface"], "side")
            self.assertEqual(data["context"], {"available": True, "fixture_id": 17})
            self.assertEqual(data["key"], draw["bound_key"])
            # Application overwrote both raster and shader fields in the
            # seed key. Reading the pre-Apply mesh key cannot satisfy this.
            self.assertEqual(data["key"]["CullMode"], 2)
            self.assertEqual(data["key"]["ColorMask"], 5)
            self.assertEqual(data["key"]["shader"]["UseLevelMesh"], 1)
            self.assertEqual(data["key"]["shader"]["ShadeVertex"], 1)
            self.assertEqual(data["key"]["shader"]["GBufferPass"], 1)
            self.assertEqual((data["target_width"], data["target_height"]), (640, 480))
            self.assertEqual((data["target_format"], data["target_samples"]), (44, 4))
            self.assertEqual(data["draw_buffers"], 2)
            self.assertTrue(data["depth_stencil"])
            self.assertNotIn("material", data)
            self.assertNotIn("probe", data)
            self.assertNotIn("shadow", data)
            self.assertIn("no per-surface material/probe", data["basis"])
        self.assertEqual(result["context_reads"], 3)
        self.assertEqual(result["immediate_calls"], 0)

    def test_flat_family_is_explicit_and_post_apply_masking_is_preserved(self):
        result = self.execute("flat")
        self.assertEqual(len(result["records"]), 3)
        for row in result["records"]:
            self.assertEqual(row["data"]["surface"], "flat")
            shader = row["data"]["key"]["shader"]
            self.assertEqual(shader["AlphaTestOnly"], 1)
            self.assertEqual(shader["NoFragmentShader"], 0)

    def test_empty_lists_and_zero_index_commands_cannot_create_witnesses(self):
        empty = self.execute("empty")
        self.assertEqual(empty["events"], [])
        self.assertEqual(empty["pipeline_ids"], [])
        for scenario in ("empty", "zero"):
            result = self.execute(scenario)
            self.assertEqual(result["records"], [])
            self.assertEqual(result["context_reads"], 0)
        zero = self.execute("zero")
        self.assertEqual([event["event"] for event in zero["events"]], ["apply", "draw"])
        self.assertEqual(zero["events"][-1]["draw_count"], 0)

    def test_disabled_and_timing_modes_do_not_read_diagnostic_state(self):
        for scenario in ("off", "timing"):
            with self.subTest(scenario=scenario):
                result = self.execute(scenario)
                self.assertEqual([event["event"] for event in result["events"]],
                                 ["apply", "draw", "draw", "apply", "draw"])
                self.assertEqual(result["records"], [])
                self.assertEqual(result["context_reads"], 0)
                self.assertEqual(result["immediate_calls"], 0)
                self.assertEqual(result["error"], "")

    def test_missing_producer_hook_preserves_draws_but_loses_geometry_evidence(self):
        current = self.execute("side")
        previous = self.execute("side", missing_hook=True)
        commands = lambda result: [event for event in result["events"]
                                   if event["event"] != "observe"]
        self.assertEqual(commands(previous), commands(current))
        self.assertEqual(previous["pipeline_ids"], current["pipeline_ids"])
        self.assertEqual(previous["records"], [])
        self.assertEqual(previous["context_reads"], 0)
        self.assertEqual(len(current["records"]), 3)

    def test_diagnostic_exception_fails_without_fabricating_a_pipeline_row(self):
        result = self.execute("failure")
        self.assertEqual(result["error"], "fixture current context failure")
        self.assertEqual(result["records"], [])
        self.assertEqual(result["context_reads"], 1)
        self.assertEqual(len([e for e in result["events"] if e["event"] == "draw"]), 3)

    def test_live_callers_supply_the_actual_surface_family_and_final_key(self):
        source = (ROOT / "src/rendering/hwrenderer/scene/hw_drawinfo.cpp").read_text()
        calls = re.findall(r"state\.DrawLevelMeshList\(([^;]+)\);", source)
        self.assertTrue(calls)
        for call in calls:
            family = "Side" if call.startswith("SeenSidesDrawLists.") else "Flat"
            self.assertTrue(call.startswith(("SeenSidesDrawLists.", "SeenFlatsDrawLists.")))
            self.assertIn("LevelMeshDrawSurface::" + family + ",", call)
        applied = definition(RENDERSTATE.read_text(), "void VkRenderState::ApplyLevelMeshPipeline(")
        saved = applied.index("mPipelineKey = pipelineKey;")
        self.assertLess(applied.index("pipelineKey.CullMode = mCullMode;"), saved)
        self.assertLess(applied.index("pipelineKey.ShaderKey.Layout.Simple3D = mWireframe;"), saved)
        self.assertLess(saved, applied.index("cmdbuffer->bindPipeline("))


if __name__ == "__main__":
    unittest.main()
