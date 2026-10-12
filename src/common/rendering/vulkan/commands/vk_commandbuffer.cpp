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
#include "vulkan/vk_levelmesh.h"
#include "vulkan/framebuffers/vk_framebuffer.h"
#include "vulkan/descriptorsets/vk_descriptorset.h"
#include <zvulkan/vulkanswapchain.h>
#include <zvulkan/vulkanbuilders.h>
#include "hw_clock.h"
#include "diagnostics/hw_sdvkdiagnostics.h"
#include "v_video.h"
#include "i_system.h"
#include <cmath>

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
	if (mRecordedCollisionReadback) CfxTrace::WitnessFail("unsubmitted-collision-readback-at-shutdown");
	for (const auto& pending : mCollisionReadbacks)
		if (pending) CfxTrace::WitnessFail("incomplete-collision-readback-at-shutdown");
}

std::unique_ptr<VkCommandBufferManager::CollisionPublicationReadback> VkCommandBufferManager::RecordCollisionReadback()
{
	try
	{
		using namespace CollisionReadback;
		Require(CfxTrace::WitnessEnabled(), "readback-without-witness");
		auto* mesh = fb->GetLevelMesh();
		Require(mesh && mesh->GetMesh(), "readback-without-level-mesh");
		auto pending = std::make_unique<CollisionPublicationReadback>();
		pending->Plan = mesh->CreatePostUseReadbackPlan();
		Require(mCollisionReadbackCount < MaxPlans && pending->Plan.Bytes <= MaxRunBytes - mCollisionReadbackBytes,
			"readback-run-budget");
		pending->Id = ++mCollisionReadbackCount;
		mCollisionReadbackBytes += pending->Plan.Bytes;
		pending->Sources = {{ mesh->GetNodeBuffer(), mesh->GetVertexBuffer(), mesh->GetIndexBuffer() }};
		pending->Staging = BufferBuilder().Size(static_cast<size_t>(pending->Plan.Bytes))
			.Usage(VK_BUFFER_USAGE_TRANSFER_DST_BIT, VMA_MEMORY_USAGE_GPU_TO_CPU)
			.DebugName("CollisionPostUseReadback").Create(fb->GetDevice());
		Require(pending->Staging && pending->Staging->diagnosticId, "readback-staging-allocation-unidentified");
		pending->Commands = mCommandPool->createBuffer();
		pending->Commands->SetDebugName("CollisionPostUseReadbackCommands");
		pending->Commands->begin();
		pending->Completion.Record(pending->Commands->diagnosticId, pending->Commands->diagnosticRecording);

		// This separate command buffer is appended AFTER every ordinary transfer,
		// draw and thread command in the existing submit. No new submit or wait is
		// introduced. Buffer-scoped barriers order all preceding uses/publications.
		PipelineBarrier()
			.AddBuffer(pending->Sources[0], VK_ACCESS_TRANSFER_WRITE_BIT | VK_ACCESS_SHADER_READ_BIT, VK_ACCESS_TRANSFER_READ_BIT)
			.AddBuffer(pending->Sources[1], VK_ACCESS_TRANSFER_WRITE_BIT | VK_ACCESS_SHADER_READ_BIT | VK_ACCESS_VERTEX_ATTRIBUTE_READ_BIT, VK_ACCESS_TRANSFER_READ_BIT)
			.AddBuffer(pending->Sources[2], VK_ACCESS_TRANSFER_WRITE_BIT | VK_ACCESS_SHADER_READ_BIT | VK_ACCESS_INDEX_READ_BIT, VK_ACCESS_TRANSFER_READ_BIT)
			.Execute(pending->Commands.get(), VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT);

		char detail[720];
		const auto& plan = pending->Plan;
		std::snprintf(detail, sizeof(detail), "readback_id=%llu snapshot_object=%u snapshot_event=%u exported_count=%u root=%d node_id=%llu vertex_id=%llu index_id=%llu staging_id=%llu cmd_id=%llu recording=%llu bytes=%llu ranges=%zu reachable_count=%zu occupied_count=%u referenced_count=%zu",
			(unsigned long long)pending->Id, plan.State.Object, plan.State.Event, plan.State.ExportedCount, plan.State.Root,
			(unsigned long long)plan.Sources[0].Id, (unsigned long long)plan.Sources[1].Id, (unsigned long long)plan.Sources[2].Id,
			(unsigned long long)pending->Staging->diagnosticId, (unsigned long long)pending->Completion.Command,
			(unsigned long long)pending->Completion.Recording, (unsigned long long)plan.Bytes, plan.Regions.size(),
			plan.ReachableNodes.size(), plan.State.OccupiedCount, plan.ReferencedVertices.size());
		CfxTrace::WitnessMark("postuse-plan", detail);
		for (const auto& region : plan.Regions)
		{
			const auto source = static_cast<unsigned int>(region.Buffer);
			std::snprintf(detail, sizeof(detail), "readback_id=%llu kind=%s identity=%u src_id=%llu src_offset=%llu dst_offset=%llu bytes=%llu",
				(unsigned long long)pending->Id, FieldName(region.Semantic), region.Identity,
				(unsigned long long)plan.Sources[source].Id, (unsigned long long)region.SrcOffset,
				(unsigned long long)region.DstOffset, (unsigned long long)region.Bytes);
			CfxTrace::WitnessMark("postuse-range", detail);
			pending->Commands->copyBuffer(pending->Sources[source], pending->Staging.get(), region.SrcOffset, region.DstOffset, region.Bytes);
		}
		// Fence completion does not replace device-to-host memory visibility.
		PipelineBarrier().AddBuffer(pending->Staging.get(), VK_ACCESS_TRANSFER_WRITE_BIT, VK_ACCESS_HOST_READ_BIT)
			.Execute(pending->Commands.get(), VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_HOST_BIT);
		pending->Commands->end();
		return pending;
	}
	catch (const std::exception& error)
	{
		CfxTrace::WitnessFail(error.what());
		I_FatalError("Collision publication readback failed: %s", error.what());
	}
	return {};
}

