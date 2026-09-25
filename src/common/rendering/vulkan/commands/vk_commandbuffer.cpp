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

#include "vk_commandbuffer.h"
#include <zvulkan/cfxtrace.h>
#include "vulkan/vk_renderdevice.h"
#include "vulkan/vk_renderstate.h"
#include "vulkan/vk_postprocess.h"
#include "vulkan/framebuffers/vk_framebuffer.h"
#include "vulkan/descriptorsets/vk_descriptorset.h"
#include <zvulkan/vulkanswapchain.h>
#include <zvulkan/vulkanbuilders.h>
#include "hw_clock.h"
#include "v_video.h"

extern int rendered_commandbuffers;
int current_rendered_commandbuffers;

extern bool gpuStatActive;
extern bool keepGpuStatActive;
extern FString gpuStatOutput;

VkCommandBufferManager::VkCommandBufferManager(VulkanRenderDevice* fb) : fb(fb)
{
	mCommandPool = CommandPoolBuilder()
		.QueueFamily(fb->GetDevice()->GraphicsFamily)
		.DebugName("mCommandPool")
		.Create(fb->GetDevice());

	for (int i = 0; i < maxConcurrentSubmitCount; i++)
	{
		mSubmitSemaphore[i].reset(new VulkanSemaphore(fb->GetDevice()));
		mSubmitFence[i].reset(new VulkanFence(fb->GetDevice()));
		if (CfxTrace::Enabled())
		{
			char name[48];
			std::snprintf(name, sizeof(name), "CFX submit semaphore slot %d", i);
			mSubmitSemaphore[i]->SetDebugName(name);
			std::snprintf(name, sizeof(name), "CFX submit fence slot %d", i);
			mSubmitFence[i]->SetDebugName(name);
		}
	}

	for (int i = 0; i < maxConcurrentSubmitCount; i++)
		mSubmitWaitFences[i] = mSubmitFence[i]->fence;

	if (fb->GetDevice()->GraphicsTimeQueries)
	{
		mTimestampQueryPool = QueryPoolBuilder()
			.QueryType(VK_QUERY_TYPE_TIMESTAMP, MaxTimestampQueries)
			.Create(fb->GetDevice());

		GetDrawCommands()->resetQueryPool(mTimestampQueryPool.get(), 0, MaxTimestampQueries);
	}
}

VkCommandBufferManager::~VkCommandBufferManager()
{
}

VulkanCommandBuffer* VkCommandBufferManager::GetTransferCommands()
{
	if (!mTransferCommands)
	{
		std::unique_lock<std::mutex> lock(mMutex);
		mTransferCommands = mCommandPool->createBuffer();
		mTransferCommands->SetDebugName("TransferCommands");
		mTransferCommands->begin();
		mLastTransferStage = nullptr;
	}
	if (CfxTrace::Enabled() && mTransferCommands)
	{
		const char* stage = CfxTrace::CurrentStage();
		if (stage != mLastTransferStage) { DiagnosticMarker(mTransferCommands.get(), stage); mLastTransferStage = stage; }
	}
	return mTransferCommands.get();
}

VulkanCommandBuffer* VkCommandBufferManager::GetDrawCommands()
{
	if (!mDrawCommands)
	{
		std::unique_lock<std::mutex> lock(mMutex);
		mDrawCommands = mCommandPool->createBuffer();
		mDrawCommands->SetDebugName("DrawCommands");
		mDrawCommands->begin();
		mLastDrawStage = nullptr;
	}
	if (CfxTrace::Enabled() && mDrawCommands)
	{
		const char* stage = CfxTrace::CurrentStage();
		if (stage != mLastDrawStage) { DiagnosticMarker(mDrawCommands.get(), stage); mLastDrawStage = stage; }
	}
	return mDrawCommands.get();
}

std::unique_ptr<VulkanCommandBuffer> VkCommandBufferManager::BeginThreadCommands()
{
	std::unique_lock<std::mutex> lock(mMutex);
	auto commands = mCommandPool->createBuffer();
	commands->SetDebugName("ThreadCommands");
	lock.unlock();
	commands->begin();
	return commands;
}

