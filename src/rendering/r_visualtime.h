#pragma once

#include <chrono>
#include <cmath>
#include <cstdint>

namespace RenderVisualTime
{
enum class Reason : uint8_t
{
	None,
	FirstFrame,
	ExplicitReset,
	Pause,
	Resume,
	LevelLoad,
	Wipe,
	CameraCut,
	LongFrameClamped,
	ClockRollback,
	InvalidTimestamp,
	RepeatedTimestamp,
	InterpolationDisabled,
};

inline const char* ReasonName(Reason reason)
{
	switch (reason)
	{
	case Reason::None: return "none";
	case Reason::FirstFrame: return "first-frame";
	case Reason::ExplicitReset: return "explicit-reset";
	case Reason::Pause: return "pause";
	case Reason::Resume: return "resume";
	case Reason::LevelLoad: return "level-load";
	case Reason::Wipe: return "wipe";
	case Reason::CameraCut: return "camera-cut";
	case Reason::LongFrameClamped: return "long-frame-clamped";
	case Reason::ClockRollback: return "clock-rollback";
	case Reason::InvalidTimestamp: return "invalid-timestamp";
	case Reason::RepeatedTimestamp: return "repeated-timestamp";
	case Reason::InterpolationDisabled: return "interpolation-disabled";
	}
	return "unknown";
}

struct Sample
{
	double DeltaSeconds = 0.0;
	double AccumulatedSeconds = 0.0;
	double TimestampSeconds = 0.0;
	uint64_t Generation = 0;
	uint64_t MainFrame = 0;
	bool DeltaValid = false;
	bool InterpolationValid = false;
	bool Clamped = false;
	Reason Discontinuity = Reason::FirstFrame;
};

class Clock
{
public:
	static constexpr double MaxDeltaSeconds = 0.2;

	void Reset(Reason reason = Reason::ExplicitReset)
	{
		if (reason == Reason::None) reason = Reason::ExplicitReset;
		BumpGeneration();
		HasPrevious = false;
		WasPaused = false;
		PendingReason = reason;
		Current.DeltaSeconds = 0.0;
		Current.AccumulatedSeconds = AccumulatedSeconds;
		Current.TimestampSeconds = 0.0;
		Current.Generation = Generation;
		Current.MainFrame = MainFrames;
		Current.DeltaValid = false;
		Current.InterpolationValid = false;
		Current.Clamped = false;
		Current.Discontinuity = reason;
	}

	Sample AdvanceMain(double timestampSeconds, bool paused, bool interpolationEnabled)
	{
		++MainFrames;
		Current.MainFrame = MainFrames;
		Current.TimestampSeconds = std::isfinite(timestampSeconds) ? timestampSeconds : 0.0;
		Current.DeltaSeconds = 0.0;
		Current.AccumulatedSeconds = AccumulatedSeconds;
		Current.DeltaValid = false;
		Current.InterpolationValid = false;
		Current.Clamped = false;

		if (!std::isfinite(timestampSeconds) || timestampSeconds < 0.0)
		{
			BumpGeneration();
			HasPrevious = false;
			WasPaused = paused;
			PendingReason = Reason::None;
			Current.Generation = Generation;
			Current.Discontinuity = Reason::InvalidTimestamp;
			return Current;
		}

		if (paused)
		{
			PreviousTimestamp = timestampSeconds;
			HasPrevious = true;
			if (!WasPaused) BumpGeneration();
			WasPaused = true;
			PendingReason = Reason::None;
			Current.Generation = Generation;
			Current.Discontinuity = Reason::Pause;
			return Current;
		}

		if (WasPaused)
		{
			WasPaused = false;
			PreviousTimestamp = timestampSeconds;
			HasPrevious = true;
			BumpGeneration();
			PendingReason = Reason::None;
			Current.Generation = Generation;
			Current.Discontinuity = Reason::Resume;
			return Current;
		}

		if (!HasPrevious)
		{
			PreviousTimestamp = timestampSeconds;
			HasPrevious = true;
			if (Generation == 0) BumpGeneration();
			Current.Generation = Generation;
			Current.Discontinuity = PendingReason == Reason::None ? Reason::FirstFrame : PendingReason;
			PendingReason = Reason::None;
			return Current;
		}

		const double rawDelta = timestampSeconds - PreviousTimestamp;
		PreviousTimestamp = timestampSeconds;
		if (rawDelta < 0.0)
		{
			BumpGeneration();
			Current.Generation = Generation;
			Current.Discontinuity = Reason::ClockRollback;
			return Current;
		}

		if (rawDelta > MaxDeltaSeconds)
		{
			AccumulatedSeconds += MaxDeltaSeconds;
			BumpGeneration();
			Current.DeltaSeconds = MaxDeltaSeconds;
			Current.AccumulatedSeconds = AccumulatedSeconds;
			Current.Generation = Generation;
			Current.DeltaValid = true;
			Current.InterpolationValid = false;
			Current.Clamped = true;
			Current.Discontinuity = Reason::LongFrameClamped;
			return Current;
		}

		AccumulatedSeconds += rawDelta;
		Current.DeltaSeconds = rawDelta;
		Current.AccumulatedSeconds = AccumulatedSeconds;
		Current.Generation = Generation;
		Current.DeltaValid = true;
		Current.InterpolationValid = interpolationEnabled;
		Current.Discontinuity = rawDelta == 0.0 ? Reason::RepeatedTimestamp :
			interpolationEnabled ? Reason::None : Reason::InterpolationDisabled;
		return Current;
	}

	const Sample& Snapshot() const { return Current; }

private:
	void BumpGeneration()
	{
		++Generation;
		if (Generation == 0) ++Generation;
	}

	double PreviousTimestamp = 0.0;
	double AccumulatedSeconds = 0.0;
	uint64_t Generation = 0;
	uint64_t MainFrames = 0;
	bool HasPrevious = false;
	bool WasPaused = false;
	Reason PendingReason = Reason::None;
	Sample Current;
};

inline double MonotonicTimestampSeconds()
{
	using namespace std::chrono;
	return duration<double>(steady_clock::now().time_since_epoch()).count();
}

inline Clock& RuntimeClock()
{
	static Clock clock;
	return clock;
}

inline void ResetRuntime(Reason reason = Reason::ExplicitReset)
{
	RuntimeClock().Reset(reason);
}

inline double InterpolationFraction(double ticFraction, bool continuityValid)
{
	if (!continuityValid || !std::isfinite(ticFraction)) return 1.0;
	if (ticFraction <= 0.0) return 0.0;
	if (ticFraction >= 1.0) return 1.0;
	return ticFraction;
}

inline double InterpolateValue(double previous, double current, double fraction, bool enabled)
{
	if (!enabled) return current;
	if (!std::isfinite(previous) || !std::isfinite(current) || !std::isfinite(fraction)) return current;
	if (fraction <= 0.0) return previous;
	if (fraction >= 1.0) return current;
	const double result = previous + (current - previous) * fraction;
	return std::isfinite(result) ? result : current;
}
}
