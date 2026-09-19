#include "vulkan/vk_keyidentity.h"

#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <map>
#include <vector>

namespace
{
	using VkKeyIdentity::PipelineState;
	using VkKeyIdentity::RenderPassState;
	using VkKeyIdentity::ShaderState;

	struct LegacyShaderKey
	{
		uint64_t Flags = 0;
		int SpecialEffect = 0;
		int EffectState = 0;
		int VertexFormat = 0;
		uint32_t Layout = 0;
	};

	struct LegacyPipelineKey
	{
		uint64_t Flags = 0;
		int Padding1 = 0;
		int Padding2 = 0;
		LegacyShaderKey ShaderKey;
		uint32_t RenderStyle = 0;
		int Padding3 = 0;
	};

	struct LegacyRenderPassKey
	{
		int DepthStencil = 0;
		int Samples = 0;
		int DrawBuffers = 0;
		int32_t DrawBufferFormat = 0;
	};

	uint64_t PackShaderFlags(const ShaderState& s)
	{
		return
			(uint64_t(s.Simple2D) << 2) |
			(uint64_t(s.TextureMode) << 4) |
			(uint64_t(s.ClampY) << 7) |
			(uint64_t(s.Brightmap) << 8) |
			(uint64_t(s.Detailmap) << 9) |
			(uint64_t(s.Glowmap) << 10) |
			(uint64_t(s.UseShadowmap) << 12) |
			(uint64_t(s.UseRaytrace) << 13) |
			(uint64_t(s.ShadowmapFilter) << 16) |
			(uint64_t(s.FogBeforeLights) << 20) |
			(uint64_t(s.FogAfterLights) << 21) |
			(uint64_t(s.FogRadial) << 22) |
			(uint64_t(s.SWLightRadial) << 23) |
			(uint64_t(s.SWLightBanded) << 24) |
			(uint64_t(s.LightMode) << 25) |
			(uint64_t(s.LightBlendMode) << 27) |
			(uint64_t(s.LightAttenuationMode) << 29) |
			(uint64_t(s.PaletteMode) << 30) |
			(uint64_t(s.FogBalls) << 31) |
			(uint64_t(s.NoFragmentShader) << 32) |
			(uint64_t(s.DepthFadeThreshold) << 33) |
			(uint64_t(s.AlphaTestOnly) << 34) |
			(uint64_t(s.LightNoNormals) << 36) |
			(uint64_t(s.UseSpriteCenter) << 37);
	}

	uint32_t PackShaderLayout(const ShaderState& s)
	{
		return s.GeneralizedLayoutBits();
	}

	LegacyShaderKey ToLegacy(const ShaderState& s)
	{
		LegacyShaderKey key;
		key.Flags = PackShaderFlags(s);
		key.SpecialEffect = s.SpecialEffect;
		key.EffectState = s.EffectState;
		key.VertexFormat = s.VertexFormat;
		key.Layout = PackShaderLayout(s);
		return key;
	}

	ShaderState FromLegacy(const LegacyShaderKey& key)
	{
		ShaderState s;
		s.Simple2D = uint8_t((key.Flags >> 2) & 1);
		s.TextureMode = uint8_t((key.Flags >> 4) & 7);
		s.ClampY = uint8_t((key.Flags >> 7) & 1);
		s.Brightmap = uint8_t((key.Flags >> 8) & 1);
		s.Detailmap = uint8_t((key.Flags >> 9) & 1);
		s.Glowmap = uint8_t((key.Flags >> 10) & 1);
		s.UseShadowmap = uint8_t((key.Flags >> 12) & 1);
		s.UseRaytrace = uint8_t((key.Flags >> 13) & 1);
		s.ShadowmapFilter = uint8_t((key.Flags >> 16) & 15);
		s.FogBeforeLights = uint8_t((key.Flags >> 20) & 1);
		s.FogAfterLights = uint8_t((key.Flags >> 21) & 1);
		s.FogRadial = uint8_t((key.Flags >> 22) & 1);
		s.SWLightRadial = uint8_t((key.Flags >> 23) & 1);
		s.SWLightBanded = uint8_t((key.Flags >> 24) & 1);
		s.LightMode = uint8_t((key.Flags >> 25) & 3);
		s.LightBlendMode = uint8_t((key.Flags >> 27) & 3);
		s.LightAttenuationMode = uint8_t((key.Flags >> 29) & 1);
		s.PaletteMode = uint8_t((key.Flags >> 30) & 1);
		s.FogBalls = uint8_t((key.Flags >> 31) & 1);
		s.NoFragmentShader = uint8_t((key.Flags >> 32) & 1);
		s.DepthFadeThreshold = uint8_t((key.Flags >> 33) & 1);
		s.AlphaTestOnly = uint8_t((key.Flags >> 34) & 1);
		s.LightNoNormals = uint8_t((key.Flags >> 36) & 1);
		s.UseSpriteCenter = uint8_t((key.Flags >> 37) & 1);
		s.SpecialEffect = key.SpecialEffect;
		s.EffectState = key.EffectState;
		s.VertexFormat = key.VertexFormat;
		s.AlphaTest = uint8_t((key.Layout >> 0) & 1);
		s.Simple = uint8_t((key.Layout >> 1) & 1);
		s.Simple3D = uint8_t((key.Layout >> 2) & 1);
		s.GBufferPass = uint8_t((key.Layout >> 3) & 1);
		s.UseLevelMesh = uint8_t((key.Layout >> 4) & 1);
		s.ShadeVertex = uint8_t((key.Layout >> 5) & 1);
		s.UseRaytracePrecise = uint8_t((key.Layout >> 6) & 1);
		return s;
	}

