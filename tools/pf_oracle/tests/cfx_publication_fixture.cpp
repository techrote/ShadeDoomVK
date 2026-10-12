// CPU-only Vulkan API callbacks. The included builder definitions are extracted
// verbatim from production vulkanbuilders.cpp by test_cfx_publication.py. No
// loader, instance, Vulkan device or renderer is created or executed.
#include "zvulkan/vulkanbuilders.h"
#include "zvulkan/vulkancompatibledevice.h"
#include <cassert>
#include <cstring>
#include <stdexcept>

static unsigned shaders = 0, graphics = 0, computes = 0, binds = 0, sets = 0, draws = 0, updates = 0, copies = 0;
static bool librariesEnabled = false;
static bool finishDuringGraphics = false;
static std::shared_ptr<CfxTrace::WitnessDescriptor> trackedSet;
static uint64_t expectedPublication = 0;
static std::vector<std::vector<uint32_t>> submittedCode;
static VKAPI_ATTR VkResult VKAPI_CALL createShader(VkDevice, const VkShaderModuleCreateInfo* info, const VkAllocationCallbacks*, VkShaderModule* out)
{
    assert(info->sType == VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO && info->codeSize % 4 == 0);
    submittedCode.emplace_back(info->pCode, info->pCode + info->codeSize / 4);
    // Deliberately recycled handles cannot be allocation identity.
    *out = (VkShaderModule)uintptr_t(0x88); ++shaders; return VK_SUCCESS;
}
static VKAPI_ATTR VkResult VKAPI_CALL createGraphics(VkDevice, VkPipelineCache, uint32_t count, const VkGraphicsPipelineCreateInfo* info, const VkAllocationCallbacks*, VkPipeline* out)
{
    assert(count == 1 && info->sType == VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO);
    for (uint32_t i = 0; i < info->stageCount; ++i) assert(info->pStages[i].module && std::strcmp(info->pStages[i].pName, "main") == 0);
    if (finishDuringGraphics) CfxTrace::WitnessFinish();
    *out = (VkPipeline)uintptr_t(0x77); ++graphics; return VK_SUCCESS;
}
static VKAPI_ATTR VkResult VKAPI_CALL createCompute(VkDevice, VkPipelineCache, uint32_t count, const VkComputePipelineCreateInfo* info, const VkAllocationCallbacks*, VkPipeline* out)
{
    assert(count == 1 && info->stage.stage == VK_SHADER_STAGE_COMPUTE_BIT);
    *out = (VkPipeline)uintptr_t(0x66); ++computes; return VK_SUCCESS;
}
static VKAPI_ATTR void VKAPI_CALL destroyShader(VkDevice, VkShaderModule, const VkAllocationCallbacks*) {}
static VKAPI_ATTR void VKAPI_CALL destroyPipeline(VkDevice, VkPipeline, const VkAllocationCallbacks*) {}
static VKAPI_ATTR void VKAPI_CALL destroyLayout(VkDevice, VkPipelineLayout, const VkAllocationCallbacks*) {}
static VKAPI_ATTR void VKAPI_CALL destroyDescriptorPool(VkDevice, VkDescriptorPool, const VkAllocationCallbacks*) {}
static VKAPI_ATTR VkResult VKAPI_CALL freeSets(VkDevice, VkDescriptorPool, uint32_t, const VkDescriptorSet*) { return VK_SUCCESS; }
static VKAPI_ATTR void VKAPI_CALL updateSets(VkDevice, uint32_t count, const VkWriteDescriptorSet* writes, uint32_t copiesCount, const VkCopyDescriptorSet*)
{
    assert(count && !copiesCount);
    for (uint32_t i = 0; i < count; ++i) assert(writes[i].descriptorCount == 1 && writes[i].dstSet);
    // Actual wrapper publication must advance only after the void API returns.
    if (trackedSet) assert(trackedSet->generation.load() == expectedPublication);
    ++updates;
}
static VKAPI_ATTR VkResult VKAPI_CALL allocateCommands(VkDevice, const VkCommandBufferAllocateInfo*, VkCommandBuffer* out)
{ *out = (VkCommandBuffer)uintptr_t(0x55); return VK_SUCCESS; }
static VKAPI_ATTR void VKAPI_CALL freeCommands(VkDevice, VkCommandPool, uint32_t, const VkCommandBuffer*) {}
static VKAPI_ATTR VkResult VKAPI_CALL createPool(VkDevice, const VkCommandPoolCreateInfo*, const VkAllocationCallbacks*, VkCommandPool* out)
{ *out = (VkCommandPool)uintptr_t(0x11); return VK_SUCCESS; }
static VKAPI_ATTR void VKAPI_CALL destroyPool(VkDevice, VkCommandPool, const VkAllocationCallbacks*) {}
static VKAPI_ATTR VkResult VKAPI_CALL beginCommands(VkCommandBuffer, const VkCommandBufferBeginInfo* info)
{ assert(info->flags == VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT); return VK_SUCCESS; }
static VKAPI_ATTR VkResult VKAPI_CALL endCommands(VkCommandBuffer) { return VK_SUCCESS; }
static VKAPI_ATTR void VKAPI_CALL bindPipeline(VkCommandBuffer, VkPipelineBindPoint point, VkPipeline pipeline)
{ assert(point == VK_PIPELINE_BIND_POINT_GRAPHICS && pipeline == (VkPipeline)uintptr_t(0x77)); ++binds; }
static VKAPI_ATTR void VKAPI_CALL bindSets(VkCommandBuffer, VkPipelineBindPoint point, VkPipelineLayout layout, uint32_t first, uint32_t count, const VkDescriptorSet* values, uint32_t dynamicCount, const uint32_t* dynamic)
{ assert(point == VK_PIPELINE_BIND_POINT_GRAPHICS && layout && first <= 1 && count == 1 && values[0]); assert(!dynamicCount || dynamic); ++sets; }
static VKAPI_ATTR void VKAPI_CALL draw(VkCommandBuffer, uint32_t count, uint32_t instances, uint32_t first, uint32_t firstInstance)
{ assert(count == 3 && instances == 1 && first == 0 && firstInstance == 0); ++draws; }
static VKAPI_ATTR void VKAPI_CALL copy(VkCommandBuffer, VkBuffer, VkBuffer, uint32_t count, const VkBufferCopy* ranges)
{ assert(count == 1 && ranges[0].size == 16); ++copies; }
PFN_vkCreateShaderModule vkCreateShaderModule = createShader;
PFN_vkCreateGraphicsPipelines vkCreateGraphicsPipelines = createGraphics;
PFN_vkCreateComputePipelines vkCreateComputePipelines = createCompute;
PFN_vkDestroyShaderModule vkDestroyShaderModule = destroyShader;
PFN_vkDestroyPipeline vkDestroyPipeline = destroyPipeline;
PFN_vkDestroyPipelineLayout vkDestroyPipelineLayout = destroyLayout;
PFN_vkDestroyDescriptorPool vkDestroyDescriptorPool = destroyDescriptorPool;
PFN_vkFreeDescriptorSets vkFreeDescriptorSets = freeSets;
PFN_vkUpdateDescriptorSets vkUpdateDescriptorSets = updateSets;
PFN_vkAllocateCommandBuffers vkAllocateCommandBuffers = allocateCommands;
PFN_vkFreeCommandBuffers vkFreeCommandBuffers = freeCommands;
PFN_vkCreateCommandPool vkCreateCommandPool = createPool;
PFN_vkDestroyCommandPool vkDestroyCommandPool = destroyPool;
PFN_vkBeginCommandBuffer vkBeginCommandBuffer = beginCommands;
PFN_vkEndCommandBuffer vkEndCommandBuffer = endCommands;
PFN_vkCmdBindPipeline vkCmdBindPipeline = bindPipeline;
PFN_vkCmdBindDescriptorSets vkCmdBindDescriptorSets = bindSets;
PFN_vkCmdDraw vkCmdDraw = draw;
PFN_vkCmdCopyBuffer vkCmdCopyBuffer = copy;
PFN_vkGetQueueCheckpointDataNV vkGetQueueCheckpointDataNV = nullptr;
VKAPI_ATTR void VKAPI_CALL vmaDestroyBuffer(VmaAllocator, VkBuffer, VmaAllocation) {}
VulkanDevice::VulkanDevice(std::shared_ptr<VulkanInstance>, std::shared_ptr<VulkanSurface>, const VulkanCompatibleDevice&) {}
VulkanDevice::~VulkanDevice() {}
bool VulkanDevice::SupportsExtension(const char*) const { return librariesEnabled; }
void VulkanDevice::SetObjectName(const char*, uint64_t, VkObjectType) {}
VulkanDeviceFaultInfo VulkanDevice::GetDeviceFaultInfo() { return {}; }
std::string VkResultToString(VkResult r) { return std::to_string(static_cast<int>(r)); }
void VulkanPrintLog(const char*, const std::string&) {}
void VulkanError(const char* message) { throw std::runtime_error(message); }

