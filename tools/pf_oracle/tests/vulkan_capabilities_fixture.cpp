#include "vulkan/vk_capabilities.h"

#include <cassert>

int main()
{
	// Intel sampler policy boundaries must remain exactly equivalent to the
	// inherited checks, including the 0.405.1286 transition.
	assert(VkClassifyIntelSamplerQuirk(0x10DE, 0x56A0, VK_MAKE_VERSION(0, 404, 999)) == VkIntelSamplerQuirk::None);
	assert(VkClassifyIntelSamplerQuirk(0x8086, 0x8A70, VK_MAKE_VERSION(0, 999, 999)) == VkIntelSamplerQuirk::DisableAnisotropyForNearestFiltering);
	assert(VkClassifyIntelSamplerQuirk(0x8086, 0x56A0, VK_MAKE_VERSION(0, 404, 999)) == VkIntelSamplerQuirk::DisableAnisotropyForNearestFiltering);
	assert(VkClassifyIntelSamplerQuirk(0x8086, 0x56A0, VK_MAKE_VERSION(0, 405, 1285)) == VkIntelSamplerQuirk::DisableAnisotropyForNearestFiltering);
	assert(VkClassifyIntelSamplerQuirk(0x8086, 0x56A0, VK_MAKE_VERSION(0, 405, 1286)) == VkIntelSamplerQuirk::BrokenNearestMipLinear);
	assert(VkClassifyIntelSamplerQuirk(0x8086, 0x56A0, VK_MAKE_VERSION(0, 406, 0)) == VkIntelSamplerQuirk::BrokenNearestMipLinear);
	assert(VkClassifyIntelSamplerQuirk(0x8086, 0xDEAD, VK_MAKE_VERSION(0, 1, 0)) == VkIntelSamplerQuirk::BrokenNearestMipLinear);

	assert(VkHasAmdRayQueryDriverQuirk(0x1002, VK_MAKE_VERSION(9, 999, 999)));
	assert(!VkHasAmdRayQueryDriverQuirk(0x1002, VK_MAKE_VERSION(10, 0, 0)));
	assert(!VkHasAmdRayQueryDriverQuirk(0x10DE, VK_MAKE_VERSION(1, 0, 0)));

	VkDescriptorIndexingCapabilityState descriptorFeatures;
	assert(!descriptorFeatures.SupportsRequiredBindlessContract());
	descriptorFeatures.PartiallyBound = true;
	descriptorFeatures.VariableDescriptorCount = true;
	descriptorFeatures.SampledImageUpdateAfterBind = true;
	descriptorFeatures.RuntimeDescriptorArray = true;
	descriptorFeatures.SampledImageArrayNonUniformIndexing = true;
	assert(descriptorFeatures.SupportsRequiredBindlessContract());
	for (int missing = 0; missing < 5; ++missing)
	{
		auto test = descriptorFeatures;
		switch (missing)
		{
		case 0: test.PartiallyBound = false; break;
		case 1: test.VariableDescriptorCount = false; break;
		case 2: test.SampledImageUpdateAfterBind = false; break;
		case 3: test.RuntimeDescriptorArray = false; break;
		case 4: test.SampledImageArrayNonUniformIndexing = false; break;
		}
		assert(!test.SupportsRequiredBindlessContract());
	}

	VulkanCapabilities caps;
	caps.RayQueryExtension = true;
	caps.RayQueryFeature = true;
	assert(caps.SupportsRayQuery());
	caps.RayQueryFeature = false;
	assert(!caps.SupportsRayQuery());
	caps.RayQueryFeature = true;
	caps.AccelerationStructureExtension = false;
	caps.AccelerationStructureFeature = false;
	// PF-007 must not silently add acceleration-structure state to the inherited
	// ray-query activation predicate; it is descriptive and independently visible.
	assert(caps.SupportsRayQuery());
	assert(!caps.SupportsAccelerationStructure());
	caps.AccelerationStructureExtension = true;
	caps.AccelerationStructureFeature = true;
	assert(caps.SupportsAccelerationStructure());

	caps.GraphicsPipelineLibraryExtension = true;
	caps.GraphicsPipelineLibraryFeature = false;
	assert(!caps.SupportsGraphicsPipelineLibrary());
	caps.GraphicsPipelineLibraryFeature = true;
	assert(caps.SupportsGraphicsPipelineLibrary());

	VkSampleCountFlags samples = VK_SAMPLE_COUNT_1_BIT | VK_SAMPLE_COUNT_2_BIT | VK_SAMPLE_COUNT_4_BIT | VK_SAMPLE_COUNT_8_BIT;
	assert(VkBestSceneSampleCount(samples, -1) == VK_SAMPLE_COUNT_1_BIT);
	assert(VkBestSceneSampleCount(samples, 0) == VK_SAMPLE_COUNT_1_BIT);
	assert(VkBestSceneSampleCount(samples, 1) == VK_SAMPLE_COUNT_1_BIT);
	assert(VkBestSceneSampleCount(samples, 3) == VK_SAMPLE_COUNT_2_BIT);
	assert(VkBestSceneSampleCount(samples, 4) == VK_SAMPLE_COUNT_4_BIT);
	assert(VkBestSceneSampleCount(samples, 64) == VK_SAMPLE_COUNT_8_BIT);
	assert(VkBestSceneSampleCount(samples, 128) == VK_SAMPLE_COUNT_8_BIT);
	assert(VkBestSceneSampleCount(VK_SAMPLE_COUNT_1_BIT | VK_SAMPLE_COUNT_4_BIT, 2) == VK_SAMPLE_COUNT_1_BIT);
	assert(VkBestSceneSampleCount(VK_SAMPLE_COUNT_1_BIT | VK_SAMPLE_COUNT_4_BIT, 4) == VK_SAMPLE_COUNT_4_BIT);

	assert(VkSelectDepthStencilFormat(true, true) == VK_FORMAT_D24_UNORM_S8_UINT);
	assert(VkSelectDepthStencilFormat(false, true) == VK_FORMAT_D32_SFLOAT_S8_UINT);
	assert(VkSelectDepthStencilFormat(false, false) == VK_FORMAT_UNDEFINED);
	assert(VkSelectNormalGBufferFormat(true, true) == VK_FORMAT_A2R10G10B10_UNORM_PACK32);
	assert(VkSelectNormalGBufferFormat(false, true) == VK_FORMAT_R8G8B8A8_UNORM);
	assert(VkSelectNormalGBufferFormat(false, false) == VK_FORMAT_UNDEFINED);

	return 0;
}