	uint64_t PackPipelineFlags(const PipelineState& p)
	{
		return
			(uint64_t(p.DrawType) << 0) |
			(uint64_t(p.CullMode) << 3) |
			(uint64_t(p.ColorMask) << 5) |
			(uint64_t(p.DepthWrite) << 9) |
			(uint64_t(p.DepthTest) << 10) |
			(uint64_t(p.DepthClamp) << 11) |
			(uint64_t(p.DepthBias) << 12) |
			(uint64_t(p.DepthFunc) << 13) |
			(uint64_t(p.StencilTest) << 15) |
			(uint64_t(p.StencilPassOp) << 16) |
			(uint64_t(p.DrawLine) << 18) |
			(uint64_t(p.IsGeneralized) << 19);
	}

	LegacyPipelineKey ToLegacy(const PipelineState& p)
	{
		LegacyPipelineKey key;
		key.Flags = PackPipelineFlags(p);
		key.ShaderKey = ToLegacy(p.ShaderKey);
		key.RenderStyle = p.RenderStyle;
		return key;
	}

	PipelineState FromLegacy(const LegacyPipelineKey& key)
	{
		PipelineState p;
		p.DrawType = uint8_t((key.Flags >> 0) & 7);
		p.CullMode = uint8_t((key.Flags >> 3) & 3);
		p.ColorMask = uint8_t((key.Flags >> 5) & 15);
		p.DepthWrite = uint8_t((key.Flags >> 9) & 1);
		p.DepthTest = uint8_t((key.Flags >> 10) & 1);
		p.DepthClamp = uint8_t((key.Flags >> 11) & 1);
		p.DepthBias = uint8_t((key.Flags >> 12) & 1);
		p.DepthFunc = uint8_t((key.Flags >> 13) & 3);
		p.StencilTest = uint8_t((key.Flags >> 15) & 1);
		p.StencilPassOp = uint8_t((key.Flags >> 16) & 3);
		p.DrawLine = uint8_t((key.Flags >> 18) & 1);
		p.IsGeneralized = uint8_t((key.Flags >> 19) & 1);
		p.ShaderKey = FromLegacy(key.ShaderKey);
		p.RenderStyle = key.RenderStyle;
		return p;
	}

	LegacyRenderPassKey ToLegacy(const RenderPassState& p)
	{
		return { p.DepthStencil, p.Samples, p.DrawBuffers, p.DrawBufferFormat };
	}

	RenderPassState FromLegacy(const LegacyRenderPassKey& key)
	{
		return { key.DepthStencil, key.Samples, key.DrawBuffers, key.DrawBufferFormat };
	}

	template <class Legacy>
	bool LegacyEqual(const Legacy& a, const Legacy& b)
	{
		return std::memcmp(&a, &b, sizeof(Legacy)) == 0;
	}