void VkCommandBufferManager::FinishCollisionReadback(unsigned int slot)
{
	auto& pending = mCollisionReadbacks[slot];
	if (!pending) return;
	try
	{
		using namespace CollisionReadback;
		// Called only after VK_SUCCESS from an ALREADY REQUIRED recycle/frame
		// fence wait, before fence reset and before either retirement list clears.
		const FenceIdentity fence = { mWitnessSubmissions[slot], (uint64_t)mSubmitFence[slot]->fence, slot };
		pending->Completion.Complete(fence, true);
		pending->Completion.RequireReadable();
		// A failed evidence recorder disables new plans, never pending Vulkan
		// lifetime handling. Retire only here, after the original fence; do not
		// map/export or dereference source owners for an already failed witness.
		if (!CfxTrace::WitnessEnabled()) { pending.reset(); return; }
		std::array<Allocation, 3> current;
		for (unsigned int i = 0; i < current.size(); ++i)
			current[i] = { pending->Sources[i]->diagnosticId, pending->Sources[i]->size };
		Validate(pending->Plan, current);
		char detail[320];
		std::snprintf(detail, sizeof(detail), "readback_id=%llu submission=%llu fence_slot=%u fence=0x%llx",
			(unsigned long long)pending->Id, (unsigned long long)fence.Submission, slot, (unsigned long long)fence.Handle);
		CfxTrace::WitnessMark("postuse-fence", detail);
		if (!CfxTrace::WitnessEnabled()) { pending.reset(); return; }
		const auto bytes = static_cast<size_t>(pending->Plan.Bytes);
		const void* mapped = pending->Staging->Map(0, bytes);
		Require(mapped != nullptr, "readback-map-failed");
		uint64_t hash = 14695981039346656037ull;
		const std::string filename = "readback-" + std::to_string(pending->Id) + ".bin";
		try
		{
			// VMA rounds non-coherent invalidation to nonCoherentAtomSize. Do not
			// dereference or fingerprint mapped bytes until this checked success.
			const VkResult invalidated = vmaInvalidateAllocation(fb->GetDevice()->allocator, pending->Staging->allocation, 0, bytes);
			Require(invalidated == VK_SUCCESS, "readback-invalidate-failed");
			const auto* data = static_cast<const unsigned char*>(mapped);
			for (size_t i = 0; i < bytes; ++i) { hash ^= data[i]; hash *= 1099511628211ull; }
			const auto path = CfxTrace::WitnessFilePath(filename.c_str());
			std::FILE* file = nullptr;
#ifdef _MSC_VER
			fopen_s(&file, path.c_str(), "wbx");
#else
			file = std::fopen(path.c_str(), "wbx");
#endif
			Require(file != nullptr, "readback-file-create-failed");
			const bool written = std::fwrite(data, 1, bytes, file) == bytes;
			const bool closed = std::fclose(file) == 0;
			Require(written && closed, "readback-file-write-or-close-failed");
		}
		catch (...) { pending->Staging->Unmap(); throw; }
		pending->Staging->Unmap();
		std::snprintf(detail, sizeof(detail), "readback_id=%llu bytes=%llu fnv1a64=0x%llx file=%s",
			(unsigned long long)pending->Id, (unsigned long long)pending->Plan.Bytes, (unsigned long long)hash, filename.c_str());
		CfxTrace::WitnessMark("postuse-readback", detail);
		pending.reset();
	}
	catch (const std::exception& error)
	{
		CfxTrace::WitnessFail(error.what());
		I_FatalError("Collision publication readback failed: %s", error.what());
	}
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
		if (CfxTrace::WitnessEnabled())
		{
			char detail[160];
			std::snprintf(detail, sizeof(detail), "submission=%llu fence_slot=%d fence=0x%llx wait=recycle result=0",
				(unsigned long long)mWitnessSubmissions[currentIndex], currentIndex, (unsigned long long)(uint64_t)mSubmitFence[currentIndex]->fence);
			CfxTrace::WitnessMark("fence-complete", detail);
		}
		FinishCollisionReadback(static_cast<unsigned int>(currentIndex));

		CfxTrace::Mark("vk-enter", "vkResetFences/recycle");
		result = vkResetFences(fb->GetDevice()->device, 1, &mSubmitFence[currentIndex]->fence);
		CfxTrace::Mark("vk-return", "vkResetFences/recycle", static_cast<int>(result));
		fb->GetDevice()->CheckVulkanError(result, "Could not reset fence");
	}

	if (CfxTrace::Enabled() || CfxTrace::WitnessEnabled() || mRecordedCollisionReadback)
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
			char detail[160];
			std::snprintf(detail, sizeof(detail), "cmd=%p cmd_id=%llu slot=%d fence=%p queue=%p", commands[i]->buffer,
				(unsigned long long)commands[i]->diagnosticId, currentIndex, (void*)mSubmitFence[currentIndex]->fence, (void*)fb->GetDevice()->GraphicsQueue);
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
	const auto submission = CfxTrace::State().submission.load();
	if (CfxTrace::WitnessEnabled() || mRecordedCollisionReadback)
		mWitnessSubmissions[currentIndex] = submission;
	if (CfxTrace::WitnessEnabled())
	{
		for (size_t i = 0; i < count; ++i)
		{
			char detail[256];
			std::snprintf(detail, sizeof(detail), "cmd_id=%llu recording=%llu submission=%llu fence=0x%llx fence_slot=%d index=%zu buffers=%zu",
				(unsigned long long)commands[i]->diagnosticId, (unsigned long long)commands[i]->diagnosticRecording,
				(unsigned long long)submission, (unsigned long long)(uint64_t)mSubmitFence[currentIndex]->fence, currentIndex, i, count);
			CfxTrace::WitnessMark("submit-command", detail);
		}
	}
	if (mRecordedCollisionReadback)
	{
		CollisionReadback::Require(!mCollisionReadbacks[currentIndex] && count &&
			commands[count - 1] == mRecordedCollisionReadback->Commands.get(), "readback-not-last-command-or-fence-slot-busy");
		const CollisionReadback::FenceIdentity fence = { submission, (uint64_t)mSubmitFence[currentIndex]->fence, static_cast<unsigned int>(currentIndex) };
		mRecordedCollisionReadback->Completion.Submit(commands[count - 1]->diagnosticId, commands[count - 1]->diagnosticRecording, fence);
		char detail[256];
		std::snprintf(detail, sizeof(detail), "readback_id=%llu submission=%llu fence_slot=%d fence=0x%llx cmd_id=%llu recording=%llu",
			(unsigned long long)mRecordedCollisionReadback->Id, (unsigned long long)submission, currentIndex,
			(unsigned long long)fence.Handle, (unsigned long long)mRecordedCollisionReadback->Completion.Command,
			(unsigned long long)mRecordedCollisionReadback->Completion.Recording);
		CfxTrace::WitnessMark("postuse-submit", detail);
		mCollisionReadbacks[currentIndex] = std::move(mRecordedCollisionReadback);
	}
	mNextSubmit++;
}

