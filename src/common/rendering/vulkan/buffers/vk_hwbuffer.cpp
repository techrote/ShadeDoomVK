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

#include "vk_hwbuffer.h"
#include "vk_buffer.h"
#include "vulkan/vk_renderdevice.h"
#include "vulkan/vk_renderstate.h"
#include "vulkan/commands/vk_commandbuffer.h"
#include "vulkan/descriptorsets/vk_descriptorset.h"
#include <zvulkan/vulkanbuilders.h>
#include "engineerrors.h"

namespace
{
void PublishTransferWrite(VulkanCommandBuffer* commands, VulkanBuffer* buffer, VkBufferUsageFlags usage, VkDeviceSize offset, VkDeviceSize size)
{
	// Transfer uploads are recorded before draw commands on the same graphics queue,
	// but queue/command-buffer order alone does not make transfer writes visible to
	// later buffer consumers. Keep the dependency scoped to this uploaded range.
	VkPipelineStageFlags dstStageMask = VK_PIPELINE_STAGE_TRANSFER_BIT;
	VkAccessFlags dstAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;

	if (usage & VK_BUFFER_USAGE_TRANSFER_SRC_BIT)
	{
		dstStageMask |= VK_PIPELINE_STAGE_TRANSFER_BIT;
		dstAccessMask |= VK_ACCESS_TRANSFER_READ_BIT;
	}

	if (usage & (VK_BUFFER_USAGE_VERTEX_BUFFER_BIT | VK_BUFFER_USAGE_INDEX_BUFFER_BIT))
		dstStageMask |= VK_PIPELINE_STAGE_VERTEX_INPUT_BIT;

	if (usage & VK_BUFFER_USAGE_VERTEX_BUFFER_BIT)
		dstAccessMask |= VK_ACCESS_VERTEX_ATTRIBUTE_READ_BIT;

	if (usage & VK_BUFFER_USAGE_INDEX_BUFFER_BIT)
		dstAccessMask |= VK_ACCESS_INDEX_READ_BIT;

	if (usage & (VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT | VK_BUFFER_USAGE_STORAGE_BUFFER_BIT))
		dstStageMask |= VK_PIPELINE_STAGE_ALL_GRAPHICS_BIT | VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT;

	if (usage & VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT)
		dstAccessMask |= VK_ACCESS_UNIFORM_READ_BIT;

	if (usage & VK_BUFFER_USAGE_STORAGE_BUFFER_BIT)
		dstAccessMask |= VK_ACCESS_SHADER_READ_BIT | VK_ACCESS_SHADER_WRITE_BIT;

	VkBufferMemoryBarrier barrier = { VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER };
	barrier.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
	barrier.dstAccessMask = dstAccessMask;
	barrier.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
	barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
	barrier.buffer = buffer->buffer;
	barrier.offset = offset;
	barrier.size = size;

	commands->pipelineBarrier(
		VK_PIPELINE_STAGE_TRANSFER_BIT,
		dstStageMask,
		0,
		0, nullptr,
		1, &barrier,
		0, nullptr);
}
}


VkHardwareBuffer::VkHardwareBuffer(VulkanRenderDevice* fb) : fb(fb)
{
	fb->GetBufferManager()->AddBuffer(this);
}

VkHardwareBuffer::~VkHardwareBuffer()
{
	if (fb)
		fb->GetBufferManager()->RemoveBuffer(this);
}

void VkHardwareBuffer::Reset()
{
	if (fb)
	{
		if (mBuffer && map)
		{
			mBuffer->Unmap();
			map = nullptr;
		}
		if (mBuffer)
			fb->GetCommands()->DrawDeleteList->Add(std::move(mBuffer));
		if (mStaging)
			fb->GetCommands()->TransferDeleteList->Add(std::move(mStaging));
	}
}