	std::vector<ShaderState> MakeShaderStates()
	{
		std::vector<ShaderState> out(1);
		auto add = [&](auto mutate)
		{
			ShaderState s;
			mutate(s);
			out.push_back(s);
		};

		add([](ShaderState& s) { s.Simple2D = 1; });
		add([](ShaderState& s) { s.TextureMode = 7; });
		add([](ShaderState& s) { s.ClampY = 1; });
		add([](ShaderState& s) { s.Brightmap = 1; });
		add([](ShaderState& s) { s.Detailmap = 1; });
		add([](ShaderState& s) { s.Glowmap = 1; });
		add([](ShaderState& s) { s.UseShadowmap = 1; });
		add([](ShaderState& s) { s.UseRaytrace = 1; });
		add([](ShaderState& s) { s.ShadowmapFilter = 15; });
		add([](ShaderState& s) { s.FogBeforeLights = 1; });
		add([](ShaderState& s) { s.FogAfterLights = 1; });
		add([](ShaderState& s) { s.FogRadial = 1; });
		add([](ShaderState& s) { s.SWLightRadial = 1; });
		add([](ShaderState& s) { s.SWLightBanded = 1; });
		add([](ShaderState& s) { s.LightMode = 3; });
		add([](ShaderState& s) { s.LightBlendMode = 3; });
		add([](ShaderState& s) { s.LightAttenuationMode = 1; });
		add([](ShaderState& s) { s.PaletteMode = 1; });
		add([](ShaderState& s) { s.FogBalls = 1; });
		add([](ShaderState& s) { s.NoFragmentShader = 1; });
		add([](ShaderState& s) { s.DepthFadeThreshold = 1; });
		add([](ShaderState& s) { s.AlphaTestOnly = 1; });
		add([](ShaderState& s) { s.LightNoNormals = 1; });
		add([](ShaderState& s) { s.UseSpriteCenter = 1; });
		add([](ShaderState& s) { s.SpecialEffect = 5; });
		add([](ShaderState& s) { s.EffectState = 17; });
		add([](ShaderState& s) { s.VertexFormat = 255; });
		add([](ShaderState& s) { s.AlphaTest = 1; });
		add([](ShaderState& s) { s.Simple = 1; });
		add([](ShaderState& s) { s.Simple3D = 1; });
		add([](ShaderState& s) { s.GBufferPass = 1; });
		add([](ShaderState& s) { s.UseLevelMesh = 1; });
		add([](ShaderState& s) { s.ShadeVertex = 1; });
		add([](ShaderState& s) { s.UseRaytracePrecise = 1; });
		return out;
	}

	std::vector<PipelineState> MakePipelineStates()
	{
		std::vector<PipelineState> out(1);
		auto add = [&](auto mutate)
		{
			PipelineState p;
			mutate(p);
			out.push_back(p);
		};

		add([](PipelineState& p) { p.DrawType = 4; });
		add([](PipelineState& p) { p.CullMode = 3; });
		add([](PipelineState& p) { p.ColorMask = 15; });
		add([](PipelineState& p) { p.DepthWrite = 1; });
		add([](PipelineState& p) { p.DepthTest = 1; });
		add([](PipelineState& p) { p.DepthClamp = 1; });
		add([](PipelineState& p) { p.DepthBias = 1; });
		add([](PipelineState& p) { p.DepthFunc = 2; });
		add([](PipelineState& p) { p.StencilTest = 1; });
		add([](PipelineState& p) { p.StencilPassOp = 2; });
		add([](PipelineState& p) { p.DrawLine = 1; });
		add([](PipelineState& p) { p.IsGeneralized = 1; });
		add([](PipelineState& p) { p.ShaderKey.EffectState = 17; });
		add([](PipelineState& p) { p.ShaderKey.UseRaytrace = 1; p.ShaderKey.UseRaytracePrecise = 1; });
		add([](PipelineState& p) { p.RenderStyle = 0xffffffffu; });
		return out;
	}

	std::vector<RenderPassState> MakeRenderPassStates()
	{
		return {
			{},
			{1, 1, 1, 37},
			{1, 2, 1, 37},
			{1, 4, 3, 37},
			{0, 8, 1, 97},
			{1, 8, 3, 0x7fffffff}
		};
	}

	template <class State, class Legacy, class ToLegacyFn>
	void AssertPartitionEquivalent(const std::vector<State>& states, ToLegacyFn toLegacy)
	{
		for (size_t i = 0; i < states.size(); ++i)
		{
			for (size_t j = 0; j < states.size(); ++j)
			{
				Legacy a = toLegacy(states[i]);
				Legacy b = toLegacy(states[j]);
				assert(LegacyEqual(a, b) == (states[i] == states[j]));
			}
		}
	}
}

