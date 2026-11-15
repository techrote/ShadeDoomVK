#pragma once

#include <atomic>
#include <cstdint>

// The production reservation operation is also executable without a Vulkan
// device. A frame owns its buffer until the GPU fence; only BeginFrame resets
// next, after the previous frame is complete. Worker joins publish the writes.
namespace VkActorShadowPolicy
{
inline int Reserve(std::atomic<int>& next, int count, int capacity,
	int maxPerRange, std::atomic<uint64_t>& overflowCasters)
{
	if (count <= 0 || capacity <= 0 || maxPerRange <= 0 || count > maxPerRange)
		return -1;
	int start = next.load(std::memory_order_relaxed);
	for (;;)
	{
		// Subtract only after checking the positive range; no signed overflow,
		// wrapping, counter advancement or overwrite on a rejected reservation.
		if (count > capacity || start < 0 || start > capacity - count)
		{
			overflowCasters.fetch_add(uint64_t(count), std::memory_order_relaxed);
			return -1;
		}
		if (next.compare_exchange_weak(start, start + count,
			std::memory_order_relaxed, std::memory_order_relaxed))
			return start;
	}
}
}
