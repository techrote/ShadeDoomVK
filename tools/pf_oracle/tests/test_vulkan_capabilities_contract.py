#!/usr/bin/env python3
"""PF-007 capability-registry source, fallback, and boundary coverage."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]


def source(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


class VulkanCapabilitiesContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.capabilities_h = source("src/common/rendering/vulkan/vk_capabilities.h")
        cls.quirks_h = source("src/common/rendering/vulkan/vk_devicequirks.h")
        cls.device_h = source("src/common/rendering/vulkan/vk_renderdevice.h")
        cls.device_cpp = source("src/common/rendering/vulkan/vk_renderdevice.cpp")
        cls.samplers_cpp = source("src/common/rendering/vulkan/samplers/vk_samplers.cpp")
        cls.descriptors_cpp = source("src/common/rendering/vulkan/descriptorsets/vk_descriptorset.cpp")
        cls.renderpass_cpp = source("src/common/rendering/vulkan/pipelines/vk_renderpass.cpp")
        cls.renderbuffers_cpp = source("src/common/rendering/vulkan/textures/vk_renderbuffers.cpp")

    def test_registry_names_required_capability_categories(self) -> None:
        for token in [
            "VkDescriptorIndexingCapabilityState",
            "VkBindlessDeviceLimits BindlessLimits",
            "RayQueryExtension",
            "RayQueryFeature",
            "AccelerationStructureExtension",
            "AccelerationStructureFeature",
            "GraphicsPipelineLibraryExtension",
            "GraphicsPipelineLibraryFeature",
            "ShaderClipDistance",
            "SceneSampleCounts",
            "DepthD24S8",
            "DepthD32S8",
            "NormalA2R10G10B10",
            "NormalR8G8B8A8",
            "IntelSamplerQuirk",
            "AmdRayQueryDriverQuirk",
        ]:
            self.assertIn(token, self.capabilities_h)

    def test_renderer_populates_and_exposes_one_snapshot(self) -> None:
        self.assertIn("VulkanCapabilities mCapabilities", self.device_h)
        self.assertIn("GetCapabilities() const", self.device_h)
        self.assertIn("VulkanCapabilities::FromDevice", self.device_cpp)
        self.assertIn("mCapabilities = VulkanCapabilities::FromDevice(mDevice.get())", self.device_cpp)
        self.assertIn("SupportsRequiredBindlessContract()", self.device_cpp)
        self.assertNotIn("bool supportsBindless =", self.device_cpp)

    def test_sampler_uses_named_quirk_instead_of_local_vendor_tables(self) -> None:
        self.assertIn("capabilities.IntelSamplerQuirk", self.samplers_cpp)
        self.assertIn("VkIntelSamplerQuirk::DisableAnisotropyForNearestFiltering", self.samplers_cpp)
        self.assertIn("VkIntelSamplerQuirk::BrokenNearestMipLinear", self.samplers_cpp)
        self.assertNotIn("CurrentDriverIntelDeviceIDs", self.samplers_cpp)
        self.assertNotIn("LegacyIntelDeviceIDs", self.samplers_cpp)
        self.assertNotIn("properties.vendorID == 0x8086", self.samplers_cpp)
        self.assertIn("CurrentDriverIntelDeviceIDs", self.quirks_h)
        self.assertIn("LegacyIntelDeviceIDs", self.quirks_h)

    def test_descriptor_pipeline_and_sample_decisions_use_registry(self) -> None:
        self.assertIn("GetCapabilities().BindlessLimits", self.descriptors_cpp)
        self.assertNotIn("PhysicalDevice.Properties.DescriptorIndexing", self.descriptors_cpp)
        self.assertIn("GetCapabilities().SupportsGraphicsPipelineLibrary()", self.renderpass_cpp)
        self.assertNotIn("SupportsExtension(VK_EXT_GRAPHICS_PIPELINE_LIBRARY_EXTENSION_NAME)", self.renderpass_cpp)
        self.assertIn("GetCapabilities().BestSceneSampleCount", self.renderbuffers_cpp)
        self.assertNotIn("sampledImageColorSampleCounts", self.renderbuffers_cpp)

    def test_optional_feature_policy_remains_separate(self) -> None:
        self.assertIn("mUseRayQuery = vk_rayquery && mCapabilities.SupportsRayQuery()", self.device_cpp)
        self.assertIn("if (vk_amd_driver_check && mCapabilities.AmdRayQueryDriverQuirk)", self.device_cpp)
        self.assertIn("if (!gl_ubershaders)", self.renderpass_cpp)
        self.assertIn("UsePipelineLibrary = false", self.renderpass_cpp)
        self.assertIn("if (fb->IsRayQueryEnabled())", self.descriptors_cpp)
        self.assertIn("VK_DESCRIPTOR_TYPE_STORAGE_BUFFER", self.descriptors_cpp)

    def test_format_preference_and_runtime_diagnostics_are_named(self) -> None:
        self.assertIn("VkSelectDepthStencilFormat", self.device_cpp)
        self.assertIn("VkSelectNormalGBufferFormat", self.device_cpp)
        self.assertIn("Vulkan capabilities:", self.device_cpp)
        self.assertIn("Vulkan quirks:", self.device_cpp)
        self.assertIn("Bindless descriptor limits:", self.device_cpp)
        self.assertIn("Vulkan render-target formats:", self.device_cpp)

    def test_compiled_quirk_and_boundary_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            executable = Path(tempdir) / "vulkan-capabilities-fixture"
            subprocess.run(
                [
                    "c++",
                    "-std=c++17",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-Ilibraries/ZVulkan/include",
                    "-Isrc/common/rendering",
                    "tools/pf_oracle/tests/vulkan_capabilities_fixture.cpp",
                    "-o",
                    str(executable),
                ],
                cwd=ROOT,
                check=True,
            )
            subprocess.run([str(executable)], cwd=ROOT, check=True)


if __name__ == "__main__":
    unittest.main()
