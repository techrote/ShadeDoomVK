#include "hw_resourcegeneration.h"

#include <cassert>

int main()
{
	FRendererResourceGenerationTable slots;

	auto first = slots.Activate(7, 3);
	assert(first.IsSet());
	assert(first.Generation == 1);
	assert(first.Epoch == 1);
	assert(slots.Validate(first));

	assert(slots.Retire(7));
	assert(!slots.Validate(first));
	assert(slots.GetStats().StaleRejects == 1);

	auto second = slots.Activate(7, 3);
	assert(second.IsSet());
	assert(second.Generation != first.Generation);
	assert(slots.Validate(second));

	slots.Reset();
	assert(!slots.Validate(second));
	auto third = slots.Activate(7, 3);
	assert(third.Epoch != second.Epoch);
	assert(slots.Validate(third));

	auto replacement = slots.Activate(7, 3);
	assert(replacement.Generation != third.Generation);
	assert(!slots.Validate(third));
	assert(slots.Validate(replacement));

	assert(!slots.Retire(99));
	const auto& slotStats = slots.GetStats();
	assert(slotStats.Activations == 4);
	assert(slotStats.Retirements == 1);
	assert(slotStats.Resets == 1);
	assert(slotStats.StaleRejects == 3);
	assert(slotStats.InvalidRetires == 1);
	assert(slotStats.DuplicateActivations == 1);

	FRendererEpoch epoch;
	auto before = epoch.Snapshot();
	assert(epoch.Validate(before));
	epoch.Invalidate();
	assert(!epoch.Validate(before));
	auto after = epoch.Snapshot();
	assert(after.Generation != before.Generation);
	assert(epoch.Validate(after));
	assert(epoch.GetStats().Invalidations == 1);
	assert(epoch.GetStats().StaleRejects == 1);

	return 0;
}
