#pragma once

#include <algorithm>
#include <cstdint>
#include <limits>
#include <vector>

#include "hwrenderer/data/hw_resourcegeneration.h"

namespace VkBindlessLayout
{
	static constexpr int FixedSlots = 3;
	static constexpr int MaxLightmapPages = 128;
	static constexpr int LightmapDescriptorsPerPage = 2;
	static constexpr int LightmapStart = FixedSlots;
	static constexpr int DynamicStart = LightmapStart + MaxLightmapPages * LightmapDescriptorsPerPage;
	static constexpr int MinimumCapacity = DynamicStart + 1;

	// Fixed set + the larger of the LevelMesh/RSBuffer scene sets visible to a
	// single graphics shader stage. This is reserved when checking the aggregate
	// update-after-bind resource limit.
	static constexpr uint32_t SceneNonBindlessResourcesPerStage = 15;
	static constexpr uint32_t SceneNonBindlessCombinedSamplersPerStage = 2;
}

enum class VkBindlessLimitSource
{
	None,
	PerStageSamplers,
	PerStageSampledImages,
	DescriptorSetSamplers,
	DescriptorSetSampledImages,
	PerStageResources,
	UpdateAfterBindPoolDescriptors
};

inline const char* VkBindlessLimitSourceName(VkBindlessLimitSource source)
{
	switch (source)
	{
	case VkBindlessLimitSource::PerStageSamplers: return "per-stage combined samplers";
	case VkBindlessLimitSource::PerStageSampledImages: return "per-stage sampled images";
	case VkBindlessLimitSource::DescriptorSetSamplers: return "pipeline-layout samplers";
	case VkBindlessLimitSource::DescriptorSetSampledImages: return "pipeline-layout sampled images";
	case VkBindlessLimitSource::PerStageResources: return "per-stage update-after-bind resources";
	case VkBindlessLimitSource::UpdateAfterBindPoolDescriptors: return "update-after-bind descriptors in all pools";
	default: return "none";
	}
}

struct VkBindlessDeviceLimits
{
	uint32_t MaxPerStageDescriptorSamplers = 0;
	uint32_t MaxPerStageDescriptorSampledImages = 0;
	uint32_t MaxDescriptorSetSamplers = 0;
	uint32_t MaxDescriptorSetSampledImages = 0;

	uint32_t MaxPerStageDescriptorUpdateAfterBindSamplers = 0;
	uint32_t MaxPerStageDescriptorUpdateAfterBindSampledImages = 0;
	uint32_t MaxDescriptorSetUpdateAfterBindSamplers = 0;
	uint32_t MaxDescriptorSetUpdateAfterBindSampledImages = 0;
	uint32_t MaxPerStageUpdateAfterBindResources = 0;
	uint32_t MaxUpdateAfterBindDescriptorsInAllPools = 0;
};

enum class VkBindlessCapacityError
{
	None,
	RequestedBelowMinimum,
	DeviceBelowMinimum
};

struct VkBindlessCapacityPlan
{
	int Requested = 0;
	int DeviceLimit = 0;
	int Effective = 0;
	VkBindlessLimitSource DeviceLimitSource = VkBindlessLimitSource::None;
	VkBindlessCapacityError Error = VkBindlessCapacityError::None;

	bool IsValid() const { return Error == VkBindlessCapacityError::None; }
};

inline uint32_t VkBindlessLimitMinusReserve(uint32_t limit, uint32_t reserve)
{
	return limit > reserve ? limit - reserve : 0;
}

inline VkBindlessCapacityPlan VkPlanBindlessCapacity(int requested, const VkBindlessDeviceLimits& limits)
{
	VkBindlessCapacityPlan plan;
	plan.Requested = requested;

	if (requested < VkBindlessLayout::MinimumCapacity)
	{
		plan.Error = VkBindlessCapacityError::RequestedBelowMinimum;
		return plan;
	}

	struct Candidate
	{
		uint32_t Value;
		VkBindlessLimitSource Source;
	};

	const uint32_t stageSamplers = std::max(
		limits.MaxPerStageDescriptorSamplers,
		limits.MaxPerStageDescriptorUpdateAfterBindSamplers);
	const uint32_t stageSampledImages = std::max(
		limits.MaxPerStageDescriptorSampledImages,
		limits.MaxPerStageDescriptorUpdateAfterBindSampledImages);
	const uint32_t setSamplers = std::max(
		limits.MaxDescriptorSetSamplers,
		limits.MaxDescriptorSetUpdateAfterBindSamplers);
	const uint32_t setSampledImages = std::max(
		limits.MaxDescriptorSetSampledImages,
		limits.MaxDescriptorSetUpdateAfterBindSampledImages);

	Candidate candidates[] =
	{
		{ VkBindlessLimitMinusReserve(stageSamplers, VkBindlessLayout::SceneNonBindlessCombinedSamplersPerStage), VkBindlessLimitSource::PerStageSamplers },
		{ VkBindlessLimitMinusReserve(stageSampledImages, VkBindlessLayout::SceneNonBindlessCombinedSamplersPerStage), VkBindlessLimitSource::PerStageSampledImages },
		{ VkBindlessLimitMinusReserve(setSamplers, VkBindlessLayout::SceneNonBindlessCombinedSamplersPerStage), VkBindlessLimitSource::DescriptorSetSamplers },
		{ VkBindlessLimitMinusReserve(setSampledImages, VkBindlessLayout::SceneNonBindlessCombinedSamplersPerStage), VkBindlessLimitSource::DescriptorSetSampledImages },
		{ VkBindlessLimitMinusReserve(limits.MaxPerStageUpdateAfterBindResources, VkBindlessLayout::SceneNonBindlessResourcesPerStage), VkBindlessLimitSource::PerStageResources },
		{ limits.MaxUpdateAfterBindDescriptorsInAllPools, VkBindlessLimitSource::UpdateAfterBindPoolDescriptors }
	};

	uint32_t deviceLimit = std::numeric_limits<uint32_t>::max();
	VkBindlessLimitSource limitingSource = VkBindlessLimitSource::None;
	for (const auto& candidate : candidates)
	{
		if (candidate.Value < deviceLimit)
		{
			deviceLimit = candidate.Value;
			limitingSource = candidate.Source;
		}
	}

	plan.DeviceLimit = deviceLimit > (uint32_t)std::numeric_limits<int>::max()
		? std::numeric_limits<int>::max()
		: (int)deviceLimit;
	plan.DeviceLimitSource = limitingSource;

	if (plan.DeviceLimit < VkBindlessLayout::MinimumCapacity)
	{
		plan.Error = VkBindlessCapacityError::DeviceBelowMinimum;
		return plan;
	}

	plan.Effective = std::min(requested, plan.DeviceLimit);
	return plan;
}

