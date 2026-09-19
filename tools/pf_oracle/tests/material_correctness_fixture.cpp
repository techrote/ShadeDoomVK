#include "hw_resourcegeneration.h"

#include <cassert>
#include <cmath>
#include <cstdint>
#include <unordered_map>

namespace
{
constexpr int CTF_Expand = 1;
constexpr int CTF_Upscale = 2;
constexpr int CTF_Indexed = 4;
constexpr int CTF_IndexedRedIsAlpha = 32;

int SpriteScaleFlags(bool upscale)
{
	int flags = CTF_Expand;
	if (upscale) flags |= CTF_Upscale;
	return flags;
}

enum class StorageVariant : uint8_t
{
	TrueColor,
	PaletteIndex,
	RedIsAlpha
};

StorageVariant SelectStorageVariant(int flags)
{
	if (flags & CTF_IndexedRedIsAlpha) return StorageVariant::RedIsAlpha;
	if (flags & CTF_Indexed) return StorageVariant::PaletteIndex;
	return StorageVariant::TrueColor;
}

struct DescriptorKey
{
	int ClampMode = 0;
	intptr_t Translation = 0;
	bool PaletteMode = false;
	bool RedIsAlpha = false;

	bool operator==(const DescriptorKey& other) const
	{
		return ClampMode == other.ClampMode &&
			Translation == other.Translation &&
			PaletteMode == other.PaletteMode &&
			RedIsAlpha == other.RedIsAlpha;
	}
};

struct DescriptorKeyHash
{
	std::size_t operator()(const DescriptorKey& key) const
	{
		std::size_t h = static_cast<std::size_t>(key.ClampMode);
		h = h * 16777619u ^ static_cast<std::size_t>(key.Translation);
		h = h * 16777619u ^ static_cast<std::size_t>(key.PaletteMode);
		h = h * 16777619u ^ static_cast<std::size_t>(key.RedIsAlpha);
		return h;
	}
};

float StableDistributionGGX(float ndh, float roughness)
{
	constexpr float Pi = 3.14159265359f;
	const float a = roughness * roughness;
	const float a2 = a * a;
	const float ndh2 = ndh * ndh;
	if (a2 <= 0.0f)
		return 0.0f;
	const float denomBase = (1.0f - ndh2) + ndh2 * a2;
	return (a2 / denomBase) / (Pi * denomBase);
}

float LegacyDistributionGGX(float ndh, float roughness)
{
	constexpr float Pi = 3.14159265359f;
	const float a = roughness * roughness;
	const float a2 = a * a;
	const float ndh2 = ndh * ndh;
	const float denomBase = ndh2 * (a2 - 1.0f) + 1.0f;
	return a2 / (Pi * denomBase * denomBase);
}

bool NearlyEqual(float a, float b, float rel = 1.0e-5f)
{
	const float scale = std::fmax(1.0f, std::fmax(std::fabs(a), std::fabs(b)));
	return std::fabs(a - b) <= rel * scale;
}
}

int main()
{
	// Sprite material identity must retain Expand and optional Upscale instead
	// of collapsing the flag word to boolean true.
	assert(SpriteScaleFlags(false) == CTF_Expand);
	assert(SpriteScaleFlags(true) == (CTF_Expand | CTF_Upscale));
	assert(SpriteScaleFlags(true) != 1);

	// RedIsAlpha and palette-index R8 uploads have different producer meaning.
	assert(SelectStorageVariant(0) == StorageVariant::TrueColor);
	assert(SelectStorageVariant(CTF_Indexed) == StorageVariant::PaletteIndex);
	assert(SelectStorageVariant(CTF_IndexedRedIsAlpha) == StorageVariant::RedIsAlpha);
	assert(SelectStorageVariant(CTF_Indexed | CTF_IndexedRedIsAlpha) == StorageVariant::RedIsAlpha);

	std::unordered_map<DescriptorKey, int, DescriptorKeyHash> descriptors;
	const DescriptorKey translatedPalette{5, 17, true, false};
	const DescriptorKey translatedAlpha{5, 17, true, true};
	const DescriptorKey otherTranslation{5, 18, true, false};
	descriptors.emplace(translatedPalette, 101);
	descriptors.emplace(translatedAlpha, 102);
	descriptors.emplace(otherTranslation, 103);
	assert(descriptors.size() == 3);
	assert(descriptors.at(translatedPalette) == 101);
	assert(descriptors.at(translatedAlpha) == 102);
	assert(descriptors.at(otherTranslation) == 103);

	// PF generation semantics still reject stale descriptor/material identities.
	FRendererResourceGenerationTable generations;
	auto first = generations.Activate(259, 3);
	assert(first.IsSet() && generations.Validate(first));
	assert(generations.Retire(259));
	assert(!generations.Validate(first));

	for (uint32_t i = 0; i < 10000; ++i)
	{
		auto current = generations.Activate(259, 3);
		assert(current.IsSet());
		assert(generations.Validate(current));
		auto stale = current;
		assert(generations.Retire(259));
		assert(!generations.Validate(stale));
	}

	// Exact zero roughness and epsilon-scale lobes must remain finite.
	const float zero = StableDistributionGGX(1.0f, 0.0f);
	assert(std::isfinite(zero) && zero == 0.0f);

	for (float roughness : {1.0e-6f, 1.0e-4f, 1.0e-2f, 0.05f})
	{
		for (float ndh : {0.0f, 0.5f, 0.999f, 1.0f})
		{
			const float value = StableDistributionGGX(ndh, roughness);
			assert(std::isfinite(value));
			assert(value >= 0.0f);
		}
	}

	// Normal roughness remains algebraically equivalent to the inherited form.
	for (float roughness : {0.25f, 0.5f, 0.75f, 1.0f})
	{
		for (float ndh : {0.0f, 0.25f, 0.5f, 0.9f, 1.0f})
		{
			const float stable = StableDistributionGGX(ndh, roughness);
			const float legacy = LegacyDistributionGGX(ndh, roughness);
			assert(std::isfinite(stable));
			assert(std::isfinite(legacy));
			assert(NearlyEqual(stable, legacy, 2.0e-5f));
		}
	}

	return 0;
}
