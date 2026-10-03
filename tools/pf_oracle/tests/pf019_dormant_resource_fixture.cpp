#include "vulkan/vk_lighttilepolicy.h"

#include <cassert>
#include <cstddef>
#include <iostream>

namespace
{
	constexpr std::size_t DynLightInfoBytes = 80;
	constexpr std::size_t LightTileBlockBytes = 4 * sizeof(int) + 16 * DynLightInfoBytes;

	std::size_t ZMinMaxBytes(int width, int height)
	{
		width = (width + 63) / 64 * 64;
		height = (height + 63) / 64 * 64;
		std::size_t bytes = 0;
		for (int i = 0; i < 6; ++i)
		{
			width >>= 1;
			height >>= 1;
			bytes += static_cast<std::size_t>(width) * static_cast<std::size_t>(height) * 8u;
		}
		return bytes;
	}
}

int main()
{
	static_assert(!VkLightTilePolicy::Enabled);
	static_assert(LightTileBlockBytes == 1296);

	constexpr int width = 1904;
	constexpr int height = 1001;
	const auto activeTiles = VkLightTilePolicy::BufferSize(width, height, LightTileBlockBytes, true);
	const auto dormantTiles = VkLightTilePolicy::BufferSize(width, height, LightTileBlockBytes, false);
	const auto zminmax = ZMinMaxBytes(width, height);

	assert(activeTiles == 622080);
	assert(dormantTiles == 1296);
	assert(zminmax == 5241600);
	assert(zminmax + activeTiles - dormantTiles == 5862384);

	// The enable seam must recover the inherited ceil(width/64)*ceil(height/64)
	// sizing, including odd and sub-tile extents.
	assert(VkLightTilePolicy::BufferSize(1, 1, LightTileBlockBytes, true) == LightTileBlockBytes);
	assert(VkLightTilePolicy::BufferSize(65, 65, LightTileBlockBytes, true) == 4 * LightTileBlockBytes);
	assert(VkLightTilePolicy::BufferSize(0, 0, LightTileBlockBytes, true) == LightTileBlockBytes);
	assert(VkLightTilePolicy::BufferSize(65, 65, LightTileBlockBytes, false) == LightTileBlockBytes);

	std::cout << "PF-019 dormant resource fixture passed: "
		<< (zminmax + activeTiles - dormantTiles)
		<< " bytes avoided at 1904x1001 before allocator overhead\n";
	return 0;
}