int main()
{
	const auto shaderStates = MakeShaderStates();
	const auto pipelineStates = MakePipelineStates();
	const auto renderPassStates = MakeRenderPassStates();

	AssertPartitionEquivalent<ShaderState, LegacyShaderKey>(shaderStates, ToLegacy);
	AssertPartitionEquivalent<PipelineState, LegacyPipelineKey>(pipelineStates, ToLegacy);
	AssertPartitionEquivalent<RenderPassState, LegacyRenderPassKey>(renderPassStates, ToLegacy);

	for (const auto& state : shaderStates)
		assert(FromLegacy(ToLegacy(state)) == state);
	for (const auto& state : pipelineStates)
		assert(FromLegacy(ToLegacy(state)) == state);
	for (const auto& state : renderPassStates)
		assert(FromLegacy(ToLegacy(state)) == state);

	// Boundary/adversarial representation noise: legacy whole-object identity
	// split on bytes that are not renderer state. Canonical identity must not.
	LegacyPipelineKey clean = ToLegacy(PipelineState{});
	LegacyPipelineKey noisy = clean;
	noisy.Padding1 = 0x12345678;
	noisy.Padding2 = -1;
	noisy.Padding3 = 0x55aa55aa;
	noisy.Flags |= uint64_t(1) << 63;            // old Unused pipeline bit
	noisy.ShaderKey.Flags |= uint64_t(1) << 0;  // old Unused0 shader bit
	noisy.ShaderKey.Layout |= uint32_t(1) << 31;// old unused layout bit
	assert(!LegacyEqual(clean, noisy));
	assert(FromLegacy(clean) == FromLegacy(noisy));

	// Map ordering must remain a strict semantic ordering and warm lookups must
	// hit reconstructed keys rather than depend on object bytes.
	std::map<ShaderState, int> shaderCache;
	for (size_t i = 0; i < shaderStates.size(); ++i)
		shaderCache.emplace(shaderStates[i], int(i));
	assert(shaderCache.size() == shaderStates.size());
	for (const auto& state : shaderStates)
		assert(shaderCache.find(FromLegacy(ToLegacy(state))) != shaderCache.end());

	std::map<PipelineState, int> pipelineCache;
	for (size_t i = 0; i < pipelineStates.size(); ++i)
		pipelineCache.emplace(pipelineStates[i], int(i));
	assert(pipelineCache.size() == pipelineStates.size());
	for (const auto& state : pipelineStates)
		assert(pipelineCache.find(FromLegacy(ToLegacy(state))) != pipelineCache.end());

	// The generalized shader cache intentionally keys layout/effect/user shader
	// and vertex format state, while specialized-only shader flags stay outside
	// that cache identity exactly as before PF-006.
	ShaderState genericBase;
	ShaderState specializedOnly = genericBase;
	specializedOnly.TextureMode = 7;
	specializedOnly.UseShadowmap = 1;
	assert(genericBase.GeneralizedCacheKey() == specializedOnly.GeneralizedCacheKey());

	ShaderState userShader = genericBase;
	userShader.EffectState = 17;
	assert(genericBase.GeneralizedCacheKey() != userShader.GeneralizedCacheKey());
	ShaderState effect = genericBase;
	effect.SpecialEffect = 5;
	assert(genericBase.GeneralizedCacheKey() != effect.GeneralizedCacheKey());
	ShaderState vertex = genericBase;
	vertex.VertexFormat = 255;
	assert(genericBase.GeneralizedCacheKey() != vertex.GeneralizedCacheKey());
	ShaderState layout = genericBase;
	layout.UseLevelMesh = 1;
	assert(genericBase.GeneralizedCacheKey() != layout.GeneralizedCacheKey());
	layout = genericBase;
	layout.UseRaytracePrecise = 1;
	assert(genericBase.GeneralizedCacheKey() != layout.GeneralizedCacheKey());

	std::cout << "PF-006 key contract fixture passed: "
		<< shaderStates.size() << " shader states, "
		<< pipelineStates.size() << " pipeline states, "
		<< renderPassStates.size() << " render-pass states\n";
	return 0;
}
