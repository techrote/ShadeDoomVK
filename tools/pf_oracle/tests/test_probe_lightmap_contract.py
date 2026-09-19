#!/usr/bin/env python3
"""Focused source-contract coverage for PF-012 probe/lightmap plumbing.

Hosted CI has no Vulkan probe runtime, so the compiled spatial fixture is paired
with route checks for the exact live copy path, fallback contract, placement
math, builder termination and the explicitly dormant AABB experiment.
"""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]


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
                return text[brace + 1 : index]
    raise AssertionError(f"unterminated function body: {signature}")


class ProbeLightmapContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lightmapper = source("src/common/rendering/vulkan/vk_lightmapper.cpp")
        cls.lightprobe = source("src/common/rendering/hwrenderer/data/hw_lightprobe.cpp")
        cls.doom_probes = source("src/rendering/hwrenderer/doom_lightprobes.cpp")
        cls.descriptors = source("src/common/rendering/vulkan/descriptorsets/vk_descriptorset.cpp")
        cls.frag_copy = source("wadsrc/static/shaders/lightmap/frag_copy.glsl")
        cls.vert_copy = source("wadsrc/static/shaders/lightmap/vert_copy.glsl")
        cls.selector = source("src/common/rendering/hwrenderer/data/hw_probe_selection.h")

    def test_auto_placement_uses_true_floor_ceiling_midpoint(self) -> None:
        self.assertIn("(floorZ + ceilingZ) * 0.5f", self.doom_probes)
        self.assertNotIn("floorZ + ceilingZ / 2", self.doom_probes)

    def test_runtime_probe_changes_invalidate_probe_map_tiles(self) -> None:
        body = function_body(self.doom_probes, "static void InvalidateLightmapProbeSelection()")
        self.assertIn("tile.ReceivedNewLight = true;", body)
        self.assertIn("LevelMeshMutationDomain::LightmapProbe", body)
        for signature in ("CCMD(addlightprobe)", "CCMD(autoaddlightprobes)"):
            self.assertIn("InvalidateLightmapProbeSelection();", function_body(self.doom_probes, signature))

    def test_copy_pass_binds_live_probe_buffer_to_fragment_stage(self) -> None:
        create = function_body(self.lightmapper, "void VkLightmapper::CreateCopyPipeline()")
        bake = function_body(self.lightmapper, "void VkLightmapper::CreateBakeImage()")
        copy = function_body(self.lightmapper, "void VkLightmapper::CopyResult()")
        self.assertIn(".AddBinding(2, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1, VK_SHADER_STAGE_FRAGMENT_BIT)", create)
        self.assertIn("VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_FRAGMENT_BIT", create)
        self.assertIn("AddPoolSize(VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 2)", create)
        self.assertIn("AddBuffer(bakeImage.copy.DescriptorSet.get(), 2", bake)
        self.assertIn("const int probeCount = UploadProbeSelection();", copy)
        self.assertIn("pc.ProbeCount = probeCount;", copy)
        self.assertIn("VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_FRAGMENT_BIT", copy)

    def test_probe_upload_uses_runtime_bindless_identity_and_is_bounded(self) -> None:
        body = function_body(self.lightmapper, "int VkLightmapper::UploadProbeSelection()")
        self.assertIn("level.levelMesh != mesh", body)
        self.assertIn("GetLightProbeTextureIndex(probe.index)", body)
        self.assertIn("HWProbeSelection::IsEncodableTextureIndex", body)
        self.assertIn("count >= probeSelection.BufferSize", body)
        self.assertIn("MaxCandidateCount", self.selector)
        self.assertNotIn("IrradianceTextureIndex", self.selector)
        self.assertNotIn("2u + 1u", self.selector)

    def test_descriptor_manager_allocates_adjacent_runtime_probe_pair(self) -> None:
        body = function_body(self.descriptors, "int VkDescriptorSetManager::GetLightProbeTextureIndex(int probeIndex)")
        self.assertIn("int bindIndex = AllocBindlessSlot(2);", body)
        self.assertIn("LightProbes[probeIndex] = bindIndex;", body)
        self.assertIn("SetBindlessTexture(bindIndex, textures->Irradiancemaps[probeIndex].View.get()", body)
        self.assertIn("SetBindlessTexture(bindIndex + 1, textures->Prefiltermaps[probeIndex].View.get()", body)
        self.assertIn("return 0;", body)
        self.assertIn("return LightProbes[probeIndex];", body)

    def test_probe_map_zero_is_explicit_fallback_and_two_probe_path_is_live(self) -> None:
        self.assertIn("const uint fallbackIndex = 0u;", self.frag_copy)
        self.assertIn("for (int i = 0; i < ProbeCount; ++i)", self.frag_copy)
        self.assertIn("candidate.textureIndex == fallbackIndex", self.frag_copy)
        self.assertIn("return closestTextureIndex;", self.frag_copy)
        self.assertNotIn("#if 1", self.frag_copy)
        self.assertNotIn("return 0;\n}", self.frag_copy)

    def test_copy_page_and_copy_buffer_bounds_fail_closed(self) -> None:
        body = function_body(self.lightmapper, "void VkLightmapper::CopyResult()")
        self.assertIn("pageIndex >= destTexture.size()", body)
        self.assertIn("pageIndex >= (unsigned int)mesh->Lightmap.TextureCount", body)
        self.assertIn("I_FatalError(\"Lightmap atlas page", body)
        self.assertIn("pos + (int)list.Size() > copytiles.BufferSize", body)

    def test_builder_completed_and_empty_states_terminate(self) -> None:
        step = function_body(
            self.lightprobe,
            "void LightProbeIncrementalBuilder::Step(const TArray<LightProbe>& probes, std::function<void(int probeIndex, const LightProbe& probe)> renderScene)",
        )
        full = function_body(
            self.lightprobe,
            "void LightProbeIncrementalBuilder::Full(const TArray<LightProbe>& probes, std::function<void(int probeIndex, const LightProbe& probe)> renderScene)",
        )
        self.assertIn("if (iterations >= 5)", step)
        self.assertIn("if (cubemapsAllocated != 0)", step)
        self.assertIn("screen->ResetLightProbes();", step)
        self.assertIn("Step(probes, renderScene);", full)
        self.assertIn("previousIndex", full)
        self.assertIn("previousAllocated", full)
        self.assertIn("previousIterations", full)

    def test_dormant_aabb_path_stays_explicitly_out_of_live_shader(self) -> None:
        update = function_body(self.lightprobe, "void LightProbeAABBTree::Update()")
        self.assertIn("Deliberately dormant", update)
        self.assertNotIn("Create(Mesh->", update.replace("//Create", ""))
        self.assertNotIn("ProbeNode", self.frag_copy)
        self.assertNotIn("nodes[]", self.frag_copy)
        self.assertIn("std::vector<int> stack", self.lightprobe)

    def test_copy_vertex_and_fragment_push_constants_agree(self) -> None:
        for shader in (self.vert_copy, self.frag_copy):
            self.assertIn("int SrcTexSize;", shader)
            self.assertIn("int DestTexSize;", shader)
            self.assertIn("int ProbeCount;", shader)
            self.assertIn("int Padding;", shader)


if __name__ == "__main__":
    unittest.main()
