#pragma once

// CFX-006: bounded query plumbing, also exercised with injected CPU-only callbacks.
#include "vulkan/vulkan_core.h"
#include "cfxtrace.h"
#include <vector>

namespace CfxFault
{
struct Payload
{
	VkDeviceFaultCountsEXT counts{ VK_STRUCTURE_TYPE_DEVICE_FAULT_COUNTS_EXT };
	VkDeviceFaultInfoEXT info{ VK_STRUCTURE_TYPE_DEVICE_FAULT_INFO_EXT };
	std::vector<VkDeviceFaultAddressInfoEXT> addresses;
	std::vector<VkDeviceFaultVendorInfoEXT> vendors;
	std::vector<uint8_t> binary;
	VkResult result = VK_ERROR_UNKNOWN;
	bool available = false;
};
inline void Counts(const char* event, const VkDeviceFaultCountsEXT& c, VkResult result)
{
	char line[160];
	std::snprintf(line, sizeof(line), "addresses=%u vendors=%u binary_bytes=%llu",
		c.addressInfoCount, c.vendorInfoCount, (unsigned long long)c.vendorBinarySize);
	CfxTrace::Mark(event, line, static_cast<int>(result));
}
inline Payload QueryEXT(VkDevice device, bool extension, bool feature, PFN_vkGetDeviceFaultInfoEXT query)
{
	Payload p;
	if (!extension || !feature || !query)
	{
		CfxTrace::Mark("device-fault-unavailable", !extension ? "EXT-not-enabled" : !feature ? "feature-not-enabled" : "entry-point-missing");
		return p;
	}
	CfxTrace::Mark("device-fault-count-enter", "vkGetDeviceFaultInfoEXT");
	p.result = query(device, &p.counts, nullptr);
	Counts("device-fault-count-return", p.counts, p.result);
	if (p.result != VK_SUCCESS && p.result != VK_INCOMPLETE) return p;
	const auto reported = p.counts;
	p.counts.addressInfoCount = std::min(p.counts.addressInfoCount, 128u);
	p.counts.vendorInfoCount = std::min(p.counts.vendorInfoCount, 128u);
	p.counts.vendorBinarySize = std::min<VkDeviceSize>(p.counts.vendorBinarySize, 32u * 1024u * 1024u);
	if (reported.addressInfoCount != p.counts.addressInfoCount || reported.vendorInfoCount != p.counts.vendorInfoCount || reported.vendorBinarySize != p.counts.vendorBinarySize)
		Counts("device-fault-cap-truncated", p.counts, p.result);
	p.addresses.resize(p.counts.addressInfoCount);
	p.vendors.resize(p.counts.vendorInfoCount);
	p.binary.resize(static_cast<size_t>(p.counts.vendorBinarySize));
	// Null pointers for zero capacity are required; a vector's empty data() is not
	// specified to be null. Keep storage alive through the query and interpretation.
	p.info.pAddressInfos = p.addresses.empty() ? nullptr : p.addresses.data();
	p.info.pVendorInfos = p.vendors.empty() ? nullptr : p.vendors.data();
	p.info.pVendorBinaryData = p.binary.empty() ? nullptr : p.binary.data();
	Counts("device-fault-data-enter", p.counts, p.result);
	p.result = query(device, &p.counts, &p.info);
	Counts("device-fault-data-return", p.counts, p.result);
	p.available = p.result == VK_SUCCESS || p.result == VK_INCOMPLETE;
	if (!p.available) return p;
	if (p.counts.addressInfoCount > p.addresses.size() || p.counts.vendorInfoCount > p.vendors.size() || p.counts.vendorBinarySize > p.binary.size())
		CfxTrace::Mark("device-fault-return-truncated", "returned counts exceed supplied storage", static_cast<int>(p.result));
	p.addresses.resize(std::min<size_t>(p.counts.addressInfoCount, p.addresses.size()));
	p.vendors.resize(std::min<size_t>(p.counts.vendorInfoCount, p.vendors.size()));
	p.binary.resize(std::min<size_t>(static_cast<size_t>(p.counts.vendorBinarySize), p.binary.size()));
	if (p.addresses.empty() && p.vendors.empty() && p.binary.empty() && !p.info.description[0])
		CfxTrace::Mark("device-fault-empty", "query returned no payload", static_cast<int>(p.result));
	return p;
}
inline void QueryNV(VkQueue queue, const char* name, bool extension, PFN_vkGetQueueCheckpointDataNV query)
{
	if (!extension || !query || !queue)
	{
		char line[120];
		std::snprintf(line, sizeof(line), "%s %s", name, !extension ? "NV-not-enabled" : !query ? "entry-point-missing" : "queue-unavailable");
		CfxTrace::Mark("checkpoint-query-unavailable", line);
		return;
	}
	char line[180];
	std::snprintf(line, sizeof(line), "%s queue=%p api=void", name, (void*)queue);
	CfxTrace::Mark("checkpoint-count-enter", line);
	uint32_t count = 0;
	query(queue, &count, nullptr);
	std::snprintf(line, sizeof(line), "%s queue=%p count=%u capacity=%u truncated=%d api=void", name, (void*)queue, count, std::min(count, 256u), count > 256 ? 1 : 0);
	CfxTrace::Mark("checkpoint-count-return", line);
	std::vector<VkCheckpointDataNV> data(std::min(count, 256u));
	for (auto& item : data) item.sType = VK_STRUCTURE_TYPE_CHECKPOINT_DATA_NV;
	count = static_cast<uint32_t>(data.size());
	if (count)
	{
		CfxTrace::Mark("checkpoint-data-enter", line);
		query(queue, &count, data.data());
		std::snprintf(line, sizeof(line), "%s queue=%p returned=%u capacity=%zu truncated=%d api=void", name, (void*)queue, count, data.size(), count > data.size() ? 1 : 0);
		CfxTrace::Mark("checkpoint-data-return", line);
	}
	for (uint32_t i = 0; i < count && i < data.size(); ++i)
	{
		std::snprintf(line, sizeof(line), "%s queue=%p stage=%u marker=%p", name, (void*)queue, data[i].stage, data[i].pCheckpointMarker);
		CfxTrace::Mark("gpu-checkpoint-confirmed", line);
	}
}
}
