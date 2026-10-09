#pragma once

// SDVK-009: pure light-buffer capacity policy shared by the live Vulkan
// uploader and host-only boundary qualification. Count is both the number of
// ivec4 range entries and the maximum number of FDynLightInfo records.
namespace VkLightUploadPolicy
{
constexpr bool Fits(int count, int uploadIndex, int dataIndex, int recordCount)
{
	return count > 0 && uploadIndex >= 0 && uploadIndex < count &&
		dataIndex >= 0 && dataIndex <= count && recordCount >= 0 &&
		recordCount <= count - dataIndex;
}
}