void VkCommandBufferManager::EndThreadCommands(std::unique_ptr<VulkanCommandBuffer> commands)
{
	commands->end();
	std::unique_lock<std::mutex> lock(mMutex);
	mThreadCommands.push_back(std::move(commands));
}

void VkCommandBufferManager::DiagnosticMarker(VulkanCommandBuffer* commands, const char* stage)
{
	if (!CfxTrace::Enabled() || !commands) return;
	if (fb->GetDevice()->Instance->EnabledExtensions.count(VK_EXT_DEBUG_UTILS_EXTENSION_NAME) && vkCmdInsertDebugUtilsLabelEXT)
	{
		VkDebugUtilsLabelEXT label = { VK_STRUCTURE_TYPE_DEBUG_UTILS_LABEL_EXT };
		label.pLabelName = stage;
		vkCmdInsertDebugUtilsLabelEXT(commands->buffer, &label);
	}
	if (fb->GetDevice()->SupportsExtension(VK_NV_DEVICE_DIAGNOSTIC_CHECKPOINTS_EXTENSION_NAME) && vkCmdSetCheckpointNV && mCheckpoints.size() < 100000)
	{
		auto marker = std::make_unique<DiagnosticCheckpoint>();
		std::snprintf(marker->name, sizeof(marker->name), "frame=%llu stage=%s",
			static_cast<unsigned long long>(CfxTrace::State().frame.load()), stage);
		char line[160];
		std::snprintf(line, sizeof(line), "marker=%p cmd=%p %s", marker.get(), commands->buffer, marker->name);
		CfxTrace::Mark("gpu-checkpoint-recorded", line);
		vkCmdSetCheckpointNV(commands->buffer, marker.get());
		mCheckpoints.push_back(std::move(marker));
	}
}

void VkCommandBufferManager::BeginFrame()
{
	if (mNextTimestampQuery > 0)
	{
		GetTransferCommands()->resetQueryPool(mTimestampQueryPool.get(), 0, mNextTimestampQuery);
		mNextTimestampQuery = 0;
	}
}

void VkCommandBufferManager::FlushCommands(VulkanCommandBuffer** commands, size_t count, bool finish, bool lastsubmit)
{
	int currentIndex = mNextSubmit % maxConcurrentSubmitCount;

	if (mNextSubmit >= maxConcurrentSubmitCount)
	{
		VkResult result;
		do
		{
			CfxTrace::Mark("vk-enter", "vkWaitForFences/recycle");
			result = vkWaitForFences(fb->GetDevice()->device, 1, &mSubmitFence[currentIndex]->fence, VK_TRUE, std::numeric_limits<uint64_t>::max());
			CfxTrace::Mark("vk-return", "vkWaitForFences/recycle", static_cast<int>(result));
			fb->GetDevice()->CheckVulkanError(result, "Could not wait for commands");
		} while (result != VK_SUCCESS);

		CfxTrace::Mark("vk-enter", "vkResetFences/recycle");
		result = vkResetFences(fb->GetDevice()->device, 1, &mSubmitFence[currentIndex]->fence);
		CfxTrace::Mark("vk-return", "vkResetFences/recycle", static_cast<int>(result));
		fb->GetDevice()->CheckVulkanError(result, "Could not reset fence");
	}

	if (CfxTrace::Enabled())
	{
		CfxTrace::NextSubmission();
		char detail[100];
		std::snprintf(detail, sizeof(detail), "graphics slot=%d buffers=%zu finish=%d last=%d",
			currentIndex, count, finish ? 1 : 0, lastsubmit ? 1 : 0);
		CfxTrace::Mark("submit-enter", detail);
	}
	QueueSubmit submit;

	for (size_t i = 0; i < count; i++)
	{
		if (CfxTrace::Enabled())
		{
			char detail[80];
			std::snprintf(detail, sizeof(detail), "cmd=%p slot=%d", commands[i]->buffer, currentIndex);
			CfxTrace::Mark("submit-buffer", detail);
		}
		submit.AddCommandBuffer(commands[i]);
	}

	if (mNextSubmit > 0)
		submit.AddWait(VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, mSubmitSemaphore[(mNextSubmit - 1) % maxConcurrentSubmitCount].get());

	if (finish && fb->GetFramebufferManager()->PresentImageIndex != -1)
	{
		submit.AddWait(VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT, fb->GetFramebufferManager()->SwapChainImageAvailableSemaphore.get());
		submit.AddSignal(fb->GetFramebufferManager()->GetRenderFinishedSemaphore());
	}

	if (!lastsubmit)
		submit.AddSignal(mSubmitSemaphore[currentIndex].get());

	CfxTrace::Mark("vk-enter", "vkQueueSubmit");
	submit.Execute(fb->GetDevice(), fb->GetDevice()->GraphicsQueue, mSubmitFence[currentIndex].get());
	CfxTrace::Mark("vk-return", "vkQueueSubmit", 0);
	mNextSubmit++;
}

