#include "vulkan/vk_keyidentity.h"

#include <array>
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

	using LegacyShaderBytes = std::array<uint8_t, 24>;
	using LegacyPipelineBytes = std::array<uint8_t, 48>;
	using LegacyRenderPassBytes = std::array<uint8_t, 16>;

	template <class T, size_t N>
	void Store(std::array<uint8_t, N>& bytes, size_t offset, T value)
	{
		assert(offset + sizeof(T) <= bytes.size());
		std::memcpy(bytes.data() + offset, &value, sizeof(T));
	}

	template <class T, size_t N>
	T Load(const std::array<uint8_t, N>& bytes, size_t offset)
	{
		assert(offset + sizeof(T) <= bytes.size());
		T value{};
		std::memcpy(&value, bytes.data() + offset, sizeof(T));
		return value;
	}

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

	LegacyShaderBytes LegacyShader(const ShaderState& s)
	{
		LegacyShaderBytes bytes{};
		Store(bytes, 0, PackShaderFlags(s));
		Store(bytes, 8, s.SpecialEffect);
		Store(bytes, 12, s.EffectState);
		Store(bytes, 16, s.VertexFormat);
		Store(bytes, 20, s.GeneralizedLayoutBits());
		return bytes;
	}

	ShaderState CanonicalShader(const LegacyShaderBytes& bytes)
	{
		ShaderState s;
		const uint64_t flags = Load<uint64_t>(bytes, 0);
		const uint32_t layout = Load<uint32_t>(bytes, 20);
		s.Simple2D = uint8_t((flags >> 2) & 1);
		s.TextureMode = uint8_t((flags >> 4) & 7);
		s.ClampY = uint8_t((flags >> 7) & 1);
		s.Brightmap = uint8_t((flags >> 8) & 1);
		s.Detailmap = uint8_t((flags >> 9) & 1);
		s.Glowmap = uint8_t((flags >> 10) & 1);
		s.UseShadowmap = uint8_t((flags >> 12) & 1);
		s.UseRaytrace = uint8_t((flags >> 13) & 1);
		s.ShadowmapFilter = uint8_t((flags >> 16) & 15);
		s.FogBeforeLights = uint8_t((flags >> 20) & 1);
		s.FogAfterLights = uint8_t((flags >> 21) & 1);
		s.FogRadial = uint8_t((flags >> 22) & 1);
		s.SWLightRadial = uint8_t((flags >> 23) & 1);
		s.SWLightBanded = uint8_t((flags >> 24) & 1);
		s.LightMode = uint8_t((flags >> 25) & 3);
		s.LightBlendMode = uint8_t((flags >> 27) & 3);
		s.LightAttenuationMode = uint8_t((flags >> 29) & 1);
		s.PaletteMode = uint8_t((flags >> 30) & 1);
		s.FogBalls = uint8_t((flags >> 31) & 1);
		s.NoFragmentShader = uint8_t((flags >> 32) & 1);
		s.DepthFadeThreshold = uint8_t((flags >> 33) & 1);
		s.AlphaTestOnly = uint8_t((flags >> 34) & 1);
		s.LightNoNormals = uint8_t((flags >> 36) & 1);
		s.UseSpriteCenter = uint8_t((flags >> 37) & 1);
		s.SpecialEffect = Load<int>(bytes, 8);
		s.EffectState = Load<int>(bytes, 12);
		s.VertexFormat = Load<int>(bytes, 16);
		s.AlphaTest = uint8_t((layout >> 0) & 1);
		s.Simple = uint8_t((layout >> 1) & 1);
		s.Simple3D = uint8_t((layout >> 2) & 1);
		s.GBufferPass = uint8_t((layout >> 3) & 1);
		s.UseLevelMesh = uint8_t((layout >> 4) & 1);
		s.ShadeVertex = uint8_t((layout >> 5) & 1);
		s.UseRaytracePrecise = uint8_t((layout >> 6) & 1);
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

	LegacyPipelineBytes LegacyPipeline(const PipelineState& p)
	{
		LegacyPipelineBytes bytes{};
		Store(bytes, 0, PackPipelineFlags(p));
		const auto shader = LegacyShader(p.ShaderKey);
		std::memcpy(bytes.data() + 16, shader.data(), shader.size());
		Store(bytes, 40, p.RenderStyle);
		return bytes;
	}

	PipelineState CanonicalPipeline(const LegacyPipelineBytes& bytes)
	{
		PipelineState p;
		const uint64_t flags = Load<uint64_t>(bytes, 0);
		p.DrawType = uint8_t((flags >> 0) & 7);
		p.CullMode = uint8_t((flags >> 3) & 3);
		p.ColorMask = uint8_t((flags >> 5) & 15);
		p.DepthWrite = uint8_t((flags >> 9) & 1);
		p.DepthTest = uint8_t((flags >> 10) & 1);
		p.DepthClamp = uint8_t((flags >> 11) & 1);
		p.DepthBias = uint8_t((flags >> 12) & 1);
		p.DepthFunc = uint8_t((flags >> 13) & 3);
		p.StencilTest = uint8_t((flags >> 15) & 1);
		p.StencilPassOp = uint8_t((flags >> 16) & 3);
		p.DrawLine = uint8_t((flags >> 18) & 1);
		p.IsGeneralized = uint8_t((flags >> 19) & 1);
		LegacyShaderBytes shader{};
		std::memcpy(shader.data(), bytes.data() + 16, shader.size());
		p.ShaderKey = CanonicalShader(shader);
		p.RenderStyle = Load<uint32_t>(bytes, 40);
		return p;
	}

	LegacyRenderPassBytes LegacyRenderPass(const RenderPassState& p)
	{
		LegacyRenderPassBytes bytes{};
		Store(bytes, 0, p.DepthStencil);
		Store(bytes, 4, p.Samples);
		Store(bytes, 8, p.DrawBuffers);
		Store(bytes, 12, p.DrawBufferFormat);
		return bytes;
	}

	RenderPassState CanonicalRenderPass(const LegacyRenderPassBytes& bytes)
	{
		return {
			Load<int>(bytes, 0),
			Load<int>(bytes, 4),
			Load<int>(bytes, 8),
			Load<int32_t>(bytes, 12)
		};
	}

	std::vector<ShaderState> ShaderCases()
	{
		std::vector<ShaderState> out(1);
		auto add = [&](auto mutate) { ShaderState s; mutate(s); out.push_back(s); };
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

	std::vector<PipelineState> PipelineCases()
	{
		std::vector<PipelineState> out(1);
		auto add = [&](auto mutate) { PipelineState p; mutate(p); out.push_back(p); };
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

	std::vector<RenderPassState> RenderPassCases()
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

	template <class State, class LegacyFn>
	void AssertPartitionEquivalent(const std::vector<State>& states, LegacyFn legacy)
	{
		for (size_t i = 0; i < states.size(); ++i)
			for (size_t j = 0; j < states.size(); ++j)
				assert((legacy(states[i]) == legacy(states[j])) == (states[i] == states[j]));
	}
}

int main()
{
	const auto shaderCases = ShaderCases();
	const auto pipelineCases = PipelineCases();
	const auto renderPassCases = RenderPassCases();

	AssertPartitionEquivalent(shaderCases, LegacyShader);
	AssertPartitionEquivalent(pipelineCases, LegacyPipeline);
	AssertPartitionEquivalent(renderPassCases, LegacyRenderPass);

	for (const auto& state : shaderCases)
		assert(CanonicalShader(LegacyShader(state)) == state);
	for (const auto& state : pipelineCases)
		assert(CanonicalPipeline(LegacyPipeline(state)) == state);
	for (const auto& state : renderPassCases)
		assert(CanonicalRenderPass(LegacyRenderPass(state)) == state);

	// Old whole-object memcmp split on representation bytes that are not
	// renderer state. Canonical identity deliberately ignores those bytes.
	LegacyPipelineBytes clean = LegacyPipeline(PipelineState{});
	LegacyPipelineBytes noisy = clean;
	Store(noisy, 8, int(0x12345678));          // Padding1
	Store(noisy, 12, int(-1));                 // Padding2
	Store(noisy, 44, int(0x55aa55aa));         // Padding3
	Store(noisy, 0, Load<uint64_t>(noisy, 0) | (uint64_t(1) << 63));
	Store(noisy, 16, Load<uint64_t>(noisy, 16) | (uint64_t(1) << 0));
	Store(noisy, 36, Load<uint32_t>(noisy, 36) | (uint32_t(1) << 31));
	assert(clean != noisy);
	assert(CanonicalPipeline(clean) == CanonicalPipeline(noisy));

	// Reconstructed semantic keys must hit warm ordered caches.
	std::map<ShaderState, int> shaderCache;
	for (size_t i = 0; i < shaderCases.size(); ++i)
		shaderCache.emplace(shaderCases[i], int(i));
	assert(shaderCache.size() == shaderCases.size());
	for (const auto& state : shaderCases)
		assert(shaderCache.find(CanonicalShader(LegacyShader(state))) != shaderCache.end());

	std::map<PipelineState, int> pipelineCache;
	for (size_t i = 0; i < pipelineCases.size(); ++i)
		pipelineCache.emplace(pipelineCases[i], int(i));
	assert(pipelineCache.size() == pipelineCases.size());
	for (const auto& state : pipelineCases)
		assert(pipelineCache.find(CanonicalPipeline(LegacyPipeline(state))) != pipelineCache.end());

	// Generalized cache identity stays deliberately narrower than specialized
	// shader identity, while user/effect/layout/vertex distinctions remain.
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
		<< shaderCases.size() << " shader states, "
		<< pipelineCases.size() << " pipeline states, "
		<< renderPassCases.size() << " render-pass states\n";
	return 0;
}
