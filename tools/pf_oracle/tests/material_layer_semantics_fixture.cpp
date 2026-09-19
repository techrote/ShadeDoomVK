#include "material_layer_semantics.h"

#include <cassert>
#include <string_view>

int main()
{
	using Semantic = MaterialLayerSemantic;

	static_assert(std::string_view(MaterialLayerSemanticName(Semantic::Albedo)) == "albedo");
	static_assert(std::string_view(MaterialLayerSemanticName(Semantic::Normal)) == "normal");
	static_assert(std::string_view(MaterialLayerSemanticName(Semantic::LegacySpecular)) == "legacy-specular");
	static_assert(std::string_view(MaterialLayerSemanticName(Semantic::Metallic)) == "metallic");
	static_assert(std::string_view(MaterialLayerSemanticName(Semantic::Roughness)) == "roughness");
	static_assert(std::string_view(MaterialLayerSemanticName(Semantic::AmbientOcclusion)) == "ambient-occlusion");
	static_assert(std::string_view(MaterialLayerSemanticName(Semantic::Brightmap)) == "brightmap-emissive");
	static_assert(std::string_view(MaterialLayerSemanticName(Semantic::Detail)) == "detail");
	static_assert(std::string_view(MaterialLayerSemanticName(Semantic::Glow)) == "glow");
	static_assert(std::string_view(MaterialLayerSemanticName(Semantic::Custom)) == "custom");
	static_assert(std::string_view(MaterialLayerSemanticName(static_cast<Semantic>(255))) == "unknown");

	// Non-custom channels are identified solely by semantic meaning. The custom
	// slot is deliberately ignored so diagnostics cannot invent positional
	// distinctions for fixed legacy channels.
	constexpr MaterialLayerSemanticKey albedo{ Semantic::Albedo, 99 };
	static_assert(albedo.Matches(Semantic::Albedo, -1));
	static_assert(albedo.Matches(Semantic::Albedo, 14));
	static_assert(!albedo.Matches(Semantic::Normal, 99));

	// Custom channels retain their authoring slot even when null slots compact
	// out of the historical binding array. Exercise the lower/upper inherited
	// custom-slot boundaries plus the anonymous compatibility value.
	constexpr MaterialLayerSemanticKey custom0{ Semantic::Custom, 0 };
	constexpr MaterialLayerSemanticKey custom14{ Semantic::Custom, 14 };
	constexpr MaterialLayerSemanticKey anonymousCustom{ Semantic::Custom, -1 };
	static_assert(custom0.Matches(Semantic::Custom, 0));
	static_assert(!custom0.Matches(Semantic::Custom, 1));
	static_assert(custom14.Matches(Semantic::Custom, 14));
	static_assert(!custom14.Matches(Semantic::Custom, 13));
	static_assert(anonymousCustom.Matches(Semantic::Custom, -1));
	static_assert(!anonymousCustom.Matches(Semantic::Custom, 0));

	assert(std::string_view(MaterialLayerSemanticName(Semantic::Brightmap)) == "brightmap-emissive");
	return 0;
}
