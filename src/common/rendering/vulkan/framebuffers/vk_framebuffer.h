
#pragma once

#include "zvulkan/vulkanobjects.h"
#include <array>
#include <map>
#include <vector>

class VulkanRenderDevice;
enum class PPFilterMode;
enum class PPWrapMode;

class VkFramebufferManager
{
public:
	VkFramebufferManager(VulkanRenderDevice* fb);
	~VkFramebufferManager();

	void AcquireImage();
	void QueuePresent();
	void RetirePresentSemaphoresAfterFrame();
	VulkanSemaphore* GetRenderFinishedSemaphore() const;

	std::map<int, std::unique_ptr<VulkanFramebuffer>> Framebuffers;

	std::shared_ptr<VulkanSwapChain> SwapChain;
	int PresentImageIndex = -1;

	std::unique_ptr<VulkanSemaphore> SwapChainImageAvailableSemaphore;
	std::vector<std::unique_ptr<VulkanSemaphore>> RenderFinishedSemaphores;

private:
	// Old image-owned semaphores must survive swapchain recreation until a
	// presentation of the new swapchain is known to have completed.
	std::vector<std::vector<std::unique_ptr<VulkanSemaphore>>> RetiredRenderFinishedSemaphores;
	int FirstPresentedImageIndex = -1;
	bool RetirementProofPending = false;
	VulkanRenderDevice* fb = nullptr;
	int CurrentWidth = 0;
	int CurrentHeight = 0;
	bool CurrentVSync = false;
	bool CurrentHdr = false;
};
