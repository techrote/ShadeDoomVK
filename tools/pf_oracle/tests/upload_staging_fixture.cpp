#include "hw_uploadstaging.h"

#include <cassert>
#include <cstddef>

int main()
{
	FRendererUploadStagingPlanner planner(32);

	auto a = planner.Acquire(8, 4);
	assert(a.IsSet() && !a.Dedicated && !a.RequiresWait && a.Offset == 0 && a.Size == 8);

	auto b = planner.Acquire(7, 4);
	assert(b.IsSet() && !b.Dedicated && !b.RequiresWait && b.Offset == 8 && b.Size == 7);

	auto c = planner.Acquire(17, 1);
	assert(c.IsSet() && !c.Dedicated && !c.RequiresWait && c.Offset == 15 && c.Size == 17);
	assert(planner.GetCursor() == 32);

	auto d = planner.Acquire(4, 4);
	assert(d.IsSet() && !d.Dedicated && d.RequiresWait && d.Offset == 0 && d.Size == 4);

	auto e = planner.Acquire(5, 8);
	assert(e.IsSet() && !e.Dedicated && !e.RequiresWait && e.Offset == 8 && e.Size == 5);

	const std::size_t cursorBeforeDedicated = planner.GetCursor();
	auto oversized = planner.Acquire(33, 4);
	assert(oversized.IsSet() && oversized.Dedicated && !oversized.RequiresWait && oversized.Offset == 0);
	assert(planner.GetCursor() == cursorBeforeDedicated);

	auto zero = planner.Acquire(0, 4);
	auto badAlignment = planner.Acquire(4, 0);
	assert(!zero.IsSet() && !badAlignment.IsSet());

	const auto& stats = planner.GetStats();
	assert(stats.Requests == 8);
	assert(stats.ArenaSlices == 5);
	assert(stats.Reuses == 4);
	assert(stats.WrapWaits == 1);
	assert(stats.DedicatedRequests == 1);
	assert(stats.InvalidRequests == 2);
	assert(stats.HighWater == 32);

	// Representative 64 MiB arena workload: 1024 64-KiB uploads fit exactly
	// into one persistent buffer with no reuse wait; the next slice must wait
	// before reusing byte zero. The legacy path needed one Vulkan staging buffer
	// allocation per upload.
	constexpr std::size_t arenaSize = 64u * 1024u * 1024u;
	constexpr std::size_t uploadSize = 64u * 1024u;
	FRendererUploadStagingPlanner burst(arenaSize);
	for (int i = 0; i < 1024; ++i)
	{
		auto slice = burst.Acquire(uploadSize, 4);
		assert(slice.IsSet() && !slice.Dedicated && !slice.RequiresWait);
	}
	assert(burst.GetCursor() == arenaSize);
	assert(burst.GetStats().HighWater == arenaSize);
	assert(burst.GetStats().WrapWaits == 0);
	auto wrap = burst.Acquire(uploadSize, 4);
	assert(wrap.RequiresWait && wrap.Offset == 0);
	assert(burst.GetStats().WrapWaits == 1);
	assert(burst.GetStats().ArenaSlices == 1025);

	// Every returned arena range remains in bounds under many wraps and odd
	// request sizes/alignment gaps.
	FRendererUploadStagingPlanner stress(257);
	for (std::size_t i = 1; i <= 10000; ++i)
	{
		const std::size_t size = 1 + (i % 127);
		const std::size_t alignment = 1 + (i % 17);
		auto slice = stress.Acquire(size, alignment);
		assert(slice.IsSet() && !slice.Dedicated);
		assert(slice.Offset <= stress.GetCapacity());
		assert(slice.Size <= stress.GetCapacity() - slice.Offset);
	}
	assert(stress.GetStats().HighWater <= stress.GetCapacity());
	assert(stress.GetStats().WrapWaits > 0);

	return 0;
}
