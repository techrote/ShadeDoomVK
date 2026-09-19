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
	assert(IrradianceTextureIndex(-1) == FallbackTextureIndex);
	assert(IrradianceTextureIndex(0) == 1u);
	assert(IrradianceTextureIndex(1) == 3u);
	assert(IrradianceTextureIndex(static_cast<int>(MaxAuthoredProbeIndex)) == MaxProbeMapTextureIndex);
	assert(IrradianceTextureIndex(static_cast<int>(MaxAuthoredProbeIndex + 1u)) == FallbackTextureIndex);
	assert(MaxCandidateCount == static_cast<std::size_t>(MaxAuthoredProbeIndex) + 1u);

	assert(FindClosest(nullptr, 0, 0.0f, 0.0f, 0.0f) == FallbackTextureIndex);
	assert(FindClosest(nullptr, 0, 0.0f, 0.0f, 0.0f, -1.0f) == FallbackTextureIndex);

	Candidate single[] = { Probe(0.0f, 0.0f, 0.0f, IrradianceTextureIndex(0)) };
	assert(FindClosest(single, 1, 0.0f, 0.0f, 0.0f) == 1u);
	assert(FindClosest(single, 1, Radius, 0.0f, 0.0f) == 1u);
	assert(FindClosest(single, 1, std::nextafter(Radius, std::numeric_limits<float>::infinity()), 0.0f, 0.0f) == FallbackTextureIndex);

	// This is the minimized two-probe regression: texels near authored probe 1
	// must resolve to descriptor 3 rather than collapsing to fallback 0.
	Candidate nearest[] =
	{
		Probe(-100.0f, 0.0f, 0.0f, IrradianceTextureIndex(0)),
		Probe(40.0f, 0.0f, 0.0f, IrradianceTextureIndex(1)),
		Probe(250.0f, 0.0f, 0.0f, IrradianceTextureIndex(2))
	};
	assert(FindClosest(nearest, 3, -90.0f, 0.0f, 0.0f) == 1u);
	assert(FindClosest(nearest, 3, 0.0f, 0.0f, 0.0f) == 3u);

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
	assert(IsEncodableTextureIndex(1));
	assert(IsEncodableTextureIndex(MaxProbeMapTextureIndex));
	assert(!IsEncodableTextureIndex(FallbackTextureIndex));
	assert(!IsEncodableTextureIndex(MaxProbeMapTextureIndex + 1u));

	Candidate vertical[] = { Probe(0.0f, 0.0f, Radius, 500) };
	assert(FindClosest(vertical, 1, 0.0f, 0.0f, 0.0f) == 500);
	vertical[0].Z = std::nextafter(Radius, std::numeric_limits<float>::infinity());
	assert(FindClosest(vertical, 1, 0.0f, 0.0f, 0.0f) == FallbackTextureIndex);

	return 0;
}
