#pragma once

#include "hw_resourcegeneration.h"
#include <algorithm>
#include <cstdint>
#include <limits>
#include <set>
#include <vector>

// PF-004: shared allocation/dirty-range contract for persistent LevelMesh buffers.
// PF-018: allocator lookup/growth instrumentation and deterministic size index.
// This header deliberately has no renderer/backend dependencies so the safety
// model can be exercised by the deterministic PF fixture.
struct MeshBufferRange
{
	int Start = 0;
	int End = 0;

	int Count() const { return End - Start; }
};

inline int MeshBufferChunkStart(const MeshBufferRange& range, int chunkSize)
{
	if (chunkSize <= 0 || range.End <= range.Start || range.Start < 0)
		return 0;
	return range.Start / chunkSize;
}

// End is exclusive. Rounding it up is essential: a dirty range wholly inside
// one BLAS partition must still rebuild that partition.
inline int MeshBufferChunkEndExclusive(const MeshBufferRange& range, int chunkSize)
{
	if (chunkSize <= 0 || range.End <= range.Start || range.Start < 0)
		return 0;
	return range.End / chunkSize + ((range.End % chunkSize) != 0 ? 1 : 0);
}

struct MeshBufferAllocatorStats
{
	uint64_t Allocations = 0;
	uint64_t Frees = 0;
	uint64_t Grows = 0;
	uint64_t Resets = 0;
	uint64_t InvalidAllocations = 0;
	uint64_t InvalidFrees = 0;
	uint64_t AllocationSearches = 0;
	uint64_t AllocationCandidates = 0;
	uint64_t GrownElements = 0;
	uint64_t PeakTotalSize = 0;
};

class MeshBufferAllocator
{
public:
	void Reset(int size)
	{
		TotalSize = std::max(size, 0);
		Unused.clear();
		FreeBySize.clear();
		if (TotalSize > 0)
		{
			Unused.push_back({ 0, TotalSize });
			IndexFreeRange(Unused.back());
		}
		Generations.Reset();
		Stats.Resets++;
		Stats.PeakTotalSize = std::max<uint64_t>(Stats.PeakTotalSize, static_cast<uint64_t>(TotalSize));
	}

	// PF-018: bounded geometric growth. The caller passes the minimum number of
	// additional elements needed after an allocation miss. Grow by at least that
	// amount, otherwise by 50% of current capacity. Existing live ranges never
	// move and integer overflow is rejected by clamping to INT_MAX.
	void Grow(int amount)
	{
		if (amount <= 0 || TotalSize >= std::numeric_limits<int>::max())
			return;

		const int64_t geometric = std::max<int64_t>(1, static_cast<int64_t>(TotalSize) / 2);
		int64_t growth = std::max<int64_t>(amount, geometric);
		growth = std::min<int64_t>(growth, static_cast<int64_t>(std::numeric_limits<int>::max()) - TotalSize);
		if (growth <= 0)
			return;

		const int oldSize = TotalSize;
		const int newSize = static_cast<int>(static_cast<int64_t>(TotalSize) + growth);
		if (!Unused.empty() && Unused.back().End == oldSize)
		{
			UnindexFreeRange(Unused.back());
			Unused.back().End = newSize;
			IndexFreeRange(Unused.back());
		}
		else
		{
			Unused.push_back({ oldSize, newSize });
			IndexFreeRange(Unused.back());
		}
		TotalSize = newSize;
		Stats.Grows++;
		Stats.GrownElements += static_cast<uint64_t>(growth);
		Stats.PeakTotalSize = std::max<uint64_t>(Stats.PeakTotalSize, static_cast<uint64_t>(TotalSize));
	}

	int GetTotalSize() const { return TotalSize; }

	int GetUsedSize() const
	{
		return TotalSize - GetFreeSize();
	}

	int GetFreeSize() const
	{
		int free = 0;
		for (const auto& range : Unused)
			free += range.Count();
		return free;
	}

	int GetLargestFreeRange() const
	{
		return FreeBySize.empty() ? 0 : FreeBySize.rbegin()->first;
	}

	int Alloc(int count)
	{
		if (count < 0)
		{
			Stats.InvalidAllocations++;
			return -1;
		}
		// Empty light lists are valid and consume no persistent identity.
		if (count == 0)
			return 0;

		Stats.AllocationSearches++;
		const auto fit = FreeBySize.lower_bound({ count, std::numeric_limits<int>::min() });
		if (fit == FreeBySize.end())
			return -1;
		Stats.AllocationCandidates++;

		const int position = fit->second;
		auto it = std::lower_bound(Unused.begin(), Unused.end(), position,
			[](const MeshBufferRange& range, int start) { return range.Start < start; });
		if (it == Unused.end() || it->Start != position || it->Count() < count)
		{
			// Internal index corruption must fail closed rather than returning an
			// overlapping allocation. This path should be unreachable.
			Stats.InvalidAllocations++;
			return -1;
		}

		const MeshBufferRange oldRange = *it;
		UnindexFreeRange(oldRange);
		it->Start += count;
		if (it->Start == it->End)
			Unused.erase(it);
		else
			IndexFreeRange(*it);

		Generations.Activate(position, static_cast<uint32_t>(count));
		Stats.Allocations++;
		return position;
	}

