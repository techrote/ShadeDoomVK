#pragma once

#include <cstddef>

namespace VkLightTilePolicy
{
	// The accepted renderer does not consume the tiled-light path:
	// hw_drawinfo.cpp leaves DispatchLightTiles disabled and frag_main.glsl
	// forces LevelMesh uLightIndex to -1. SDVK-009 owns any future revival.
	// Changing this one policy seam restores the retained producer resources.
	inline constexpr bool Enabled = false;
	inline constexpr int TileSize = 64;

	constexpr std::size_t BufferSize(
		int width,
		int height,
		std::size_t blockSize,
		bool enabled = Enabled)
	{
		if (blockSize == 0)
			return 0;

		// LevelMesh descriptor binding 4 remains live ABI even when the consumer
		// is dormant, so retain one valid block rather than a null descriptor.
		if (!enabled)
			return blockSize;

		const std::size_t safeWidth = width > 0 ? static_cast<std::size_t>(width) : 1u;
		const std::size_t safeHeight = height > 0 ? static_cast<std::size_t>(height) : 1u;
		const std::size_t tilesX = (safeWidth + TileSize - 1u) / TileSize;
		const std::size_t tilesY = (safeHeight + TileSize - 1u) / TileSize;
		return tilesX * tilesY * blockSize;
	}
}
