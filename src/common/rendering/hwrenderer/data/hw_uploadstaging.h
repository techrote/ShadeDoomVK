#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <limits>

struct FRendererUploadStagingSlice
{
	std::size_t Offset = 0;
	std::size_t Size = 0;
	bool RequiresWait = false;
	bool Dedicated = false;

	bool IsSet() const { return Size != 0; }
};

struct FRendererUploadStagingStats
{
	uint64_t Requests = 0;
	uint64_t ArenaSlices = 0;
	uint64_t Reuses = 0;
	uint64_t WrapWaits = 0;
	uint64_t DedicatedRequests = 0;
	uint64_t InvalidRequests = 0;
	uint64_t BytesRequested = 0;
	std::size_t HighWater = 0;
};

class FRendererUploadStagingPlanner
{
public:
	explicit FRendererUploadStagingPlanner(std::size_t capacity = 0) : Capacity(capacity) {}

	FRendererUploadStagingSlice Acquire(std::size_t size, std::size_t alignment = 4)
	{
		Stats.Requests++;
		if (size == 0 || alignment == 0)
		{
			Stats.InvalidRequests++;
			return {};
		}

		Stats.BytesRequested += static_cast<uint64_t>(size);
		if (Capacity == 0 || size > Capacity)
		{
			Stats.DedicatedRequests++;
			return { 0, size, false, true };
		}

		std::size_t aligned = 0;
		bool wraps = !AlignUp(Cursor, alignment, aligned) || aligned > Capacity || size > Capacity - aligned;
		if (wraps)
			aligned = 0;

		FRendererUploadStagingSlice slice;
		slice.Offset = aligned;
		slice.Size = size;
		slice.RequiresWait = wraps && HasIssuedArenaSlice;
		Cursor = aligned + size;

		Stats.ArenaSlices++;
		if (HasIssuedArenaSlice)
			Stats.Reuses++;
		else
			HasIssuedArenaSlice = true;
		if (slice.RequiresWait)
			Stats.WrapWaits++;
		Stats.HighWater = std::max(Stats.HighWater, Cursor);
		return slice;
	}

	std::size_t GetCapacity() const { return Capacity; }
	std::size_t GetCursor() const { return Cursor; }
	const FRendererUploadStagingStats& GetStats() const { return Stats; }

private:
	static bool AlignUp(std::size_t value, std::size_t alignment, std::size_t& result)
	{
		if (alignment == 0)
			return false;
		const std::size_t remainder = value % alignment;
		const std::size_t padding = remainder == 0 ? 0 : alignment - remainder;
		if (value > std::numeric_limits<std::size_t>::max() - padding)
			return false;
		result = value + padding;
		return true;
	}

	std::size_t Capacity = 0;
	std::size_t Cursor = 0;
	bool HasIssuedArenaSlice = false;
	FRendererUploadStagingStats Stats;
};
