#include "vulkan/textures/vk_texture_upload_contract.h"

#include <cassert>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <vector>

static std::size_t Choose(const std::vector<std::size_t>& candidates, std::size_t requested)
{
	std::size_t best = std::numeric_limits<std::size_t>::max();
	for (auto candidate : candidates)
	{
		if (VkTexturePreferStagingCandidate(requested, candidate, best))
			best = candidate;
	}
	return best;
}

int main()
{
	FRendererEpoch manager;
	FRendererEpoch target;

	VkTextureUploadTicket ticket;
	ticket.Id = 1;
	ticket.ManagerEpoch = manager.Snapshot();
	ticket.TargetEpoch = target.Snapshot();
	assert(ticket.IsSet());
	assert(VkTextureUploadTicketCurrent(ticket, manager, target));

	// Recreating/resetting the target must reject the old completion.
	target.Invalidate();
	assert(!VkTextureUploadTicketCurrent(ticket, manager, target));

	// A new target ticket is still rejected after manager teardown/reset.
	ticket.TargetEpoch = target.Snapshot();
	assert(VkTextureUploadTicketCurrent(ticket, manager, target));
	manager.Invalidate();
	assert(!VkTextureUploadTicketCurrent(ticket, manager, target));

	// Upload IDs never expose zero, including uint64_t rollover.
	assert(VkTextureNextUploadId(0) == 1);
	assert(VkTextureNextUploadId(41) == 42);
	assert(VkTextureNextUploadId(std::numeric_limits<uint64_t>::max()) == 1);

	// Best-fit selection: reject undersized buffers, prefer exact fit, then
	// smallest sufficient fit. This is the production pool's reuse policy.
	assert(Choose({64, 128, 256}, 129) == 256);
	assert(Choose({512, 128, 256}, 256) == 256);
	assert(Choose({64, 128}, 129) == std::numeric_limits<std::size_t>::max());
	assert(Choose({4096, 4096, 8192}, 4096) == 4096);

	// Boundary admission: zero and oversized allocations are never cached;
	// exact remaining budget is accepted, one byte beyond is rejected.
	assert(!VkTextureCanPoolStaging(0, 0));
	assert(!VkTextureCanPoolStaging(VkTextureStagingMaxPooledBuffer + 1, 0));
	assert(VkTextureCanPoolStaging(VkTextureStagingMaxPooledBuffer,
		VkTextureStagingPoolBudget - VkTextureStagingMaxPooledBuffer));
	assert(!VkTextureCanPoolStaging(VkTextureStagingMaxPooledBuffer,
		VkTextureStagingPoolBudget - VkTextureStagingMaxPooledBuffer + 1));

	// A representative repeated-upload model demonstrates the allocation
	// reduction without weakening retirement: only buffers retired after a
	// completed transfer become reuse candidates.
	constexpr int rounds = 128;
	constexpr int inFlightWidth = 8;
	int baselineAllocations = 0;
	int pooledAllocations = 0;
	std::vector<std::size_t> retired;
	for (int round = 0; round < rounds; ++round)
	{
		for (int i = 0; i < inFlightWidth; ++i)
		{
			baselineAllocations++;
			auto chosen = Choose(retired, 1024 * 1024);
			if (chosen == std::numeric_limits<std::size_t>::max())
				pooledAllocations++;
			else
				retired.erase(retired.begin());
		}

		// Model one completed transfer batch. Nothing is reusable before this
		// retirement point; afterwards all eight buffers may be reused.
		retired.assign(inFlightWidth, 1024 * 1024);
	}
	assert(baselineAllocations == rounds * inFlightWidth);
	assert(pooledAllocations == inFlightWidth);
	assert(pooledAllocations * 100 / baselineAllocations < 2);

	return 0;
}
