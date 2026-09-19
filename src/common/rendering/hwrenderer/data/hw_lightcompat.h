//
//---------------------------------------------------------------------------
//
// ShadeDoomVK lighting compatibility bridge.
//
// These values are inherited rendering calibration, not physical units.
// Keep CPU authoring/packing and shader-side compatibility documentation in
// sync with docs/shadedoomvk/PF-011-LIGHTING-COMPATIBILITY-CONTRACT.md.
//
//---------------------------------------------------------------------------

#pragma once

#include <algorithm>

namespace HWLightCompat
{
	constexpr float AdditiveGpuColorScale = 0.2f;
	constexpr float SunProxyDistance = 100000.0f;
	constexpr float SunProxyRadius = 100000000.0f;
	constexpr float SunProxyStrength = 1500.0f;

	inline float NormalizeColorChannel(int channel)
	{
		return channel / 255.0f;
	}

	inline float ClampLinearity(float linearity)
	{
		return std::clamp(linearity, 0.0f, 1.0f);
	}
}
