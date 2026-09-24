#include "hw_lightreuse.h"

#include <cassert>
#include <cstdint>
#include <limits>

struct Packed
{
	uint32_t a = 0;
	uint32_t b = 0;
};

int main()
{
	HWLightPackingRevisionClock clock;
	HWLightPackingContextState context;
	HWLightPackingSnapshot<Packed> sourceA;
	HWLightPackingSnapshot<Packed> sourceB;

	const uint64_t epoch1 = context.Begin(1);
	assert(epoch1 == 1);
	Packed packed{ 10, 20 };

	const uint64_t aRevision1 =
		HWCommitLightPackingSnapshot(sourceA, packed, 0, 7, epoch1, clock);
	assert(aRevision1 != 0);
	assert(sourceA.valid);

	Packed reused{};
	int reusedClass = -1;
	uint64_t reusedRevision = 0;
	assert(HWTryReuseLightPackingSnapshot(
		sourceA, epoch1, 7, reused, reusedClass, reusedRevision));
	assert(reused.a == 10 && reused.b == 20);
	assert(reusedClass == 0);
	assert(reusedRevision == aRevision1);

	// Equal bytes in distinct source objects never establish shared identity.
	const uint64_t bRevision1 =
		HWCommitLightPackingSnapshot(sourceB, packed, 0, 7, epoch1, clock);
	assert(bRevision1 != 0);
	assert(bRevision1 != aRevision1);

	// Repeated references to one source are safe only while the exact physical
	// positions still carry that same source revision. Replacing either
	// position with another equal-byte source must force a copy.
	const uint64_t duplicatePrevious[] = { aRevision1, aRevision1 };
	const uint64_t duplicateUnchanged[] = { aRevision1, aRevision1 };
	const uint64_t duplicateReplaced[] = { aRevision1, bRevision1 };
	assert(HWLightUploadClassCanReuse(duplicateUnchanged, duplicatePrevious, 2));
	assert(!HWLightUploadClassCanReuse(duplicateReplaced, duplicatePrevious, 2));

	context.End(epoch1);
	const uint64_t epoch2 = context.Begin(2);
	assert(epoch2 == 2);

	// A new render epoch must execute accepted packing once before it may reuse.
	assert(!HWTryReuseLightPackingSnapshot(
		sourceA, epoch2, 7, reused, reusedClass, reusedRevision));
	const uint64_t aRevision2 =
		HWCommitLightPackingSnapshot(sourceA, packed, 0, 7, epoch2, clock);
	assert(aRevision2 == aRevision1);
	assert(HWTryReuseLightPackingSnapshot(
		sourceA, epoch2, 7, reused, reusedClass, reusedRevision));

	// Packed-state mutation, class transition, and portal-group change each
	// create a new monotonic revision.
	Packed mutated{ 11, 20 };
	const uint64_t mutationRevision =
		HWCommitLightPackingSnapshot(sourceA, mutated, 0, 7, epoch2, clock);
	assert(mutationRevision != aRevision2);
	const uint64_t classRevision =
		HWCommitLightPackingSnapshot(sourceA, mutated, 1, 7, epoch2, clock);
	assert(classRevision != mutationRevision);
	const uint64_t groupRevision =
		HWCommitLightPackingSnapshot(sourceA, mutated, 1, 8, epoch2, clock);
	assert(groupRevision != classRevision);

	// A recreated/reused source starts invalid and therefore cannot inherit the
	// previous object's revision even when its bytes happen to match.
	HWLightPackingSnapshot<Packed> recreated{};
	const uint64_t recreatedRevision =
		HWCommitLightPackingSnapshot(recreated, mutated, 1, 8, epoch2, clock);
	assert(recreatedRevision != 0);
	assert(recreatedRevision != groupRevision);

	// Upload reuse is all-or-nothing for a class. Any unsupported revision 0 or
	// any changed source token forces the accepted copy path.
	const uint64_t previous[] = { aRevision2, bRevision1 };
	const uint64_t unchanged[] = { aRevision2, bRevision1 };
	const uint64_t unsupported[] = { aRevision2, 0 };
	const uint64_t changed[] = { aRevision2, bRevision1 + 100 };
	assert(HWLightUploadClassCanReuse(unchanged, previous, 2));
	assert(!HWLightUploadClassCanReuse(unsupported, previous, 2));
	assert(!HWLightUploadClassCanReuse(changed, previous, 2));

	// Reusing an epoch (including uint64 wrap to an old value) fails closed.
	context.End(epoch2);
	assert(context.Begin(2) == 0);
	assert(context.Disabled());
	assert(context.ActiveEpoch() == 0);

	// Revision exhaustion similarly fails closed before a stale token can wrap.
	HWLightPackingRevisionClock wrapping(
		std::numeric_limits<uint64_t>::max() - 1);
	assert(wrapping.Allocate() == std::numeric_limits<uint64_t>::max() - 1);
	assert(wrapping.Allocate() == 0);
	assert(wrapping.Disabled());

	HWLightPackingSnapshot<Packed> afterWrap{};
	const uint64_t wrapRevision =
		HWCommitLightPackingSnapshot(afterWrap, packed, 0, 7, 3, wrapping);
	assert(wrapRevision == 0);
	assert(!afterWrap.valid);

	return 0;
}
