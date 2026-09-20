#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <tuple>
#include <vector>

// PF-015: deterministic shadow-map overflow selection contract.
// The inherited 1D shadow map has exactly 1024 light rows. When the eligible
// set fits, caller order is intentionally preserved. Only overflow invokes the
// spatial key ordering below.
constexpr std::size_t HWShadowMapLightCapacity = 1024;

struct HWShadowSelectionKey
{
	double DistanceSquared = 0.0;
	double X = 0.0;
	double Y = 0.0;
	double Z = 0.0;
	float Radius = 0.0f;
	float Strength = 0.0f;
	float Linearity = 0.0f;
	float SoftShadowRadius = 0.0f;
	double LightDefIntensity = 0.0;
	int Red = 0;
	int Green = 0;
	int Blue = 0;
	int Intensity = 0;
	int SecondaryIntensity = 0;
	uint8_t LightType = 0;
	bool Subtractive = false;
	bool Additive = false;
	bool Spot = false;
};

inline bool HWShadowSelectionLess(const HWShadowSelectionKey& a, const HWShadowSelectionKey& b)
{
	return std::tie(a.DistanceSquared, a.X, a.Y, a.Z, a.Radius, a.Strength,
		a.Linearity, a.SoftShadowRadius, a.LightDefIntensity,
		a.Red, a.Green, a.Blue, a.Intensity, a.SecondaryIntensity,
		a.LightType, a.Subtractive, a.Additive, a.Spot) <
		std::tie(b.DistanceSquared, b.X, b.Y, b.Z, b.Radius, b.Strength,
			b.Linearity, b.SoftShadowRadius, b.LightDefIntensity,
			b.Red, b.Green, b.Blue, b.Intensity, b.SecondaryIntensity,
			b.LightType, b.Subtractive, b.Additive, b.Spot);
}

template<class Payload>
struct HWShadowSelectionCandidate
{
	Payload Value;
	HWShadowSelectionKey Key;
};

// Preserve the exact inherited <=capacity ordering. On overflow, nearest
// lights win first and the remaining semantic fields provide deterministic
// tie-breaking independent of linked-list traversal order. Exact-key ties are
// renderer-equivalent for this selector; stable_sort retains caller order only
// inside that semantic-equivalence class.
template<class Payload>
inline void HWSelectShadowCandidates(std::vector<HWShadowSelectionCandidate<Payload>>& candidates,
	std::size_t capacity = HWShadowMapLightCapacity)
{
	if (candidates.size() <= capacity)
		return;

	std::stable_sort(candidates.begin(), candidates.end(),
		[](const auto& a, const auto& b) { return HWShadowSelectionLess(a.Key, b.Key); });
	candidates.resize(capacity);
}
