// CPU-only Vulkan callbacks: no loader, driver, instance or GPU is used.
#include "zvulkan/vulkanobjects.h"
#include "zvulkan/vulkancompatibledevice.h"
#include "vulkan/descriptorsets/vk_bindless.h"
#include <cassert>
#include <cstring>
#include <stdexcept>

static int scenario = 0, calls = 0, copied = 0, destroyed = 0;
static uint32_t capacity = 0;
static VKAPI_ATTR VkResult VKAPI_CALL fault(VkDevice, VkDeviceFaultCountsEXT* c, VkDeviceFaultInfoEXT* p)
{
    ++calls;
    if (!p)
    {
        if (scenario == 1) return VK_ERROR_DEVICE_LOST;
        c->addressInfoCount = scenario == 3 ? 999 : scenario == 0 ? 0 : 1;
        c->vendorInfoCount = scenario == 3 ? 999 : 0;
        c->vendorBinarySize = scenario == 3 ? 100ull * 1024 * 1024 : 0;
        return VK_SUCCESS;
    }
    assert(c->addressInfoCount <= 128 && c->vendorInfoCount <= 128 && c->vendorBinarySize <= 32ull*1024*1024);
    if (!c->addressInfoCount) assert(!p->pAddressInfos);
    if (!c->vendorInfoCount) assert(!p->pVendorInfos);
    if (!c->vendorBinarySize) assert(!p->pVendorBinaryData);
    if (scenario == 2) return VK_ERROR_UNKNOWN;
    if (scenario == 3)
    {
        for (uint32_t i = 0; i < c->addressInfoCount; ++i) p->pAddressInfos[i].reportedAddress = 0x1234;
        c->addressInfoCount = 900; c->vendorInfoCount = 900; c->vendorBinarySize = 100ull*1024*1024;
        return VK_INCOMPLETE;
    }
    if (scenario == 4)
    {
        p->pAddressInfos[0].addressType = VK_DEVICE_FAULT_ADDRESS_TYPE_READ_INVALID_EXT;
        p->pAddressInfos[0].reportedAddress = 0x1234;
        std::strcpy(p->description, "synthetic fault");
    }
    return VK_SUCCESS;
}
static VKAPI_ATTR void VKAPI_CALL checkpoints(VkQueue, uint32_t* c, VkCheckpointDataNV* data)
{
    ++calls;
    if (!data) { *c = scenario == 0 ? 0 : 900; return; }
    capacity = *c;
    assert(capacity <= 256);
    if (scenario == 3) { *c = 0; return; }
    for (uint32_t i = 0; i < capacity; ++i)
    {
        assert(data[i].sType == VK_STRUCTURE_TYPE_CHECKPOINT_DATA_NV);
        data[i].stage = VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT;
        data[i].pCheckpointMarker = reinterpret_cast<void*>(uintptr_t(0x77));
    }
    *c = scenario == 2 ? 900 : capacity;
}
// Only the PFN variables reached by this fixture are defined. None dispatch to Vulkan.
PFN_vkGetQueueCheckpointDataNV vkGetQueueCheckpointDataNV = checkpoints;
static VKAPI_ATTR VkResult VKAPI_CALL allocate(VkDevice, const VkCommandBufferAllocateInfo*, VkCommandBuffer* out)
{ *out = reinterpret_cast<VkCommandBuffer>(uintptr_t(0x55)); return VK_SUCCESS; }
static VKAPI_ATTR void VKAPI_CALL freeCommands(VkDevice, VkCommandPool, uint32_t, const VkCommandBuffer*) {}
static VKAPI_ATTR VkResult VKAPI_CALL createPool(VkDevice, const VkCommandPoolCreateInfo*, const VkAllocationCallbacks*, VkCommandPool* out)
{ *out = (VkCommandPool)uintptr_t(0x11); return VK_SUCCESS; }
static VKAPI_ATTR void VKAPI_CALL destroyPool(VkDevice, VkCommandPool, const VkAllocationCallbacks*) {}
static VKAPI_ATTR void VKAPI_CALL copy(VkCommandBuffer cmd, VkBuffer, VkBuffer, uint32_t count, const VkBufferCopy* ranges)
{ assert(cmd && count == 1 && ranges->srcOffset == 2 && ranges->dstOffset == 4 && ranges->size == 3); ++copied; }
PFN_vkAllocateCommandBuffers vkAllocateCommandBuffers = allocate;
PFN_vkFreeCommandBuffers vkFreeCommandBuffers = freeCommands;
PFN_vkCreateCommandPool vkCreateCommandPool = createPool;
PFN_vkDestroyCommandPool vkDestroyCommandPool = destroyPool;
PFN_vkCmdCopyBuffer vkCmdCopyBuffer = copy;
VKAPI_ATTR void VKAPI_CALL vmaDestroyBuffer(VmaAllocator, VkBuffer, VmaAllocation) { ++destroyed; }
VulkanDevice::VulkanDevice(std::shared_ptr<VulkanInstance>, std::shared_ptr<VulkanSurface>, const VulkanCompatibleDevice&) {}
VulkanDevice::~VulkanDevice() {}
bool VulkanDevice::SupportsExtension(const char*) const { return false; }
VulkanDeviceFaultInfo VulkanDevice::GetDeviceFaultInfo() { throw std::bad_alloc(); }
std::string VkResultToString(VkResult r) { return std::to_string(static_cast<int>(r)); }
void VulkanPrintLog(const char*, const std::string&) {}
void VulkanError(const char* message) { throw std::runtime_error(message); }

