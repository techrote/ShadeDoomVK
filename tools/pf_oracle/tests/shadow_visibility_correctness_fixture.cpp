#include "hw_shadowselection.h"
#include "hw_visibilitycache.h"

#include <algorithm>
#include <cassert>
#include <cstdint>
#include <vector>

namespace
{
struct Candidate
{
	int id;
	double x;
};

HWShadowSelectionCandidate<Candidate> MakeCandidate(int id, double x, double viewX = 0.0)
{
	HWShadowSelectionCandidate<Candidate> candidate;
	candidate.Value = { id, x };
	candidate.Key.DistanceSquared = (x - viewX) * (x - viewX);
	candidate.Key.X = x;
	candidate.Key.Radius = 64.0f;
	candidate.Key.Strength = 1.0f;
	candidate.Key.Red = id & 255;
	candidate.Key.Green = (id >> 8) & 255;
	candidate.Key.Intensity = 64;
	return candidate;
}

std::vector<int> Ids(const std::vector<HWShadowSelectionCandidate<Candidate>>& candidates)
{
	std::vector<int> ids;
	for (const auto& candidate : candidates)
		ids.push_back(candidate.Value.id);
	return ids;
}
}

int main()
{
	// Below the physical row cap the inherited linked-list order is untouched.
	std::vector<HWShadowSelectionCandidate<Candidate>> below;
	below.push_back(MakeCandidate(3, 300.0));
	below.push_back(MakeCandidate(1, 100.0));
	below.push_back(MakeCandidate(2, 200.0));
	const auto belowBefore = Ids(below);
	HWSelectShadowCandidates(below);
	assert(Ids(below) == belowBefore);

	// The exact boundary is also an identity/order-preserving path.
	std::vector<HWShadowSelectionCandidate<Candidate>> atCap;
	for (int i = 0; i < static_cast<int>(HWShadowMapLightCapacity); ++i)
		atCap.push_back(MakeCandidate(i, 5000.0 - i));
	const auto atCapBefore = Ids(atCap);
	HWSelectShadowCandidates(atCap);
	assert(atCap.size() == HWShadowMapLightCapacity);
	assert(Ids(atCap) == atCapBefore);

	// Overflow chooses the same nearest semantic set even if traversal order is reversed.
	std::vector<HWShadowSelectionCandidate<Candidate>> forward;
	for (int i = 0; i < 1100; ++i)
		forward.push_back(MakeCandidate(i, static_cast<double>(i + 1)));
	auto reverse = forward;
	std::reverse(reverse.begin(), reverse.end());
	HWSelectShadowCandidates(forward);
	HWSelectShadowCandidates(reverse);
	assert(forward.size() == HWShadowMapLightCapacity);
	assert(reverse.size() == HWShadowMapLightCapacity);
	assert(Ids(forward) == Ids(reverse));
	for (int i = 0; i < static_cast<int>(HWShadowMapLightCapacity); ++i)
		assert(forward[i].Value.id == i);

	// Relevance follows the active view position rather than creation order.
	std::vector<HWShadowSelectionCandidate<Candidate>> left;
	std::vector<HWShadowSelectionCandidate<Candidate>> right;
	for (int i = 0; i < 1030; ++i)
	{
		const double x = static_cast<double>(i * 10);
		left.push_back(MakeCandidate(i, x, 0.0));
		right.push_back(MakeCandidate(i, x, 10290.0));
	}
	HWSelectShadowCandidates(left);
	HWSelectShadowCandidates(right);
	assert(left.front().Value.id == 0);
	assert(right.front().Value.id == 1029);
	assert(left.back().Value.id != right.back().Value.id);

	// Equal-distance candidates are ordered by semantic spatial/light fields,
	// not caller order or pointer identity.
	auto tieA = MakeCandidate(7, -10.0);
	auto tieB = MakeCandidate(8, 10.0);
	tieA.Key.Red = tieB.Key.Red = 10;
	tieA.Key.Green = tieB.Key.Green = 20;
	tieA.Key.DistanceSquared = tieB.Key.DistanceSquared = 100.0;
	std::vector<HWShadowSelectionCandidate<Candidate>> tieForward;
	for (int i = 0; i < 1023; ++i)
		tieForward.push_back(MakeCandidate(100 + i, static_cast<double>(1000 + i)));
	tieForward.push_back(tieB);
	tieForward.push_back(tieA);
	auto tieReverse = tieForward;
	std::reverse(tieReverse.begin(), tieReverse.end());
	HWSelectShadowCandidates(tieForward);
	HWSelectShadowCandidates(tieReverse);
	assert(tieForward.front().Value.id == 7);
	assert(tieReverse.front().Value.id == 7);

	// Stable actor/light/world inputs permit reuse.
	auto valid = HWCheckVisibilityCacheValidity(false, 9, 9, 2, 2, false);
	assert(valid.CanReuse());

	// A moving world occluder advances PF-004 Query and must force a miss even
	// when actor and light are stationary.
	auto movedWorld = HWCheckVisibilityCacheValidity(false, 9, 10, 2, 2, false);
	assert(!movedWorld.CanReuse());
	assert(movedWorld.WorldQueryChanged);

	// Portal-group displacement is spatial cache identity; transient PF-010
	// pass IDs are intentionally not required when this stable context matches.
	auto portalChanged = HWCheckVisibilityCacheValidity(false, 10, 10, 2, 3, false);
	assert(!portalChanged.CanReuse());
	assert(portalChanged.PortalContextChanged);

	auto actorMoved = HWCheckVisibilityCacheValidity(true, 10, 10, 3, 3, false);
	assert(!actorMoved.CanReuse());
	assert(actorMoved.ActorPositionChanged);

	auto lightMoved = HWCheckVisibilityCacheValidity(false, 10, 10, 3, 3, true);
	assert(!lightMoved.CanReuse());
	assert(lightMoved.LightStateChanged);

	return 0;
}
