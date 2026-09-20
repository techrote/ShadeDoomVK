#include "hw_lightquery.h"

#include <algorithm>
#include <cassert>
#include <chrono>
#include <cstdint>
#include <functional>
#include <iostream>
#include <random>
#include <vector>

struct Light
{
	int id;
	int klass;
};

static std::vector<int> collect_generation(const std::vector<Light*>& candidates, HWGenerationSet<Light*>& seen)
{
	seen.BeginQuery();
	std::vector<int> result;
	for (auto* light : candidates)
		if (seen.MarkFirst(light)) result.push_back(light->id);
	return result;
}

static std::vector<int> collect_sorted(const std::vector<Light*>& candidates)
{
	std::vector<Light*> seen;
	std::vector<int> result;
	std::less<Light*> less;
	for (auto* light : candidates)
	{
		auto it = std::lower_bound(seen.begin(), seen.end(), light, less);
		if (it == seen.end() || *it != light)
		{
			seen.insert(it, light);
			result.push_back(light->id);
		}
	}
	return result;
}

struct Selection
{
	int id;
	int group;
	int klass;

	bool operator==(const Selection& other) const
	{
		return id == other.id && group == other.group && klass == other.klass;
	}
};

static std::vector<Selection> selected(const std::vector<Light*>& candidates, int group)
{
	HWGenerationSet<Light*> localSeen;
	localSeen.BeginQuery();
	std::vector<Selection> result;
	for (auto* light : candidates)
		if (localSeen.MarkFirst(light)) result.push_back({light->id, group, light->klass});
	return result;
}

int main()
{
	Light a{1, 0}, b{2, 1}, c{3, 2};
	HWGenerationSet<Light*> seen;

	// Duplicate suppression must preserve first-encounter identity/order and
	// must reset logically without clearing/re-sorting the tracked key table.
	std::vector<Light*> duplicated{&b, &a, &b, &c, &a};
	assert((collect_generation(duplicated, seen) == std::vector<int>{2, 1, 3}));
	assert((collect_generation(duplicated, seen) == std::vector<int>{2, 1, 3}));
	assert(seen.CurrentGeneration() == 2);
	assert(seen.TrackedKeys() == 3);

	// Portal qualification boundary model: a local source is exact only when
	// every baseline-touched subsector resolves to the actor section and portal
	// group. A translated portal may change light coordinates, not this identity
	// predicate; a second section or group forces baseline fallback.
	const int actorSection = 7;
	const int actorGroup = 3;
	auto exact = [&](const std::vector<std::pair<int, int>>& touched)
	{
		bool saw = false;
		bool ok = true;
		for (auto [section, group] : touched)
		{
			saw = true;
			if (section != actorSection || group != actorGroup) ok = false;
		}
		return saw && ok;
	};
	assert(exact({{7, 3}, {7, 3}}));
	assert(!exact({{7, 3}, {8, 3}}));
	assert(!exact({{7, 3}, {7, 4}}));
	assert(!exact({}));

	// The live qualification compares selected identity, portal-group context,
	// class and order. Pin that exact contract independently of pointer ordering.
	assert((selected(duplicated, actorGroup) == std::vector<Selection>{{2, 3, 1}, {1, 3, 0}, {3, 3, 2}}));
	assert(selected(duplicated, actorGroup) == selected(duplicated, actorGroup));
	assert(selected(duplicated, actorGroup) != selected(duplicated, actorGroup + 1));

	// Dense representative work proxy: the new generation marking returns the
	// same selected identities/order as the old sorted-membership algorithm.
	// Emit timing evidence without making CI correctness depend on wall-clock
	// scheduling noise.
	std::vector<Light> dense(4096);
	std::vector<Light*> candidates;
	candidates.reserve(dense.size() * 2);
	for (int i = 0; i < (int)dense.size(); ++i)
	{
		dense[i] = {i, i % 3};
		candidates.push_back(&dense[i]);
	}
	std::mt19937 rng(0x50463136u);
	std::shuffle(candidates.begin(), candidates.end(), rng);
	candidates.insert(candidates.end(), candidates.begin(), candidates.end());

	auto start = std::chrono::steady_clock::now();
	auto oldResult = collect_sorted(candidates);
	auto oldNs = std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now() - start).count();
	start = std::chrono::steady_clock::now();
	auto newResult = collect_generation(candidates, seen);
	auto newNs = std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now() - start).count();
	assert(oldResult == newResult);
	assert(newResult.size() == dense.size());

	std::cout << "PF-016 dense duplicate benchmark: sorted_ns=" << oldNs
		<< " generation_ns=" << newNs << " selected=" << newResult.size() << '\n';
	return 0;
}
