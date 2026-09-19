#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    p = ROOT / path
    return p, p.read_text(encoding="utf-8")


def save(path, text):
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_one(path, old, new):
    p, text = load(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one exact match, got {count}: {old[:80]!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


def regex_one(path, pattern, replacement):
    p, text = load(path)
    result, count = re.subn(pattern, replacement, text, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{path}: expected one regex match, got {count}: {pattern[:80]!r}")
    p.write_text(result, encoding="utf-8")


# Expose one central descriptive capability snapshot from the render device.
path = "src/common/rendering/vulkan/vk_renderdevice.h"
replace_one(path,
    '#include <zvulkan/vulkanobjects.h>\n',
    '#include <zvulkan/vulkanobjects.h>\n#include "vk_capabilities.h"\n')
replace_one(path,
    '\tVulkanDevice* GetDevice() { return mDevice.get(); }\n',
    '\tVulkanDevice* GetDevice() { return mDevice.get(); }\n\tconst VulkanCapabilities& GetCapabilities() const { return mCapabilities; }\n')
replace_one(path,
    '\tstd::shared_ptr<VulkanDevice> mDevice;\n',
    '\tstd::shared_ptr<VulkanDevice> mDevice;\n\tVulkanCapabilities mCapabilities;\n')
save(path, load(path)[1])

# Populate device/driver facts once, preserve existing runtime policy, and expose diagnostics.
path = "src/common/rendering/vulkan/vk_renderdevice.cpp"
factory = r'''VulkanCapabilities VulkanCapabilities::FromDevice(VulkanDevice* device)
{
	VulkanCapabilities capabilities;
	const auto& properties = device->PhysicalDevice.Properties.Properties;
	const auto& descriptorFeatures = device->EnabledFeatures.DescriptorIndexing;
	const auto& coreLimits = properties.limits;
	const auto& indexingLimits = device->PhysicalDevice.Properties.DescriptorIndexing;

	capabilities.VendorID = properties.vendorID;
	capabilities.DeviceID = properties.deviceID;
	capabilities.DriverVersion = properties.driverVersion;
	capabilities.DeviceType = properties.deviceType;

	capabilities.DescriptorIndexing.PartiallyBound = descriptorFeatures.descriptorBindingPartiallyBound;
	capabilities.DescriptorIndexing.VariableDescriptorCount = descriptorFeatures.descriptorBindingVariableDescriptorCount;
	capabilities.DescriptorIndexing.SampledImageUpdateAfterBind = descriptorFeatures.descriptorBindingSampledImageUpdateAfterBind;
	capabilities.DescriptorIndexing.RuntimeDescriptorArray = descriptorFeatures.runtimeDescriptorArray;
	capabilities.DescriptorIndexing.SampledImageArrayNonUniformIndexing = descriptorFeatures.shaderSampledImageArrayNonUniformIndexing;

	capabilities.BindlessLimits.MaxPerStageDescriptorSamplers = coreLimits.maxPerStageDescriptorSamplers;
	capabilities.BindlessLimits.MaxPerStageDescriptorSampledImages = coreLimits.maxPerStageDescriptorSampledImages;
	capabilities.BindlessLimits.MaxDescriptorSetSamplers = coreLimits.maxDescriptorSetSamplers;
	capabilities.BindlessLimits.MaxDescriptorSetSampledImages = coreLimits.maxDescriptorSetSampledImages;
	capabilities.BindlessLimits.MaxPerStageDescriptorUpdateAfterBindSamplers = indexingLimits.maxPerStageDescriptorUpdateAfterBindSamplers;
	capabilities.BindlessLimits.MaxPerStageDescriptorUpdateAfterBindSampledImages = indexingLimits.maxPerStageDescriptorUpdateAfterBindSampledImages;
	capabilities.BindlessLimits.MaxDescriptorSetUpdateAfterBindSamplers = indexingLimits.maxDescriptorSetUpdateAfterBindSamplers;
	capabilities.BindlessLimits.MaxDescriptorSetUpdateAfterBindSampledImages = indexingLimits.maxDescriptorSetUpdateAfterBindSampledImages;
	capabilities.BindlessLimits.MaxPerStageUpdateAfterBindResources = indexingLimits.maxPerStageUpdateAfterBindResources;
	capabilities.BindlessLimits.MaxUpdateAfterBindDescriptorsInAllPools = indexingLimits.maxUpdateAfterBindDescriptorsInAllPools;

	capabilities.RayQueryExtension = device->SupportsExtension(VK_KHR_RAY_QUERY_EXTENSION_NAME);
	capabilities.RayQueryFeature = device->PhysicalDevice.Features.RayQuery.rayQuery;
	capabilities.AccelerationStructureExtension = device->SupportsExtension(VK_KHR_ACCELERATION_STRUCTURE_EXTENSION_NAME);
	capabilities.AccelerationStructureFeature = device->PhysicalDevice.Features.AccelerationStructure.accelerationStructure;
	capabilities.GraphicsPipelineLibraryExtension = device->SupportsExtension(VK_EXT_GRAPHICS_PIPELINE_LIBRARY_EXTENSION_NAME);
	capabilities.GraphicsPipelineLibraryFeature = device->EnabledFeatures.GraphicsPipelineLibrary.graphicsPipelineLibrary;
	capabilities.ShaderClipDistance = device->PhysicalDevice.Features.Features.shaderClipDistance;

	capabilities.SceneSampleCounts = coreLimits.sampledImageColorSampleCounts &
		coreLimits.sampledImageDepthSampleCounts & coreLimits.sampledImageStencilSampleCounts;
	capabilities.IntelSamplerQuirk = VkClassifyIntelSamplerQuirk(
		properties.vendorID, properties.deviceID, properties.driverVersion);
	capabilities.AmdRayQueryDriverQuirk = VkHasAmdRayQueryDriverQuirk(
		properties.vendorID, properties.driverVersion);
	return capabilities;
}

'''
replace_one(path,
    'VulkanRenderDevice::VulkanRenderDevice(void *hMonitor, bool fullscreen, std::shared_ptr<VulkanInstance> instance, std::shared_ptr<VulkanSurface> surface) : SystemBaseFrameBuffer(hMonitor, fullscreen)\n',
    factory + 'VulkanRenderDevice::VulkanRenderDevice(void *hMonitor, bool fullscreen, std::shared_ptr<VulkanInstance> instance, std::shared_ptr<VulkanSurface> surface) : SystemBaseFrameBuffer(hMonitor, fullscreen)\n')
replace_one(path,
    '\tmDevice = builder.Create(instance);\n\n',
    '''\tmDevice = builder.Create(instance);\n\tmCapabilities = VulkanCapabilities::FromDevice(mDevice.get());\n\tmCapabilities.DepthD24S8 = SupportsRenderTargetFormat(VK_FORMAT_D24_UNORM_S8_UINT);\n\tmCapabilities.DepthD32S8 = SupportsRenderTargetFormat(VK_FORMAT_D32_SFLOAT_S8_UINT);\n\tmCapabilities.NormalA2R10G10B10 = SupportsNormalGBufferFormat(VK_FORMAT_A2R10G10B10_UNORM_PACK32);\n\tmCapabilities.NormalR8G8B8A8 = SupportsNormalGBufferFormat(VK_FORMAT_R8G8B8A8_UNORM);\n\tmCapabilities.DepthStencilFormat = VkSelectDepthStencilFormat(mCapabilities.DepthD24S8, mCapabilities.DepthD32S8);\n\tmCapabilities.NormalFormat = VkSelectNormalGBufferFormat(mCapabilities.NormalA2R10G10B10, mCapabilities.NormalR8G8B8A8);\n\n''')
regex_one(path,
    r'\tbool supportsBindless =\n.*?\tif \(!supportsBindless\)\n\t\{\n\t\tI_FatalError\("This GPU does not support the required Vulkan descriptor-indexing features for bindless sampled images"\);\n\t\}\n',
    '''\tif (!mCapabilities.SupportsRequiredBindlessContract())\n\t{\n\t\tI_FatalError("This GPU does not support the required Vulkan descriptor-indexing features for bindless sampled images");\n\t}\n''')
replace_one(path,
    '\tmUseRayQuery = vk_rayquery && mDevice->SupportsExtension(VK_KHR_RAY_QUERY_EXTENSION_NAME) && mDevice->PhysicalDevice.Features.RayQuery.rayQuery;\n',
    '\tmUseRayQuery = vk_rayquery && mCapabilities.SupportsRayQuery();\n')
old_amd = '''\tif (vk_amd_driver_check)\n\t{\n\t\t// While we found a workaround for the SPIR-V compiler crashing on specialization constants with rayquery,\n\t\t// the AMDVLK driver (but not the Mesa one!) now produces a shader that only the FIRST frame runs for 10\n\t\t// seconds. This produces a device lost on Windows (command buffer killed by OS) and the freeze from hell\n\t\t// on Linux.\n\t\t//\n\t\t// Maybe some day AMD will have a driver that works for us. Until that day their hardware gets demoted to\n\t\t// the legacy path without RT cores, sorry.\n\t\tauto& props = mDevice->PhysicalDevice.Properties.Properties;\n\t\tif (props.vendorID == 0x1002 && VK_VERSION_MAJOR(props.driverVersion) < 10)\n\t\t{\n\t\t\tif (mUseRayQuery)\n\t\t\t{\n\t\t\t\tPrintf("AMD driver detected. Disabling RT cores. You can force RT cores on by setting vk_amd_driver_check to false.\\n");\n\t\t\t\tmUseRayQuery = false;\n\t\t\t}\n\t\t}\n\t}\n'''
new_amd = '''\tif (vk_amd_driver_check && mCapabilities.AmdRayQueryDriverQuirk)\n\t{\n\t\t// Inherited AMDVLK workaround: specialization-constant/ray-query shaders can stall the first frame\n\t\t// long enough to lose the device on Windows or freeze Linux. PF-007 only centralizes the driver\n\t\t// classification; the existing user override and legacy-path fallback remain unchanged.\n\t\tif (mUseRayQuery)\n\t\t{\n\t\t\tPrintf("AMD driver detected. Disabling RT cores. You can force RT cores on by setting vk_amd_driver_check to false.\\n");\n\t\t\tmUseRayQuery = false;\n\t\t}\n\t}\n'''
replace_one(path, old_amd, new_amd)
old_formats = '''\tif (SupportsRenderTargetFormat(VK_FORMAT_D24_UNORM_S8_UINT))\n\t{\n\t\tDepthStencilFormat = VK_FORMAT_D24_UNORM_S8_UINT;\n\t}\n\telse if (SupportsRenderTargetFormat(VK_FORMAT_D32_SFLOAT_S8_UINT))\n\t{\n\t\tDepthStencilFormat = VK_FORMAT_D32_SFLOAT_S8_UINT;\n\t}\n\telse\n\t{\n\t\tI_FatalError("This device does not support any of the required depth stencil image formats.");\n\t}\n\n\tif (SupportsNormalGBufferFormat(VK_FORMAT_A2R10G10B10_UNORM_PACK32))\n\t{\n\t\tNormalFormat = VK_FORMAT_A2R10G10B10_UNORM_PACK32;\n\t}\n\telse if (SupportsNormalGBufferFormat(VK_FORMAT_R8G8B8A8_UNORM))\n\t{\n\t\tNormalFormat = VK_FORMAT_R8G8B8A8_UNORM;\n\t}\n\telse\n\t{\n\t\tI_FatalError("This device does not support any of the required normal buffer image formats.");\n\t}\n'''
new_formats = '''\tDepthStencilFormat = mCapabilities.DepthStencilFormat;\n\tif (DepthStencilFormat == VK_FORMAT_UNDEFINED)\n\t\tI_FatalError("This device does not support any of the required depth stencil image formats.");\n\n\tNormalFormat = mCapabilities.NormalFormat;\n\tif (NormalFormat == VK_FORMAT_UNDEFINED)\n\t\tI_FatalError("This device does not support any of the required normal buffer image formats.");\n'''
replace_one(path, old_formats, new_formats)
log_line = '\tPrintf(PRINT_LOG, "Min. uniform buffer offset alignment: %" PRIu64 "\\n", limits.minUniformBufferOffsetAlignment);\n'
log_more = log_line + '''\tPrintf(PRINT_LOG, "Vulkan capabilities: bindless=%s ray-query=%s acceleration-structure=%s pipeline-library=%s shader-clip-distance=%s; ray-query-enabled=%s\\n",\n\t\tmCapabilities.SupportsRequiredBindlessContract() ? "yes" : "no",\n\t\tmCapabilities.SupportsRayQuery() ? "yes" : "no",\n\t\tmCapabilities.SupportsAccelerationStructure() ? "yes" : "no",\n\t\tmCapabilities.SupportsGraphicsPipelineLibrary() ? "yes" : "no",\n\t\tmCapabilities.ShaderClipDistance ? "yes" : "no",\n\t\tmUseRayQuery ? "yes" : "no");\n\tPrintf(PRINT_LOG, "Vulkan quirks: intel-sampler=%s amd-ray-query-driver=%s\\n",\n\t\tVkIntelSamplerQuirkName(mCapabilities.IntelSamplerQuirk),\n\t\tmCapabilities.AmdRayQueryDriverQuirk ? "yes" : "no");\n\tPrintf(PRINT_LOG, "Vulkan scene sample counts: 0x%x\\n", (unsigned)mCapabilities.SceneSampleCounts);\n\tPrintf(PRINT_LOG, "Bindless descriptor limits: stage-samplers=%u stage-images=%u set-samplers=%u set-images=%u uab-stage-samplers=%u uab-stage-images=%u uab-set-samplers=%u uab-set-images=%u uab-stage-resources=%u uab-pool=%u\\n",\n\t\tmCapabilities.BindlessLimits.MaxPerStageDescriptorSamplers,\n\t\tmCapabilities.BindlessLimits.MaxPerStageDescriptorSampledImages,\n\t\tmCapabilities.BindlessLimits.MaxDescriptorSetSamplers,\n\t\tmCapabilities.BindlessLimits.MaxDescriptorSetSampledImages,\n\t\tmCapabilities.BindlessLimits.MaxPerStageDescriptorUpdateAfterBindSamplers,\n\t\tmCapabilities.BindlessLimits.MaxPerStageDescriptorUpdateAfterBindSampledImages,\n\t\tmCapabilities.BindlessLimits.MaxDescriptorSetUpdateAfterBindSamplers,\n\t\tmCapabilities.BindlessLimits.MaxDescriptorSetUpdateAfterBindSampledImages,\n\t\tmCapabilities.BindlessLimits.MaxPerStageUpdateAfterBindResources,\n\t\tmCapabilities.BindlessLimits.MaxUpdateAfterBindDescriptorsInAllPools);\n\tPrintf(PRINT_LOG, "Vulkan render-target formats: d24s8=%s d32s8=%s depth-selected=%d a2r10g10b10=%s rgba8=%s normal-selected=%d\\n",\n\t\tmCapabilities.DepthD24S8 ? "yes" : "no",\n\t\tmCapabilities.DepthD32S8 ? "yes" : "no",\n\t\t(int)mCapabilities.DepthStencilFormat,\n\t\tmCapabilities.NormalA2R10G10B10 ? "yes" : "no",\n\t\tmCapabilities.NormalR8G8B8A8 ? "yes" : "no",\n\t\t(int)mCapabilities.NormalFormat);\n'''
replace_one(path, log_line, log_more)

# Sampler decisions consume the central quirk classification; remove duplicate tables.
path = "src/common/rendering/vulkan/samplers/vk_samplers.cpp"
replace_one(path, '#include <unordered_set>\n', '')
regex_one(path,
    r'\nstd::unordered_set<uint32_t> CurrentDriverIntelDeviceIDs =\n\{.*?\n\};\n\nstd::unordered_set<uint32_t> LegacyIntelDeviceIDs =\n\{.*?\n\};\n\nVkSamplerManager::VkSamplerManager',
    '\nVkSamplerManager::VkSamplerManager')
replace_one(path,
    '\tconst auto& properties = fb->GetDevice()->PhysicalDevice.Properties.Properties;\n',
    '\tconst auto& capabilities = fb->GetCapabilities();\n')
replace_one(path,
    '\t\tif (properties.deviceType != VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU)\n',
    '\t\tif (capabilities.DeviceType != VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU)\n')
regex_one(path,
    r'\t// Intel devices handles anisotropic filtering differently than what we want\.\n\tbool brokenNearestMipLinear = false;\n\tif \(properties\.vendorID == 0x8086\)\n\t\{.*?\n\t\}\n\n\tfor \(int i = CLAMP_NONE;',
    '''\t// Preserve the inherited Intel sampler workarounds, but classify the device/driver once.\n\tbool brokenNearestMipLinear = false;\n\tswitch (capabilities.IntelSamplerQuirk)\n\t{\n\tcase VkIntelSamplerQuirk::DisableAnisotropyForNearestFiltering:\n\t\t// Old hardware and old drivers have to turn AF off if we want any nearest filtering.\n\t\tif (TexFilter[filter].magFilter != VK_FILTER_LINEAR || TexFilter[filter].minFilter != VK_FILTER_LINEAR)\n\t\t\tmaxAnisotropy = 1.0f;\n\t\tbreak;\n\tcase VkIntelSamplerQuirk::BrokenNearestMipLinear:\n\t\t// None (trilinear) still does not work. Use None (linear mipmap) instead.\n\t\tif (filter == 6)\n\t\t\tfilter = 5;\n\t\tbrokenNearestMipLinear = true;\n\t\tbreak;\n\tdefault:\n\t\tbreak;\n\t}\n\n\tfor (int i = CLAMP_NONE;''')

# Bindless capacity consumes the snapshot limits rather than re-reading device properties.
path = "src/common/rendering/vulkan/descriptorsets/vk_descriptorset.cpp"
regex_one(path,
    r'\tconst auto& coreLimits = fb->GetDevice\(\)->PhysicalDevice\.Properties\.Properties\.limits;\n\tconst auto& indexingLimits = fb->GetDevice\(\)->PhysicalDevice\.Properties\.DescriptorIndexing;\n\n\tVkBindlessDeviceLimits limits;\n.*?\tlimits\.MaxUpdateAfterBindDescriptorsInAllPools = indexingLimits\.maxUpdateAfterBindDescriptorsInAllPools;\n',
    '\tconst auto& limits = fb->GetCapabilities().BindlessLimits;\n')

# Pipeline-library hardware support is descriptive; gl_ubershaders remains policy.
path = "src/common/rendering/vulkan/pipelines/vk_renderpass.cpp"
replace_one(path,
    '''\tconst auto device = fb->GetDevice();\n\t\n\tUsePipelineLibrary = device->SupportsExtension(VK_EXT_GRAPHICS_PIPELINE_LIBRARY_EXTENSION_NAME) // Is this supported?\n\t\t&& device->EnabledFeatures.GraphicsPipelineLibrary.graphicsPipelineLibrary; // Well yes, but actually no.\n''',
    '''\tUsePipelineLibrary = fb->GetCapabilities().SupportsGraphicsPipelineLibrary();\n''')

# Preserve the inherited MSAA selection algorithm behind a named registry query.
path = "src/common/rendering/vulkan/textures/vk_renderbuffers.cpp"
regex_one(path,
    r'VkSampleCountFlagBits VkRenderBuffers::GetBestSampleCount\(\)\n\{.*?\n\}\n\nvoid VkRenderBuffers::BeginFrame',
    '''VkSampleCountFlagBits VkRenderBuffers::GetBestSampleCount()\n{\n\treturn fb->GetCapabilities().BestSceneSampleCount((int)gl_multisample);\n}\n\nvoid VkRenderBuffers::BeginFrame''')

print("PF-007 source transforms applied successfully")
