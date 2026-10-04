// PF113 current-source CPU fixture. Never links a renderer or executes Vulkan.
// Generated definitions are extracted from actual producer/builders and GLSL.
// Bounded allocations, constant-colour sample services and passive observers
// prove source semantics; they cannot prove spatial GPU filtering or rendering.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <functional>
#include <iostream>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

using uint = uint32_t;
static int Checks = 0;
static void Check(bool condition, const char* message)
{
    ++Checks;
    if (!condition) throw std::runtime_error(message);
}

struct vec2
{
    float x = 0, y = 0;
    vec2() = default;
    vec2(float xx, float yy) : x(xx), y(yy) { }
};
struct vec3
{
    float x = 0, y = 0, z = 0;
    vec3() = default;
    explicit vec3(float v) : x(v), y(v), z(v) { }
    vec3(float xx, float yy, float zz) : x(xx), y(yy), z(zz) { }
};
static vec3 operator+(vec3 a, vec3 b) { return { a.x + b.x, a.y + b.y, a.z + b.z }; }
static vec3 operator-(vec3 a, vec3 b) { return { a.x - b.x, a.y - b.y, a.z - b.z }; }
static vec3 operator*(vec3 a, float b) { return { a.x * b, a.y * b, a.z * b }; }
static vec2 operator-(double a, vec2 b)
{
    const float scalar = static_cast<float>(a);
    return { scalar - b.x, scalar - b.y };
}
static float dot(vec3 a, vec3 b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
static vec2 fract(vec2 v) { return { v.x - std::floor(v.x), v.y - std::floor(v.y) }; }
struct uvec4 { uint x, y, z, w; };
struct ShaderLightmap { vec2 xy; };
struct SampleResult { vec3 irradiance, prefiltered; std::array<float, 4> weights; };
static std::array<float, 4> ObservedWeights = {};
static void ResetSampleObserver() { ObservedWeights = {}; }
static void ObserveWeights(float a, float b, float c, float d) { ObservedWeights = { a, b, c, d }; }

template<typename T> struct TArray : std::vector<T>
{
    TArray() = default;
    explicit TArray(int count, bool zeroInitialize) : std::vector<T>(static_cast<size_t>(count))
    {
        (void)zeroInitialize;
        Check(count >= 0 && count <= 1024 * 1024, "CPU array service bound");
    }
    int size() const { return static_cast<int>(std::vector<T>::size()); }
    void Push(const T& item) { this->push_back(item); }
};
enum
{
    VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO = 15,
    VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO = 14, VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO = 31,
    VK_IMAGE_TYPE_2D = 1, VK_IMAGE_TILING_OPTIMAL = 0, VK_IMAGE_LAYOUT_UNDEFINED = 0,
    VK_SHARING_MODE_EXCLUSIVE = 0, VK_SAMPLE_COUNT_1_BIT = 1,
    VK_FILTER_LINEAR = 1, VK_SAMPLER_ADDRESS_MODE_REPEAT = 0,
    VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE = 2, VK_FALSE = 0,
    VK_BORDER_COLOR_INT_OPAQUE_BLACK = 3, VK_COMPARE_OP_ALWAYS = 7,
    VK_SAMPLER_MIPMAP_MODE_LINEAR = 1,
    VK_IMAGE_VIEW_TYPE_MAX_ENUM = 0x7fffffff, VK_FILTER_MAX_ENUM = 0x7fffffff,
    VK_SAMPLER_MIPMAP_MODE_MAX_ENUM = 0x7fffffff, VK_SAMPLER_ADDRESS_MODE_MAX_ENUM = 0x7fffffff,
    VK_FORMAT_UNDEFINED = 0,
    VK_IMAGE_VIEW_TYPE_2D = 1, VK_IMAGE_VIEW_TYPE_CUBE = 3,
    VK_IMAGE_ASPECT_COLOR_BIT = 1,
    VK_FORMAT_R8G8B8A8_UNORM = 37, VK_FORMAT_R16G16_SFLOAT = 83,
    VK_FORMAT_R16G16B16A16_SFLOAT = 97, VK_FORMAT_R16_UINT = 74,
    VK_IMAGE_USAGE_SAMPLED_BIT = 4, VK_IMAGE_USAGE_TRANSFER_DST_BIT = 2,
    VK_BUFFER_USAGE_TRANSFER_DST_BIT = 2, VK_IMAGE_CREATE_CUBE_COMPATIBLE_BIT = 16,
    VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL = 7, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL = 6,
    VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL = 5,
    CLAMP_XY_NOMIP = 4,
};
#define VK_NULL_HANDLE nullptr
struct Subresource
{
    int aspectMask = 0, baseMipLevel = 0, levelCount = 0, baseArrayLayer = 0;
    int layerCount = 0, mipLevel = 0;
};
using VkFormat = int;
using VkImageAspectFlags = int;
using VkSamplerAddressMode = int;
using VkImageViewType = int;
using VkFilter = int;
using VkSamplerMipmapMode = int;
using VkBool32 = int;
using VkResult = int;
using VkImageView = int;
using VkSampler = int;
struct VulkanDevice
{
    int device = 1, failures = 0;
    void CheckVulkanError(VkResult result, const char* message)
    {
        if (result != 0) { ++failures; throw std::runtime_error(message); }
    }
};
struct Extent { int width = 0, height = 0, depth = 0; };
struct ImageInfo
{
    int sType = 0, imageType = 0, arrayLayers = 0, tiling = 0, initialLayout = 0;
    int sharingMode = 0, samples = 0, flags = 0, mipLevels = 0, format = 0;
    Extent extent;
};
struct VulkanImage
{
    VulkanImage* image = this; // CPU handle service, not a VkImage.
    int width = 1, height = 1, levels = 1, layers = 1, format = 0;
    int mipLevels = 1, layerCount = 1;
    int layout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
    vec3 radiance;
};
using VkImage = VulkanImage*;
using VkImageSubresourceRange = Subresource;
struct ViewInfo { int sType = 0, viewType = 0, format = 0; VulkanImage* image = nullptr; Subresource subresourceRange; };
static std::map<VkImageView, ViewInfo> CreatedViews;
static bool FailNextView = false;
static VkResult vkCreateImageView(int device, const ViewInfo* info, const void* allocator, VkImageView* handle)
{
    (void)allocator;
    Check(device == 1 && info && handle && CreatedViews.size() < 64, "Bounded image-view API argument service");
    if (FailNextView) { FailNextView = false; return -1; }
    *handle = static_cast<int>(CreatedViews.size()) + 1;
    CreatedViews.emplace(*handle, *info);
    return 0;
}
struct VulkanImageView
{
#include "VulkanImageView_creation.hpp"
    CreationArguments Creation;
    VulkanImage* owner; int type; Subresource range;
    VulkanImageView(VulkanDevice* device, VkImageView view)
        : owner(CreatedViews.at(view).image), type(CreatedViews.at(view).viewType), range(CreatedViews.at(view).subresourceRange)
    {
        Check(device != nullptr && !Creation.Captured, "Actual metadata defaults stay unknown until successful builder capture");
    }
    void SetDebugName(const char* name) { (void)name; }
};
struct VkTextureImage { std::unique_ptr<VulkanImage> Image; std::unique_ptr<VulkanImageView> View; };
class ImageBuilder
{
    ImageInfo imageInfo;
public:
    ImageBuilder();
    ImageBuilder& Size(int width, int height, int mipLevels = 1, int arrayLayers = 1);
    ImageBuilder& Format(int f) { imageInfo.format = f; return *this; }
    ImageBuilder& Usage(int value) { (void)value; return *this; }
    ImageBuilder& Flags(int value) { (void)value; return *this; }
    ImageBuilder& DebugName(const char* value) { (void)value; return *this; }
    std::unique_ptr<VulkanImage> Create(VulkanDevice* device)
    {
        (void)device;
        Check(imageInfo.extent.width > 0 && imageInfo.extent.height > 0 && imageInfo.extent.width <= 512 && imageInfo.extent.height <= 512 && imageInfo.mipLevels >= 1 && imageInfo.mipLevels <= 5 && imageInfo.arrayLayers <= 6, "CPU image service bound");
        auto p = std::make_unique<VulkanImage>();
        p->width = imageInfo.extent.width; p->height = imageInfo.extent.height;
        p->levels = p->mipLevels = imageInfo.mipLevels;
        p->layers = p->layerCount = imageInfo.arrayLayers; p->format = imageInfo.format;
        return p;
    }
};
class ImageViewBuilder
{
    ViewInfo viewInfo;
    const char* debugName = nullptr;
public:
    ImageViewBuilder(); // Body is extracted unchanged from ZVulkan.
    ImageViewBuilder& Type(int type) { viewInfo.viewType = type; return *this; }
    ImageViewBuilder& Image(VulkanImage* image, VkFormat format, VkImageAspectFlags aspectMask = VK_IMAGE_ASPECT_COLOR_BIT, int mipLevel = 0, int arrayLayer = 0, int levelCount = 0, int layerCount = 0);
    ImageViewBuilder& DebugName(const char* name) { debugName = name; return *this; }
    std::unique_ptr<VulkanImageView> Create(VulkanDevice* device);
};
struct VkClearColorValue { std::array<float, 4> float32 = {}; };
struct VkImageCopy { Extent extent; Subresource srcSubresource, dstSubresource; };
struct DeleteList
{
    int retired = 0;
    template<typename T> void Add(std::unique_ptr<T> value) { Check(value != nullptr, "CPU delete-list service owns value"); ++retired; }
};
struct Commands
{
    DeleteList deletion;
    DeleteList* DrawDeleteList = &deletion;
    int copiedImages = 0, clears = 0;
    Commands* GetTransferCommands() { return this; }
    Commands* GetDrawCommands() { return this; }
    void copyImage(VulkanImage* source, int sourceLayout, VulkanImage* target, int targetLayout, uint32_t count, const VkImageCopy* regions)
    {
        Check(source && target && regions && count > 0 && count <= 5, "CPU copy service bound");
        Check(source->layout == sourceLayout && target->layout == targetLayout, "Actual source copy layout order");
        target->radiance = source->radiance;
        ++copiedImages;
    }
    void clearColorImage(VulkanImage* target, int layout, const VkClearColorValue* color, int count, const VkImageSubresourceRange* range)
    {
        Check(target && color && range && count == 1 && target->layout == layout, "Actual source clear layout order");
        target->radiance = { color->float32[0], color->float32[1], color->float32[2] };
        ++clears;
    }
};
class VkImageTransition
{
    std::vector<std::pair<VkTextureImage*, int>> changes;
public:
    VkImageTransition& AddImage(VkTextureImage* image, int layout, bool discard, int baseMip = 0, int mips = 1, int baseLayer = 0, int layers = 1)
    {
        (void)discard; (void)baseMip; (void)mips; (void)baseLayer; (void)layers;
        changes.emplace_back(image, layout);
        return *this;
    }
    void Execute(Commands* commands)
    {
        Check(commands != nullptr, "CPU transition service commands");
        for (const auto& item : changes) { Check(item.first->Image != nullptr, "CPU transition service image"); item.first->Image->layout = item.second; }
    }
};
struct SamplerInfo
{
    int sType = 0, magFilter = 0, minFilter = 0, addressModeU = 0, addressModeV = 0, addressModeW = 0;
    int anisotropyEnable = 0, borderColor = 0, unnormalizedCoordinates = 0, compareEnable = 0, compareOp = 0, mipmapMode = 0;
    float maxAnisotropy = 0, mipLodBias = 0, minLod = 0, maxLod = 0;
};
static std::map<VkSampler, SamplerInfo> CreatedSamplers;
static bool FailNextSampler = false;
static VkResult vkCreateSampler(int device, const SamplerInfo* info, const void* allocator, VkSampler* handle)
{
    (void)allocator;
    Check(device == 1 && info && handle && CreatedSamplers.size() < 32, "Bounded sampler API argument service");
    if (FailNextSampler) { FailNextSampler = false; return -1; }
    *handle = static_cast<int>(CreatedSamplers.size()) + 1;
    CreatedSamplers.emplace(*handle, *info);
    return 0;
}
struct VulkanSampler
{
#include "VulkanSampler_creation.hpp"
    CreationArguments Creation;
    SamplerInfo info;
    VulkanSampler() = default;
    VulkanSampler(VulkanDevice* device, VkSampler sampler) : info(CreatedSamplers.at(sampler))
    {
        Check(device != nullptr && !Creation.Captured, "Actual sampler metadata remains unknown before successful capture");
    }
    void SetDebugName(const char* name) { (void)name; }
};
using Sampler = VulkanSampler;
class SamplerBuilder
{
    SamplerInfo samplerInfo;
    const char* debugName = nullptr;
public:
    SamplerBuilder();
    SamplerBuilder& AddressMode(VkSamplerAddressMode addressMode);
    SamplerBuilder& DebugName(const char* name) { debugName = name; return *this; }
    std::unique_ptr<VulkanSampler> Create(VulkanDevice* device);
};
struct Framebuffer;
struct VkSamplerManager
{
    Framebuffer* fb;
    explicit VkSamplerManager(Framebuffer* owner) : fb(owner) { }
    Sampler other;
    std::array<std::unique_ptr<Sampler>, 2> mSamplers, mOverrideSamplers;
    std::unique_ptr<Sampler> IrradiancemapSampler, PrefiltermapSampler;
    Sampler* Get(int clamp) { (void)clamp; return &other; }
    void CreateIrradiancemapSampler();
    void CreatePrefiltermapSampler();
    void CreateHWSamplers()
    {
        for (auto& value : mSamplers) value = std::make_unique<Sampler>();
        for (auto& value : mOverrideSamplers) value = std::make_unique<Sampler>();
    }
    void ResetHWSamplers();
    void DeleteHWSamplers();
};
struct EpochService { int invalidations = 0; void Invalidate() { ++invalidations; } };
struct Framebuffer;
class VkTextureManager
{
    Framebuffer* fb;
public:
    explicit VkTextureManager(Framebuffer* owner) : fb(owner) { }
    std::unique_ptr<VulkanImage> NullTexture, BrdfLutTexture;
    std::unique_ptr<VulkanImageView> NullTextureView, BrdfLutTextureView;
    std::vector<VkTextureImage> Irradiancemaps, Prefiltermaps;
    EpochService LightProbeEpoch;
#include "source_constants.hpp"
    void CreateFixtureInitial();
    void CreateNullTexture();
    void CreateBrdfLutTexture();
    void CreateGamePalette() { }
    void CreateShadowmap() { }
    void CreateLightmap() { }
    void CreateIrradiancemap();
    void CreatePrefiltermap();
    void CheckIrradiancemapSize(int count);
    void CheckPrefiltermapSize(int count);
    void ResetLightProbes();
    void CopyIrradiancemap(const std::vector<std::unique_ptr<VulkanImage>>& probes);
    void CopyPrefiltermap(const std::vector<std::unique_ptr<VulkanImage>>& probes);
    void UploadIrradiancemap(int count, const TArray<uint16_t>& data)
    {
        Check(count >= 0 && count <= 8 && data.size() == IrradiancemapSize * IrradiancemapSize * 6 * 3 * count, "CPU initial upload service size");
        CheckIrradiancemapSize(count); // Actual extracted allocation/view logic.
        for (auto& map : Irradiancemaps) map.Image->radiance = {};
    }
    void UploadPrefiltermap(int count, const TArray<uint16_t>& data)
    {
        Check(count >= 0 && count <= 8 && data.size() > 0, "CPU initial prefilter upload service size");
        CheckPrefiltermapSize(count);
        for (auto& map : Prefiltermaps) map.Image->radiance = {};
    }
    VulkanImageView* GetNullTextureView() { return NullTextureView.get(); }
    VulkanImageView* GetBrdfLutTextureView() { return BrdfLutTextureView.get(); }
};
struct Framebuffer
{
    VulkanDevice device;
    VkTextureManager* textures = nullptr;
    Commands commands;
    VkSamplerManager samplers;
    Framebuffer() : samplers(this) { }
    VulkanDevice* GetDevice() { return &device; }
    Commands* GetCommands() { return &commands; }
    VkTextureManager* GetTextureManager() { return textures; }
    VkSamplerManager* GetSamplerManager() { return &samplers; }
};
class VkDescriptorSetManager
{
    Framebuffer* fb;
public:
    explicit VkDescriptorSetManager(Framebuffer* owner) : fb(owner) { }
    std::vector<int> LightProbes;
    std::map<int, VulkanImageView*> bindings;
    int allocationCount = 0;
    int AllocBindlessSlot(int span)
    {
        static constexpr std::array<int, 8> bases = { 731, 905, 1201, 1505, 1901, 2305, 2801, 3205 };
        Check(span == 2 && allocationCount < static_cast<int>(bases.size()), "Bounded nonordinal allocator service");
        return bases[static_cast<size_t>(allocationCount++)];
    }
    void SetBindlessTexture(int slot, VulkanImageView* view, Sampler* sampler)
    {
        Check(slot >= 0 && slot < 4096 && view && sampler, "Bounded descriptor publication service");
        bindings[slot] = view;
    }
    int GetLightProbeTextureIndex(int probeIndex);
    void SetFixtureFixed();
};
struct ProbeMap { std::vector<std::unique_ptr<VulkanImage>> probes; };
namespace Pf113ProbeDiagnostics
{
    static bool Observing() { return false; }
    static void Publication(Framebuffer* fb, bool after) { (void)fb; (void)after; }
}
class VkLightprober
{
    Framebuffer* fb;
public:
    explicit VkLightprober(Framebuffer* owner) : fb(owner) { }
    ProbeMap irradianceMap, prefilterMap;
    void EndLightProbePass();
};
struct ScreenService
{
    VkTextureManager* textures;
    VkLightprober* prober;
    int publications = 0;
    void ResetLightProbes() { textures->ResetLightProbes(); }
    void EndLightProbePass() { ++publications; prober->EndLightProbePass(); }
};
static ScreenService* screen = nullptr;
struct LightProbe { int index = 0; };
class LightProbeIncrementalBuilder
{
public:
    int lastIndex = 0, collected = 0, cubemapsAllocated = 0, iterations = 0;
    void Step(const TArray<LightProbe>& probes, std::function<void(int, const LightProbe&)> renderScene);
};
struct HelperEvent { bool prefiltered; uint base; };
static std::vector<HelperEvent> HelperEvents;
static int PairAdditions = 0, CubeLookups = 0, NonuniformCalls = 0;
struct ObservedIndex { uint value; ObservedIndex(uint v) : value(v) { } };
static bool operator==(ObservedIndex a, uint b) { return a.value == b; }
static ObservedIndex operator+(ObservedIndex a, uint b) { ++PairAdditions; return a.value + b; }
static void ObserveHelper(bool prefiltered, uint base) { HelperEvents.push_back({ prefiltered, base }); }
struct QualifiedIndex { uint value; };
static QualifiedIndex nonuniformEXT(ObservedIndex value) { ++NonuniformCalls; return { value.value }; }
struct SampleEvent { int slot; bool cube, explicitLod, incompatible, qualified; float lod; vec3 direction; };
static std::vector<SampleEvent> SampleEvents;
static VkDescriptorSetManager* SampleOwner = nullptr;
static uvec4 Gathered = {};
static int GatherCalls = 0;
struct SamplerRef { int slot; bool cube, qualified; };
struct SamplerArray
{
    bool cube;
    SamplerRef operator[](uint slot) const { Check(slot < 4096, "Sample descriptor index bound"); if (cube) ++CubeLookups; return { static_cast<int>(slot), cube, false }; }
    SamplerRef operator[](int slot) const { Check(slot >= 0, "Negative sample index is outside this fixture"); return (*this)[static_cast<uint>(slot)]; }
    SamplerRef operator[](QualifiedIndex slot) const { auto result = (*this)[slot.value]; result.qualified = true; return result; }
    SamplerRef operator[](ObservedIndex slot) const { return (*this)[slot.value]; }
};
static const SamplerArray cubeTextures = { true }, uintTextures = { false };
struct Sampled { vec3 rgb; };
static Sampled Sample(SamplerRef sampler, vec3 direction, bool explicitLod, float lod)
{
    const auto found = SampleOwner->bindings.find(sampler.slot);
    Check(found != SampleOwner->bindings.end() && found->second, "Sample must name an actually published view");
    const bool incompatible = sampler.cube && found->second->type != VK_IMAGE_VIEW_TYPE_CUBE;
    SampleEvents.push_back({ sampler.slot, sampler.cube, explicitLod, incompatible, sampler.qualified, lod, direction });
    // The zero placeholder below is only a logger service. It is never used as
    // a radiometric expectation for an incompatible original sample.
    return { incompatible ? vec3{} : found->second->owner->radiance };
}
[[maybe_unused]] static Sampled texture(SamplerRef sampler, vec3 direction) { return Sample(sampler, direction, false, 0); }
static Sampled textureLod(SamplerRef sampler, vec3 direction, float lod) { return Sample(sampler, direction, true, lod); }
static uvec4 textureGather(SamplerRef sampler, vec2 uv)
{
    (void)uv;
    Check(!sampler.cube, "Original probe map gather uses the integer 2D alias");
    const auto found = SampleOwner->bindings.find(sampler.slot);
    Check(found != SampleOwner->bindings.end() && found->second->type == VK_IMAGE_VIEW_TYPE_2D &&
        found->second->owner->format == VK_FORMAT_R16_UINT, "Controlled gather input is a real typed CPU R16 2D view");
    ++GatherCalls;
    return Gathered;
}
static int nonuniformEXT(int value) { return value; }

#include "pf113_current_extracted.hpp"

static bool Near(float a, float b) { return std::fabs(a - b) <= 0.00001f; }
static bool Near(vec3 a, vec3 b) { return Near(a.x, b.x) && Near(a.y, b.y) && Near(a.z, b.z); }
static void ClearSamples()
{
    SampleEvents.clear(); HelperEvents.clear(); GatherCalls = 0;
    PairAdditions = CubeLookups = NonuniformCalls = 0;
}
static int BadSamples()
{
    return static_cast<int>(std::count_if(SampleEvents.begin(), SampleEvents.end(), [](const SampleEvent& event) { return event.incompatible; }));
}
static std::unique_ptr<VulkanImage> ProducedProbe(vec3 color, int levels = 1)
{
    auto image = std::make_unique<VulkanImage>();
    image->width = 32; image->height = 32; image->levels = image->mipLevels = levels; image->layers = image->layerCount = 6;
    image->layout = VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL; image->radiance = color;
    return image;
}
static SampleResult DrawCurrent(int lightmap, int token, vec2 uv = { .25f, .6f }, float roughness = .375f)
{
    return CurrentSampling(lightmap, token, { uv }, { 0, 0, 1 }, { 1, 0, 0 }, roughness);
}
static void ExpectNoReads(int calls)
{
    Check(SampleEvents.empty() && CubeLookups == 0 && NonuniformCalls == 0 && PairAdditions == 0,
        "Zero guard precedes descriptor lookup, nonuniform evaluation and pair addition");
    Check(HelperEvents.size() == static_cast<size_t>(calls), "Missing helpers preserve source invocation order");
    for (const auto& event : HelperEvents) Check(event.base == 0, "Skipped helper sees exact sentinel zero");
}
static void ExpectLegalReads(int count)
{
    Check(BadSamples() == 0 && SampleEvents.size() == static_cast<size_t>(count), "Only live compatible cube views are read");
    Check(CubeLookups == count && NonuniformCalls == count && PairAdditions == count / 2, "Every actual cube read is nonuniform qualified; pair addition only live prefilter");
    for (const auto& event : SampleEvents) Check(event.explicitLod && event.qualified && event.slot > 1, "Current reads use explicit LOD and nonuniform live pair");
}
static void ExerciseCurrent()
{
    Framebuffer fb;
    fb.samplers.CreateIrradiancemapSampler(); fb.samplers.CreatePrefiltermapSampler();
    const auto* persistentIrrSampler = fb.samplers.IrradiancemapSampler.get();
    const auto* persistentPrefSampler = fb.samplers.PrefiltermapSampler.get();
    const auto& info = persistentIrrSampler->info;
    const auto& captured = persistentIrrSampler->Creation;
    Check(captured.Captured && captured.MinFilter == info.minFilter && captured.MagFilter == info.magFilter &&
        captured.MipmapMode == info.mipmapMode && captured.AddressU == info.addressModeU && captured.AddressV == info.addressModeV && captured.AddressW == info.addressModeW &&
        captured.AnisotropyEnable == info.anisotropyEnable && Near(captured.MaxAnisotropy, info.maxAnisotropy) && Near(captured.MipLodBias, info.mipLodBias) &&
        Near(captured.MinLod, info.minLod) && Near(captured.MaxLod, info.maxLod), "Actual sampler builder captures the same successful API arguments, not guessed defaults");
    const auto samplerCount = CreatedSamplers.size();
    FailNextSampler = true;
    try { SamplerBuilder().Create(fb.GetDevice()); Check(false, "Failed sampler API must throw before publishing captured wrapper"); }
    catch (const std::runtime_error&) { Check(CreatedSamplers.size() == samplerCount && fb.device.failures == 1, "Failed sampler creation does not publish a wrapper or successful API argument record"); }
    Check(info.minFilter == VK_FILTER_LINEAR && info.magFilter == VK_FILTER_LINEAR && info.anisotropyEnable == VK_FALSE &&
        Near(info.mipLodBias, 0) && Near(info.minLod, 0) && Near(info.maxLod, 100), "Actual dedicated sampler preserves one-mip LOD0 filtering contract");
    Check(info.addressModeU == VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE && info.addressModeV == info.addressModeU && info.addressModeW == info.addressModeU,
        "Actual dedicated sampler clamps every cube axis");
    fb.samplers.CreateHWSamplers(); fb.samplers.ResetHWSamplers();
    Check(fb.commands.deletion.retired == 4 && persistentIrrSampler == fb.samplers.IrradiancemapSampler.get() && persistentPrefSampler == fb.samplers.PrefiltermapSampler.get(),
        "Actual user filter reset retires ordinary arrays while preserving dedicated probe samplers");
    VkTextureManager manager(&fb);
    fb.textures = &manager;
    manager.CreateFixtureInitial();
    for (const auto* view : { manager.NullTextureView.get(), manager.BrdfLutTextureView.get(), manager.Irradiancemaps[0].View.get(), manager.Prefiltermaps[0].View.get() })
    {
        const auto& creation = view->Creation;
        Check(creation.Captured && creation.Image == view->owner && creation.ViewType == view->type && creation.Format == view->owner->format &&
            creation.Range.baseMipLevel == view->range.baseMipLevel && creation.Range.levelCount == view->range.levelCount &&
            creation.Range.baseArrayLayer == view->range.baseArrayLayer && creation.Range.layerCount == view->range.layerCount && creation.Range.aspectMask == view->range.aspectMask,
            "Actual image-view builder captures every selected API argument from its successful creation record");
    }
    const auto viewCount = CreatedViews.size();
    FailNextView = true;
    try { ImageViewBuilder().Image(manager.NullTexture.get(), VK_FORMAT_R8G8B8A8_UNORM).Create(fb.GetDevice()); Check(false, "Failed view API must throw before publishing captured wrapper"); }
    catch (const std::runtime_error&) { Check(CreatedViews.size() == viewCount && fb.device.failures == 2, "Failed view creation does not publish a wrapper or successful API argument record"); }
    VkDescriptorSetManager descriptors(&fb);
    descriptors.SetFixtureFixed();
    SampleOwner = &descriptors;
    // Bounded input service for the real shader's R16 gather. This is not a
    // claim that the entire Vulkan lightmap copy pass ran in this CPU draft.
    auto probeMapImage = ImageBuilder().Size(1, 1).Format(VK_FORMAT_R16_UINT).Create(fb.GetDevice());
    auto probeMapView = ImageViewBuilder().Image(probeMapImage.get(), VK_FORMAT_R16_UINT).Create(fb.GetDevice());
    descriptors.SetBindlessTexture(4, probeMapView.get(), fb.samplers.Get(CLAMP_XY_NOMIP));
    Check(descriptors.bindings.at(0)->type == VK_IMAGE_VIEW_TYPE_2D && descriptors.bindings.at(1)->type == VK_IMAGE_VIEW_TYPE_2D,
        "Actual original null/BRDF creation uses the extracted 2D view default");
    Check(manager.Irradiancemaps.size() == 1 && manager.Prefiltermaps.size() == 1, "Actual constructor wrappers allocate exactly one sampled pair");
    const int authoredZero = descriptors.GetLightProbeTextureIndex(0);
    Check(authoredZero == 731 && authoredZero > 0 && descriptors.bindings.at(authoredZero)->type == VK_IMAGE_VIEW_TYPE_CUBE,
        "Authored zero is an allocator-backed nonzero cube pair");
    Check(descriptors.GetLightProbeTextureIndex(1) == 0 && descriptors.GetLightProbeTextureIndex(1) == 0,
        "Unavailable authored one remains the real lookup zero sentinel");
    Check(descriptors.allocationCount == 1 && descriptors.LightProbes.at(1) == -1, "Missing lookup does not cache or allocate a fabricated pair");
    Check(manager.Irradiancemaps[0].Image->mipLevels == 1 && manager.Irradiancemaps[0].View->range.baseMipLevel == 0 && manager.Irradiancemaps[0].View->range.levelCount == 1 &&
        manager.Irradiancemaps[0].View->range.layerCount == 6, "Actual irradiance producer/view exposes exactly mip zero and six faces");
    Check(manager.Prefiltermaps[0].Image->mipLevels == 5 && manager.Prefiltermaps[0].View->range.levelCount == 5,
        "Actual prefilter view retains all roughness mips");
    ClearSamples(); const auto uniformZero = DrawCurrent(-1, descriptors.GetLightProbeTextureIndex(1)); ExpectNoReads(2);
    Check(GatherCalls == 0 && Near(uniformZero.irradiance, {}) && Near(uniformZero.prefiltered, {}), "Missing uniform IBL contributes exact zero");
    ClearSamples(); Gathered = { 0, 0, 0, 0 }; const auto allZero = DrawCurrent(3, 0); ExpectNoReads(8);
    Check(GatherCalls == 1 && Near(allZero.irradiance, {}) && Near(allZero.prefiltered, {}), "All-zero gathered taps contribute zero after actual weights");

    VkLightprober prober(&fb);
    ScreenService service{ &manager, &prober, 0 };
    screen = &service;
    LightProbeIncrementalBuilder builder;
    TArray<LightProbe> authored;
    authored.Push({ 0 }); authored.Push({ 1 });
    int renders = 0;
    auto render = [&](int index, const LightProbe& probe)
    {
        Check(index == probe.index, "Original builder preserves authored rendering order");
        ++renders;
        ClearSamples(); DrawCurrent(-1, descriptors.GetLightProbeTextureIndex(1)); ExpectNoReads(2);
        prober.irradianceMap.probes.push_back(ProducedProbe({ float(index + 1), 0, 0 }));
        prober.prefilterMap.probes.push_back(ProducedProbe({ 0, float(index + 1), 0 }, 5));
    };
    builder.Step(authored, render);
    Check(renders == 0 && service.publications == 0 && manager.LightProbeEpoch.invalidations == 1, "Initial count reset precedes all renders/publication");
    builder.Step(authored, render);
    Check(renders == 1 && service.publications == 0 && manager.Irradiancemaps.size() == 1, "First probe draw sees target one unavailable");
    builder.Step(authored, render);
    Check(renders == 2 && service.publications == 1 && manager.Irradiancemaps.size() == 2 && manager.Prefiltermaps.size() == 2,
        "Completed original pass grows sampled maps only after both probe draws");
    const int authoredOne = descriptors.GetLightProbeTextureIndex(1);
    Check(authoredOne == 905 && descriptors.GetLightProbeTextureIndex(1) == authoredOne && descriptors.allocationCount == 2,
        "Original unavailable-to-published lookup retries then caches the actual independent pair");
    ClearSamples(); const auto published = DrawCurrent(-1, authoredOne); ExpectLegalReads(2);
    Check(BadSamples() == 0 && Near(published.irradiance, { 2, 0, 0 }) && Near(published.prefiltered, { 0, 2, 0 }), "Published uniform pair reads legal copied probe radiance");
    Check(SampleEvents[0].slot == authoredOne && SampleEvents[1].slot == authoredOne + 1 && Near(SampleEvents[1].lod, 1.5f), "Original uniform order and roughness LOD");

    manager.CheckIrradiancemapSize(4); manager.CheckPrefiltermapSize(4);
    const std::array<vec3, 4> irr = { vec3{ 1, 0, 0 }, vec3{ 0, 2, 0 }, vec3{ 0, 0, 3 }, vec3{ 4, 5, 6 } };
    const std::array<vec3, 4> pref = { vec3{ 2, 1, 0 }, vec3{ 3, 0, 1 }, vec3{ 1, 4, 2 }, vec3{ 0, 2, 3 } };
    std::array<int, 4> tokens = {};
    for (int i = 0; i < 4; ++i)
    {
        manager.Irradiancemaps[static_cast<size_t>(i)].Image->radiance = irr[static_cast<size_t>(i)];
        manager.Prefiltermaps[static_cast<size_t>(i)].Image->radiance = pref[static_cast<size_t>(i)];
        tokens[static_cast<size_t>(i)] = descriptors.GetLightProbeTextureIndex(i);
    }
    Gathered = { static_cast<uint>(tokens[0]), static_cast<uint>(tokens[1]), static_cast<uint>(tokens[2]), static_cast<uint>(tokens[3]) };
    ClearSamples(); const auto golden = DrawCurrent(3, 0); ExpectLegalReads(8);
    Check(BadSamples() == 0 && Near(golden.irradiance, { .9f, .95f, 2.25f }) && Near(golden.prefiltered, { 1.35f, 2.4f, 1.45f }), "Original all-live golden contribution is not ordinal-derived");
    const std::array<float, 4> coefficients = { .30f, .10f, .45f, .15f };
    for (size_t i = 0; i < 4; ++i)
    {
        Check(Near(golden.weights[i], coefficients[i]), "Golden uses actual original bilinear coefficients");
        Check(SampleEvents[i].slot == tokens[i] && SampleEvents[i].explicitLod && Near(SampleEvents[i].lod, 0) && Near(SampleEvents[i].direction, { 0, 0, 1 }), "Four irradiance reads preserve order/N with explicit LOD0");
        Check(SampleEvents[i + 4].slot == tokens[i] + 1 && SampleEvents[i + 4].explicitLod && Near(SampleEvents[i + 4].lod, 1.5f), "Original four prefilter sample order and LOD");
        Check(Near(SampleEvents[i + 4].direction, { 1, 0, 0 }) && !HelperEvents[i].prefiltered && HelperEvents[i].base == static_cast<uint>(tokens[i]) && HelperEvents[i + 4].prefiltered,
            "Passive observer records unchanged irradiance then prefilter helper order and R");
    }
    ClearSamples(); Gathered = { static_cast<uint>(tokens[0]), 0, static_cast<uint>(tokens[2]), 0 }; const auto mixed = DrawCurrent(3, 0); ExpectLegalReads(4);
    Check(Near(mixed.irradiance, { .3f, 0, 1.35f }) && Near(mixed.prefiltered, { 1.05f, 2.1f, .9f }), "Mixed live taps keep original coefficients without renormalizing missing mass");
    for (size_t i = 0; i < 4; ++i) Check(Near(mixed.weights[i], coefficients[i]), "Mixed tap coefficients match all-live source coefficients");
    Check(HelperEvents.size() == 8 && HelperEvents[1].base == 0 && HelperEvents[3].base == 0 && HelperEvents[5].base == 0 && HelperEvents[7].base == 0,
        "Mixed missing taps preserve call order but do not read sentinel views");
    ClearSamples(); Gathered = { static_cast<uint>(tokens[0]), 0, static_cast<uint>(tokens[2]), static_cast<uint>(tokens[3]) };
    const auto zeroWeightMissing = DrawCurrent(3, 0, { 1, 1 }); ExpectLegalReads(6);
    Check(Near(ObservedWeights[0], 1) && Near(ObservedWeights[1], 0) && Near(zeroWeightMissing.irradiance, irr[0]) && Near(zeroWeightMissing.prefiltered, pref[0]), "Zero-weight missing tap is guarded without changing live weighted result");
    for (float roughness : { 0.0f, .375f, 1.0f })
    {
        ClearSamples(); const auto uniform = DrawCurrent(-1, tokens[2], {}, roughness); ExpectLegalReads(2);
        Check(Near(uniform.irradiance, irr[2]) && Near(uniform.prefiltered, pref[2]) && Near(SampleEvents[0].lod, 0) && Near(SampleEvents[1].lod, roughness * 4),
            "Uniform live tokens retain direction-specific incident colours and original roughness LOD");
    }
    ClearSamples(); CurrentSampling(-1, tokens[3], {}, { .2f, -.3f, .8f }, { -.7f, .4f, .1f }, .625f); ExpectLegalReads(2);
    Check(Near(SampleEvents[0].direction, { .2f, -.3f, .8f }) && Near(SampleEvents[1].direction, { -.7f, .4f, .1f }) && Near(SampleEvents[1].lod, 2.5f),
        "Actual helper passes caller N/R without reconstruction or normalization");

    const auto* oldIrr = manager.Irradiancemaps[0].View.get();
    const auto* oldPref = manager.Prefiltermaps[0].View.get();
    manager.ResetLightProbes();
    Check(manager.LightProbeEpoch.invalidations == 2 && oldIrr == manager.Irradiancemaps[0].View.get() && oldPref == manager.Prefiltermaps[0].View.get(), "Actual reset preserves existing sampled owners while invalidating its domain");
    ClearSamples(); const auto cleared = DrawCurrent(-1, authoredZero); ExpectLegalReads(2);
    Check(BadSamples() == 0 && Near(cleared.irradiance, {}) && Near(cleared.prefiltered, {}), "Cleared real authored zero pair remains legal, separate from sentinel zero");
    Check(descriptors.bindings.at(0)->type == VK_IMAGE_VIEW_TYPE_2D && descriptors.bindings.at(1)->type == VK_IMAGE_VIEW_TYPE_2D, "Original fixed 2D users were never repurposed");

    ShaderSelection::probes = { { { 0, 0, 0 }, 0 }, { { 0, 0, 0 }, 0x10000u }, { { 10, 0, 0 }, static_cast<uint>(authoredOne) } };
    ShaderSelection::ProbeCount = static_cast<int>(ShaderSelection::probes.size());
    Check(ShaderSelection::findClosestProbe({ 0, 0, 0 }, 512) == static_cast<uint>(authoredOne), "Actual selector omits fallback and unencodable tokens");
    ShaderSelection::ProbeCount = 2;
    Check(ShaderSelection::findClosestProbe({ 0, 0, 0 }, 512) == 0, "Actual selector with no eligible live candidates emits fallback zero");
    screen = nullptr; SampleOwner = nullptr;
}

int main(int argc, char** argv)
{
    try
    {
        Check(argc == 2 && std::strcmp(argv[1], "--current") == 0, "Choose --current source-extracted CPU checks");
        ExerciseCurrent();
        std::cout << "CURRENT SOURCE PASS: " << Checks << " CPU service/source checks. No Vulkan execution or spatial GPU filtering claim.\n";
        return 0;
    }
    catch (const std::exception& error)
    {
        std::cerr << "FAIL: " << error.what() << " (CPU source/services only)\n";
        return 1;
    }
}
