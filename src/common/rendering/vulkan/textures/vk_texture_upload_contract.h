#pragma once

#include "hwrenderer/data/hw_resourcegeneration.h"

#include <cstddef>
#include <cstdint>
#include <limits>

struct VkTextureUploadTicket
{
	uint64_t Id = 0;
	FRendererEpochToken ManagerEpoch;
	FRendererEpochToken TargetEpoch;

	bool IsSet() const
	{
		return Id != 0 && ManagerEpoch.IsSet() && TargetEpoch.IsSet();
	}
};

struct VkTextureUploadStats
{
	uint64_t JobsQueued = 0;
	uint64_t JobsCompleted = 0;
	uint64_t StaleJobsRejected = 0;
	uint64_t StagingAllocations = 0;
	uint64_t StagingReuses = 0;
	uint64_t StagingDrops = 0;
	uint64_t TransferWaits = 0;
	std::size_t PooledBytes = 0;
	std::size_t PooledHighWater = 0;
};

// Reusable upload buffers are retained only after the transfer fence that used
// them has completed. Keep the cache bounded so burst uploads cannot turn the
// pool into an unbounded second copy of texture memory.
constexpr std::size_t VkTextureStagingPoolBudget = 64u * 1024u * 1024u;
constexpr std::size_t VkTextureStagingMaxPooledBuffer = 16u * 1024u * 1024u;

inline bool VkTextureCanPoolStaging(std::size_t bufferSize, std::size_t pooledBytes)
{
	if (bufferSize == 0 || bufferSize > VkTextureStagingMaxPooledBuffer)
		return false;
	return pooledBytes <= VkTextureStagingPoolBudget &&
		bufferSize <= VkTextureStagingPoolBudget - pooledBytes;
}

inline bool VkTexturePreferStagingCandidate(std::size_t requested, std::size_t candidate, std::size_t best)
{
	return candidate >= requested && candidate < best;
}

inline uint64_t VkTextureNextUploadId(uint64_t current)
{
	current++;
	return current == 0 ? 1 : current;
}

inline bool VkTextureUploadTicketCurrent(const VkTextureUploadTicket& ticket,
	const FRendererEpoch& managerEpoch, const FRendererEpoch& targetEpoch)
{
	return ticket.IsSet() && managerEpoch.IsCurrent(ticket.ManagerEpoch) && targetEpoch.IsCurrent(ticket.TargetEpoch);
}