void VkCommandBufferManager::FlushCommands(bool finish, bool lastsubmit, bool uploadOnly)
{
	fb->GetDescriptorSetManager()->UpdateBindlessDescriptorSet();

	if (!uploadOnly)
		fb->GetRenderState()->EndRenderPass();

	std::unique_lock<std::mutex> lock(mMutex);
	const bool hadDrawCommands = !uploadOnly && (mDrawCommands || !mThreadCommands.empty());

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

	if (CfxTrace::WitnessEnabled() && hadDrawCommands && fb->GetLevelMesh() && fb->GetLevelMesh()->GetMesh())
	{
		CollisionReadback::Require(!mRecordedCollisionReadback, "overlapping-unsubmitted-readback");
		mRecordedCollisionReadback = RecordCollisionReadback();
		mFlushCommands.push_back(mRecordedCollisionReadback->Commands.get());
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
		for (int slot = 0; slot < numWaitFences; ++slot)
		{
			if (CfxTrace::WitnessEnabled() || mCollisionReadbacks[slot])
			{
				CollisionReadback::Require(result == VK_SUCCESS, "readback-frame-fence-not-successful");
				char detail[160];
				std::snprintf(detail, sizeof(detail), "submission=%llu fence_slot=%d fence=0x%llx wait=frame result=0",
					(unsigned long long)mWitnessSubmissions[slot], slot, (unsigned long long)(uint64_t)mSubmitFence[slot]->fence);
				CfxTrace::WitnessMark("fence-complete", detail);
				FinishCollisionReadback(static_cast<unsigned int>(slot));
			}
		}

		if (finish)
			fb->GetFramebufferManager()->RetirePresentSemaphoresAfterFrame();

		CfxTrace::Mark("vk-enter", "vkResetFences/frame");
		result = vkResetFences(fb->GetDevice()->device, numWaitFences, mSubmitWaitFences);
		CfxTrace::Mark("vk-return", "vkResetFences/frame", static_cast<int>(result));
		fb->GetDevice()->CheckVulkanError(result, "Could not reset fences");
		mNextSubmit = 0;
	}

	DeleteFrameObjects(uploadOnly);

	// NV checkpoint retrieval is valid only after device loss. Safe activation
	// is established by capability and gpu-checkpoint-recorded breadcrumbs.

	if (finish)
	{
		Finish.Unclock();
		rendered_commandbuffers = current_rendered_commandbuffers;
		current_rendered_commandbuffers = 0;
	}
}

