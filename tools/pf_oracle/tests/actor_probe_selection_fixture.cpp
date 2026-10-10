// SDVK-010: use the actual production selector; host C++17 warnings-as-errors.
#include "hw_actor_probe_selection.h"
#include <array>
#include <cassert>
#include <cmath>
#include <cstring>
#include <limits>

using namespace HWActorProbeSelection;

int main()
{
    const std::array<Candidate, 2> probes{{{-96, -96, 80, 0}, {96, 96, 112, 1}}};
    auto at = [&](std::size_t i) { return probes.at(i); };
    auto choose = [&](double x, double y, double z, int sector = 0, bool portal = false) {
        return Resolve(x, y, z, probes.size(), at, sector, portal);
    };
    const auto left = choose(-96, -96, 80);
    const auto right = choose(96, 96, 112);
    assert(left.selected && left.spatial && left.authoredIndex == 0 && left.distanceSquared == 0);
    assert(right.selected && right.spatial && right.authoredIndex == 1 && right.distanceSquared == 0);
    // Move in a single sector between different authored probes.
    assert(choose(-80, -80, 80, 0).authoredIndex == 0);
    assert(choose(80, 80, 112, 0).authoredIndex == 1);
    // Stable tie, deterministic boundary, no hidden interpolation.
    std::array<Candidate, 2> tied{{{-10, 0, 0, 0}, {10, 0, 0, 1}}};
    auto tieAt = [&](std::size_t i) { return tied.at(i); };
    assert(Resolve(0, 0, 0, 2, tieAt, 1, false).authoredIndex == 0);
    assert(Resolve(0, 0, 0, 2, tieAt, 1, true).authoredIndex == 1);
    assert(std::strcmp(Resolve(0, 0, 0, 2, tieAt, 1, true).policy, "portal-sector-conservative") == 0);
    assert(!Resolve(0, 0, 0, 2, tieAt, -1, true).selected);
    assert(!Resolve(0, 0, 0, 2, tieAt, 200, true).selected);

    // Inclusive PF-012 radius and fail-closed absent fallback, never
    // substituting authored probe 0 when spatially ineligible.
    std::array<Candidate, 1> one{{{0, 0, 0, 0}}};
    auto oneAt = [&](std::size_t i) { return one.at(i); };
    assert(Resolve(Radius, 0, 0, 1, oneAt, 0, false).authoredIndex == 0);
    auto outside = Resolve(std::nextafter(Radius, std::numeric_limits<double>::infinity()),
                           0, 0, 1, oneAt, 0, false);
    assert(!outside.selected && outside.authoredIndex == -1 &&
           std::strcmp(outside.policy, "no-probe-in-radius") == 0);
    assert(!Resolve(0, 0, 0, 0, oneAt, 0, false).selected);
    assert(!Resolve(std::numeric_limits<double>::quiet_NaN(), 0, 0, 1, oneAt, 0, false).selected);
    assert(!Resolve(0, std::numeric_limits<double>::infinity(), 0, 1, oneAt, 0, true).selected);

    // Stale ordinal, nonfinite authored source, and distance overflow reject.
    std::array<Candidate, 2> invalid{{{0, 0, 0, 1}, {5, 0, 0, 99}}};
    auto invalidAt = [&](std::size_t i) { return invalid.at(i); };
    assert(!Resolve(0, 0, 0, 2, invalidAt, 0, false).selected);
    assert(!Resolve(0, 0, 0, 2, invalidAt, 0, true).selected);
    invalid[0] = {0, 0, std::numeric_limits<double>::infinity(), 0};
    assert(!Resolve(0, 0, 0, 2, invalidAt, 0, false).selected);
    assert(!Resolve(1e300, 0, 0, 1, oneAt, 0, false).selected);
    // Probe publication is not a selector input. The PF-113 descriptor
    // producer independently handles missing, partial and rebuilt cubemaps.
    return 0;
}