#include "cfx_witness_production.inc"

int main(int argc, char** argv)
{
    assert(argc == 2);
    const std::string mode = argv[1];
    if (mode == "recordcap" || mode == "streamcap" || mode == "blobcap" || mode == "uploadcap")
    {
        assert(CfxTrace::WitnessEnabled());
        if (mode == "recordcap") CfxTrace::WitnessState().records = CfxTrace::WitnessRecordLimit - 2;
        if (mode == "streamcap") CfxTrace::WitnessState().streamBytes = CfxTrace::WitnessStreamByteLimit - 1024;
        if (mode == "blobcap") CfxTrace::WitnessExportBytes("oversize.spv", (void*)uintptr_t(1), CfxTrace::WitnessBlobLimit + 1);
        if (mode == "uploadcap") CfxTrace::WitnessUpload(1, 2, 0, 0, (void*)uintptr_t(1), CfxTrace::WitnessBlobLimit + 1);
        CfxTrace::WitnessMark("over-limit", "test=bounded");
        CfxTrace::WitnessFinish();
        return 0;
    }
    if (mode == "legacycap") CfxTrace::State().resourceRecords.store(8192);
    librariesEnabled = mode == "library";
    finishDuringGraphics = mode == "closemidbuild";
    bool active = CfxTrace::WitnessEnabled();
    VulkanDevice device({}, {}, {});
    VulkanCommandPool pool(&device, 0);
    VulkanDescriptorPool descriptorPool(&device, (VkDescriptorPool)uintptr_t(0x22));
    VulkanPipelineLayout layout(&device, (VkPipelineLayout)uintptr_t(0x44));
    // Known synthetic words test exact argument capture, not SPIR-V validity.
    const std::vector<uint32_t> vertex = {0x07230203, 0x00010000, 11, 3, 0, 0x12345678};
    const std::vector<uint32_t> fragment = {0x07230203, 0x00010300, 22, 4, 0, 0xabcdef00};
    const uint32_t constant = 0x13572468;
    std::unique_ptr<VulkanPipeline> pipeline, vertexLibrary, fragmentLibrary;
    if (librariesEnabled)
    {
        vertexLibrary = GraphicsPipelineBuilder().Layout(&layout).Flags(VK_PIPELINE_CREATE_LIBRARY_BIT_KHR)
            .LibraryFlags(VK_GRAPHICS_PIPELINE_LIBRARY_PRE_RASTERIZATION_SHADERS_BIT_EXT).AddVertexShader(vertex).AddConstant(17, constant).Create(&device);
        fragmentLibrary = GraphicsPipelineBuilder().Layout(&layout).Flags(VK_PIPELINE_CREATE_LIBRARY_BIT_KHR)
            .LibraryFlags(VK_GRAPHICS_PIPELINE_LIBRARY_FRAGMENT_SHADER_BIT_EXT).AddFragmentShader(fragment).Create(&device);
        pipeline = GraphicsPipelineBuilder().Layout(&layout).AddLibrary(vertexLibrary.get()).AddLibrary(fragmentLibrary.get()).Create(&device);
    }
    else pipeline = GraphicsPipelineBuilder().Layout(&layout).AddVertexShader(vertex).AddConstant(17, constant).AddFragmentShader(fragment).Create(&device);
    active = CfxTrace::WitnessEnabled();
    assert(submittedCode.size() == 2 && submittedCode[0] == vertex && submittedCode[1] == fragment);
    if (active) assert(pipeline->witness && pipeline->witness->stages.size() == 2 && pipeline->witness->stages[0]->shader.id != pipeline->witness->stages[1]->shader.id);
    auto descriptor = std::make_unique<VulkanDescriptorSet>(&device, &descriptorPool, (VkDescriptorSet)uintptr_t(0x33));
    trackedSet = descriptor->witness;
    VulkanBuffer staging(&device, (VkBuffer)uintptr_t(0x99), nullptr, 32);
    VulkanBuffer nodes(&device, (VkBuffer)uintptr_t(0xaa), nullptr, 16);
    VulkanBuffer vertices(&device, (VkBuffer)uintptr_t(0xbb), nullptr, 48);
    VulkanBuffer indices(&device, (VkBuffer)uintptr_t(0xcc), nullptr, 12);
    WriteDescriptors writes;
    writes.AddBuffer(descriptor.get(), 2, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, &nodes)
        .AddBuffer(descriptor.get(), 3, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, &vertices)
        .AddBuffer(descriptor.get(), 4, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, &indices).Execute(&device);
    if (active) assert(descriptor->witness->generation.load() == 1);
    auto cmd = pool.createBuffer();
    cmd->begin();
    CfxTrace::Upload(staging.diagnosticId, nodes.diagnosticId, 0, 0, "abcdefghijklmnop", 16);
    cmd->copyBuffer(&staging, &nodes); // actual WHOLE_SIZE is destination size16
    cmd->bindPipeline(VK_PIPELINE_BIND_POINT_GRAPHICS, pipeline.get());
    const uint32_t dynamic[] = {16, 32};
    cmd->bindDescriptorSet(VK_PIPELINE_BIND_POINT_GRAPHICS, &layout, 0, descriptor.get(), 2, dynamic);
    std::unique_ptr<VulkanPipelineLayout> otherLayout;
    if (mode == "disturbed")
    {
        otherLayout = std::make_unique<VulkanPipelineLayout>(&device, (VkPipelineLayout)uintptr_t(0x45));
        cmd->bindDescriptorSet(VK_PIPELINE_BIND_POINT_GRAPHICS, otherLayout.get(), 1, descriptor.get());
    }
    if (mode == "stale")
    {
        expectedPublication = active ? 1 : 0;
        WriteDescriptors().AddBuffer(descriptor.get(), 2, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, &nodes).Execute(&device);
        if (active) assert(descriptor->witness->generation.load() == 2);
    }
    if (mode == "retired") { descriptor.reset(); pipeline.reset(); }
    if (mode == "raw")
    {
        cmd->bindPipeline(VK_PIPELINE_BIND_POINT_GRAPHICS, pipeline->pipeline);
        cmd->bindDescriptorSets(VK_PIPELINE_BIND_POINT_GRAPHICS, layout.layout, 0, 1, &descriptor->set, 0, nullptr);
    }
    cmd->draw(3, 1, 0, 0);
    cmd->end();
    if (mode == "reset") { cmd->begin(); cmd->draw(3, 1, 0, 0); cmd->end(); }
    if (mode == "reuse")
    {
        const auto previousId = descriptor->diagnosticId;
        descriptor.reset();
        descriptor = std::make_unique<VulkanDescriptorSet>(&device, &descriptorPool, (VkDescriptorSet)uintptr_t(0x33));
        if (active) assert(descriptor->diagnosticId != previousId && descriptor->witness->generation == 0);
        trackedSet = descriptor->witness; expectedPublication = 0;
        writes = WriteDescriptors();
        writes.AddBuffer(descriptor.get(), 2, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, &nodes).Execute(&device);
        cmd->begin(); cmd->bindPipeline(VK_PIPELINE_BIND_POINT_GRAPHICS, pipeline.get());
        cmd->bindDescriptorSet(VK_PIPELINE_BIND_POINT_GRAPHICS, &layout, 0, descriptor.get());
        cmd->draw(3, 1, 0, 0); cmd->end();
    }
    CfxTrace::WitnessFinish();
    std::printf("shaders=%u graphics=%u compute=%u pipeline_binds=%u set_binds=%u draws=%u updates=%u copies=%u\n", shaders, graphics, computes, binds, sets, draws, updates, copies);
}
