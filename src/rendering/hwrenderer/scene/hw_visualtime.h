#pragma once

#include "r_visualtime.h"
#include "hw_rendercontext.h"

enum class HWVisualTimeScope : uint8_t
{
	MainOwner,
	MainSibling,
	MainPortal,
	NonMainFallback,
};

inline const char* HWVisualTimeScopeName(HWVisualTimeScope scope)
{
	switch (scope)
	{
	case HWVisualTimeScope::MainOwner: return "main-owner";
	case HWVisualTimeScope::MainSibling: return "main-sibling";
	case HWVisualTimeScope::MainPortal: return "main-portal";
	case HWVisualTimeScope::NonMainFallback: return "non-main-fallback";
	}
	return "unknown";
}

struct HWVisualTimeSample
{
	RenderVisualTime::Sample Time;
	HWVisualTimeScope Scope = HWVisualTimeScope::NonMainFallback;
	bool AdvancesMainClock = false;
};

inline HWVisualTimeSample GetHWVisualTime(const HWRenderContext& context)
{
	HWVisualTimeSample result;
	result.Time = RenderVisualTime::RuntimeClock().Snapshot();
	if (context.rootType != HWRenderContextType::MainView)
	{
		result.Time = {};
		result.Time.Discontinuity = RenderVisualTime::Reason::None;
		result.Scope = HWVisualTimeScope::NonMainFallback;
		return result;
	}

	if (context.IsPortal())
	{
		result.Scope = HWVisualTimeScope::MainPortal;
	}
	else if (context.eyeIndex == 0)
	{
		result.Scope = HWVisualTimeScope::MainOwner;
		result.AdvancesMainClock = true;
	}
	else
	{
		result.Scope = HWVisualTimeScope::MainSibling;
	}
	return result;
}

inline bool HWVisualInterpolationContinuity(const HWRenderContext& context)
{
	if (context.rootType != HWRenderContextType::MainView) return true;
	return RenderVisualTime::RuntimeClock().Snapshot().InterpolationValid;
}

inline double HWVisualInterpolationFraction(const HWRenderContext& context, double ticFraction)
{
	return RenderVisualTime::InterpolationFraction(ticFraction, HWVisualInterpolationContinuity(context));
}