void VkHardwareBuffer::SetData(size_t size, const void *data, BufferUsageType usage)
{
	size_t bufsize = max(size, (size_t)16); // For supporting zero byte buffers

	// If SetData is called multiple times we have to keep the old buffers alive as there might still be draw commands referencing them
	if (mBuffer)
	{
		fb->GetCommands()->DrawDeleteList->Add(std::move(mBuffer));
	}
	if (mStaging)
	{
		fb->GetCommands()->TransferDeleteList->Add(std::move(mStaging));
	}

	if (usage == BufferUsageType::Static || usage == BufferUsageType::Stream)
	{
		// Note: we could recycle buffers here for the stream usage type to improve performance

		mPersistent = false;

		mBuffer = BufferBuilder()
			.Usage(VK_BUFFER_USAGE_TRANSFER_DST_BIT | mBufferType, VMA_MEMORY_USAGE_GPU_ONLY)
			.Size(bufsize)
			.DebugName(usage == BufferUsageType::Static ? "VkHardwareBuffer.Static" : "VkHardwareBuffer.Stream")
			.Create(fb->GetDevice());

		mStaging = BufferBuilder()
			.Usage(VK_BUFFER_USAGE_TRANSFER_SRC_BIT, VMA_MEMORY_USAGE_CPU_ONLY)
			.Size(bufsize)
			.DebugName(usage == BufferUsageType::Static ? "VkHardwareBuffer.Staging.Static" : "VkHardwareBuffer.Staging.Stream")
			.Create(fb->GetDevice());

		if (data)
		{
			void* dst = mStaging->Map(0, bufsize);
			memcpy(dst, data, size);
			mStaging->Unmap();
		}

		auto commands = fb->GetCommands()->GetTransferCommands();
		commands->copyBuffer(mStaging.get(), mBuffer.get());
		PublishTransferWrite(commands, mBuffer.get(), mBufferType, 0, mBuffer->size);
	}
	else if (usage == BufferUsageType::Persistent)
	{
		mPersistent = true;

		mBuffer = BufferBuilder()
			.Usage(mBufferType, VMA_MEMORY_USAGE_UNKNOWN, VMA_ALLOCATION_CREATE_DEDICATED_MEMORY_BIT | VMA_ALLOCATION_CREATE_MAPPED_BIT)
			.MemoryType(
				VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,
				VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT | VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)
			.Size(bufsize)
			.DebugName("VkHardwareBuffer.Persistent")
			.Create(fb->GetDevice());

		map = mBuffer->Map(0, bufsize);
		if (data)
			memcpy(map, data, size);
	}
	else if (usage == BufferUsageType::Mappable)
	{
		mPersistent = false;

		mBuffer = BufferBuilder()
			.Usage(mBufferType, VMA_MEMORY_USAGE_UNKNOWN, 0)
			.MemoryType(
				VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,
				VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT | VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)
			.Size(bufsize)
			.DebugName("VkHardwareBuffer.Mappable")
			.Create(fb->GetDevice());

		if (data)
		{
			void* dst = mBuffer->Map(0, bufsize);
			memcpy(dst, data, size);
			mBuffer->Unmap();
		}
	}

	buffersize = size;
}

void VkHardwareBuffer::SetSubData(size_t offset, size_t size, const void *data)
{
	size = max(size, (size_t)16); // For supporting zero byte buffers

	if (mStaging)
	{
		void *dst = mStaging->Map(offset, size);
		memcpy(dst, data, size);
		mStaging->Unmap();

		auto commands = fb->GetCommands()->GetTransferCommands();
		commands->copyBuffer(mStaging.get(), mBuffer.get(), offset, offset, size);
		PublishTransferWrite(commands, mBuffer.get(), mBufferType, offset, size);
	}
	else
	{
		void *dst = mBuffer->Map(offset, size);
		memcpy(dst, data, size);
		mBuffer->Unmap();
	}
}

void VkHardwareBuffer::Map()
{
	if (!mPersistent)
		map = mBuffer->Map(0, mBuffer->size);
}

void VkHardwareBuffer::Unmap()
{
	if (!mPersistent)
	{
		mBuffer->Unmap();
		map = nullptr;
	}
}

void *VkHardwareBuffer::Lock(unsigned int size)
{
	size = max(size, (unsigned int)16); // For supporting zero byte buffers

	if (!mBuffer)
	{
		// The model mesh loaders lock multiple non-persistent buffers at the same time. This is not allowed in vulkan.
		// VkDeviceMemory can only be mapped once and multiple non-persistent buffers may come from the same device memory object.
		mStaticUpload.Resize(size);
		map = mStaticUpload.Data();
	}
	else if (!mPersistent)
	{
		map = mBuffer->Map(0, size);
	}
	return map;
}

void VkHardwareBuffer::Unlock()
{
	if (!mBuffer)
	{
		map = nullptr;
		SetData(mStaticUpload.Size(), mStaticUpload.Data(), BufferUsageType::Static);
		mStaticUpload.Clear();
	}
	else if (!mPersistent)
	{
		mBuffer->Unmap();
		map = nullptr;
	}
}
