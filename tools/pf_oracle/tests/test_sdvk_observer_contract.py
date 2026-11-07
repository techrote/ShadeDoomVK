"""SDVK-002 bounded native observer controls; no GPU qualification claim."""
from pathlib import Path
import json
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle.fixture_runner import run_fixture


class SdvkObserverTests(unittest.TestCase):
    def test_actual_core_limits_concurrency_nonfinite_and_no_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="sdvk-observation-test-") as directory:
            output = Path(directory) / "control.json"
            run_fixture(
                ROOT / "tools/pf_oracle/tests/sdvk_observation_fixture.cpp",
                includes=[ROOT / "src/rendering/hwrenderer/diagnostics"],
                args=[str(output)],
            )
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(data["schema"], "sdvk-observation-core-fixture/v1")
            self.assertEqual(data["unicode"], "é 東京 🎮")
            self.assertEqual(data["records"][0]["count"], 160)
            self.assertEqual(data["records"][1]["data"]["cpu_render_view_ms"], 1.125)

    def test_sampler_material_observer_does_not_create_or_validate_resources(self):
        source = (ROOT / "src/common/rendering/vulkan/textures/vk_sdvkdiagnostics.cpp").read_text()
        executable = re.sub(r"//[^\n]*", "", source)
        for name in ["GetDescriptorEntry", "GetImage", "GetIndexedMaterialImage", "ValidateTexture", "GetLightProbeTextureIndex", "ValidateBindlessIdentity"]:
            self.assertNotRegex(executable, rf"\b{name}\s*\(")
        self.assertIn("GetLayerDiagnostic", source)
        self.assertIn("GetCreationArguments", source)
        # The shared serializer reads the exact already-bound uniform index in
        # both immediate and submitted-mesh paths, without resolving resources.
        self.assertIn("candidate.bindlessIndex == uniforms.uTextureIndex", source)
        self.assertIn("Material(fb, state->mMaterial, state->mSurfaceUniforms, context)", source)
        self.assertIn("Material(state->fb, materialState, uniforms, context)", source)

    def test_pipeline_serialization_covers_canonical_fields(self):
        source = (ROOT / "src/common/rendering/vulkan/textures/vk_sdvkdiagnostics.cpp").read_text()
        canonical = (ROOT / "src/common/rendering/vulkan/vk_keyidentity.h").read_text()
        body = canonical.split("struct ShaderState", 1)[1].split("auto Tie()", 1)[0]
        fields = re.findall(r"(?:uint8_t|int)\s+(\w+)\s*=", body)
        self.assertGreater(len(fields), 30)
        for field in fields:
            self.assertIn(f"SDVK_SHADER_FIELD({field});", source)

    def test_nonfinite_guards_use_precise_native_compiler_flags(self):
        cmake = (ROOT / "src/CMakeLists.txt").read_text()
        group = cmake.split(
            "set_source_files_properties(rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.cpp", 1
        )[1].split(")", 1)[0]
        for source in [
            "common/rendering/vulkan/textures/vk_sdvkdiagnostics.cpp",
            "common/rendering/vulkan/commands/vk_commandbuffer.cpp",
        ]:
            self.assertIn(source, group)
        self.assertIn('PROPERTIES COMPILE_FLAGS "${PF020_DIAGNOSTIC_MATH}"', group)
        self.assertIn('set(PF020_DIAGNOSTIC_MATH "-fno-fast-math -ffp-contract=off")', cmake)
        self.assertIn('set(PF020_DIAGNOSTIC_MATH "/fp:precise")', cmake)

    def test_camera_and_hardware_angles_keep_their_actual_domains(self):
        source = (ROOT / "src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.cpp").read_text()
        frame_camera = source.split('.Raw("camera",', 1)[1].split('.Raw("settings",', 1)[0]
        self.assertIn('.Raw("angles", \'[\' + Number(r_viewpoint.Angles.Yaw.Degrees())', frame_camera)
        self.assertIn('Number(r_viewpoint.Angles.Pitch.Degrees())', frame_camera)
        self.assertIn('Number(r_viewpoint.Angles.Roll.Degrees())', frame_camera)
        self.assertIn('.Raw("hardware_angles", \'[\' + Number(r_viewpoint.HWAngles.Yaw.Degrees())', frame_camera)
        context = source.split("std::string Context(", 1)[1].split("void Dump(", 1)[0]
        self.assertIn('Number(vp.HWAngles.Yaw.Degrees())', context)
        self.assertIn('.Str("angle_space", "hardware-view")', context)

    def test_observer_messages_do_not_render_capture_paths_in_the_hud(self):
        source = (ROOT / "src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.cpp").read_text()
        calls = re.findall(r'\bPrintf\s*\(([^\n]+)', source)
        self.assertGreater(len(calls), 0)
        self.assertTrue(all(call.startswith('PRINT_HIGH | PRINT_NONOTIFY, ') for call in calls))

    def test_frame_closes_after_existing_gpu_resolution_and_preserves_pf(self):
        main = (ROOT / "src/d_main.cpp").read_text()
        body = main.split("static void End2DAndUpdate()", 1)[1].split("//====", 1)[0]
        self.assertLess(body.index("screen->Update()"), body.index("SdvkDiagnostics::FramePresented()"))
        scene = (ROOT / "src/rendering/hwrenderer/scene/hw_drawinfo.cpp").read_text()
        self.assertIn("Pf020ViewDiagnostics::SceneBegin(this, drawmode)", scene)
        self.assertIn("Pf020ViewDiagnostics::SceneEnd(this)", scene)
        header = (ROOT / "src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.h").read_text()
        self.assertIn("memory_order_relaxed", header)
        observer = (ROOT / "src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.cpp").read_text()
        self.assertIn('"COLLECTED_PENDING_VALIDATION" : "FAIL"', observer)
        self.assertIn("observer.Records.DroppedCount() == 0", observer)
        completion = observer.split("void FramePresented()", 1)[1].split("void SceneBegin(", 1)[0]
        # A console screenshot only schedules ga_screenshot. The completion
        # path must use the existing writer before quit, with tracing stopped.
        final_capture = completion.split("const bool complete =", 1)[1]
        self.assertLess(final_capture.index("StateFlag.store(false"), final_capture.index("M_ScreenShot("))
        self.assertLess(final_capture.index("GpuFlag.store(false"), final_capture.index("M_ScreenShot("))
        self.assertLess(final_capture.index("M_ScreenShot("), final_capture.index('AddCommandString("quit")'))
        # Opt-in intermediate checkpoints are state-only and run after EndFrame
        # has closed per-draw capture, before any next-phase input is queued.
        end_frame = observer.split("void EndFrame()", 1)[1].split("void FramePresented()", 1)[0]
        self.assertIn("StateFlag.store(false", end_frame)
        checkpoint = completion.split("const bool complete =", 1)[0]
        self.assertIn("observer.SpecialSurfaceInput && frame > 0 && frame <= 96 && frame % 8 == 0", checkpoint)
        self.assertLess(checkpoint.index("M_ScreenShot("), checkpoint.index("DriveSpecialSurfaceInput(observer)"))

    def test_context_producer_and_fallback_slots_are_explicit(self):
        hardware = (ROOT / "src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.cpp").read_text(encoding="utf-8")
        vulkan = (ROOT / "src/common/rendering/vulkan/textures/vk_sdvkdiagnostics.cpp").read_text(encoding="utf-8")
        self.assertIn('.Str("producer", kind)', hardware)
        self.assertIn('"fallback-placeholder"', vulkan)
        self.assertIn('GetSourceLump() == 0', vulkan)
        self.assertIn('GetWidth() == 1', vulkan)
        self.assertIn('GetHeight() == 1', vulkan)


if __name__ == "__main__":
    unittest.main()
