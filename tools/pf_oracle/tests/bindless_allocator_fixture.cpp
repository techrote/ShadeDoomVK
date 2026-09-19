#include "vk_bindless.h"

#include <cassert>
#include <cstring>

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

int main()
{
	static_assert(VkBindlessLayout::FixedSlots == 3);
	static_assert(VkBindlessLayout::MaxLightmapPages == 128);
	static_assert(VkBindlessLayout::LightmapDescriptorsPerPage == 2);
	static_assert(VkBindlessLayout::DynamicStart == 259);
	static_assert(VkBindlessLayout::MinimumCapacity == 260);

	{
		auto limits = MakeLimits(20000);
		limits.MaxUpdateAfterBindDescriptorsInAllPools = 16000;
		auto plan = VkPlanBindlessCapacity(16536, limits);
		assert(plan.IsValid());
		assert(plan.DeviceLimit == 16000);
		assert(plan.Effective == 16000);
		assert(plan.DeviceLimitSource == VkBindlessLimitSource::UpdateAfterBindPoolDescriptors);
		assert(std::strcmp(VkBindlessLimitSourceName(plan.DeviceLimitSource), "update-after-bind descriptors in all pools") == 0);
	}

	{
		auto limits = MakeLimits(20000);
		auto plan = VkPlanBindlessCapacity(1000, limits);
		assert(plan.IsValid());
		assert(plan.Effective == 1000);
		assert(plan.DeviceLimit > plan.Effective);
	}

	{
		auto limits = MakeLimits(20000);
		auto plan = VkPlanBindlessCapacity(VkBindlessLayout::MinimumCapacity - 1, limits);
		assert(!plan.IsValid());
		assert(plan.Error == VkBindlessCapacityError::RequestedBelowMinimum);
	}

	{
		auto limits = MakeLimits(VkBindlessLayout::MinimumCapacity - 1);
		auto plan = VkPlanBindlessCapacity(16536, limits);
		assert(!plan.IsValid());
		assert(plan.Error == VkBindlessCapacityError::DeviceBelowMinimum);
	}

	{
		auto limits = MakeLimits(20000);
		limits.MaxPerStageDescriptorUpdateAfterBindSampledImages = 900;
		limits.MaxPerStageDescriptorSampledImages = 800;
		auto plan = VkPlanBindlessCapacity(16536, limits);
		assert(plan.IsValid());
		assert(plan.DeviceLimit == 898);
		assert(plan.DeviceLimitSource == VkBindlessLimitSource::PerStageSampledImages);
	}

	VkBindlessSlotAllocator allocator;
	allocator.Configure(VkBindlessLayout::DynamicStart, VkBindlessLayout::DynamicStart + 10);

	const int first = allocator.Allocate(2);
	const int second = allocator.Allocate(3);
	assert(first == VkBindlessLayout::DynamicStart);
	assert(second == VkBindlessLayout::DynamicStart + 2);

	auto firstIdentity = allocator.CurrentIdentity(first);
	assert(firstIdentity.IsSet());
	assert(firstIdentity.Span == 2);
	assert(allocator.ValidateIdentity(firstIdentity));

	assert(allocator.Free(first));
	assert(!allocator.ValidateIdentity(firstIdentity));

	const int reused = allocator.Allocate(2);
	assert(reused == first);
	auto reusedIdentity = allocator.CurrentIdentity(reused);
	assert(reusedIdentity.IsSet());
	assert(reusedIdentity.Generation != firstIdentity.Generation);
	assert(allocator.ValidateIdentity(reusedIdentity));

	// A different allocation size must not consume the size-3 bucket.
	const int five = allocator.Allocate(5);
	assert(five == VkBindlessLayout::DynamicStart + 5);

	const auto& fullStats = allocator.GetStats();
	assert(fullStats.CurrentDescriptors == 10);
	assert(fullStats.HighWaterDescriptors == 10);
	assert(fullStats.Allocations == 4);
	assert(fullStats.Reuses == 1);
	assert(fullStats.Frees == 1);
	assert(allocator.GetFreeDescriptorCount() == 0);

	assert(allocator.Allocate(1) == -1);
	assert(allocator.GetStats().Failures == 1);

	assert(!allocator.Free(VkBindlessLayout::FixedSlots));
	assert(allocator.GetStats().InvalidFrees == 1);

	assert(allocator.Free(reused));
	assert(!allocator.Free(reused));
	assert(allocator.GetStats().InvalidFrees == 2);

	assert(allocator.Free(second));
	const int secondReused = allocator.Allocate(3);
	assert(secondReused == second);

	return 0;
}
