#include "hw_lightcompat.h"

#include <algorithm>
#include <cassert>
#include <cmath>

namespace
{
struct Color3
{
	float r;
	float g;
	float b;
};

float BaselineDistanceAttenuation(float dist, float radius, float strength, float linearity)
{
	float a = dist / radius;
	float b = std::clamp(1.0f - a * a * a * a, 0.0f, 1.0f);
	float inverseSquare = (b * b) / (dist * dist + 1.0f) * strength;
	float linear = std::clamp((radius - dist) / radius, 0.0f, 1.0f);
	return inverseSquare * (1.0f - linearity) + linear * linearity;
}

float BaselineLightStrength(float authoringRadius)
{
	const float renderRadius = authoringRadius * 2.0f;
	return std::min(1500.0f, (renderRadius * renderRadius) / 10.0f);
}

Color3 BaselineGpuPackedColor(int red, int green, int blue, float lightDefIntensity,
	float alpha, bool multiplyAlpha, bool additive, bool subtractive)
{
	float scale = additive ? HWLightCompat::AdditiveGpuColorScale : 1.0f;
	if (multiplyAlpha)
		scale *= alpha;
	scale *= lightDefIntensity;

	Color3 color{
		red / 255.0f * scale,
		green / 255.0f * scale,
		blue / 255.0f * scale,
	};

	if (subtractive)
	{
		const float length = std::sqrt(color.r * color.r + color.g * color.g + color.b * color.b);
		color = {length - color.r, length - color.g, length - color.b};
	}
	return color;
}

Color3 BaselineCpuAggregateColor(int red, int green, int blue, float lightDefIntensity,
	float alpha, bool multiplyAlpha, bool subtractive)
{
	float scale = multiplyAlpha ? alpha : 1.0f;
	scale *= lightDefIntensity;

	Color3 color{
		red / 255.0f * scale,
		green / 255.0f * scale,
		blue / 255.0f * scale,
	};

	if (subtractive)
	{
		const float length = std::sqrt(color.r * color.r + color.g * color.g + color.b * color.b);
		color = {-(length - color.r), -(length - color.g), -(length - color.b)};
	}
	return color;
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

void AssertColorNear(const Color3& actual, const Color3& expected, float tolerance = 1.0e-5f)
{
	assert(Near(actual.r, expected.r, tolerance));
	assert(Near(actual.g, expected.g, tolerance));
	assert(Near(actual.b, expected.b, tolerance));
}
}

int main()
{
	static_assert(HWLightCompat::AdditiveGpuColorScale == 0.2f);
	static_assert(HWLightCompat::SunProxyDistance == 100000.0f);
	static_assert(HWLightCompat::SunProxyRadius == 100000000.0f);
	static_assert(HWLightCompat::SunProxyStrength == 1500.0f);

	// Authoring and packing boundaries.
	assert(Near(HWLightCompat::NormalizeColorChannel(0), 0.0f));
	assert(Near(HWLightCompat::NormalizeColorChannel(128), 128.0f / 255.0f));
	assert(Near(HWLightCompat::NormalizeColorChannel(255), 1.0f));
	assert(Near(HWLightCompat::ClampLinearity(-1.0f), 0.0f));
	assert(Near(HWLightCompat::ClampLinearity(0.0f), 0.0f));
	assert(Near(HWLightCompat::ClampLinearity(0.5f), 0.5f));
	assert(Near(HWLightCompat::ClampLinearity(1.0f), 1.0f));
	assert(Near(HWLightCompat::ClampLinearity(2.0f), 1.0f));
	assert(Near(BaselineLightStrength(0.0f), 0.0f));
	assert(Near(BaselineLightStrength(10.0f), 40.0f));
	assert(Near(BaselineLightStrength(100.0f), 1500.0f));

	// GLDEFS intensity and RF2_LIGHTMULTALPHA remain multiplicative before
	// color-class conversion. Additive packing alone receives the 0.2 bridge.
	AssertColorNear(
		BaselineGpuPackedColor(255, 128, 0, 1.5f, 0.5f, true, false, false),
		{0.75f, (128.0f / 255.0f) * 0.75f, 0.0f});
	AssertColorNear(
		BaselineGpuPackedColor(255, 128, 64, 1.0f, 1.0f, false, true, false),
		{0.2f, (128.0f / 255.0f) * 0.2f, (64.0f / 255.0f) * 0.2f});

	// GPU subtractive lights store a positive complement and are subtracted by
	// the shader; the CPU aggregate path stores the corresponding negative RGB.
	const Color3 gpuSubtractive = BaselineGpuPackedColor(64, 128, 255, 1.0f, 1.0f, false, false, true);
	const Color3 cpuSubtractive = BaselineCpuAggregateColor(64, 128, 255, 1.0f, 1.0f, false, true);
	assert(gpuSubtractive.r >= 0.0f && gpuSubtractive.g >= 0.0f && gpuSubtractive.b >= 0.0f);
	assert(Near(gpuSubtractive.r, -cpuSubtractive.r));
	assert(Near(gpuSubtractive.g, -cpuSubtractive.g));
	assert(Near(gpuSubtractive.b, -cpuSubtractive.b));
	AssertColorNear(
		BaselineGpuPackedColor(255, 0, 0, 1.0f, 1.0f, false, false, true),
		{0.0f, 1.0f, 1.0f});

	// Representative inverse-square/linear blend vectors frozen from the
	// inherited equation. Boundaries include the light origin and radius.
	assert(Near(BaselineDistanceAttenuation(0.0f, 64.0f, 1500.0f, 0.0f), 1500.0f));
	assert(Near(BaselineDistanceAttenuation(8.0f, 64.0f, 1500.0f, 0.0f), 23.065656f, 1.0e-4f));
	assert(Near(BaselineDistanceAttenuation(32.0f, 64.0f, 1500.0f, 0.0f), 1.2862043f, 1.0e-5f));
	assert(Near(BaselineDistanceAttenuation(64.0f, 64.0f, 1500.0f, 0.0f), 0.0f));
	assert(Near(BaselineDistanceAttenuation(8.0f, 64.0f, 1500.0f, 1.0f), 0.875f));
	assert(Near(BaselineDistanceAttenuation(8.0f, 64.0f, 1500.0f, 0.5f), 11.970328f, 1.0e-4f));
	assert(Near(BaselineDistanceAttenuation(80.0f, 64.0f, 1500.0f, 0.25f), 0.0f));

	// Deterministic moving-light state samples. These protect the response curve
	// at several interior points instead of only the origin/radius endpoints.
	assert(Near(BaselineDistanceAttenuation(16.0f, 64.0f, 1500.0f, 0.0f), 5.7910666f, 1.0e-4f));
	assert(Near(BaselineDistanceAttenuation(24.0f, 64.0f, 1500.0f, 0.0f), 2.4978516f, 1.0e-4f));
	assert(Near(BaselineDistanceAttenuation(40.0f, 64.0f, 1500.0f, 0.0f), 0.6728051f, 1.0e-5f));
	assert(Near(BaselineDistanceAttenuation(48.0f, 64.0f, 1500.0f, 0.0f), 0.3041001f, 1.0e-5f));
	assert(Near(BaselineDistanceAttenuation(56.0f, 64.0f, 1500.0f, 0.0f), 0.08188347f, 1.0e-5f));

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
