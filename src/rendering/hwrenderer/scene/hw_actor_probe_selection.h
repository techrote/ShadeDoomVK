#pragma once

// SDVK-010: actor-card environment probe ownership. Pure host-testable
// authored-ordinal selection; this never creates or reuses GPU descriptors.
// Actor and authored candidate coordinates are source-level Doom XYZ.
#include <cmath>
#include <cstddef>

namespace HWActorProbeSelection
{
constexpr double Radius = 512.0; // bounded PF-012 per-lightmap selection distance
constexpr double RadiusSquared = Radius * Radius;

struct Candidate
{
    double x, y, z;
    int authoredIndex;
};

struct Result
{
    int authoredIndex = -1; // -1 is absent; authored probe ordinal 0 is valid
    int sectorTarget = -1;
    std::size_t candidateCount = 0;
    double distanceSquared = -1.0;
    const char* policy = "no-probes";
    bool spatial = false;
    bool selected = false;
};

// Nearest valid authored source position within inclusive 512 units.
// Distance ties preserve the authored iteration order. No unproven
// temporally smoothed/blended light response is introduced.
// If portal group provenance is ambiguous, keep the inherited sector
// selection: an arbitrary spatially close probe across a linked portal
// is not evidence that it belongs to this actor's local lighting domain.
// PF-113 later resolves the selected ordinal to an actually published,
// adjacent irradiance/prefilter pair or a zero-radiance fallback.
template<class CandidateAt>
Result Resolve(double x, double y, double z, std::size_t count,
               CandidateAt candidateAt, int sectorTarget, bool portalAmbiguous)
{
    Result result;
    result.sectorTarget = sectorTarget;
    result.candidateCount = count;
    if (!count) return result;
    if (!std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z))
    {
        result.policy = "invalid-position";
        return result;
    }
    if (portalAmbiguous)
    {
        result.policy = "portal-sector-conservative";
        if (sectorTarget >= 0 && static_cast<std::size_t>(sectorTarget) < count)
        {
            const Candidate c = candidateAt(static_cast<std::size_t>(sectorTarget));
            if (c.authoredIndex == sectorTarget && std::isfinite(c.x) &&
                std::isfinite(c.y) && std::isfinite(c.z))
            {
                result.authoredIndex = sectorTarget;
                result.selected = true;
            }
        }
        return result;
    }

    result.policy = "spatial-nearest";
    result.spatial = true;
    double closestSquared = RadiusSquared;
    for (std::size_t i = 0; i < count; ++i)
    {
        const Candidate c = candidateAt(i);
        if (c.authoredIndex < 0 || static_cast<std::size_t>(c.authoredIndex) != i ||
            !std::isfinite(c.x) || !std::isfinite(c.y) || !std::isfinite(c.z))
            continue;
        const double dx = c.x - x, dy = c.y - y, dz = c.z - z;
        const double d2 = dx * dx + dy * dy + dz * dz;
        if (std::isfinite(d2) && d2 <= RadiusSquared &&
            (!result.selected || d2 < closestSquared))
        {
            closestSquared = d2;
            result.distanceSquared = d2;
            result.authoredIndex = c.authoredIndex;
            result.selected = true;
        }
    }
    if (!result.selected) result.policy = "no-probe-in-radius";
    return result;
}
} // namespace HWActorProbeSelection
