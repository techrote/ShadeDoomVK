#pragma once

#include <cstdint>
#include <cstddef>
#include <vector>

struct FRendererResourceIdentity
{
	int32_t Index = -1;
	uint32_t Generation = 0;
	uint32_t Epoch = 0;
	uint32_t Span = 0;

	bool IsSet() const
	{
		return Index >= 0 && Generation != 0 && Epoch != 0 && Span != 0;
	}
};

struct FRendererLifetimeStats
{
	uint64_t Activations = 0;
	uint64_t Retirements = 0;
	uint64_t Resets = 0;
	uint64_t StaleRejects = 0;
	uint64_t InvalidRetires = 0;
	uint64_t DuplicateActivations = 0;
};

class FRendererResourceGenerationTable
{
public:
	FRendererResourceIdentity Activate(int index, uint32_t span = 1)
	{
		if (index < 0 || span == 0)
			return {};

		EnsureSlot(index);
		auto& slot = Slots[(std::size_t)index];
		if (slot.Generation == 0)
			slot.Generation = 1;
		if (slot.Live)
		{
			Stats.DuplicateActivations++;
			slot.Generation = NextGeneration(slot.Generation);
		}

		slot.Live = true;
		slot.Span = span;
		Stats.Activations++;
		return { index, slot.Generation, Epoch, span };
	}

	bool Retire(int index)
	{
		if (index < 0 || (std::size_t)index >= Slots.size() || !Slots[(std::size_t)index].Live)
		{
			Stats.InvalidRetires++;
			return false;
		}

		auto& slot = Slots[(std::size_t)index];
		slot.Live = false;
		slot.Span = 0;
		slot.Generation = NextGeneration(slot.Generation);
		Stats.Retirements++;
		return true;
	}

	void Reset()
	{
		Epoch = NextGeneration(Epoch);
		Slots.clear();
		Stats.Resets++;
	}

	FRendererResourceIdentity Current(int index) const
	{
		if (index < 0 || (std::size_t)index >= Slots.size())
			return {};

		const auto& slot = Slots[(std::size_t)index];
		if (!slot.Live || slot.Generation == 0 || slot.Span == 0)
			return {};
		return { index, slot.Generation, Epoch, slot.Span };
	}

	bool IsCurrent(const FRendererResourceIdentity& identity) const
	{
		if (!identity.IsSet() || identity.Epoch != Epoch || identity.Index < 0 || (size_t)identity.Index >= Slots.size())
			return false;

		const auto& slot = Slots[(size_t)identity.Index];
		return slot.Live && slot.Generation == identity.Generation && slot.Span == identity.Span;
	}

	bool Validate(const FRendererResourceIdentity& identity)
	{
		if (IsCurrent(identity))
			return true;
		Stats.StaleRejects++;
		return false;
	}

	uint32_t GetEpoch() const { return Epoch; }
	const FRendererLifetimeStats& GetStats() const { return Stats; }

private:
	struct SlotState
	{
		uint32_t Generation = 0;
		uint32_t Span = 0;
		bool Live = false;
	};

	static uint32_t NextGeneration(uint32_t value)
	{
		value++;
		return value == 0 ? 1 : value;
	}

	void EnsureSlot(int index)
	{
		if (Slots.size() <= (std::size_t)index)
			Slots.resize((std::size_t)index + 1);
	}

	uint32_t Epoch = 1;
	std::vector<SlotState> Slots;
	FRendererLifetimeStats Stats;
};

struct FRendererEpochToken
{
	uint32_t Generation = 0;

	bool IsSet() const { return Generation != 0; }
};

struct FRendererEpochStats
{
	uint64_t Invalidations = 0;
	uint64_t StaleRejects = 0;
};

class FRendererEpoch
{
public:
	FRendererEpochToken Snapshot() const { return { Generation }; }

	void Invalidate()
	{
		Generation = NextGeneration(Generation);
		Stats.Invalidations++;
	}

	bool IsCurrent(FRendererEpochToken token) const
	{
		return token.IsSet() && token.Generation == Generation;
	}

	bool Validate(FRendererEpochToken token)
	{
		if (IsCurrent(token))
			return true;
		Stats.StaleRejects++;
		return false;
	}

	const FRendererEpochStats& GetStats() const { return Stats; }

private:
	static uint32_t NextGeneration(uint32_t value)
	{
		value++;
		return value == 0 ? 1 : value;
	}

	uint32_t Generation = 1;
	FRendererEpochStats Stats;
};
