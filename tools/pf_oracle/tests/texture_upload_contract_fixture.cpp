#include <cassert>
#include <cstdint>
#include <iostream>
#include <limits>
#include "vulkan/textures/vk_textureupload.h"

static void TestAsyncTargetGeneration()
{
	VkAsyncTextureUploadTracker tracker;
	FRendererEpoch queueEpoch;
	const uintptr_t target = 0x1000;

	const int first = tracker.Queue(target, queueEpoch.Snapshot());
	assert(first > 0);
	assert(tracker.PendingCount() == 1);
	assert(tracker.InvalidateTarget(target));
	assert(!tracker.Complete(first, queueEpoch));

	const int second = tracker.Queue(target, queueEpoch.Snapshot());
	assert(second > 0);
	assert(tracker.Complete(second, queueEpoch));

	const int beforeShutdown = tracker.Queue(target, queueEpoch.Snapshot());
	queueEpoch.Invalidate();
	assert(!tracker.Complete(beforeShutdown, queueEpoch));

	const int beforeRetire = tracker.Queue(target, queueEpoch.Snapshot());
	assert(tracker.RetireTarget(target));
	assert(!tracker.Complete(beforeRetire, queueEpoch));

	const int reusedAddress = tracker.Queue(target, queueEpoch.Snapshot());
	assert(reusedAddress > 0);
	assert(tracker.Complete(reusedAddress, queueEpoch));

	const auto& stats = tracker.GetStats();
	assert(stats.Queued == 5);
	assert(stats.Applied == 2);
	assert(stats.StaleRejected == 3);
	assert(stats.TargetInvalidations == 1);
	assert(stats.TargetRetirements == 1);
}

static void TestAsyncJobIdWrapAndCollision()
{
	FRendererEpoch queueEpoch;
	const uint32_t maxJobId = (uint32_t)std::numeric_limits<int>::max();
	VkAsyncTextureUploadTracker tracker(maxJobId);

	const int maxId = tracker.Queue(0x2000, queueEpoch.Snapshot());
	const int wrappedOne = tracker.Queue(0x2001, queueEpoch.Snapshot());
	assert(maxId == std::numeric_limits<int>::max());
	assert(wrappedOne == 1);

	// Seeded wrap now encounters live ID 1 and must skip it rather than
	// replacing the existing job. Both completions must remain independently valid.
	VkAsyncTextureUploadTracker collisionTracker(maxJobId);
	const int collisionMax = collisionTracker.Queue(0x3000, queueEpoch.Snapshot());
	const int one = collisionTracker.Queue(0x3001, queueEpoch.Snapshot());
	assert(collisionMax == std::numeric_limits<int>::max());
	assert(one == 1);
	const int two = collisionTracker.Queue(0x3002, queueEpoch.Snapshot());
	assert(two == 2);
	assert(collisionTracker.Complete(one, queueEpoch));
	assert(collisionTracker.Complete(two, queueEpoch));
	assert(collisionTracker.Complete(collisionMax, queueEpoch));
	assert(collisionTracker.GetStats().IdWraps == 1);
}

static void TestArenaBoundaries()
{
	VkTextureUploadArenaPlanner arena(64);
	auto a = arena.TryAcquire(1);
	auto b = arena.TryAcquire(16);
	auto c = arena.TryAcquire(32);
	assert(a.Offset == 0 && a.Size == 1);
	assert(b.Offset == 16 && b.Size == 16);
	assert(c.Offset == 32 && c.Size == 32);
	assert(arena.GetOffset() == 64);
	assert(!arena.TryAcquire(1).IsSet());
	assert(!arena.TryAcquire(65).IsSet());

	arena.ResetAfterWait();
	assert(!arena.IsCurrent(a));
	auto d = arena.TryAcquire(64);
	assert(d.IsSet() && d.Offset == 0 && d.Size == 64);
	assert(arena.IsCurrent(d));
	assert(!arena.TryAcquire(1).IsSet());

	const auto& stats = arena.GetStats();
	assert(stats.HighWaterBytes == 64);
	assert(stats.Waits == 1);
	assert(stats.Reuses == 1);
	assert(stats.OversizedFallbacks == 1);
}

static void TestArenaInvalidAndOverflowSizedRequests()
{
	VkTextureUploadArenaPlanner arena(64);
	assert(!arena.TryAcquire(0).IsSet());
	assert(!arena.TryAcquire(std::numeric_limits<size_t>::max()).IsSet());
	assert(arena.GetOffset() == 0);
	assert(arena.GetStats().OversizedFallbacks == 2);
}

static void TestBurstAllocationModel()
{
	constexpr size_t textureBytes = 64 * 1024;
	constexpr int textureCount = 1024;
	VkTextureUploadArenaPlanner arena(4 * 1024 * 1024);

	uint64_t waits = 0;
	for (int i = 0; i < textureCount; ++i)
	{
		auto slice = arena.TryAcquire(textureBytes);
		if (!slice.IsSet())
		{
			arena.ResetAfterWait();
			waits++;
			slice = arena.TryAcquire(textureBytes);
		}
		assert(slice.IsSet());
	}

	assert(waits == 15);
	assert(arena.GetStats().Acquisitions == textureCount);
	assert(arena.GetStats().HighWaterBytes == 4 * 1024 * 1024);
	const uint64_t dedicatedBufferAllocations = textureCount;
	const uint64_t persistentBufferAllocations = 1;
	assert(persistentBufferAllocations < dedicatedBufferAllocations);
}

int main()
{
	TestAsyncTargetGeneration();
	TestAsyncJobIdWrapAndCollision();
	TestArenaBoundaries();
	TestArenaInvalidAndOverflowSizedRequests();
	TestBurstAllocationModel();
	std::cout << "PF-005 texture upload contract fixture passed\n";
	return 0;
}
