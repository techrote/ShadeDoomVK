#pragma once

#include "vulkaninstance.h"
#include "cfxtrace.h"

#include <functional>
#include <mutex>
#include <vector>
#include <algorithm>
#include <memory>
#include <string>

class VulkanSwapChain;
class VulkanSemaphore;
class VulkanFence;
class VulkanPhysicalDevice;
class VulkanSurface;
class VulkanCompatibleDevice;

class VulkanDeviceFaultInfo
{
public:
	std::string description;
	// std::vector<std::string> addressInfos;
	std::vector<std::string> vendorInfos;
};

class VulkanDevice
{
public:
	VulkanDevice(std::shared_ptr<VulkanInstance> instance, std::shared_ptr<VulkanSurface> surface, const VulkanCompatibleDevice& selectedDevice);
	~VulkanDevice();

	std::set<std::string> EnabledDeviceExtensions;
	VulkanDeviceFeatures EnabledFeatures;

	VulkanPhysicalDevice PhysicalDevice;

	std::shared_ptr<VulkanInstance> Instance;
	std::shared_ptr<VulkanSurface> Surface;

	VkDevice device = VK_NULL_HANDLE;
	VmaAllocator allocator = VK_NULL_HANDLE;

	VkQueue GraphicsQueue = VK_NULL_HANDLE;
	VkQueue PresentQueue = VK_NULL_HANDLE;

	int GraphicsFamily = -1;
	int PresentFamily = -1;
	bool GraphicsTimeQueries = false;

	bool SupportsExtension(const char* ext) const;

	void SetObjectName(const char* name, uint64_t handle, VkObjectType type);

	VulkanDeviceFaultInfo GetDeviceFaultInfo();

	inline void CheckVulkanError(VkResult result, const char* text)
	{
		if (result >= VK_SUCCESS) return;
		CfxTrace::Mark("vk-error", text, static_cast<int>(result));
		if (result == VK_ERROR_DEVICE_LOST)
		{
			if (CfxTrace::Enabled()) { CfxTrace::State().deviceLost.store(true); CfxTrace::Mark("device-lost-observed", text, static_cast<int>(result)); }
			if (SupportsExtension(VK_NV_DEVICE_DIAGNOSTIC_CHECKPOINTS_EXTENSION_NAME) && vkGetQueueCheckpointDataNV)
			{
				auto capture = [](VkQueue queue, const char* queueName) {
					if (!queue) return;
					uint32_t count = 0;
					vkGetQueueCheckpointDataNV(queue, &count, nullptr);
					std::vector<VkCheckpointDataNV> data(std::min(count, 256u));
					for (auto& item : data) item.sType = VK_STRUCTURE_TYPE_CHECKPOINT_DATA_NV;
					count = static_cast<uint32_t>(data.size());
					if (count) vkGetQueueCheckpointDataNV(queue, &count, data.data());
					for (uint32_t i = 0; i < count && i < data.size(); i++)
					{
						char line[120];
						std::snprintf(line, sizeof(line), "%s stage=%u marker=%p", queueName, data[i].stage, data[i].pCheckpointMarker);
						CfxTrace::Mark("gpu-checkpoint-confirmed", line);
					}
				};
				capture(GraphicsQueue, "graphics");
				if (PresentQueue != GraphicsQueue) capture(PresentQueue, "present");
			}
			VulkanDeviceFaultInfo info = GetDeviceFaultInfo();
			if (!info.description.empty())
				VulkanPrintLog("fault", info.description);
			for (const std::string& vendorInfo : info.vendorInfos)
				VulkanPrintLog("fault", vendorInfo);
		}
		VulkanError((text + std::string(": ") + VkResultToString(result)).c_str());
	}

private:
	void CreateDevice();
	void CreateAllocator();
	void ReleaseResources();
};
