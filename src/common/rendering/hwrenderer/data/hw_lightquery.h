#pragma once

#include <cstdint>
#include <functional>
#include <limits>
#include <unordered_map>

// PF-016 renderer-owned duplicate suppression. A query advances a generation
// instead of clearing/sorting a pointer array. Stable pointer identity is used
// only for the duration of a generation; an address reused later cannot match
// because the generation has advanced.
template<class Key, class Hash = std::hash<Key>>
class HWGenerationSet
{
public:
	void BeginQuery()
	{
		if (Generation == std::numeric_limits<uint64_t>::max())
		{
			Marks.clear();
			Generation = 1;
		}
		else
		{
			++Generation;
			if (Generation == 0) Generation = 1;
		}
	}

	bool MarkFirst(const Key& key)
	{
		auto inserted = Marks.emplace(key, Generation);
		if (inserted.second) return true;
		if (inserted.first->second == Generation) return false;
		inserted.first->second = Generation;
		return true;
	}

	uint64_t CurrentGeneration() const { return Generation; }
	size_t TrackedKeys() const { return Marks.size(); }

private:
	std::unordered_map<Key, uint64_t, Hash> Marks;
	uint64_t Generation = 0;
};
