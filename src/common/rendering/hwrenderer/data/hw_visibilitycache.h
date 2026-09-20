#pragma once

#include <cstdint>

// PF-015: visibility cache reuse is valid only when every spatial input that
// can change the LevelMesh trace remains equivalent. PF-010 pass identity is
// deliberately not included: it changes every render pass even when the trace
// inputs are identical. The stable portal-group coordinate context is included.
struct HWVisibilityCacheValidity
{
	bool ActorPositionChanged = false;
	bool WorldQueryChanged = false;
	bool PortalContextChanged = false;
	bool LightStateChanged = false;

	bool CanReuse() const
	{
		return !ActorPositionChanged && !WorldQueryChanged &&
			!PortalContextChanged && !LightStateChanged;
	}
};

inline HWVisibilityCacheValidity HWCheckVisibilityCacheValidity(
	bool actorPositionChanged,
	uint64_t cachedQueryEpoch,
	uint64_t currentQueryEpoch,
	int cachedPortalGroup,
	int currentPortalGroup,
	bool lightStateChanged)
{
	HWVisibilityCacheValidity result;
	result.ActorPositionChanged = actorPositionChanged;
	result.WorldQueryChanged = cachedQueryEpoch != currentQueryEpoch;
	result.PortalContextChanged = cachedPortalGroup != currentPortalGroup;
	result.LightStateChanged = lightStateChanged;
	return result;
}
