#pragma once

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>

// PF-017 source-owned temporal light reuse primitives.
//
// Revision value 0 is reserved for "unqualified / copy through the accepted
// path". Exhaustion disables reuse instead of wrapping into a stale token.
class HWLightPackingRevisionClock
{
public:
	explicit HWLightPackingRevisionClock(uint64_t nextRevision = 1)
		: mNextRevision(nextRevision)
	{
	}

	uint64_t Allocate()
	{
		if (mDisabled || mNextRevision == 0 ||
			mNextRevision == std::numeric_limits<uint64_t>::max())
		{
			mDisabled = true;
			return 0;
		}

		return mNextRevision++;
	}

	bool Disabled() const { return mDisabled; }

private:
	uint64_t mNextRevision = 1;
	bool mDisabled = false;
};

// A top-level PF-010 render epoch is the mutation boundary for qualified
// source-owned snapshots. Epoch 0, rollback, or wrap disables reuse rather
// than allowing an old snapshot to become current again.
class HWLightPackingContextState
{
public:
	uint64_t Begin(uint64_t epoch)
	{
		if (mDisabled || epoch == 0 || (mLastEpoch != 0 && epoch <= mLastEpoch))
		{
			mDisabled = true;
			mActiveEpoch = 0;
			return 0;
		}

		mLastEpoch = epoch;
		mActiveEpoch = epoch;
		return epoch;
	}

	void End(uint64_t epoch)
	{
		if (mActiveEpoch == epoch)
			mActiveEpoch = 0;
	}

	uint64_t ActiveEpoch() const { return mActiveEpoch; }
	bool Disabled() const { return mDisabled; }

private:
	uint64_t mLastEpoch = 0;
	uint64_t mActiveEpoch = 0;
	bool mDisabled = false;
};

template<class PackedRecord>
struct HWLightPackingSnapshot
{
	PackedRecord packed{};
	uint64_t contextEpoch = 0;
	uint64_t revision = 0;
	int portalGroup = 0;
	int lightClass = 0;
	bool valid = false;
};

template<class PackedRecord>
bool HWTryReuseLightPackingSnapshot(
	const HWLightPackingSnapshot<PackedRecord>& snapshot,
	uint64_t contextEpoch,
	int portalGroup,
	PackedRecord& packed,
	int& lightClass,
	uint64_t& revision)
{
	if (!snapshot.valid || snapshot.revision == 0 ||
		contextEpoch == 0 || snapshot.contextEpoch != contextEpoch ||
		snapshot.portalGroup != portalGroup)
	{
		return false;
	}

	packed = snapshot.packed;
	lightClass = snapshot.lightClass;
	revision = snapshot.revision;
	return true;
}

template<class PackedRecord>
uint64_t HWCommitLightPackingSnapshot(
	HWLightPackingSnapshot<PackedRecord>& snapshot,
	const PackedRecord& packed,
	int lightClass,
	int portalGroup,
	uint64_t contextEpoch,
	HWLightPackingRevisionClock& clock)
{
	const bool changed =
		!snapshot.valid ||
		snapshot.portalGroup != portalGroup ||
		snapshot.lightClass != lightClass ||
		std::memcmp(&snapshot.packed, &packed, sizeof(PackedRecord)) != 0;

	if (changed)
	{
		const uint64_t revision = clock.Allocate();
		if (revision == 0)
		{
			snapshot.valid = false;
			snapshot.contextEpoch = 0;
			snapshot.revision = 0;
			return 0;
		}

		snapshot.packed = packed;
		snapshot.portalGroup = portalGroup;
		snapshot.lightClass = lightClass;
		snapshot.revision = revision;
		snapshot.valid = true;
	}

	snapshot.contextEpoch = contextEpoch;
	return snapshot.revision;
}

inline bool HWLightUploadClassCanReuse(
	const uint64_t* revisions,
	const uint64_t* previousRevisions,
	size_t count)
{
	for (size_t i = 0; i < count; ++i)
	{
		if (revisions[i] == 0 || revisions[i] != previousRevisions[i])
			return false;
	}
	return true;
}