int main(int argc, char** argv)
{
    assert(argc == 2);
    std::string mode = argv[1];
    if (mode == "faults")
    {
        assert(!CfxFault::QueryEXT(nullptr, false, true, fault).available);
        assert(!CfxFault::QueryEXT(nullptr, true, false, fault).available);
        assert(!CfxFault::QueryEXT(nullptr, true, true, nullptr).available);
        assert(calls == 0);
        for (scenario = 0; scenario < 5; ++scenario)
        {
            const auto p = CfxFault::QueryEXT(nullptr, true, true, fault);
            assert(p.available == (scenario == 0 || scenario >= 3));
            if (scenario == 4) { assert(p.addresses.size() == 1 && p.addresses[0].reportedAddress == 0x1234); assert(std::string(p.info.description) == "synthetic fault"); }
            if (scenario == 3) { assert(p.addresses.size() == 128 && p.vendors.size() == 128 && p.binary.size() == 32ull*1024*1024); assert(p.addresses[0].reportedAddress == 0x1234); }
        }
        calls = 0;
        CfxFault::QueryNV(nullptr, "graphics", true, checkpoints);
        CfxFault::QueryNV((VkQueue)uintptr_t(1), "graphics", false, checkpoints);
        CfxFault::QueryNV((VkQueue)uintptr_t(1), "graphics", true, nullptr);
        assert(calls == 0);
        for (scenario = 0; scenario < 4; ++scenario) CfxFault::QueryNV((VkQueue)uintptr_t(1), "graphics", true, checkpoints);
        assert(calls == 7 && capacity == 256);
    }
    else if (mode == "handler")
    {
        VulkanDevice device({}, {}, {});
        try { device.CheckVulkanError(VK_ERROR_DEVICE_LOST, "synthetic-submit"); assert(false); }
        catch (const std::runtime_error& e) { assert(std::string(e.what()) == "synthetic-submit: -4"); }
        assert(CfxTrace::State().deviceLost.load() == CfxTrace::Enabled());
    }
    else
    {
        const bool active = CfxTrace::ResourcesEnabled();
        VulkanDevice device({}, {}, {});
        VulkanCommandPool pool(&device, 0);
        {
            VulkanBuffer a(&device, (VkBuffer)uintptr_t(1), nullptr, 32), b(&device, (VkBuffer)uintptr_t(2), nullptr, 32);
            auto cmd = pool.createBuffer();
            assert((a.diagnosticId != 0) == active);
            assert(!active || (a.diagnosticId != b.diagnosticId && b.diagnosticId != cmd->diagnosticId));
            // Hash known bytes; copying stays identical in enabled/disabled modes.
            CfxTrace::Upload(a.diagnosticId, b.diagnosticId, 2, 4, "abc", 3);
            cmd->copyBuffer(&a, &b, 2, 4, 3);
            CfxTrace::NextSubmission();
            CfxTrace::Object("synthetic-submit-buffer", "command", cmd->diagnosticId, (uint64_t)cmd->buffer);
            VkBindlessSlotAllocator slots; slots.Configure(259, 300);
            const int start = slots.Allocate(2); auto old = slots.CurrentIdentity(start);
            assert(slots.Free(start) && slots.Allocate(2) == start);
            assert(!slots.ValidateIdentity(old) && slots.CurrentIdentity(start).Generation != old.Generation);
            if (mode == "caps")
            {
                // Invalid pointer proves omitted hashing never dereferences the input.
                CfxTrace::Upload(a.diagnosticId, b.diagnosticId, 0, 0, (void*)uintptr_t(1), 16777217);
                CfxTrace::State().hashBytes.store(67108864);
                CfxTrace::Upload(a.diagnosticId, b.diagnosticId, 0, 0, (void*)uintptr_t(1), 1);
                CfxTrace::State().resourceRecords.store(8192);
                CfxTrace::ResourceMark("must-be-omitted", "");
                CfxTrace::ResourceMark("must-be-omitted", "");
                CfxTrace::Mark("device-lost-observed", "synthetic after truncation", -4);
            }
        }
        assert(copied == 1 && destroyed == 2);
        assert(!active || CfxTrace::State().hashBytes.load() >= 3);
        if (!active) assert(CfxTrace::State().hashBytes.load() == 0 && CfxTrace::State().resourceRecords.load() == 0);
    }
}
