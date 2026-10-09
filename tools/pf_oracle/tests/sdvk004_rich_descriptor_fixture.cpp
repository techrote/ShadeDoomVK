#include "vk_bindless.h"

#include <cassert>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <limits>
#include <vector>

struct Allocation
{
	int Index = -1;
	FRendererResourceIdentity Identity;
	int Span = 0;
};

using Group = std::vector<Allocation>;

static VkBindlessDeviceLimits MakeLimits(uint32_t value)
{
	VkBindlessDeviceLimits limits;
	limits.MaxPerStageDescriptorSamplers = value;
	limits.MaxPerStageDescriptorSampledImages = value;
	limits.MaxDescriptorSetSamplers = value;
	limits.MaxDescriptorSetSampledImages = value;
	limits.MaxPerStageDescriptorUpdateAfterBindSamplers = value;
	limits.MaxPerStageDescriptorUpdateAfterBindSampledImages = value;
	limits.MaxDescriptorSetUpdateAfterBindSamplers = value;
	limits.MaxDescriptorSetUpdateAfterBindSampledImages = value;
	limits.MaxPerStageUpdateAfterBindResources = value;
	limits.MaxUpdateAfterBindDescriptorsInAllPools = value;
	return limits;
}

static Group AllocateGroup(VkBindlessSlotAllocator& allocator, int count, int span)
{
	Group group;
	group.reserve(static_cast<std::size_t>(count));
	for (int i = 0; i < count; ++i)
	{
		const int index = allocator.Allocate(span);
		assert(index >= VkBindlessLayout::DynamicStart);
		const auto identity = allocator.CurrentIdentity(index);
		assert(identity.IsSet());
		assert(identity.Span == static_cast<uint32_t>(span));
		assert(allocator.ValidateIdentity(identity));
		group.push_back({ index, identity, span });
	}
	return group;
}

static void RecycleOne(VkBindlessSlotAllocator& allocator, Group& group, std::size_t position)
{
	auto& allocation = group.at(position % group.size());
	const auto old = allocation.Identity;
	assert(allocator.Free(allocation.Index));
	assert(!allocator.ValidateIdentity(old));
	const int index = allocator.Allocate(allocation.Span);
	assert(index == allocation.Index);
	const auto fresh = allocator.CurrentIdentity(index);
	assert(fresh.IsSet());
	assert(fresh.Generation != old.Generation || fresh.Epoch != old.Epoch);
	assert(allocator.ValidateIdentity(fresh));
	allocation = { index, fresh, allocation.Span };
}

static void RebuildGroup(VkBindlessSlotAllocator& allocator, Group& group)
{
	const int span = group.front().Span;
	for (const auto& allocation : group)
	{
		const auto old = allocation.Identity;
		assert(allocator.Free(allocation.Index));
		assert(!allocator.ValidateIdentity(old));
	}
	group = AllocateGroup(allocator, static_cast<int>(group.size()), span);
}

static void StressOwnerEpoch(FRendererEpoch& epoch, int cycles)
{
	for (int i = 0; i < cycles; ++i)
	{
		const auto old = epoch.Snapshot();
		epoch.Invalidate();
		assert(!epoch.Validate(old));
		assert(epoch.Validate(epoch.Snapshot()));
	}
}

