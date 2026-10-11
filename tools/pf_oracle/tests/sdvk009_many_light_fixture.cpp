#include "vulkan/vk_lightuploadpolicy.h"

#include <algorithm>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <vector>

namespace
{
constexpr std::size_t DynLightInfoBytes = 80;
constexpr std::size_t RangeBytes = 4 * sizeof(int);
constexpr int InheritedTileCap = 16;

enum class LightClass { Normal, Subtractive, Additive };
struct Light { int id; LightClass cls; };

std::vector<Light> OrderedLights(int count)
{
    std::vector<Light> lights;
    lights.reserve(count);
    // Production FDynLightData is class-partitioned. Preserve encounter order
    // within each class, then normal/subtractive/additive range order.
    for (LightClass cls : {LightClass::Normal, LightClass::Subtractive, LightClass::Additive})
        for (int i = 0; i < count; ++i)
            if (LightClass(i % 3) == cls) lights.push_back({i, cls});
    return lights;
}

std::vector<Light> InheritedTile(const std::vector<Light>& input)
{
    return {input.begin(), input.begin() + std::min<std::size_t>(InheritedTileCap, input.size())};
}

std::vector<int> IndexedTile(const std::vector<Light>& input)
{
    std::vector<int> indices;
    indices.reserve(input.size());
    for (const auto& light : input) indices.push_back(light.id);
    return indices;
}
}

int main()
{
    using VkLightUploadPolicy::Fits;
    static_assert(Fits(4, 0, 0, 0));
    static_assert(Fits(4, 3, 4, 0)); // last valid range entry may name an empty list
    static_assert(!Fits(4, 4, 0, 0)); // one-past range entry is never valid
    static_assert(Fits(4, 0, 3, 1));
    static_assert(!Fits(4, 0, 3, 2));
    static_assert(!Fits(4, -1, 0, 0));
    static_assert(!Fits(4, 0, -1, 0));

    const auto dense = OrderedLights(256);
    const auto inherited = InheritedTile(dense);
    const auto indexed = IndexedTile(dense);
    assert(dense.size() == 256);
    assert(inherited.size() == 16); // inherited path silently truncates equivalence
    assert(indexed.size() == dense.size());
    for (std::size_t i = 0; i < dense.size(); ++i) assert(indexed[i] == dense[i].id);

    // Representative resource model at the accepted PF-019 reference extent.
    // This is structure/memory evidence only, not a GPU performance claim.
    constexpr std::size_t tiles = 30 * 16; // ceil(1904/64) * ceil(1001/64)
    const std::size_t inheritedFullCopy = tiles * (RangeBytes + dense.size() * DynLightInfoBytes);
    const std::size_t indexedOverlap = dense.size() * DynLightInfoBytes + tiles * (RangeBytes + dense.size() * sizeof(uint32_t));
    const std::size_t currentPerDrawCopies = tiles * (RangeBytes + dense.size() * DynLightInfoBytes);
    assert(inheritedFullCopy == currentPerDrawCopies);
    assert(indexedOverlap < inheritedFullCopy);
    // Even the indexed representation cannot reduce fragment loop work for a
    // pathological case where every semantically eligible light overlaps every tile.
    const std::size_t overlapLoopEntries = tiles * dense.size();
    assert(overlapLoopEntries == 122880);

    std::cout << "SDVK-009 many-light fixture passed: inherited_cap=" << inherited.size()
              << " indexed_overlap_bytes=" << indexedOverlap
              << " full_record_copy_bytes=" << inheritedFullCopy
              << " overlap_loop_entries=" << overlapLoopEntries << "\n";
    return 0;
}
