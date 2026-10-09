#!/usr/bin/env python3
"""SDVK-004 rich-material descriptor/lifetime qualification contract."""

from __future__ import annotations

import json
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


class Sdvk004RichDescriptorContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bindless = source("src/common/rendering/vulkan/descriptorsets/vk_bindless.h")
        cls.descriptors = source("src/common/rendering/vulkan/descriptorsets/vk_descriptorset.cpp")
        cls.material = source("src/common/rendering/vulkan/textures/vk_hwtexture.cpp")
        cls.texture_manager = source("src/common/rendering/vulkan/textures/vk_texture.cpp")
        cls.render_device = source("src/common/rendering/vulkan/vk_renderdevice.cpp")
        cls.game_texture = source("src/common/textures/gametexture.cpp")
        cls.observer = source("src/common/rendering/vulkan/textures/vk_sdvkdiagnostics.cpp")

    def test_rich_pressure_fixture(self) -> None:
        result = run_fixture(
            "tools/pf_oracle/tests/sdvk004_rich_descriptor_fixture.cpp",
            includes=("src/common/rendering", "src/common/rendering/vulkan/descriptorsets"),
            root=ROOT,
            capture_output=True,
        )
        data = json.loads(result.stdout)
        self.assertEqual(data["schema"], "sdvk004-rich-descriptor-stress/v1")
        self.assertEqual(data["status"], "PASS")
        self.assertEqual(data["unique_semantic_materials"], 576)
        self.assertEqual(data["translation_palette_variants"], 128)
        self.assertEqual(data["canvas_materials"], 64)
        self.assertEqual(data["custom_shader_materials"], 64)
        self.assertEqual(data["probe_pairs"], 64)
        self.assertEqual(data["lightmap_peak_pages"], 128)
        self.assertEqual(data["rebuild_cycles"], 64)
        self.assertEqual(data["descriptor_high_water"], 3072)
        self.assertEqual(data["dynamic_capacity"], 4096)
        self.assertEqual(data["pressure_percent"], 75)
        self.assertEqual(data["descriptor_failures"], 0)
        self.assertEqual(data["descriptor_invalid_frees"], 0)
        self.assertGreaterEqual(data["descriptor_reuses"], 832)
        self.assertGreaterEqual(data["stale_rejects"], 832)
        self.assertEqual(data["tight_capacity_failures"], 3)
        self.assertEqual(data["allocator_epoch_stale_rejects"], 1)
        self.assertEqual(data["texture_epoch_invalidations"], 64)
        self.assertEqual(data["lightmap_epoch_invalidations"], 64)
        self.assertEqual(data["probe_epoch_invalidations"], 64)
        self.assertEqual(
            data["device_limit_source"],
            "update-after-bind descriptors in all pools",
        )

    def test_impossible_span_is_rejected_before_exact_bucket_growth(self) -> None:
        body = function_body(self.bindless, "int Allocate(int count)")
        guard = body.index("count > Capacity - DynamicStart")
        bucket = body.index("const int bucket = count - 1")
        resize = body.index("FreeSlots.resize")
        self.assertLess(guard, bucket)
        self.assertLess(guard, resize)

    def test_material_identity_and_custom_sampler_contract_stays_on_live_path(self) -> None:
        body = function_body(self.material, "VkMaterial::DescriptorEntry& VkMaterial::GetDescriptorEntry")
        for token in [
            "set.clampmode == clampmode",
            "set.remap == translationp",
            "set.globalShaderAddr == globalShaderAddr",
            "set.indexed == state.mPaletteMode",
            "set.redIsAlpha == indexedRedIsAlpha",
            "textureCount = 2",
            "textureCount = numLayersMat",
            "CustomShaderTextures",
            "CustomShaderTextureSampling[i]",
            "GetLayerFilter(i), clampmode",
        ]:
            self.assertIn(token, body)
        self.assertIn("CreateIndexedPalette()", body)
        self.assertIn("ResolveIndexedTranslation(translation)", body)

    def test_sampler_invalidation_retires_descriptor_consumers_before_sampler_rebuild(self) -> None:
        body = function_body(self.render_device, "void VulkanRenderDevice::SetTextureFilterMode()")
        retire = body.index("mDescriptorSetManager->ResetHWTextureSets()")
        rebuild = body.index("mSamplerManager->ResetHWSamplers()")
        self.assertLess(retire, rebuild)

        reset = function_body(self.descriptors, "void VkDescriptorSetManager::ResetHWTextureSets()")
        self.assertIn("mat->DeleteDescriptors()", reset)
        self.assertIn("FreeBindlessSlot(colormap->Renderdev.bindIndex)", reset)
        self.assertIn("for (int index : LightProbes)", reset)
        self.assertIn("FreeBindlessSlot(index)", reset)

    def test_canvas_cleanup_retires_material_descriptors_with_hardware_resource(self) -> None:
        clean = function_body(self.game_texture, "void FGameTexture::CleanHardwareData(bool full)")
        self.assertIn("Base->CleanHardwareTextures()", clean)
        self.assertIn("mat->DeleteDescriptors()", clean)

        canvas = function_body(self.render_device, "void VulkanRenderDevice::RenderTextureView")
        self.assertIn("tex->GetHardwareTexture(0, 0)", canvas)
        self.assertIn("BaseLayer->GetImage(tex, 0, 0)", canvas)
        self.assertIn("VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL", canvas)
        self.assertIn("VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL", canvas)
        self.assertIn("tex->SetUpdated(true)", canvas)

    def test_lightmap_and_probe_ownership_use_existing_epochs_and_descriptor_policy(self) -> None:
        lightmap = function_body(self.texture_manager, "void VkTextureManager::CreateLightmap(int size, int count")
        self.assertIn("LightmapEpoch.Invalidate()", lightmap)
        probe_reset = function_body(self.texture_manager, "void VkTextureManager::ResetLightProbes()")
        self.assertIn("LightProbeEpoch.Invalidate()", probe_reset)
        self.assertNotIn("Irradiancemaps.clear()", probe_reset)
        self.assertNotIn("Prefiltermaps.clear()", probe_reset)

        publish = function_body(self.descriptors, "void VkDescriptorSetManager::UpdateBindlessDescriptorSet()")
        self.assertIn("VkPlanLightmapDescriptorPublication", publish)
        self.assertIn("UsesFallback(page)", publish)
        self.assertIn("Bindless.PublishedLightmapPages = publication.NextPublishedPages", publish)

        probes = function_body(self.descriptors, "int VkDescriptorSetManager::GetLightProbeTextureIndex(int probeIndex)")
        self.assertIn("AllocBindlessSlot(2)", probes)
        self.assertIn("Irradiancemaps[probeIndex].View", probes)
        self.assertIn("Prefiltermaps[probeIndex].View", probes)

    def test_existing_observer_exposes_reusable_pressure_and_epoch_state(self) -> None:
        body = function_body(self.observer, "void VulkanResources(VulkanRenderDevice* device)")
        for token in [
            '"descriptor_requested"',
            '"descriptor_device_limit"',
            '"descriptor_capacity"',
            '"descriptor_dynamic_start"',
            '"descriptor_current"',
            '"descriptor_high_water"',
            '"descriptor_allocations"',
            '"descriptor_reuses"',
            '"descriptor_frees"',
            '"descriptor_failures"',
            '"descriptor_invalid_frees"',
            '"descriptor_limit_source"',
            '"texture_epoch"',
            '"lightmap_epoch"',
            '"probe_epoch"',
            '"hardware_textures"',
            '"lightmap_pages"',
            '"irradiance_maps"',
            '"prefilter_maps"',
        ]:
            self.assertIn(token, body)


if __name__ == "__main__":
    unittest.main()
