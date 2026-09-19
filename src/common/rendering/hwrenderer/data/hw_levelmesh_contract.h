#pragma once

#include "hw_resourcegeneration.h"
#include <algorithm>
#include <cstdint>
#include <vector>

// PF-004: shared allocation/dirty-range contract for persistent LevelMesh buffers.
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
};

class MeshBufferAllocator
{
public:
	void Reset(int size)
	{
		TotalSize = std::max(size, 0);
		Unused.clear();
		if (TotalSize > 0)
			Unused.push_back({ 0, TotalSize });
		Generations.Reset();
		Stats.Resets++;
	}

	// Preserve the inherited growth policy. PF-018 owns allocator growth/perf.
	void Grow(int amount)
	{
		if (amount <= 0)
			return;
		amount = (amount + TotalSize) * 2;
		if (!Unused.empty() && Unused.back().End == TotalSize)
		{
			TotalSize += amount;
			Unused.back().End = TotalSize;
		}
		else
		{
			Unused.push_back({ TotalSize, TotalSize + amount });
			TotalSize += amount;
		}
		Stats.Grows++;
	}

	int GetTotalSize() const { return TotalSize; }

	int GetUsedSize() const
	{
		int used = TotalSize;
		for (const auto& range : Unused)
			used -= range.Count();
		return used;
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

		for (auto it = Unused.begin(); it != Unused.end(); ++it)
		{
			if (it->Count() < count)
				continue;

			const int position = it->Start;
			it->Start += count;
			if (it->Start == it->End)
				Unused.erase(it);

			Generations.Activate(position, static_cast<uint32_t>(count));
			Stats.Allocations++;
			return position;
		}

		return -1;
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
			left->End = right->End;
			Unused.erase(right);
		}
		else if (mergeLeft)
		{
			(right - 1)->End = range.End;
		}
		else if (mergeRight)
		{
			right->Start = range.Start;
		}
		else
		{
			Unused.insert(right, range);
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
	int TotalSize = 0;
	std::vector<MeshBufferRange> Unused;
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