struct VkBindlessAllocationStats
{
	int CurrentDescriptors = 0;
	int HighWaterDescriptors = 0;
	uint64_t Allocations = 0;
	uint64_t Reuses = 0;
	uint64_t Frees = 0;
	uint64_t Failures = 0;
	uint64_t InvalidFrees = 0;
};

class VkBindlessSlotAllocator
{
public:
	void Configure(int dynamicStart, int capacity)
	{
		DynamicStart = dynamicStart;
		Capacity = capacity;
		NextIndex = dynamicStart;
		AllocSizes.clear();
		FreeSlots.clear();
		Stats = {};
		Generations.Reset();
	}

	int Allocate(int count)
	{
		if (count <= 0 || DynamicStart < 0 || Capacity <= DynamicStart)
		{
			Stats.Failures++;
			return -1;
		}

		const int bucket = count - 1;
		if (FreeSlots.size() <= (std::size_t)bucket)
			FreeSlots.resize((std::size_t)bucket + 1);

		int index = -1;
		if (!FreeSlots[(std::size_t)bucket].empty())
		{
			index = FreeSlots[(std::size_t)bucket].back();
			FreeSlots[(std::size_t)bucket].pop_back();
			Stats.Reuses++;
		}
		else
		{
			if (NextIndex > Capacity - count)
			{
				Stats.Failures++;
				return -1;
			}

			index = NextIndex;
			if (AllocSizes.size() < (std::size_t)(index + count))
				AllocSizes.resize((std::size_t)(index + count), 0);
			AllocSizes[(std::size_t)index] = count;
			NextIndex += count;
		}

		Generations.Activate(index, (uint32_t)count);
		Stats.CurrentDescriptors += count;
		Stats.HighWaterDescriptors = std::max(Stats.HighWaterDescriptors, Stats.CurrentDescriptors);
		Stats.Allocations++;
		return index;
	}

	bool Free(int index)
	{
		if (index < DynamicStart || index < 0 || (std::size_t)index >= AllocSizes.size())
		{
			Stats.InvalidFrees++;
			return false;
		}

		const auto identity = Generations.Current(index);
		if (!identity.IsSet())
		{
			Stats.InvalidFrees++;
			return false;
		}

		const int count = AllocSizes[(std::size_t)index];
		if (count <= 0 || !Generations.Retire(index))
		{
			Stats.InvalidFrees++;
			return false;
		}

		const int bucket = count - 1;
		if (FreeSlots.size() <= (std::size_t)bucket)
			FreeSlots.resize((std::size_t)bucket + 1);
		FreeSlots[(std::size_t)bucket].push_back(index);

		Stats.CurrentDescriptors -= count;
		Stats.Frees++;
		return true;
	}

	FRendererResourceIdentity CurrentIdentity(int index) const
	{
		return Generations.Current(index);
	}

	bool ValidateIdentity(const FRendererResourceIdentity& identity)
	{
		return Generations.Validate(identity);
	}

	int GetCapacity() const { return Capacity; }
	int GetDynamicStart() const { return DynamicStart; }
	int GetNextIndex() const { return NextIndex; }
	int GetFreeDescriptorCount() const { return std::max(0, Capacity - DynamicStart - Stats.CurrentDescriptors); }
	const VkBindlessAllocationStats& GetStats() const { return Stats; }
	const FRendererLifetimeStats& GetLifetimeStats() const { return Generations.GetStats(); }

private:
	int DynamicStart = 0;
	int Capacity = 0;
	int NextIndex = 0;
	std::vector<int> AllocSizes;
	std::vector<std::vector<int>> FreeSlots;
	FRendererResourceGenerationTable Generations;
	VkBindlessAllocationStats Stats;
};
