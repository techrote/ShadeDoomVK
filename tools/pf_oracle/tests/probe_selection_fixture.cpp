#include "hw_probe_selection.h"

#include <cassert>
#include <cmath>
#include <cstdint>
#include <limits>

using namespace HWProbeSelection;

static Candidate Probe(float x, float y, float z, uint32_t textureIndex)
{
	Candidate candidate;
	candidate.X = x;
	candidate.Y = y;
	candidate.Z = z;
	candidate.TextureIndex = textureIndex;
	return candidate;
}

int main()
{
	assert(sizeof(Candidate) == 16);
	assert(MaxCandidateCount == 32768u);
	assert(IsEncodableTextureIndex(1));
	assert(IsEncodableTextureIndex(MaxProbeMapTextureIndex));
	assert(!IsEncodableTextureIndex(FallbackTextureIndex));
	assert(!IsEncodableTextureIndex(MaxProbeMapTextureIndex + 1u));

	assert(FindClosest(nullptr, 0, 0.0f, 0.0f, 0.0f) == FallbackTextureIndex);
	assert(FindClosest(nullptr, 0, 0.0f, 0.0f, 0.0f, -1.0f) == FallbackTextureIndex);

	// Runtime descriptor identities are intentionally not derived from authored
	// probe ordinals. The selector must preserve whatever valid pair-start index
	// the bindless allocator assigned.
	Candidate single[] = { Probe(0.0f, 0.0f, 0.0f, 701u) };
	assert(FindClosest(single, 1, 0.0f, 0.0f, 0.0f) == 701u);
	assert(FindClosest(single, 1, Radius, 0.0f, 0.0f) == 701u);
	assert(FindClosest(single, 1, std::nextafter(Radius, std::numeric_limits<float>::infinity()), 0.0f, 0.0f) == FallbackTextureIndex);

	// Minimized two-probe regression: a texel near the second live probe must
	// resolve to its allocator-returned descriptor rather than fallback 0.
	Candidate nearest[] =
	{
		Probe(-100.0f, 0.0f, 0.0f, 913u),
		Probe(40.0f, 0.0f, 0.0f, 1201u),
		Probe(250.0f, 0.0f, 0.0f, 1517u)
	};
	assert(FindClosest(nearest, 3, -90.0f, 0.0f, 0.0f) == 913u);
	assert(FindClosest(nearest, 3, 0.0f, 0.0f, 0.0f) == 1201u);

	// Equal-distance ties are stable: the first active-placement entry wins.
	Candidate tieAB[] = { Probe(-10.0f, 0.0f, 0.0f, 400), Probe(10.0f, 0.0f, 0.0f, 402) };
	Candidate tieBA[] = { Probe(10.0f, 0.0f, 0.0f, 402), Probe(-10.0f, 0.0f, 0.0f, 400) };
	assert(FindClosest(tieAB, 2, 0.0f, 0.0f, 0.0f) == 400);
	assert(FindClosest(tieBA, 2, 0.0f, 0.0f, 0.0f) == 402);

	// R16_UINT value 0 is reserved for explicit fallback. Out-of-range descriptor
	// identities are excluded rather than silently truncating.
	Candidate bounds[] =
	{
		Probe(0.0f, 0.0f, 0.0f, FallbackTextureIndex),
		Probe(0.0f, 0.0f, 0.0f, MaxProbeMapTextureIndex + 1u),
		Probe(1.0f, 0.0f, 0.0f, MaxProbeMapTextureIndex)
	};
	assert(FindClosest(bounds, 3, 0.0f, 0.0f, 0.0f) == MaxProbeMapTextureIndex);

	Candidate vertical[] = { Probe(0.0f, 0.0f, Radius, 500) };
	assert(FindClosest(vertical, 1, 0.0f, 0.0f, 0.0f) == 500);
	vertical[0].Z = std::nextafter(Radius, std::numeric_limits<float>::infinity());
	assert(FindClosest(vertical, 1, 0.0f, 0.0f, 0.0f) == FallbackTextureIndex);

	return 0;
}