void VkCommandBufferManager::DeleteFrameObjects(bool uploadOnly)
{
	CollisionReadback::Require(!mRecordedCollisionReadback, "retirement-before-readback-submit");
	for (const auto& pending : mCollisionReadbacks)
		CollisionReadback::Require(!pending, "retirement-before-readback-fence");
	CfxTrace::Object("retirement-list-release", "transfer-list", TransferDeleteList->DiagnosticId, 0, TransferDeleteList->TotalSize);
	TransferDeleteList = std::make_unique<DeleteList>();
	if (!uploadOnly)
	{
		CfxTrace::Object("retirement-list-release", "draw-list", DrawDeleteList->DiagnosticId, 0, DrawDeleteList->TotalSize);
		DrawDeleteList = std::make_unique<DeleteList>();
	}
}

void VkCommandBufferManager::FinishPublicationWitness()
{
	if (!CfxTrace::WitnessEnabled()) return;
	// The observer may close only after its existing screenshot/frame wait has
	// drained the real submit fences. Completion must never create another wait.
	if (mNextSubmit != 0 || mRecordedCollisionReadback || mTransferCommands || mDrawCommands ||
		!mThreadCommands.empty() || !mFlushCommands.empty() || mCollisionReadbackCount == 0)
	{
		CfxTrace::WitnessFail("witness-finish-has-unsubmitted-or-uncompleted-commands");
		I_FatalError("Collision publication witness cannot finish before normal command completion");
	}
	for (const auto& pending : mCollisionReadbacks)
	{
		if (pending)
		{
			CfxTrace::WitnessFail("witness-finish-has-pending-readback");
			I_FatalError("Collision publication witness has an incomplete readback");
		}
	}
	CfxTrace::WitnessFinish();
}

