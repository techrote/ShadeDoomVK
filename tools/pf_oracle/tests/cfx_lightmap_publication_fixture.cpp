// CPU descriptor/owner model using the production publication planner.
// No Vulkan loader, shaders, content or physical GPU execution.
#include "vulkan/descriptorsets/vk_bindless.h"
#include <array>
#include <cassert>
#include <climits>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

namespace
{
enum class SampleType { Float, UInt };
struct Image { SampleType Type; bool Alive = true; };
struct Page { int Light; int Probe; };

struct DescriptorOwners
{
	int PublishedPages = 0;
	int NextImage = 10;
	std::map<int, Image> Images;
	std::vector<Page> Active;
	std::vector<Page> Retired;
	std::array<int, VkBindlessLayout::MinimumCapacity> Descriptors{};
	Page Fallback = { 1, 2 };
	bool PendingDraw = false;

	DescriptorOwners()
	{
		Images.emplace(Fallback.Light, Image{ SampleType::Float });
		Images.emplace(Fallback.Probe, Image{ SampleType::UInt });
		Descriptors[VkBindlessLayout::DynamicStart] = 999; // dynamic-slot sentinel
	}

	void Replace(int pages)
	{
		// The production atlas changes at BeginFrame after the previous frame
		// fences. Resource ownership remains in DrawDeleteList until its fence.
		assert(!PendingDraw);
		Retired.insert(Retired.end(), Active.begin(), Active.end());
		Active.clear();
		for (int page = 0; page < pages; ++page)
		{
			Page value = { NextImage++, NextImage++ };
			Images.emplace(value.Light, Image{ SampleType::Float });
			Images.emplace(value.Probe, Image{ SampleType::UInt });
			Active.push_back(value);
		}
	}

	void ReleaseAfterFence()
	{
		assert(!PendingDraw);
		for (const auto& page : Retired)
		{
			Images.at(page.Light).Alive = false;
			Images.at(page.Probe).Alive = false;
		}
		Retired.clear();
	}

	void Write(std::array<int, VkBindlessLayout::MinimumCapacity>& output, int page, Page value) const
	{
		const int index = VkBindlessLayout::LightmapStart + page * VkBindlessLayout::LightmapDescriptorsPerPage;
		assert(index >= VkBindlessLayout::LightmapStart && index + 1 < VkBindlessLayout::DynamicStart);
		assert(Images.at(value.Light).Alive && Images.at(value.Light).Type == SampleType::Float);
		assert(Images.at(value.Probe).Alive && Images.at(value.Probe).Type == SampleType::UInt);
		output[index] = value.Light;
		output[index + 1] = value.Probe;
	}

	void LegacyPublish()
	{
		// Preserve the historical failure mechanism: no writes for removed pages.
		for (int page = 0; page < static_cast<int>(Active.size()); ++page)
			Write(Descriptors, page, Active[page]);
		PublishedPages = static_cast<int>(Active.size());
	}

	void Publish(bool failExecute = false, int capacity = VkBindlessLayout::MinimumCapacity)
	{
		const auto plan = VkPlanLightmapDescriptorPublication(PublishedPages, static_cast<int>(Active.size()), capacity);
		if (!plan.IsValid())
			throw std::invalid_argument("invalid descriptor publication range");
		auto staged = Descriptors;
		for (int page = 0; page < plan.WritePages; ++page)
			Write(staged, page, plan.UsesFallback(page) ? Fallback : Active[page]);
		if (failExecute)
			throw std::runtime_error("synthetic descriptor execution failure");
		Descriptors = staged; // fake vkUpdateDescriptorSets execution
		PublishedPages = plan.NextPublishedPages; // only after successful execution
	}

	bool Dangling(int page) const
	{
		const int index = VkBindlessLayout::LightmapStart + page * VkBindlessLayout::LightmapDescriptorsPerPage;
		return !Images.at(Descriptors[index]).Alive || !Images.at(Descriptors[index + 1]).Alive;
	}

