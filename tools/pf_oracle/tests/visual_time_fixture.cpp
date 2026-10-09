#include "r_visualtime.h"
#include "hw_rendercontext.h"
#include "hw_visualtime.h"

#include <cassert>
#include <cmath>

int main()
{
	using namespace RenderVisualTime;

	Clock clock;
	auto sample = clock.AdvanceMain(10.0, false, true);
	assert(!sample.DeltaValid && !sample.InterpolationValid);
	assert(sample.Discontinuity == Reason::FirstFrame);
	assert(sample.DeltaSeconds == 0.0 && sample.AccumulatedSeconds == 0.0);

	sample = clock.AdvanceMain(10.01, false, true);
	assert(sample.DeltaValid && sample.InterpolationValid);
	assert(std::abs(sample.DeltaSeconds - 0.01) < 1e-12);
	const auto accumulated = sample.AccumulatedSeconds;
	sample = clock.AdvanceMain(10.01, false, true);
	assert(sample.DeltaValid && sample.DeltaSeconds == 0.0);
	assert(sample.AccumulatedSeconds == accumulated && sample.Discontinuity == Reason::RepeatedTimestamp);

	sample = clock.AdvanceMain(11.0, false, true);
	assert(sample.DeltaValid && !sample.InterpolationValid && sample.Clamped);
	assert(sample.DeltaSeconds == Clock::MaxDeltaSeconds && sample.Discontinuity == Reason::LongFrameClamped);
	const auto generation = sample.Generation;
	sample = clock.AdvanceMain(10.5, false, true);
	assert(!sample.DeltaValid && sample.Discontinuity == Reason::ClockRollback && sample.Generation != generation);

	sample = clock.AdvanceMain(10.6, true, true);
	assert(!sample.DeltaValid && sample.Discontinuity == Reason::Pause);
	const auto pausedAccumulated = sample.AccumulatedSeconds;
	sample = clock.AdvanceMain(50.0, true, true);
	assert(!sample.DeltaValid && sample.AccumulatedSeconds == pausedAccumulated);
	sample = clock.AdvanceMain(50.1, false, true);
	assert(!sample.DeltaValid && sample.Discontinuity == Reason::Resume);
	assert(sample.AccumulatedSeconds == pausedAccumulated);
	sample = clock.AdvanceMain(50.11, false, true);
	assert(sample.DeltaValid && sample.InterpolationValid);

	// Disabling snaps to current immediately. Re-enabling also snaps for one
	// sample so presentation cannot jump backwards from a current endpoint to
	// an older mid-tic value; the following sample may interpolate again.
	sample = clock.AdvanceMain(50.12, false, false);
	assert(sample.DeltaValid && !sample.InterpolationValid);
	assert(sample.Discontinuity == Reason::InterpolationDisabled);
	const auto disabledGeneration = sample.Generation;
	sample = clock.AdvanceMain(50.13, false, true);
	assert(sample.DeltaValid && !sample.InterpolationValid);
	assert(sample.Discontinuity == Reason::InterpolationEnabled);
	assert(sample.Generation != disabledGeneration);
	sample = clock.AdvanceMain(50.14, false, true);
	assert(sample.DeltaValid && sample.InterpolationValid);

	clock.Reset(Reason::LevelLoad);
	sample = clock.AdvanceMain(60.0, false, true);
	assert(!sample.DeltaValid && sample.Discontinuity == Reason::LevelLoad);
	clock.Reset(Reason::Wipe);
	sample = clock.AdvanceMain(61.0, false, true);
	assert(!sample.DeltaValid && sample.Discontinuity == Reason::Wipe);
	clock.Reset(Reason::CameraCut);
	sample = clock.AdvanceMain(62.0, false, true);
	assert(!sample.DeltaValid && sample.Discontinuity == Reason::CameraCut);

	sample = clock.AdvanceMain(NAN, false, true);
	assert(!sample.DeltaValid && sample.Discontinuity == Reason::InvalidTimestamp);
	sample = clock.AdvanceMain(INFINITY, false, true);
	assert(!sample.DeltaValid && sample.Discontinuity == Reason::InvalidTimestamp);

	assert(InterpolationFraction(0.0, true) == 0.0);
	assert(InterpolationFraction(1.0, true) == 1.0);
	assert(InterpolationFraction(0.25, true) == 0.25);
	assert(InterpolationFraction(-1.0, true) == 0.0);
	assert(InterpolationFraction(2.0, true) == 1.0);
	assert(InterpolationFraction(NAN, true) == 1.0);
	assert(InterpolationFraction(0.5, false) == 1.0);

	assert(InterpolateValue(0.2, 0.8, 0.0, true) == 0.2);
	assert(InterpolateValue(0.2, 0.8, 1.0, true) == 0.8);
	const double alpha25 = InterpolateValue(0.2, 0.8, 0.25, true);
	const double alpha50 = InterpolateValue(0.2, 0.8, 0.50, true);
	const double alpha75 = InterpolateValue(0.2, 0.8, 0.75, true);
	assert(0.2 < alpha25 && alpha25 < alpha50 && alpha50 < alpha75 && alpha75 < 0.8);
	assert(InterpolateValue(1.0, 2.0, 0.5, false) == 2.0);
	assert(InterpolateValue(1.0, 2.0, NAN, true) == 2.0);

	int simulationTic = 77;
	Clock sixtyHz;
	for (int i = 0; i < 20; ++i) sixtyHz.AdvanceMain(100.0 + i / 60.0, false, true);
	Clock oneFortyFourHz;
	for (int i = 0; i < 48; ++i) oneFortyFourHz.AdvanceMain(100.0 + i / 144.0, false, true);
	Clock twentyHz;
	for (int i = 0; i < 8; ++i) twentyHz.AdvanceMain(100.0 + i / 20.0, false, true);
	assert(simulationTic == 77);

	RuntimeClock().Reset(Reason::ExplicitReset);
	RuntimeClock().AdvanceMain(200.0, false, true);
	const auto live = RuntimeClock().AdvanceMain(200.01, false, true);
	assert(live.DeltaValid);
	const auto before = RuntimeClock().Snapshot();

	HWRenderContextSequence sequence;
	const auto mainEpoch = sequence.BeginEpoch();
	const auto main0 = MakeHWRootRenderContext(HWRenderContextType::MainView, mainEpoch, sequence.AllocateIdentity(), -1, 0);
	const auto main1 = MakeHWRootRenderContext(HWRenderContextType::MainView, mainEpoch, sequence.AllocateIdentity(), -1, 1);
	const auto mainPortal = MakeHWPortalRenderContext(main0, sequence.AllocateIdentity(), true, false);
	const auto nestedMainPortal = MakeHWPortalRenderContext(mainPortal, sequence.AllocateIdentity(), false, true);
	auto visual = GetHWVisualTime(main0);
	assert(visual.Scope == HWVisualTimeScope::MainOwner && visual.AdvancesMainClock);
	assert(visual.Time.DeltaSeconds == before.DeltaSeconds);
	visual = GetHWVisualTime(main1);
	assert(visual.Scope == HWVisualTimeScope::MainSibling && !visual.AdvancesMainClock);
	visual = GetHWVisualTime(mainPortal);
	assert(visual.Scope == HWVisualTimeScope::MainPortal && visual.Time.DeltaSeconds == before.DeltaSeconds);
	visual = GetHWVisualTime(nestedMainPortal);
	assert(visual.Scope == HWVisualTimeScope::MainPortal && visual.Time.DeltaSeconds == before.DeltaSeconds);

	const auto cameraEpoch = sequence.BeginEpoch();
	const auto camera = MakeHWRootRenderContext(HWRenderContextType::CameraTexture, cameraEpoch, sequence.AllocateIdentity(), -1, 0);
	visual = GetHWVisualTime(camera);
	assert(visual.Scope == HWVisualTimeScope::NonMainFallback);
	assert(!visual.Time.DeltaValid && visual.Time.DeltaSeconds == 0.0 && visual.Time.AccumulatedSeconds == 0.0);

	for (int face = 0; face < 6; ++face)
	{
		const auto probeEpoch = sequence.BeginEpoch();
		const auto probe = MakeHWRootRenderContext(HWRenderContextType::LightProbe, probeEpoch, sequence.AllocateIdentity(), face, 0);
		const auto probePortal = MakeHWPortalRenderContext(probe, sequence.AllocateIdentity(), false, true);
		assert(!GetHWVisualTime(probe).Time.DeltaValid);
		assert(!GetHWVisualTime(probePortal).Time.DeltaValid);
	}

	const auto saveEpoch = sequence.BeginEpoch();
	const auto save = MakeHWRootRenderContext(HWRenderContextType::SavePicture, saveEpoch, sequence.AllocateIdentity(), -1, 0);
	assert(!GetHWVisualTime(save).Time.DeltaValid);

	const auto after = RuntimeClock().Snapshot();
	assert(after.MainFrame == before.MainFrame);
	assert(after.Generation == before.Generation);
	assert(after.AccumulatedSeconds == before.AccumulatedSeconds);
	assert(after.DeltaSeconds == before.DeltaSeconds);
	const auto nextMain = RuntimeClock().AdvanceMain(200.02, false, true);
	assert(nextMain.DeltaValid && std::abs(nextMain.DeltaSeconds - 0.01) < 1e-12);

	const auto recreatedEpoch = sequence.BeginEpoch();
	const auto recreatedMain = MakeHWRootRenderContext(HWRenderContextType::MainView, recreatedEpoch, sequence.AllocateIdentity(), -1, 0);
	assert(GetHWVisualTime(recreatedMain).Time.MainFrame == nextMain.MainFrame);
	return 0;
}