void VkCommandBufferManager::FlushCommands(bool finish, bool lastsubmit, bool uploadOnly)
{
	fb->GetDescriptorSetManager()->UpdateBindlessDescriptorSet();

	if (!uploadOnly)
		fb->GetRenderState()->EndRenderPass();

	std::unique_lock<std::mutex> lock(mMutex);

	if (mTransferCommands)
	{
		mTransferCommands->end();
		mFlushCommands.push_back(mTransferCommands.get());
		TransferDeleteList->Add(std::move(mTransferCommands));
	}

	if (!uploadOnly)
	{
		if (mDrawCommands)
		{
			mDrawCommands->end();
			mFlushCommands.push_back(mDrawCommands.get());
			DrawDeleteList->Add(std::move(mDrawCommands));
		}

		for (auto& buffer : mThreadCommands)
		{
			mFlushCommands.push_back(buffer.get());
			DrawDeleteList->Add(std::move(buffer));
		}
		mThreadCommands.clear();
	}

	if (!mFlushCommands.empty())
	{
		FlushCommands(mFlushCommands.data(), mFlushCommands.size(), finish, lastsubmit);
		current_rendered_commandbuffers += (int)mFlushCommands.size();
		mFlushCommands.clear();
	}
}

void VkCommandBufferManager::WaitForCommands(bool finish, bool uploadOnly)
{
	if (finish)
	{
		Finish.Reset();
		Finish.Clock();

		CfxTrace::Mark("vk-enter", "AcquireImage");
		fb->GetFramebufferManager()->AcquireImage();
		CfxTrace::Mark("vk-return", "AcquireImage");
	}

	FlushCommands(finish, true, uploadOnly);

	if (finish)
	{
		if (!fb->GetVSync())
			fb->FPSLimit();
		CfxTrace::Mark("vk-enter", "QueuePresent");
		fb->GetFramebufferManager()->QueuePresent();
		CfxTrace::Mark("vk-return", "QueuePresent");
	}

	int numWaitFences = min(mNextSubmit, (int)maxConcurrentSubmitCount);
	if (numWaitFences > 0)
	{
		CfxTrace::Mark("vk-enter", "vkWaitForFences/frame");
		VkResult result = vkWaitForFences(fb->GetDevice()->device, numWaitFences, mSubmitWaitFences, VK_TRUE, std::numeric_limits<uint64_t>::max());
		CfxTrace::Mark("vk-return", "vkWaitForFences/frame", static_cast<int>(result));
		fb->GetDevice()->CheckVulkanError(result, "Could not wait for commands");
		if (result == VK_TIMEOUT)
			VulkanError("vkWaitForFences timed out! Broken display driver?");

		if (finish)
			fb->GetFramebufferManager()->RetirePresentSemaphoresAfterFrame();

		CfxTrace::Mark("vk-enter", "vkResetFences/frame");
		result = vkResetFences(fb->GetDevice()->device, numWaitFences, mSubmitWaitFences);
		CfxTrace::Mark("vk-return", "vkResetFences/frame", static_cast<int>(result));
		fb->GetDevice()->CheckVulkanError(result, "Could not reset fences");
		mNextSubmit = 0;
	}

	DeleteFrameObjects(uploadOnly);

	if (finish && CfxTrace::Enabled() &&
		fb->GetDevice()->SupportsExtension(VK_NV_DEVICE_DIAGNOSTIC_CHECKPOINTS_EXTENSION_NAME) &&
		vkGetQueueCheckpointDataNV)
	{
		static bool checked = false;
		if (!checked)
		{
			checked = true;
			uint32_t count = 0;
			vkGetQueueCheckpointDataNV(fb->GetDevice()->GraphicsQueue, &count, nullptr);
			CfxTrace::Mark("gpu-checkpoint-smoke", count ? "queue-returned-markers" : "queue-returned-zero");
		}
	}

	if (finish)
	{
		Finish.Unclock();
		rendered_commandbuffers = current_rendered_commandbuffers;
		current_rendered_commandbuffers = 0;
	}
}

