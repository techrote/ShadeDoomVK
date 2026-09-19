#pragma once

#include <algorithm>
#include <cstdint>
#include <zvulkan/vulkan.h>
#include "vulkan/descriptorsets/vk_bindless.h"
#include "vulkan/vk_devicequirks.h"

class VulkanDevice;

struct VkDescriptorIndexingCapabilityState
{
	bool PartiallyBound = false;
	bool VariableDescriptorCount = false;
	bool SampledImageUpdateAfterBind = false;
	bool RuntimeDescriptorArray = false;
	bool SampledImageArrayNonUniformIndexing = false;

	bool SupportsRequiredBindlessContract() const
	{
		return PartiallyBound && VariableDescriptorCount && SampledImageUpdateAfterBind &&
			RuntimeDescriptorArray && SampledImageArrayNonUniformIndexing;
	}
};

inline VkSampleCountFlagBits VkBestSceneSampleCount(VkSampleCountFlags supported, int requested)
{
	requested = std::max(0, std::min(requested, 64));
	int samples = 1;
	VkSampleCountFlags bit = VK_SAMPLE_COUNT_1_BIT;
	VkSampleCountFlags best = VK_SAMPLE_COUNT_1_BIT;
	while (samples <= requested)
	{
		if (supported & bit)
			best = bit;
		if (samples == 64)
			break;
		samples <<= 1;
		bit <<= 1;
	}
	return static_cast<VkSampleCountFlagBits>(best);
}

inline VkFormat VkSelectDepthStencilFormat(bool supportsD24S8, bool supportsD32S8)
{
	if (supportsD24S8)
		return VK_FORMAT_D24_UNORM_S8_UINT;
	if (supportsD32S8)
		return VK_FORMAT_D32_SFLOAT_S8_UINT;
	return VK_FORMAT_UNDEFINED;
}

inline VkFormat VkSelectNormalGBufferFormat(bool supportsA2R10G10B10, bool supportsR8G8B8A8)
{
	if (supportsA2R10G10B10)
		return VK_FORMAT_A2R10G10B10_UNORM_PACK32;
	if (supportsR8G8B8A8)
		return VK_FORMAT_R8G8B8A8_UNORM;
	return VK_FORMAT_UNDEFINED;
}

// A single descriptive snapshot of Vulkan device/driver capability state.
// User quality/configuration choices are deliberately not stored here.  For
// example, vk_rayquery and gl_ubershaders remain policy inputs layered over
// SupportsRayQuery() and SupportsGraphicsPipelineLibrary() respectively.
struct VulkanCapabilities
{
	uint32_t VendorID = 0;
	uint32_t DeviceID = 0;
	uint32_t DriverVersion = 0;
	VkPhysicalDeviceType DeviceType = VK_PHYSICAL_DEVICE_TYPE_OTHER;

	VkDescriptorIndexingCapabilityState DescriptorIndexing;
	VkBindlessDeviceLimits BindlessLimits;

	bool RayQueryExtension = false;
	bool RayQueryFeature = false;
	bool AccelerationStructureExtension = false;
	bool AccelerationStructureFeature = false;
	bool GraphicsPipelineLibraryExtension = false;
	bool GraphicsPipelineLibraryFeature = false;
	bool ShaderClipDistance = false;

	VkSampleCountFlags SceneSampleCounts = VK_SAMPLE_COUNT_1_BIT;

	bool DepthD24S8 = false;
	bool DepthD32S8 = false;
	bool NormalA2R10G10B10 = false;
	bool NormalR8G8B8A8 = false;
	VkFormat DepthStencilFormat = VK_FORMAT_UNDEFINED;
	VkFormat NormalFormat = VK_FORMAT_UNDEFINED;

	VkIntelSamplerQuirk IntelSamplerQuirk = VkIntelSamplerQuirk::None;
	bool AmdRayQueryDriverQuirk = false;

	static VulkanCapabilities FromDevice(VulkanDevice* device);

	bool SupportsRequiredBindlessContract() const
	{
		return DescriptorIndexing.SupportsRequiredBindlessContract();
	}

	bool SupportsRayQuery() const
	{
		// Preserve the inherited activation condition exactly.  Acceleration
		// structure support is exposed independently rather than silently adding
		// a new requirement in PF-007.
		return RayQueryExtension && RayQueryFeature;
	}

	bool SupportsAccelerationStructure() const
	{
		return AccelerationStructureExtension && AccelerationStructureFeature;
	}

	bool SupportsGraphicsPipelineLibrary() const
	{
		return GraphicsPipelineLibraryExtension && GraphicsPipelineLibraryFeature;
	}

	VkSampleCountFlagBits BestSceneSampleCount(int requested) const
	{
		return VkBestSceneSampleCount(SceneSampleCounts, requested);
	}
};
