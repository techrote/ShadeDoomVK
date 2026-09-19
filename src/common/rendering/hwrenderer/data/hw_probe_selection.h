#pragma once

#include <cstddef>
#include <cstdint>

namespace HWProbeSelection
{
	static constexpr float Radius = 512.0f;
	static constexpr uint32_t FallbackTextureIndex = 0;
	static constexpr uint32_t MaxProbeMapTextureIndex = 0xffffu;

	struct Candidate
	{
		float X = 0.0f;
		float Y = 0.0f;
		float Z = 0.0f;
		uint32_t TextureIndex = FallbackTextureIndex;
	};

	inline bool IsEncodableTextureIndex(uint32_t textureIndex)
	{
		return textureIndex > FallbackTextureIndex && textureIndex <= MaxProbeMapTextureIndex;
	}

	inline uint32_t FindClosest(const Candidate* candidates, std::size_t count, float x, float y, float z, float radius = Radius)
	{
		if (!candidates || count == 0 || radius < 0.0f)
			return FallbackTextureIndex;

		const float radiusSquared = radius * radius;
		float closestDistanceSquared = radiusSquared;
		uint32_t closestTextureIndex = FallbackTextureIndex;
		bool found = false;

		for (std::size_t i = 0; i < count; ++i)
		{
			const Candidate& candidate = candidates[i];
			if (!IsEncodableTextureIndex(candidate.TextureIndex))
				continue;

			const float dx = candidate.X - x;
			const float dy = candidate.Y - y;
			const float dz = candidate.Z - z;
			const float distanceSquared = dx * dx + dy * dy + dz * dz;
			if (distanceSquared <= radiusSquared && (!found || distanceSquared < closestDistanceSquared))
			{
				closestDistanceSquared = distanceSquared;
				closestTextureIndex = candidate.TextureIndex;
				found = true;
			}
		}

		return closestTextureIndex;
	}
}