void VkCommandBufferManager::DeleteFrameObjects(bool uploadOnly)
{
	TransferDeleteList = std::make_unique<DeleteList>();
	if (!uploadOnly)
		DrawDeleteList = std::make_unique<DeleteList>();
}

void VkCommandBufferManager::PushGroup(VulkanCommandBuffer* cmdbuffer, const FString& name)
{
	if (!gpuStatActive)
		return;

	if (mNextTimestampQuery < MaxTimestampQueries && fb->GetDevice()->GraphicsTimeQueries)
	{
		TimestampQuery q;
		q.name = name;
		q.startIndex = mNextTimestampQuery++;
		q.endIndex = 0;
		cmdbuffer->writeTimestamp(VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT, mTimestampQueryPool.get(), q.startIndex);
		mGroupStack.push_back(timeElapsedQueries.size());
		timeElapsedQueries.push_back(q);
	}
}

void VkCommandBufferManager::PopGroup(VulkanCommandBuffer* cmdbuffer)
{
	if (!gpuStatActive || mGroupStack.empty())
		return;

	TimestampQuery& q = timeElapsedQueries[mGroupStack.back()];
	mGroupStack.pop_back();

	if (mNextTimestampQuery < MaxTimestampQueries && fb->GetDevice()->GraphicsTimeQueries)
	{
		q.endIndex = mNextTimestampQuery++;
		cmdbuffer->writeTimestamp(VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT, mTimestampQueryPool.get(), q.endIndex);
	}
}

void VkCommandBufferManager::UpdateGpuStats()
{
	uint64_t timestamps[MaxTimestampQueries];
	if (mNextTimestampQuery > 0)
		mTimestampQueryPool->getResults(0, mNextTimestampQuery, sizeof(uint64_t) * mNextTimestampQuery, timestamps, sizeof(uint64_t), VK_QUERY_RESULT_64_BIT | VK_QUERY_RESULT_WAIT_BIT);

	double timestampPeriod = fb->GetDevice()->PhysicalDevice.Properties.Properties.limits.timestampPeriod;

	gpuStatOutput = "";
	for (auto& q : timeElapsedQueries)
	{
		if (q.endIndex <= q.startIndex)
			continue;

		int64_t timeElapsed = max(static_cast<int64_t>(timestamps[q.endIndex] - timestamps[q.startIndex]), (int64_t)0);
		double timeNS = timeElapsed * timestampPeriod;

		FString out;
		out.Format("%s=%04.2f ms\n", q.name.GetChars(), timeNS / 1000000.0f);
		gpuStatOutput += out;
	}
	timeElapsedQueries.clear();
	mGroupStack.clear();

	gpuStatActive = keepGpuStatActive;
	keepGpuStatActive = false;
}