	bool CanFree(int position, int count) const
	{
		if (count == 0)
			return position >= 0 && position <= TotalSize;
		if (position < 0 || count < 0 || position > TotalSize || count > TotalSize - position)
			return false;

		const auto current = Generations.Current(position);
		if (!current.IsSet() || current.Span != static_cast<uint32_t>(count))
			return false;

		const MeshBufferRange range { position, position + count };
		auto right = std::lower_bound(Unused.begin(), Unused.end(), range,
			[](const auto& a, const auto& b) { return a.Start < b.Start; });
		if (right != Unused.begin() && (right - 1)->End > range.Start)
			return false;
		return right == Unused.end() || right->Start >= range.End;
	}

	bool Free(int position, int count)
	{
		if (count == 0)
			return CanFree(position, count);
		if (!CanFree(position, count))
		{
			Stats.InvalidFrees++;
			return false;
		}
		if (!Generations.Retire(position))
		{
			Stats.InvalidFrees++;
			return false;
		}

		const MeshBufferRange range { position, position + count };
		auto right = std::lower_bound(Unused.begin(), Unused.end(), range,
			[](const auto& a, const auto& b) { return a.Start < b.Start; });
		const bool mergeLeft = right != Unused.begin() && (right - 1)->End == range.Start;
		const bool mergeRight = right != Unused.end() && right->Start == range.End;

		if (mergeLeft && mergeRight)
		{
			auto left = right - 1;
			UnindexFreeRange(*left);
			UnindexFreeRange(*right);
			left->End = right->End;
			Unused.erase(right);
			IndexFreeRange(*left);
		}
		else if (mergeLeft)
		{
			auto left = right - 1;
			UnindexFreeRange(*left);
			left->End = range.End;
			IndexFreeRange(*left);
		}
		else if (mergeRight)
		{
			UnindexFreeRange(*right);
			right->Start = range.Start;
			IndexFreeRange(*right);
		}
		else
		{
			right = Unused.insert(right, range);
			IndexFreeRange(*right);
		}

		Stats.Frees++;
		return true;
	}

	FRendererResourceIdentity CurrentIdentity(int position) const { return Generations.Current(position); }
	bool ValidateIdentity(const FRendererResourceIdentity& identity) { return Generations.Validate(identity); }
	const FRendererLifetimeStats& GetLifetimeStats() const { return Generations.GetStats(); }
	const MeshBufferAllocatorStats& GetStats() const { return Stats; }
	const std::vector<MeshBufferRange>& GetFreeRanges() const { return Unused; }

private:
	void IndexFreeRange(const MeshBufferRange& range)
	{
		if (range.Count() > 0)
			FreeBySize.insert({ range.Count(), range.Start });
	}

	void UnindexFreeRange(const MeshBufferRange& range)
	{
		if (range.Count() > 0)
			FreeBySize.erase({ range.Count(), range.Start });
	}

	int TotalSize = 0;
	std::vector<MeshBufferRange> Unused;
	std::set<std::pair<int, int>> FreeBySize;
	FRendererResourceGenerationTable Generations;
	MeshBufferAllocatorStats Stats;
};

enum class LevelMeshMutationDomain : uint32_t
{
	None = 0,
	Geometry = 1u << 0,
	Surface = 1u << 1,
	Lights = 1u << 2,
	Query = 1u << 3,
	Portals = 1u << 4,
	LightmapProbe = 1u << 5,
	All = Geometry | Surface | Lights | Query | Portals | LightmapProbe
};

inline LevelMeshMutationDomain operator|(LevelMeshMutationDomain a, LevelMeshMutationDomain b)
{
	return static_cast<LevelMeshMutationDomain>(static_cast<uint32_t>(a) | static_cast<uint32_t>(b));
}

inline bool LevelMeshMutationIncludes(LevelMeshMutationDomain mask, LevelMeshMutationDomain domain)
{
	return (static_cast<uint32_t>(mask) & static_cast<uint32_t>(domain)) != 0;
}

struct LevelMeshMutationEpochSnapshot
{
	uint64_t Geometry = 0;
	uint64_t Surface = 0;
	uint64_t Lights = 0;
	uint64_t Query = 0;
	uint64_t Portals = 0;
	uint64_t LightmapProbe = 0;
	uint64_t Resets = 0;
};

class LevelMeshMutationEpochs
{
public:
	void Reset()
	{
		Epochs.Resets++;
		Mark(LevelMeshMutationDomain::All);
	}

	void Mark(LevelMeshMutationDomain mask)
	{
		if (LevelMeshMutationIncludes(mask, LevelMeshMutationDomain::Geometry)) Epochs.Geometry++;
		if (LevelMeshMutationIncludes(mask, LevelMeshMutationDomain::Surface)) Epochs.Surface++;
		if (LevelMeshMutationIncludes(mask, LevelMeshMutationDomain::Lights)) Epochs.Lights++;
		if (LevelMeshMutationIncludes(mask, LevelMeshMutationDomain::Query)) Epochs.Query++;
		if (LevelMeshMutationIncludes(mask, LevelMeshMutationDomain::Portals)) Epochs.Portals++;
		if (LevelMeshMutationIncludes(mask, LevelMeshMutationDomain::LightmapProbe)) Epochs.LightmapProbe++;
	}

	const LevelMeshMutationEpochSnapshot& Snapshot() const { return Epochs; }

private:
	LevelMeshMutationEpochSnapshot Epochs;
};
