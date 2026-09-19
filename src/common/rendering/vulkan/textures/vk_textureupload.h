#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <unordered_map>
#include <vector>

#include "hwrenderer/data/hw_resourcegeneration.h"

struct VkAsyncTextureUploadStats
{
	uint64_t Queued = 0;
	uint64_t Applied = 0;
	uint64_t StaleRejected = 0;
	uint64_t TargetInvalidations = 0;
	uint64_t TargetRetirements = 0;
	uint64_t InvalidTargets = 0;
	uint64_t IdWraps = 0;
	uint64_t IdCollisions = 0;
};

class VkAsyncTextureUploadTracker
{
public:
	explicit VkAsyncTextureUploadTracker(uint32_t initialJobId = 1)
		: NextJobId(NormalizeJobId(initialJobId))
	{
	}

	int Queue(uintptr_t targetKey, FRendererEpochToken queueEpoch)
	{
		if (!queueEpoch.IsSet())
		{
			Stats.InvalidTargets++;
			return 0;
		}

		const int slot = EnsureTarget(targetKey);
		if (slot < 0)
		{
			Stats.InvalidTargets++;
			return 0;
		}

		const int id = AllocateJobId();
		if (id == 0)
		{
			Stats.InvalidTargets++;
			return 0;
		}

		Jobs[id] = { Targets.Current(slot), queueEpoch };
		Stats.Queued++;
		return id;
	}

	bool Complete(int id, FRendererEpoch& queueEpoch)
	{
		auto it = Jobs.find(id);
		if (it == Jobs.end())
		{
			Stats.StaleRejected++;
			return false;
		}

		const Job job = it->second;
		Jobs.erase(it);
		const bool queueCurrent = queueEpoch.Validate(job.QueueEpoch);
		const bool targetCurrent = Targets.Validate(job.Target);
		if (!queueCurrent || !targetCurrent)
		{
			Stats.StaleRejected++;
			return false;
		}

		Stats.Applied++;
		return true;
	}

	bool InvalidateTarget(uintptr_t targetKey)
	{
		auto it = TargetSlots.find(targetKey);
		if (it == TargetSlots.end())
			return false;

		const int slot = it->second;
		if (!Targets.Retire(slot))
			return false;
		Targets.Activate(slot);
		Stats.TargetInvalidations++;
		return true;
	}

	bool RetireTarget(uintptr_t targetKey)
	{
		auto it = TargetSlots.find(targetKey);
		if (it == TargetSlots.end())
			return false;

		const int slot = it->second;
		if (!Targets.Retire(slot))
			return false;
		TargetSlots.erase(it);
		FreeTargetSlots.push_back(slot);
		Stats.TargetRetirements++;
		return true;
	}

	bool HasTarget(uintptr_t targetKey) const
	{
		return TargetSlots.find(targetKey) != TargetSlots.end();
	}

	size_t PendingCount() const { return Jobs.size(); }
	const VkAsyncTextureUploadStats& GetStats() const { return Stats; }
	const FRendererLifetimeStats& GetLifetimeStats() const { return Targets.GetStats(); }

private:
	struct Job
	{
		FRendererResourceIdentity Target;
		FRendererEpochToken QueueEpoch;
	};

	static uint32_t NormalizeJobId(uint32_t id)
	{
		const uint32_t maxJobId = (uint32_t)std::numeric_limits<int>::max();
		return id == 0 || id > maxJobId ? 1 : id;
	}

	int AllocateJobId()
	{
		const uint32_t maxJobId = (uint32_t)std::numeric_limits<int>::max();
		for (uint64_t attempts = 0; attempts < maxJobId; attempts++)
		{
			const uint32_t candidate = NextJobId;
			if (NextJobId == maxJobId)
			{
				NextJobId = 1;
				Stats.IdWraps++;
			}
			else
			{
				NextJobId++;
			}

			const int id = (int)candidate;
			if (Jobs.find(id) == Jobs.end())
				return id;
			Stats.IdCollisions++;
		}
		return 0;
	}

	int EnsureTarget(uintptr_t targetKey)
	{
		if (targetKey == 0)
			return -1;

		auto existing = TargetSlots.find(targetKey);
		if (existing != TargetSlots.end())
			return existing->second;

		int slot;
		if (!FreeTargetSlots.empty())
		{
			slot = FreeTargetSlots.back();
			FreeTargetSlots.pop_back();
		}
		else
		{
			if (NextTargetSlot == std::numeric_limits<int>::max())
				return -1;
			slot = NextTargetSlot++;
		}

		TargetSlots[targetKey] = slot;
		Targets.Activate(slot);
		return slot;
	}

	uint32_t NextJobId = 1;
	int NextTargetSlot = 0;
	std::unordered_map<uintptr_t, int> TargetSlots;
	std::vector<int> FreeTargetSlots;
	std::unordered_map<int, Job> Jobs;
	FRendererResourceGenerationTable Targets;
	VkAsyncTextureUploadStats Stats;
};

struct VkTextureUploadArenaStats
{
	uint64_t Requests = 0;
	uint64_t Acquisitions = 0;
	uint64_t OversizedFallbacks = 0;
	uint64_t Waits = 0;
	uint64_t Resets = 0;
	uint64_t Reuses = 0;
	size_t CurrentBytes = 0;
	size_t HighWaterBytes = 0;
};

struct VkTextureUploadSlice
{
	size_t Offset = 0;
	size_t Size = 0;
	uint32_t Epoch = 0;

	bool IsSet() const { return Size != 0 && Epoch != 0; }
};

class VkTextureUploadArenaPlanner
{
public:
	static constexpr size_t DefaultCapacity = 64u * 1024u * 1024u;
	static constexpr size_t Alignment = 16u;

	explicit VkTextureUploadArenaPlanner(size_t capacity = DefaultCapacity) : Capacity(capacity) {}

	VkTextureUploadSlice TryAcquire(size_t bytes)
	{
		Stats.Requests++;
		if (bytes == 0 || bytes > Capacity)
		{
			Stats.OversizedFallbacks++;
			return {};
		}

		const size_t aligned = Align(bytes);
		if (aligned > Capacity || Offset > Capacity - aligned)
			return {};

		VkTextureUploadSlice slice { Offset, bytes, Epoch };
		Offset += aligned;
		Stats.Acquisitions++;
		Stats.CurrentBytes = Offset;
		Stats.HighWaterBytes = std::max(Stats.HighWaterBytes, Offset);
		return slice;
	}

	void ResetAfterWait()
	{
		if (Offset != 0)
			Stats.Reuses++;
		Offset = 0;
		Stats.CurrentBytes = 0;
		Epoch = NextEpoch(Epoch);
		Stats.Waits++;
		Stats.Resets++;
	}

	bool IsCurrent(const VkTextureUploadSlice& slice) const
	{
		return slice.IsSet() && slice.Epoch == Epoch && slice.Offset <= Capacity && slice.Size <= Capacity - slice.Offset;
	}

	size_t GetCapacity() const { return Capacity; }
	size_t GetOffset() const { return Offset; }
	const VkTextureUploadArenaStats& GetStats() const { return Stats; }

private:
	static size_t Align(size_t value)
	{
		if (value > std::numeric_limits<size_t>::max() - (Alignment - 1))
			return std::numeric_limits<size_t>::max();
		return (value + Alignment - 1) & ~(Alignment - 1);
	}

	static uint32_t NextEpoch(uint32_t value)
	{
		value++;
		return value == 0 ? 1 : value;
	}

	size_t Capacity = 0;
	size_t Offset = 0;
	uint32_t Epoch = 1;
	VkTextureUploadArenaStats Stats;
};