int main()
{
	static_assert(VkBindlessLayout::DynamicStart == 259);
	static_assert(VkBindlessLayout::MinimumCapacity == 260);

	// Device-limit qualification: the effective count is clamped to the actual
	// update-after-bind pool limit, while invalid requested/device limits fail.
	auto limits = MakeLimits(8192);
	limits.MaxUpdateAfterBindDescriptorsInAllPools = 4355;
	const auto plan = VkPlanBindlessCapacity(6000, limits);
	assert(plan.IsValid());
	assert(plan.DeviceLimit == 4355);
	assert(plan.Effective == 4355);
	assert(plan.DeviceLimitSource == VkBindlessLimitSource::UpdateAfterBindPoolDescriptors);

	const auto requestedTooSmall = VkPlanBindlessCapacity(VkBindlessLayout::MinimumCapacity - 1, MakeLimits(8192));
	assert(!requestedTooSmall.IsValid());
	assert(requestedTooSmall.Error == VkBindlessCapacityError::RequestedBelowMinimum);

	const auto deviceTooSmall = VkPlanBindlessCapacity(8192, MakeLimits(VkBindlessLayout::MinimumCapacity - 1));
	assert(!deviceTooSmall.IsValid());
	assert(deviceTooSmall.Error == VkBindlessCapacityError::DeviceBelowMinimum);

	// 4096 dynamic descriptors. Spans mirror the live Vulkan material binding
	// path: ordinary=albedo+3 fixed optional slots, legacy=+normal/specular,
	// PBR=+normal/M/R/AO, indexed/palette=R8+palette row, canvas=one layer,
	// and a rich custom-shader case adds four authored custom textures to PBR.
	VkBindlessSlotAllocator allocator;
	allocator.Configure(VkBindlessLayout::DynamicStart, plan.Effective);
	Group ordinary = AllocateGroup(allocator, 128, 4);
	Group legacy = AllocateGroup(allocator, 96, 6);
	Group pbr = AllocateGroup(allocator, 96, 8);
	Group palette = AllocateGroup(allocator, 128, 2);
	Group canvas = AllocateGroup(allocator, 64, 1);
	Group custom = AllocateGroup(allocator, 64, 12);
	Group probes = AllocateGroup(allocator, 64, 2);

	const auto initial = allocator.GetStats();
	assert(initial.CurrentDescriptors == 3072);
	assert(initial.HighWaterDescriptors == 3072);
	assert(allocator.GetFreeDescriptorCount() == 1024);

	// Repeated canvas replacement, translated/paletted material invalidation and
	// rich PBR rebuilds must retire old identities before exact-size reuse.
	constexpr int rebuildCycles = 64;
	for (int cycle = 0; cycle < rebuildCycles; ++cycle)
	{
		RecycleOne(allocator, canvas, static_cast<std::size_t>(cycle));
		RecycleOne(allocator, palette, static_cast<std::size_t>(cycle));
		RecycleOne(allocator, pbr, static_cast<std::size_t>(cycle));
	}

	// Sampler invalidation follows ResetHWTextureSets: every live material and
	// probe allocation is retired, then the same semantic workload is rebuilt.
	RebuildGroup(allocator, ordinary);
	RebuildGroup(allocator, legacy);
	RebuildGroup(allocator, pbr);
	RebuildGroup(allocator, palette);
	RebuildGroup(allocator, canvas);
	RebuildGroup(allocator, custom);
	RebuildGroup(allocator, probes);

	const auto qualified = allocator.GetStats();
	const auto lifetime = allocator.GetLifetimeStats();
	assert(qualified.CurrentDescriptors == 3072);
	assert(qualified.HighWaterDescriptors == 3072);
	assert(qualified.Failures == 0);
	assert(qualified.InvalidFrees == 0);
	assert(qualified.Reuses >= 832);
	assert(lifetime.StaleRejects >= 832);
	assert(allocator.GetFreeDescriptorCount() == 1024);

	// Fixed lightmap/probe-page publication never enters the dynamic range, and
	// shrink publishes fallbacks over every formerly-live reserved page.
	const auto fullPages = VkPlanLightmapDescriptorPublication(0, 128, plan.Effective);
	assert(fullPages.IsValid());
	assert(fullPages.EndDescriptor == VkBindlessLayout::DynamicStart);
	const auto shrinkPages = VkPlanLightmapDescriptorPublication(128, 3, plan.Effective);
	assert(shrinkPages.IsValid());
	assert(shrinkPages.WritePages == 128);
	assert(shrinkPages.ActivePages == 3);
	assert(shrinkPages.UsesFallback(3));
	assert(shrinkPages.UsesFallback(127));
	assert(shrinkPages.EndDescriptor == VkBindlessLayout::DynamicStart);
	const auto tooManyPages = VkPlanLightmapDescriptorPublication(128, 129, plan.Effective);
	assert(!tooManyPages.IsValid());
	assert(tooManyPages.Error == VkLightmapDescriptorPublicationError::PageCountOutOfRange);

	// Map/resource resets use the accepted PF-002 owner epochs; each previous
	// token becomes stale while a fresh token remains valid.
	FRendererEpoch textureEpoch;
	FRendererEpoch lightmapEpoch;
	FRendererEpoch probeEpoch;
	StressOwnerEpoch(textureEpoch, rebuildCycles);
	StressOwnerEpoch(lightmapEpoch, rebuildCycles);
	StressOwnerEpoch(probeEpoch, rebuildCycles);
	assert(textureEpoch.GetStats().Invalidations == rebuildCycles);
	assert(textureEpoch.GetStats().StaleRejects == rebuildCycles);
	assert(lightmapEpoch.GetStats().Invalidations == rebuildCycles);
	assert(lightmapEpoch.GetStats().StaleRejects == rebuildCycles);
	assert(probeEpoch.GetStats().Invalidations == rebuildCycles);
	assert(probeEpoch.GetStats().StaleRejects == rebuildCycles);

	// Descriptor-manager recreation advances the allocator epoch and rejects a
	// token from the previous address-space instance even if the index repeats.
	VkBindlessSlotAllocator restarted;
	restarted.Configure(VkBindlessLayout::DynamicStart, VkBindlessLayout::DynamicStart + 8);
	const int restartIndex = restarted.Allocate(4);
	const auto preRestart = restarted.CurrentIdentity(restartIndex);
	restarted.Configure(VkBindlessLayout::DynamicStart, VkBindlessLayout::DynamicStart + 8);
	assert(!restarted.ValidateIdentity(preRestart));
	const int postRestartIndex = restarted.Allocate(4);
	assert(postRestartIndex == restartIndex);
	const auto postRestart = restarted.CurrentIdentity(postRestartIndex);
	assert(postRestart.Epoch != preRestart.Epoch);
	assert(restarted.ValidateIdentity(postRestart));

	// Near capacity, exact-size fragmentation and pathological requests all fail
	// explicitly without invalidating still-live allocations or over-growing
	// allocator bookkeeping.
	VkBindlessSlotAllocator tight;
	tight.Configure(VkBindlessLayout::DynamicStart, VkBindlessLayout::DynamicStart + 17);
	const int tight8 = tight.Allocate(8);
	const int tight4 = tight.Allocate(4);
	const int tight5 = tight.Allocate(5);
	assert(tight8 >= 0 && tight4 >= 0 && tight5 >= 0);
	const auto tight8Identity = tight.CurrentIdentity(tight8);
	assert(tight.GetFreeDescriptorCount() == 0);
	assert(tight.Allocate(1) == -1);
	assert(tight.ValidateIdentity(tight8Identity));
	assert(tight.Free(tight4));
	assert(tight.GetFreeDescriptorCount() == 4);
	assert(tight.Allocate(5) == -1);
	assert(tight.GetFreeDescriptorCount() == 4);
	assert(tight.Allocate(4) == tight4);
	assert(tight.Allocate(std::numeric_limits<int>::max()) == -1);
	assert(tight.GetStats().Failures == 3);
	assert(tight.GetStats().CurrentDescriptors == 17);
	assert(tight.GetStats().HighWaterDescriptors == 17);

	const int dynamicCapacity = plan.Effective - VkBindlessLayout::DynamicStart;
	const int pressurePercent = qualified.HighWaterDescriptors * 100 / dynamicCapacity;
	std::cout
		<< "{\"schema\":\"sdvk004-rich-descriptor-stress/v1\""
		<< ",\"status\":\"PASS\""
		<< ",\"effective_capacity\":" << plan.Effective
		<< ",\"dynamic_start\":" << VkBindlessLayout::DynamicStart
		<< ",\"dynamic_capacity\":" << dynamicCapacity
		<< ",\"unique_semantic_materials\":576"
		<< ",\"ordinary_materials\":128"
		<< ",\"legacy_materials\":96"
		<< ",\"pbr_materials\":96"
		<< ",\"translation_palette_variants\":128"
		<< ",\"canvas_materials\":64"
		<< ",\"custom_shader_materials\":64"
		<< ",\"probe_pairs\":64"
		<< ",\"lightmap_peak_pages\":128"
		<< ",\"rebuild_cycles\":" << rebuildCycles
		<< ",\"descriptor_current\":" << qualified.CurrentDescriptors
		<< ",\"descriptor_high_water\":" << qualified.HighWaterDescriptors
		<< ",\"descriptor_free\":" << allocator.GetFreeDescriptorCount()
		<< ",\"pressure_percent\":" << pressurePercent
		<< ",\"descriptor_allocations\":" << qualified.Allocations
		<< ",\"descriptor_reuses\":" << qualified.Reuses
		<< ",\"descriptor_frees\":" << qualified.Frees
		<< ",\"descriptor_failures\":" << qualified.Failures
		<< ",\"descriptor_invalid_frees\":" << qualified.InvalidFrees
		<< ",\"stale_rejects\":" << lifetime.StaleRejects
		<< ",\"tight_capacity_failures\":" << tight.GetStats().Failures
		<< ",\"allocator_epoch_stale_rejects\":" << restarted.GetLifetimeStats().StaleRejects
		<< ",\"texture_epoch_invalidations\":" << textureEpoch.GetStats().Invalidations
		<< ",\"lightmap_epoch_invalidations\":" << lightmapEpoch.GetStats().Invalidations
		<< ",\"probe_epoch_invalidations\":" << probeEpoch.GetStats().Invalidations
		<< ",\"device_limit_source\":\"" << VkBindlessLimitSourceName(plan.DeviceLimitSource) << "\""
		<< "}\n";
	return 0;
}
