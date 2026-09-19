#include "hw_lightcompat.h"

#include <algorithm>
#include <cassert>
#include <cmath>

namespace
{
float BaselineDistanceAttenuation(float dist, float radius, float strength, float linearity)
{
	float a = dist / radius;
	float b = std::clamp(1.0f - a * a * a * a, 0.0f, 1.0f);
	float inverseSquare = (b * b) / (dist * dist + 1.0f) * strength;
	float linear = std::clamp((radius - dist) / radius, 0.0f, 1.0f);
	return inverseSquare * (1.0f - linearity) + linear * linearity;
}

float BaselineSpotSmoothStep(float edge0, float edge1, float x)
{
	float t = std::clamp((x - edge0) / (edge1 - edge0), 0.0f, 1.0f);
	return t * t * (3.0f - 2.0f * t);
}

bool Near(float a, float b, float tolerance = 1.0e-5f)
{
	return std::fabs(a - b) <= tolerance;
}
}

int main()
{
	static_assert(HWLightCompat::AdditiveGpuColorScale == 0.2f);
	static_assert(HWLightCompat::SunProxyDistance == 100000.0f);
	static_assert(HWLightCompat::SunProxyRadius == 100000000.0f);
	static_assert(HWLightCompat::SunProxyStrength == 1500.0f);

	assert(Near(HWLightCompat::NormalizeColorChannel(0), 0.0f));
	assert(Near(HWLightCompat::NormalizeColorChannel(128), 128.0f / 255.0f));
	assert(Near(HWLightCompat::NormalizeColorChannel(255), 1.0f));

	assert(Near(HWLightCompat::ClampLinearity(-1.0f), 0.0f));
	assert(Near(HWLightCompat::ClampLinearity(0.0f), 0.0f));
	assert(Near(HWLightCompat::ClampLinearity(0.5f), 0.5f));
	assert(Near(HWLightCompat::ClampLinearity(1.0f), 1.0f));
	assert(Near(HWLightCompat::ClampLinearity(2.0f), 1.0f));

	// Representative inverse-square/linear blend vectors frozen from the
	// inherited equation. Boundaries include the light origin and radius.
	assert(Near(BaselineDistanceAttenuation(0.0f, 64.0f, 1500.0f, 0.0f), 1500.0f));
	assert(Near(BaselineDistanceAttenuation(8.0f, 64.0f, 1500.0f, 0.0f), 23.065656f, 1.0e-4f));
	assert(Near(BaselineDistanceAttenuation(32.0f, 64.0f, 1500.0f, 0.0f), 1.2862043f, 1.0e-5f));
	assert(Near(BaselineDistanceAttenuation(64.0f, 64.0f, 1500.0f, 0.0f), 0.0f));
	assert(Near(BaselineDistanceAttenuation(8.0f, 64.0f, 1500.0f, 1.0f), 0.875f));
	assert(Near(BaselineDistanceAttenuation(8.0f, 64.0f, 1500.0f, 0.5f), 11.970328f, 1.0e-4f));
	assert(Near(BaselineDistanceAttenuation(80.0f, 64.0f, 1500.0f, 0.25f), 0.0f));

	// Spotlight edge behavior: exact outer edge is zero, exact inner edge is
	// one, and the midpoint of the cosine interval is exactly one half.
	const float outer = std::cos(25.0f * 3.14159265359f / 180.0f);
	const float inner = std::cos(10.0f * 3.14159265359f / 180.0f);
	assert(Near(BaselineSpotSmoothStep(outer, inner, outer - 0.01f), 0.0f));
	assert(Near(BaselineSpotSmoothStep(outer, inner, outer), 0.0f));
	assert(Near(BaselineSpotSmoothStep(outer, inner, (outer + inner) * 0.5f), 0.5f));
	assert(Near(BaselineSpotSmoothStep(outer, inner, inner), 1.0f));
	assert(Near(BaselineSpotSmoothStep(outer, inner, inner + 0.01f), 1.0f));

	return 0;
}