bool VkCommandBufferManager::PushGroup(VulkanCommandBuffer* cmdbuffer, const FString& name)
{
	if (!gpuStatActive)
		return false;

	if (mNextTimestampQuery < MaxTimestampQueries && fb->GetDevice()->GraphicsTimeQueries)
	{
		TimestampQuery q;
		q.name = name;
		q.startIndex = mNextTimestampQuery++;
		q.endIndex = 0;
		cmdbuffer->writeTimestamp(VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT, mTimestampQueryPool.get(), q.startIndex);
		mGroupStack.push_back(timeElapsedQueries.size());
		timeElapsedQueries.push_back(q);
		return true;
	}
	return false;
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
	bool timestampResultsReady = true;
	if (mNextTimestampQuery > 0)
		timestampResultsReady = mTimestampQueryPool->getResults(0, mNextTimestampQuery, sizeof(uint64_t) * mNextTimestampQuery, timestamps, sizeof(uint64_t), VK_QUERY_RESULT_64_BIT | VK_QUERY_RESULT_WAIT_BIT);

	double timestampPeriod = fb->GetDevice()->PhysicalDevice.Properties.Properties.limits.timestampPeriod;

	// Reuse the existing requested profiling readback: never issue an additional
	// query or wait for diagnostics. These can be nested named groups measured at
	// COLOR_ATTACHMENT_OUTPUT; they are not a sum or a whole-frame GPU timer.
	const bool diagnosticsRequested = SdvkDiagnostics::GpuTimingRequested();
	bool diagnosticQueriesReady = false;
	uint64_t timestampMask = std::numeric_limits<uint64_t>::max();
	if (diagnosticsRequested)
	{
		const auto* device = fb->GetDevice();
		const auto& families = device->PhysicalDevice.QueueFamilies;
		const bool familyKnown = device->GraphicsFamily >= 0 && static_cast<size_t>(device->GraphicsFamily) < families.size();
		const uint32_t validBits = familyKnown ? families[device->GraphicsFamily].timestampValidBits : 0;
		const char* unavailable = nullptr;
		if (!device->GraphicsTimeQueries || (familyKnown && validBits == 0))
			unavailable = "graphics_queue_timestamp_queries_unsupported";
		else if (!familyKnown || validBits < 36 || validBits > 64 || !std::isfinite(timestampPeriod) || timestampPeriod <= 0)
			unavailable = "graphics_queue_timestamp_metadata_invalid";
		else if (!gpuStatActive)
			unavailable = "gpu_timestamp_profiler_warmup";
		else if (!timestampResultsReady)
			unavailable = "gpu_timestamp_query_results_unavailable";
		else if (mNextTimestampQuery == 0 || timeElapsedQueries.empty())
			unavailable = "no_gpu_timestamp_groups_recorded";
		else if (mNextTimestampQuery >= MaxTimestampQueries || !mGroupStack.empty() ||
			std::any_of(timeElapsedQueries.begin(), timeElapsedQueries.end(), [&](const TimestampQuery& q)
				{ return q.endIndex <= q.startIndex || q.endIndex >= static_cast<uint32_t>(mNextTimestampQuery); }))
			unavailable = "gpu_timestamp_groups_incomplete_or_capacity_reached";

		if (unavailable)
			SdvkDiagnostics::GpuUnavailable(unavailable);
		else
		{
			diagnosticQueriesReady = true;
			if (validBits < 64) timestampMask = (uint64_t(1) << validBits) - 1;
		}
	}

	gpuStatOutput = "";
	for (auto& q : timeElapsedQueries)
	{
		if (!timestampResultsReady || q.endIndex <= q.startIndex)
			continue;

		if (diagnosticQueriesReady)
		{
			// VkQueueFamilyProperties::timestampValidBits defines modulo wrap.
			// This measures an interval shorter than one full counter period;
			// timestamps alone cannot disambiguate additional complete wraps.
			const uint64_t elapsedTicks = (timestamps[q.endIndex] - timestamps[q.startIndex]) & timestampMask;
			SdvkDiagnostics::GpuGroup(q.name.GetChars(), double(elapsedTicks) * timestampPeriod / 1000000.0);
		}

		// Preserve the inherited display calculation and rounding independently.
		int64_t timeElapsed = max(static_cast<int64_t>(timestamps[q.endIndex] - timestamps[q.startIndex]), (int64_t)0);
		double timeNS = timeElapsed * timestampPeriod;

		FString out;
		out.Format("%s=%04.2f ms\n", q.name.GetChars(), timeNS / 1000000.0f);
		gpuStatOutput += out;
	}
	timeElapsedQueries.clear();
	mGroupStack.clear();

	gpuStatActive = keepGpuStatActive || diagnosticsRequested;
	keepGpuStatActive = false;
}
