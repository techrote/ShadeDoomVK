#pragma once

#include <cstdint>
#include <tuple>

// Canonical renderer-key state used by PF-006.
//
// These structures intentionally contain semantic state only. They do not
// mirror C++ object layout, padding, or the reserved/unused bits carried by
// the packed shader words used as the shader specialization ABI.
namespace VkKeyIdentity
{
	struct ShaderState
	{
		uint8_t Simple2D = 0;
		uint8_t TextureMode = 0;
		uint8_t ClampY = 0;
		uint8_t Brightmap = 0;
		uint8_t Detailmap = 0;
		uint8_t Glowmap = 0;
		uint8_t UseShadowmap = 0;
		uint8_t UseRaytrace = 0;
		uint8_t ShadowmapFilter = 0;
		uint8_t FogBeforeLights = 0;
		uint8_t FogAfterLights = 0;
		uint8_t FogRadial = 0;
		uint8_t SWLightRadial = 0;
		uint8_t SWLightBanded = 0;
		uint8_t LightMode = 0;
		uint8_t LightBlendMode = 0;
		uint8_t LightAttenuationMode = 0;
		uint8_t PaletteMode = 0;
		uint8_t FogBalls = 0;
		uint8_t NoFragmentShader = 0;
		uint8_t DepthFadeThreshold = 0;
		uint8_t AlphaTestOnly = 0;
		uint8_t LightNoNormals = 0;
		uint8_t UseSpriteCenter = 0;

		int SpecialEffect = 0;
		int EffectState = 0;
		int VertexFormat = 0;

		uint8_t AlphaTest = 0;
		uint8_t Simple = 0;
		uint8_t Simple3D = 0;
		uint8_t GBufferPass = 0;
		uint8_t UseLevelMesh = 0;
		uint8_t ShadeVertex = 0;
		uint8_t UseRaytracePrecise = 0;

		auto Tie() const
		{
			return std::tie(
				Simple2D, TextureMode, ClampY, Brightmap, Detailmap, Glowmap,
				UseShadowmap, UseRaytrace, ShadowmapFilter,
				FogBeforeLights, FogAfterLights, FogRadial,
				SWLightRadial, SWLightBanded,
				LightMode, LightBlendMode, LightAttenuationMode,
				PaletteMode, FogBalls, NoFragmentShader,
				DepthFadeThreshold, AlphaTestOnly, LightNoNormals, UseSpriteCenter,
				SpecialEffect, EffectState, VertexFormat,
				AlphaTest, Simple, Simple3D, GBufferPass,
				UseLevelMesh, ShadeVertex, UseRaytracePrecise);
		}

		bool operator<(const ShaderState& other) const { return Tie() < other.Tie(); }
		bool operator==(const ShaderState& other) const { return Tie() == other.Tie(); }
		bool operator!=(const ShaderState& other) const { return !(*this == other); }

		uint32_t GeneralizedLayoutBits() const
		{
			return
				(uint32_t(AlphaTest) << 0) |
				(uint32_t(Simple) << 1) |
				(uint32_t(Simple3D) << 2) |
				(uint32_t(GBufferPass) << 3) |
				(uint32_t(UseLevelMesh) << 4) |
				(uint32_t(ShadeVertex) << 5) |
				(uint32_t(UseRaytracePrecise) << 6);
		}

		uint64_t GeneralizedCacheKey() const
		{
			return uint64_t(GeneralizedLayoutBits()) |
				(uint64_t(EffectState) << 32) |
				((uint64_t(SpecialEffect) & 0xff) << 48) |
				((uint64_t(VertexFormat) & 0xff) << 56);
		}
	};

	struct RenderStyleState
	{
		uint8_t BlendOp = 0;
		uint8_t SrcAlpha = 0;
		uint8_t DestAlpha = 0;
		uint8_t Flags = 0;

		auto Tie() const
		{
			return std::tie(BlendOp, SrcAlpha, DestAlpha, Flags);
		}

		bool operator<(const RenderStyleState& other) const { return Tie() < other.Tie(); }
		bool operator==(const RenderStyleState& other) const { return Tie() == other.Tie(); }
		bool operator!=(const RenderStyleState& other) const { return !(*this == other); }
	};

	struct PipelineState
	{
		uint8_t DrawType = 0;
		uint8_t CullMode = 0;
		uint8_t ColorMask = 0;
		uint8_t DepthWrite = 0;
		uint8_t DepthTest = 0;
		uint8_t DepthClamp = 0;
		uint8_t DepthBias = 0;
		uint8_t DepthFunc = 0;
		uint8_t StencilTest = 0;
		uint8_t StencilPassOp = 0;
		uint8_t DrawLine = 0;
		uint8_t IsGeneralized = 0;
		ShaderState ShaderKey;
		RenderStyleState RenderStyle;

		auto Tie() const
		{
			return std::tie(
				DrawType, CullMode, ColorMask,
				DepthWrite, DepthTest, DepthClamp, DepthBias, DepthFunc,
				StencilTest, StencilPassOp, DrawLine, IsGeneralized,
				ShaderKey, RenderStyle);
		}

		bool operator<(const PipelineState& other) const { return Tie() < other.Tie(); }
		bool operator==(const PipelineState& other) const { return Tie() == other.Tie(); }
		bool operator!=(const PipelineState& other) const { return !(*this == other); }
	};

	struct RenderPassState
	{
		int DepthStencil = 0;
		int Samples = 0;
		int DrawBuffers = 0;
		int32_t DrawBufferFormat = 0;

		auto Tie() const
		{
			return std::tie(DepthStencil, Samples, DrawBuffers, DrawBufferFormat);
		}

		bool operator<(const RenderPassState& other) const { return Tie() < other.Tie(); }
		bool operator==(const RenderPassState& other) const { return Tie() == other.Tie(); }
		bool operator!=(const RenderPassState& other) const { return !(*this == other); }
	};
}
