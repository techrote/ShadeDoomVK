#pragma once

#include <cstdint>

// Semantic identity for the material channels that already exist in the
// inherited renderer. This metadata must not be used to reorder legacy shader
// bindings: FMaterial retains the historical binding order and exposes the
// semantic identity alongside it.
enum class MaterialLayerSemantic : uint8_t
{
	Albedo,
	Normal,
	LegacySpecular,
	Metallic,
	Roughness,
	AmbientOcclusion,
	Brightmap,
	Detail,
	Glow,
	Custom,
};

struct MaterialLayerSemanticKey
{
	MaterialLayerSemantic semantic = MaterialLayerSemantic::Custom;
	int customIndex = -1;

	constexpr bool Matches(MaterialLayerSemantic candidateSemantic, int candidateCustomIndex) const
	{
		if (semantic != candidateSemantic)
			return false;
		return semantic != MaterialLayerSemantic::Custom || customIndex == candidateCustomIndex;
	}
};

constexpr const char* MaterialLayerSemanticName(MaterialLayerSemantic semantic)
{
	switch (semantic)
	{
	case MaterialLayerSemantic::Albedo: return "albedo";
	case MaterialLayerSemantic::Normal: return "normal";
	case MaterialLayerSemantic::LegacySpecular: return "legacy-specular";
	case MaterialLayerSemantic::Metallic: return "metallic";
	case MaterialLayerSemantic::Roughness: return "roughness";
	case MaterialLayerSemantic::AmbientOcclusion: return "ambient-occlusion";
	case MaterialLayerSemantic::Brightmap: return "brightmap-emissive";
	case MaterialLayerSemantic::Detail: return "detail";
	case MaterialLayerSemantic::Glow: return "glow";
	case MaterialLayerSemantic::Custom: return "custom";
	}
	return "unknown";
}
