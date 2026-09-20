#include <cassert>
#include <cstdint>
#include <cstring>
#include <utility>
#include <vector>

namespace
{
constexpr float NoValue = 100000000.0f;

struct ThreeDFloorSample
{
	float floorHeight;
	float ceilingHeight;
};

std::pair<float, float> ResolveClipBounds(
	float actorFloor,
	float actorCeiling,
	float baseFloor,
	float baseCeiling,
	const std::vector<ThreeDFloorSample>& samples,
	bool heightSecMatch = false)
{
	float bottom = NoValue;
	float top = -NoValue;

	if (!samples.empty())
	{
		for (const auto& sample : samples)
		{
			if (sample.floorHeight == actorFloor) bottom = sample.floorHeight;
			if (sample.ceilingHeight == actorCeiling) top = sample.ceilingHeight;
			if (bottom != NoValue && top != -NoValue) break;
		}
	}
	else if (heightSecMatch)
	{
		bottom = actorFloor;
		top = actorCeiling;
	}

	if (bottom == NoValue) bottom = baseFloor;
	if (top == -NoValue) top = baseCeiling;
	return {bottom, top};
}

struct SkyIdentity
{
	float xOffset[2];
	float yOffset;
	std::uintptr_t texture[2];
	std::int32_t skyTextureId;
	bool mirrored;
	bool doubleSky;
	bool sky2;
	std::uint32_t fadeColor;
};

bool SameSky(const SkyIdentity& a, const SkyIdentity& b)
{
	return a.xOffset[0] == b.xOffset[0] &&
		a.xOffset[1] == b.xOffset[1] &&
		a.yOffset == b.yOffset &&
		a.texture[0] == b.texture[0] &&
		a.texture[1] == b.texture[1] &&
		a.skyTextureId == b.skyTextureId &&
		a.mirrored == b.mirrored &&
		a.doubleSky == b.doubleSky &&
		a.sky2 == b.sky2 &&
		a.fadeColor == b.fadeColor;
}

SkyIdentity MakeSky(unsigned char fill)
{
	SkyIdentity value;
	std::memset(&value, fill, sizeof(value));
	value.xOffset[0] = 1.25f;
	value.xOffset[1] = -2.5f;
	value.yOffset = 3.75f;
	value.texture[0] = 0x1000u;
	value.texture[1] = 0x2000u;
	value.skyTextureId = 17;
	value.mirrored = true;
	value.doubleSky = false;
	value.sky2 = true;
	value.fadeColor = 0x11223344u;
	return value;
}

bool IsMirrored(int lineMirrorFlag, int planeMirrorFlag)
{
	return !!((lineMirrorFlag ^ planeMirrorFlag) & 1);
}
}

int main()
{
	// No 3D-floor or height-sector candidate: both base planes must resolve.
	auto base = ResolveClipBounds(0.0f, 128.0f, 0.0f, 128.0f, {});
	assert(base.first == 0.0f);
	assert(base.second == 128.0f);
	assert(base.second != -NoValue);

	// A floor-only match must not suppress the ordinary ceiling fallback.
	auto floorOnly = ResolveClipBounds(16.0f, 144.0f, 0.0f, 160.0f,
		{{16.0f, 120.0f}});
	assert(floorOnly.first == 16.0f);
	assert(floorOnly.second == 160.0f);

	// A ceiling-only match must preserve that 3D-floor ceiling while the
	// ordinary floor fallback remains independent.
	auto ceilingOnly = ResolveClipBounds(24.0f, 144.0f, 0.0f, 160.0f,
		{{8.0f, 144.0f}});
	assert(ceilingOnly.first == 0.0f);
	assert(ceilingOnly.second == 144.0f);

	// Separate 3D-floor samples may satisfy floor and ceiling independently.
	auto both = ResolveClipBounds(24.0f, 144.0f, 0.0f, 160.0f,
		{{24.0f, 112.0f}, {8.0f, 144.0f}, {24.0f, 144.0f}});
	assert(both.first == 24.0f);
	assert(both.second == 144.0f);

	// Height-sector behavior remains the inherited paired actor bounds.
	auto heightSec = ResolveClipBounds(-32.0f, 96.0f, -64.0f, 128.0f, {}, true);
	assert(heightSec.first == -32.0f);
	assert(heightSec.second == 96.0f);

	// Object representation is not sky identity. Deliberately different
	// padding bytes must not split two semantically identical sky records.
	auto skyA = MakeSky(0xA5);
	auto skyB = MakeSky(0x5A);
	assert(SameSky(skyA, skyB));
	assert(std::memcmp(&skyA, &skyB, sizeof(SkyIdentity)) != 0);

	// +0 and -0 are numerically identical offsets even though their object
	// representations differ.
	skyA = MakeSky(0x00);
	skyB = skyA;
	skyA.xOffset[0] = 0.0f;
	skyB.xOffset[0] = -0.0f;
	assert(SameSky(skyA, skyB));

	const SkyIdentity canonical = MakeSky(0x00);
	auto changed = canonical;
	changed.xOffset[0] += 1.0f; assert(!SameSky(canonical, changed));
	changed = canonical; changed.xOffset[1] -= 1.0f; assert(!SameSky(canonical, changed));
	changed = canonical; changed.yOffset += 1.0f; assert(!SameSky(canonical, changed));
	changed = canonical; changed.texture[0] += 1u; assert(!SameSky(canonical, changed));
	changed = canonical; changed.texture[1] += 1u; assert(!SameSky(canonical, changed));
	changed = canonical; changed.skyTextureId += 1; assert(!SameSky(canonical, changed));
	changed = canonical; changed.mirrored = !changed.mirrored; assert(!SameSky(canonical, changed));
	changed = canonical; changed.doubleSky = !changed.doubleSky; assert(!SameSky(canonical, changed));
	changed = canonical; changed.sky2 = !changed.sky2; assert(!SameSky(canonical, changed));
	changed = canonical; changed.fadeColor ^= 1u; assert(!SameSky(canonical, changed));

	// PF-010 mirror/plane-mirror parity remains XOR of the low parity bits.
	assert(!IsMirrored(0, 0));
	assert(IsMirrored(1, 0));
	assert(IsMirrored(0, 1));
	assert(!IsMirrored(1, 1));
	assert(!IsMirrored(2, 0));
	assert(IsMirrored(3, 2));

	return 0;
}
