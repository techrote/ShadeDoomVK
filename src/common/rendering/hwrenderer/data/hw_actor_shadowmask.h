#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cmath>

// CPU-only source-alpha filtering. Kept separate from actor/renderer state so
// native tests exercise the exact mask construction used by the live renderer.
namespace HWActorShadow
{
inline bool BuildAlphaMask(const uint8_t* bgra, int sourceWidth, int sourceHeight,
	int maskWidth, int maskHeight, unsigned alphaCutoff,
	uint32_t* words, size_t wordCount)
{
	if (!words || !bgra || sourceWidth <= 0 || sourceHeight <= 0 ||
		sourceWidth > 2048 || sourceHeight > 2048 || maskWidth <= 0 ||
		maskHeight <= 0 || maskWidth > 2048 || maskHeight > 2048 ||
		wordCount != (size_t(maskWidth) * size_t(maskHeight) + 31) / 32 ||
		alphaCutoff == 0 || alphaCutoff > 255)
		return false;
	std::fill(words, words + wordCount, 0u);
	bool anyOpaque = false;
	for (int y = 0; y < maskHeight; ++y)
	{
		for (int x = 0; x < maskWidth; ++x)
		{
			// A box footprint on downsampled axes preserves area coverage. On
			// upsampled axes bilinear alpha reconstructs a clean, bounded edge;
			// RGB never participates and displayed sprite texels are untouched.
			const double centerX = (double(x) + 0.5) * sourceWidth / maskWidth - 0.5;
			const double centerY = (double(y) + 0.5) * sourceHeight / maskHeight - 0.5;
			const double spanX = std::max(1.0, double(sourceWidth) / maskWidth);
			const double spanY = std::max(1.0, double(sourceHeight) / maskHeight);
			const double minX = centerX - spanX * 0.5;
			const double maxX = centerX + spanX * 0.5;
			const double minY = centerY - spanY * 0.5;
			const double maxY = centerY + spanY * 0.5;
			const int beginX = int(std::floor(minX + 0.5));
			const int endX = int(std::ceil(maxX + 0.5));
			const int beginY = int(std::floor(minY + 0.5));
			const int endY = int(std::ceil(maxY + 0.5));
			double alpha = 0.0;
			for (int sy = beginY; sy < endY; ++sy)
			{
				const double weightY = std::max(0.0, std::min(maxY, sy + 0.5) - std::max(minY, sy - 0.5));
				const int py = std::clamp(sy, 0, sourceHeight - 1);
				for (int sx = beginX; sx < endX; ++sx)
				{
					const double weightX = std::max(0.0, std::min(maxX, sx + 0.5) - std::max(minX, sx - 0.5));
					const int px = std::clamp(sx, 0, sourceWidth - 1);
					alpha += bgra[(size_t(py) * sourceWidth + px) * 4 + 3] * weightX * weightY;
				}
			}
			if (alpha >= alphaCutoff * spanX * spanY)
			{
				const size_t bit = size_t(y) * maskWidth + x;
				words[bit / 32] |= uint32_t(1) << (bit % 32);
				anyOpaque = true;
			}
		}
	}
	return anyOpaque;
}
}
