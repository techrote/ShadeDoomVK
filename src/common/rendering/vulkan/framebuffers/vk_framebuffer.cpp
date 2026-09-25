/*
**  Vulkan backend
**  Copyright (c) 2016-2020 Magnus Norddahl
**
**  This software is provided 'as-is', without any express or implied
**  warranty.  In no event will the authors be held liable for any damages
**  arising from the use of this software.
**
**  Permission is granted to anyone to use this software for any purpose,
**  including commercial applications, and to alter it and redistribute it
**  freely, subject to the following restrictions:
**
**  1. The origin of this software must not be misrepresented; you must not
**     claim that you wrote the original software. If you use this software
**     in a product, an acknowledgment in the product documentation would be
**     appreciated but is not required.
**  2. Altered source versions must be plainly marked as such, and must not be
**     misrepresented as being the original software.
**  3. This notice may not be removed or altered from any source distribution.
**
*/

#include <zvulkan/vulkanobjects.h>
#include <zvulkan/vulkandevice.h>
#include <zvulkan/vulkanbuilders.h>
#include <zvulkan/vulkanswapchain.h>
#include "vulkan/vk_renderdevice.h"
#include "vulkan/vk_postprocess.h"
#include "vk_framebuffer.h"

CVAR(Bool, vk_hdr, false, CVAR_ARCHIVE | CVAR_GLOBALCONFIG);

VkFramebufferManager::VkFramebufferManager(VulkanRenderDevice* fb) : fb(fb)
{
	if (fb->IsSurfaceAvailable())
	{
		SwapChain = VulkanSwapChainBuilder()
			.Create(fb->GetDevice());

		SwapChainImageAvailableSemaphore = SemaphoreBuilder()
			.DebugName("SwapChainImageAvailableSemaphore")
			.Create(fb->GetDevice());

	}
}

VkFramebufferManager::~VkFramebufferManager()
{
}

VulkanSemaphore* VkFramebufferManager::GetRenderFinishedSemaphore() const
{
	return RenderFinishedSemaphores[PresentImageIndex].get();
}

void VkFramebufferManager::AcquireImage()
{
	if (!SwapChain)
		return;

	if (SwapChain->Lost() || fb->GetClientWidth() != CurrentWidth || fb->GetClientHeight() != CurrentHeight || fb->GetVSync() != CurrentVSync || CurrentHdr != vk_hdr)
	{
		// A graphics fence only proves the signal operation completed; it does not
		// prove that vkQueuePresentKHR has consumed its wait semaphore. Before a
		// swapchain rebuild replaces image-owned semaphores, retire all presentation
		// work that can still reference the old set.
		if (SwapChain->ImageCount() > 0)
		{
			VkResult result = vkQueueWaitIdle(fb->GetDevice()->PresentQueue);
			fb->GetDevice()->CheckVulkanError(result, "Could not wait for presentation queue during swapchain recreation");
		}

		Framebuffers.clear();

		CurrentWidth = fb->GetClientWidth();
		CurrentHeight = fb->GetClientHeight();
		CurrentVSync = fb->GetVSync();
		CurrentHdr = vk_hdr;

		SwapChain->Create(CurrentWidth, CurrentHeight, CurrentVSync ? 2 : 3, CurrentVSync, CurrentHdr);

		// Present-wait binary semaphores are owned by swapchain image. Reacquiring
		// an image proves its previous presentation has retired, making the matching
		// semaphore safe to signal again without a steady-state queue idle.
		RenderFinishedSemaphores.clear();
		RenderFinishedSemaphores.reserve(SwapChain->ImageCount());
		for (int i = 0; i < SwapChain->ImageCount(); i++)
		{
			RenderFinishedSemaphores.push_back(SemaphoreBuilder()
				.DebugName("RenderFinishedSemaphore")
				.Create(fb->GetDevice()));
		}
	}

	PresentImageIndex = SwapChain->AcquireImage(SwapChainImageAvailableSemaphore.get());
	if (PresentImageIndex != -1)
	{
		fb->GetPostprocess()->DrawPresentTexture(fb->mOutputLetterbox, true, false);
	}
}

void VkFramebufferManager::QueuePresent()
{
	if (PresentImageIndex != -1)
		SwapChain->QueuePresent(PresentImageIndex, GetRenderFinishedSemaphore());
}
