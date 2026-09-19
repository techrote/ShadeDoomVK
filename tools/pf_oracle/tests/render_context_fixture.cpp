#include "hw_rendercontext.h"

#include <cassert>
#include <cstring>

int main()
{
	HWRenderContextSequence sequence;
	const auto epoch = sequence.BeginEpoch();
	assert(epoch != 0);

	const auto main = MakeHWRootRenderContext(
		HWRenderContextType::MainView, epoch, sequence.AllocateIdentity(), -1, 0);
	assert(main.type == HWRenderContextType::MainView);
	assert(main.rootType == HWRenderContextType::MainView);
	assert(main.epoch == epoch);
	assert(main.identity != 0);
	assert(!main.HasParent());
	assert(main.recursionDepth == 0);
	assert(main.probeFace == -1);
	assert(main.mainView);
	assert(main.postprocessEligible);
	assert(main.historyEligible);
	assert(std::strcmp(HWRenderContextTypeName(main.type), "main") == 0);

	const auto camera = MakeHWRootRenderContext(
		HWRenderContextType::CameraTexture, epoch, sequence.AllocateIdentity(), -1, 0);
	assert(camera.identity != main.identity);
	assert(!camera.mainView);
	assert(!camera.postprocessEligible);
	assert(!camera.historyEligible);

	const auto save = MakeHWRootRenderContext(
		HWRenderContextType::SavePicture, epoch, sequence.AllocateIdentity(), -1, 0);
	assert(!save.mainView);
	assert(save.postprocessEligible);
	assert(!save.historyEligible);

	uint64_t probeIdentities[6] = {};
	for (int face = 0; face < 6; ++face)
	{
		const auto probe = MakeHWRootRenderContext(
			HWRenderContextType::LightProbe, epoch, sequence.AllocateIdentity(), face, 0);
		assert(probe.type == HWRenderContextType::LightProbe);
		assert(probe.rootType == HWRenderContextType::LightProbe);
		assert(probe.probeFace == face);
		assert(!probe.mainView);
		assert(!probe.postprocessEligible);
		assert(!probe.historyEligible);
		for (int previous = 0; previous < face; ++previous)
			assert(probe.identity != probeIdentities[previous]);
		probeIdentities[face] = probe.identity;
	}

	// Mirror parity is the inherited XOR rule. A recursive child has a distinct
	// identity, keeps the root classification, and may never claim main history.
	const auto lineMirror = MakeHWPortalRenderContext(
		main, sequence.AllocateIdentity(), true, false);
	assert(lineMirror.IsPortal());
	assert(lineMirror.rootType == HWRenderContextType::MainView);
	assert(lineMirror.epoch == main.epoch);
	assert(lineMirror.parentIdentity == main.identity);
	assert(lineMirror.recursionDepth == 1);
	assert(lineMirror.lineMirror);
	assert(!lineMirror.planeMirror);
	assert(lineMirror.mirrored);
	assert(!lineMirror.mainView);
	assert(!lineMirror.postprocessEligible);
	assert(!lineMirror.historyEligible);

	// Two active mirror dimensions cancel handedness while still remaining
	// individually inspectable, and recursion/parent identity must advance.
	const auto doubleMirror = MakeHWPortalRenderContext(
		lineMirror, sequence.AllocateIdentity(), true, true);
	assert(doubleMirror.parentIdentity == lineMirror.identity);
	assert(doubleMirror.recursionDepth == 2);
	assert(doubleMirror.lineMirror);
	assert(doubleMirror.planeMirror);
	assert(!doubleMirror.mirrored);

	// Probe recursion retains the originating cubemap face but remains a portal
	// pass, preventing accidental reuse as a top-level probe or main history.
	const auto probeRoot = MakeHWRootRenderContext(
		HWRenderContextType::LightProbe, epoch, sequence.AllocateIdentity(), 5, 0);
	const auto probePortal = MakeHWPortalRenderContext(
		probeRoot, sequence.AllocateIdentity(), false, true);
	assert(probePortal.type == HWRenderContextType::Portal);
	assert(probePortal.rootType == HWRenderContextType::LightProbe);
	assert(probePortal.probeFace == 5);
	assert(probePortal.parentIdentity == probeRoot.identity);
	assert(probePortal.mirrored);
	assert(!probePortal.historyEligible);

	// Classifier boundaries preserve the existing RenderViewpoint booleans and
	// give probe faces priority over offscreen camera classification.
	assert(ClassifyHWRenderContext(true, true, -1) == HWRenderContextType::MainView);
	assert(ClassifyHWRenderContext(true, false, -1) == HWRenderContextType::SavePicture);
	assert(ClassifyHWRenderContext(false, false, -1) == HWRenderContextType::CameraTexture);
	assert(ClassifyHWRenderContext(false, false, 0) == HWRenderContextType::LightProbe);
	assert(ClassifyHWRenderContext(true, true, 5) == HWRenderContextType::LightProbe);

	// A new top-level invocation advances the epoch and may reuse local identity
	// numbers safely only because the pair (epoch, identity) is the contract.
	const auto nextEpoch = sequence.BeginEpoch();
	assert(nextEpoch != epoch);
	const auto nextMain = MakeHWRootRenderContext(
		HWRenderContextType::MainView, nextEpoch, sequence.AllocateIdentity(), -1, 0);
	assert(nextMain.identity == 1);
	assert(nextMain.epoch != main.epoch);

	return 0;
}