	bool IsFallback(int page) const
	{
		const int index = VkBindlessLayout::LightmapStart + page * VkBindlessLayout::LightmapDescriptorsPerPage;
		return Descriptors[index] == Fallback.Light && Descriptors[index + 1] == Fallback.Probe;
	}
};

void Retirement()
{
	DescriptorOwners legacy;
	legacy.Replace(1);
	legacy.LegacyPublish();
	legacy.PendingDraw = true;
	legacy.PendingDraw = false; // old frame fence completed
	legacy.Replace(0);
	legacy.LegacyPublish();
	assert(!legacy.Dangling(0)); // retired allocation still alive before release
	legacy.ReleaseAfterFence();
	assert(legacy.Dangling(0)); // old reserved descriptors survived their owners

	DescriptorOwners repaired;
	repaired.Replace(1);
	repaired.Publish();
	repaired.PendingDraw = true;
	repaired.PendingDraw = false;
	repaired.Replace(0);
	repaired.Publish(); // removed slots rewritten while old owners still alive
	assert(repaired.IsFallback(0));
	repaired.ReleaseAfterFence();
	assert(!repaired.Dangling(0));
	assert(repaired.Active.empty() && repaired.Retired.empty()); // no old atlas retention
	assert(repaired.Images.at(repaired.Fallback.Light).Alive && repaired.Images.at(repaired.Fallback.Probe).Alive);
	assert(repaired.Descriptors[VkBindlessLayout::DynamicStart] == 999);
}

void GrowthShrink()
{
	DescriptorOwners state;
	state.Publish(); // zero -> zero
	assert(state.PublishedPages == 0);
	state.Replace(1);
	state.Publish(); // zero -> one
	assert(!state.IsFallback(0));
	state.Replace(3);
	state.Publish(); // growth republishes all active pages
	state.ReleaseAfterFence();
	for (int page = 0; page < 3; ++page) assert(!state.IsFallback(page) && !state.Dangling(page));
	state.Publish(); // equal-count publication
	state.Replace(1);
	state.Publish(); // shrink republishes active page 0 and removes pages 1,2
	state.ReleaseAfterFence();
	assert(!state.IsFallback(0) && !state.Dangling(0));
	assert(state.IsFallback(1) && state.IsFallback(2));
	state.Replace(0);
	state.Publish();
	state.ReleaseAfterFence();
	for (int page = 0; page < 3; ++page) assert(state.IsFallback(page) && !state.Dangling(page));
	assert(state.Descriptors[VkBindlessLayout::DynamicStart] == 999);
}

void FullReservation()
{
	const auto full = VkPlanLightmapDescriptorPublication(128, 128, VkBindlessLayout::MinimumCapacity);
	assert(full.IsValid() && full.WritePages == 128 && full.EndDescriptor == VkBindlessLayout::DynamicStart);
	assert(!full.UsesFallback(-1) && !full.UsesFallback(128));
	DescriptorOwners state;
	state.Replace(128);
	state.Publish();
	state.Replace(0);
	state.Publish();
	state.ReleaseAfterFence();
	for (int page = 0; page < 128; ++page) assert(state.IsFallback(page) && !state.Dangling(page));
	assert(state.Descriptors[VkBindlessLayout::DynamicStart] == 999);
}

void InvalidRanges()
{
	for (const auto& input : std::vector<std::array<int, 3>>{
		{ -1, 0, 260 }, { 0, -1, 260 }, { 129, 0, 260 }, { 0, 129, 260 },
		{ INT_MAX, 0, 260 }, { 0, INT_MAX, 260 }, { 128, 0, 258 }, { 0, 128, 258 }, { 1, 0, 4 }, { 0, 0, -1 } })
	{
		const auto plan = VkPlanLightmapDescriptorPublication(input[0], input[1], input[2]);
		assert(!plan.IsValid() && plan.WritePages == 0 && !plan.UsesFallback(0));
	}
	DescriptorOwners state;
	state.Replace(1);
	state.Publish();
	state.Replace(0);
	const auto before = state.Descriptors;
	try { state.Publish(false, 4); assert(false); } catch (const std::invalid_argument&) {}
	assert(state.Descriptors == before && state.PublishedPages == 1);
}

void FailedExecute()
{
	DescriptorOwners state;
	state.Replace(1);
	state.Publish();
	state.Replace(0);
	const auto before = state.Descriptors;
	try { state.Publish(true); assert(false); } catch (const std::runtime_error&) {}
	assert(state.Descriptors == before && state.PublishedPages == 1);
	assert(!state.Dangling(0)); // no premature owner retirement after failed publication
	state.Publish();
	state.ReleaseAfterFence();
	assert(state.PublishedPages == 0 && state.IsFallback(0) && !state.Dangling(0));
}
}

int main(int argc, char** argv)
{
	assert(argc == 2);
	const std::string scenario = argv[1];
	if (scenario == "retirement") Retirement();
	else if (scenario == "growth-shrink") GrowthShrink();
	else if (scenario == "full-reservation") FullReservation();
	else if (scenario == "invalid-ranges") InvalidRanges();
	else if (scenario == "failed-execute") FailedExecute();
	else return 2;
	std::cout << scenario << " passed\n";
}
