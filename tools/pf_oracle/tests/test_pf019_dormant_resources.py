#!/usr/bin/env python3
"""PF-019 dormant tiled-light resource and no-speculation contract."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle.fixture_runner import run_fixture


def source(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


def function_body(text: str, signature: str) -> str:
    start = text.find(signature)
    if start < 0:
        raise AssertionError(f"missing function signature: {signature}")
    brace = text.find("{", start)
    if brace < 0:
        raise AssertionError(f"missing function body: {signature}")
    depth = 0
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[brace + 1:index]
    raise AssertionError(f"unterminated function body: {signature}")


class PF019DormantResourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = source("src/common/rendering/vulkan/vk_lighttilepolicy.h")
        cls.device = source("src/common/rendering/vulkan/vk_renderdevice.h")
        cls.buffers = source("src/common/rendering/vulkan/textures/vk_renderbuffers.cpp")
        cls.descriptors = source("src/common/rendering/vulkan/descriptorsets/vk_descriptorset.cpp")
        cls.shader = source("src/common/rendering/vulkan/shaders/vk_shader.cpp")
        cls.renderpass = source("src/common/rendering/vulkan/pipelines/vk_renderpass.cpp")
        cls.renderpass_h = source("src/common/rendering/vulkan/pipelines/vk_renderpass.h")
        cls.shader_h = source("src/common/rendering/vulkan/shaders/vk_shader.h")
        cls.renderstate = source("src/common/rendering/vulkan/vk_renderstate.cpp")
        cls.drawinfo = source("src/rendering/hwrenderer/scene/hw_drawinfo.cpp")
        cls.frag = source("wadsrc/static/shaders/scene/frag_main.glsl")

    def test_accepted_consumer_is_proven_dormant(self) -> None:
        self.assertIn("//uLightIndex = int(uint(gl_FragCoord.x)", self.frag)
        self.assertIn("uLightIndex = -1;", self.frag)
        dispatch = self.drawinfo.index("state.DispatchLightTiles(")
        comment_open = self.drawinfo.rfind("/*", 0, dispatch)
        comment_close = self.drawinfo.find("*/", dispatch)
        self.assertGreaterEqual(comment_open, 0)
        self.assertGreater(comment_close, dispatch)

    def test_one_explicit_policy_seam_defaults_disabled(self) -> None:
        self.assertIn("inline constexpr bool Enabled = false;", self.policy)
        self.assertIn("bool IsLightTilesEnabled() const { return VkLightTilePolicy::Enabled; }", self.device)

    def test_resize_skips_zminmax_but_preserves_levelmesh_binding_buffer(self) -> None:
        begin = function_body(self.buffers, "void VkRenderBuffers::BeginFrame(int width, int height, int sceneWidth, int sceneHeight)")
        create_tiles = function_body(self.buffers, "void VkRenderBuffers::CreateSceneLightTiles(int width, int height)")
        self.assertIn("if (fb->IsLightTilesEnabled())", begin)
        self.assertIn("CreateSceneZMinMax(width, height);", begin)
        self.assertIn("CreateSceneLightTiles(width, height);", begin)
        self.assertIn("VkLightTilePolicy::BufferSize(", create_tiles)
        self.assertIn("fb->IsLightTilesEnabled()", create_tiles)
        levelmesh = function_body(self.descriptors, "void VkDescriptorSetManager::UpdateLevelMeshSet()")
        self.assertIn("SceneLightTiles.get()", levelmesh)
        self.assertIn("VK_DESCRIPTOR_TYPE_STORAGE_BUFFER", levelmesh)

    def test_dormant_descriptor_work_is_not_created_allocated_or_rewritten(self) -> None:
        ctor = function_body(self.descriptors, "VkDescriptorSetManager::VkDescriptorSetManager(VulkanRenderDevice* fb)")
        init = function_body(self.descriptors, "void VkDescriptorSetManager::Init()")
        frame = function_body(self.descriptors, "void VkDescriptorSetManager::BeginFrame()")
        for body in (ctor, init, frame):
            self.assertIn("fb->IsLightTilesEnabled()", body)
        self.assertIn("CreateLightTilesLayout();", ctor)
        self.assertIn("CreateZMinMaxPool();", ctor)
        self.assertIn("LightTiles.Set = LightTiles.Pool->allocate", init)
        self.assertIn("UpdateLightTilesSet();", frame)
        self.assertIn("UpdateZMinMaxSet();", frame)

    def test_dormant_shader_and_pipeline_creation_are_gated(self) -> None:
        shader_ctor = function_body(self.shader, "VkShaderManager::VkShaderManager(VulkanRenderDevice* fb)")
        pass_ctor = function_body(self.renderpass, "VkRenderPassManager::VkRenderPassManager(VulkanRenderDevice* fb)")
        dispatch = function_body(self.renderstate, "void VkRenderState::DispatchLightTiles(const VSMatrix& worldToView, float m5)")
        self.assertIn("if (fb->IsLightTilesEnabled())", shader_ctor)
        self.assertIn("ZMinMax.vert = CachedGLSLCompiler()", shader_ctor)
        self.assertIn("LightTiles = CachedGLSLCompiler()", shader_ctor)
        self.assertIn("if (fb->IsLightTilesEnabled())", pass_ctor)
        self.assertIn("CreateLightTilesPipeline();", pass_ctor)
        self.assertIn("CreateZMinMaxPipeline();", pass_ctor)
        self.assertTrue(dispatch.lstrip().startswith("if (!fb->IsLightTilesEnabled())\n\t\treturn;"))

    def test_pf006_ordered_key_topology_is_deliberately_unchanged(self) -> None:
        self.assertIn("std::map<VkPipelineKey, PipelineData> GeneralizedPipelines;", self.renderpass_h)
        self.assertIn("std::map<VkPipelineKey, PipelineData> SpecializedPipelines;", self.renderpass_h)
        self.assertIn("std::map<uint64_t, std::unique_ptr<VkShaderProgram>> generic;", self.shader_h)
        self.assertIn("std::map<VkShaderKey, std::unique_ptr<VkShaderProgram>> specialized;", self.shader_h)
        self.assertNotIn("unordered_map", self.renderpass_h + self.shader_h)

    def test_compiled_resource_policy_fixture(self) -> None:
        run_fixture("tools/pf_oracle/tests/pf019_dormant_resource_fixture.cpp",
                    includes=('src/common/rendering',), root=ROOT)


if __name__ == "__main__":
    unittest.main()
