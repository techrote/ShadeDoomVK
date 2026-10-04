// Disposable PF113 original-source draft. CPU only; never links a renderer.
// The generated header contains original producer/consumer bodies. This file
// supplies bounded allocation, object/copy and sample-log services. A successful
// --observe-original run means the defect was reproduced, not repaired.
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
struct Subresource
{
    int aspectMask = 0, baseMipLevel = 0, levelCount = 0, baseArrayLayer = 0;
    int layerCount = 0, mipLevel = 0;
};
struct ViewInfo { int sType = 0, viewType = 0; Subresource subresourceRange; };
struct VulkanImage
{
    VulkanImage* image = this; // CPU handle service, not a VkImage.
    int width = 1, height = 1, levels = 1, layers = 1, format = 0;
    int layout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
    vec3 radiance;
};
struct VulkanImageView { VulkanImage* owner; int type; };
struct VkTextureImage { std::unique_ptr<VulkanImage> Image; std::unique_ptr<VulkanImageView> View; };
class ImageBuilder
{
    int width = 1, height = 1, levels = 1, layers = 1, format = 0;
public:
    ImageBuilder& Size(int w, int h, int l = 1, int a = 1) { width = w; height = h; levels = l; layers = a; return *this; }
    ImageBuilder& Format(int f) { format = f; return *this; }
    ImageBuilder& Usage(int value) { (void)value; return *this; }
    ImageBuilder& Flags(int value) { (void)value; return *this; }
    ImageBuilder& DebugName(const char* value) { (void)value; return *this; }
    std::unique_ptr<VulkanImage> Create(int device)
    {
        (void)device;
        Check(width > 0 && height > 0 && width <= 512 && height <= 512 && levels <= 5 && layers <= 6, "CPU image service bound");
        auto p = std::make_unique<VulkanImage>();
        p->width = width; p->height = height; p->levels = levels; p->layers = layers; p->format = format;
        return p;
    }
};
class ImageViewBuilder
{
    ViewInfo viewInfo;
    VulkanImage* owner = nullptr;
public:
    ImageViewBuilder(); // Body is extracted unchanged from ZVulkan.
    ImageViewBuilder& Type(int type) { viewInfo.viewType = type; return *this; }
    ImageViewBuilder& Image(VulkanImage* image, int format) { owner = image; (void)format; return *this; }
    ImageViewBuilder& DebugName(const char* name) { (void)name; return *this; }
    std::unique_ptr<VulkanImageView> Create(int device)
    {
        (void)device;
        Check(owner != nullptr, "CPU view service requires an image");
        if (viewInfo.viewType == VK_IMAGE_VIEW_TYPE_CUBE) Check(owner->layers == 6, "Actual cube view needs six faces");
        return std::make_unique<VulkanImageView>(VulkanImageView{ owner, viewInfo.viewType });
    }
};
struct VkClearColorValue { std::array<float, 4> float32 = {}; };
using VkImageSubresourceRange = Subresource;
struct Extent { int width = 0, height = 0, depth = 0; };
struct VkImageCopy { Extent extent; Subresource srcSubresource, dstSubresource; };
struct Commands
{
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
struct Sampler { };
struct SamplerManager
{
    Sampler other;
    std::unique_ptr<Sampler> IrradiancemapSampler = std::make_unique<Sampler>();
    std::unique_ptr<Sampler> PrefiltermapSampler = std::make_unique<Sampler>();
    Sampler* Get(int clamp) { (void)clamp; return &other; }
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
    VkTextureManager* textures = nullptr;
    Commands commands;
    SamplerManager samplers;
    int GetDevice() { return 0; }
    Commands* GetCommands() { return &commands; }
    VkTextureManager* GetTextureManager() { return textures; }
    SamplerManager* GetSamplerManager() { return &samplers; }
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
struct SampleEvent { int slot; bool cube, explicitLod, incompatible; float lod; vec3 direction; };
static std::vector<SampleEvent> SampleEvents;
static VkDescriptorSetManager* SampleOwner = nullptr;
static uvec4 Gathered = {};
static int GatherCalls = 0;
struct SamplerRef { int slot; bool cube; };
struct SamplerArray
{
    bool cube;
    SamplerRef operator[](uint slot) const { Check(slot < 4096, "Sample descriptor index bound"); return { static_cast<int>(slot), cube }; }
    SamplerRef operator[](int slot) const { Check(slot >= 0, "Negative sample index is outside this original fixture"); return (*this)[static_cast<uint>(slot)]; }
};
static const SamplerArray cubeTextures = { true }, uintTextures = { false };
struct Sampled { vec3 rgb; };
static Sampled Sample(SamplerRef sampler, vec3 direction, bool explicitLod, float lod)
{
    const auto found = SampleOwner->bindings.find(sampler.slot);
    Check(found != SampleOwner->bindings.end() && found->second, "Sample must name an actually published view");
    const bool incompatible = sampler.cube && found->second->type != VK_IMAGE_VIEW_TYPE_CUBE;
    SampleEvents.push_back({ sampler.slot, sampler.cube, explicitLod, incompatible, lod, direction });
    // The zero placeholder below is only a logger service. It is never used as
    // a radiometric expectation for an incompatible original sample.
    return { incompatible ? vec3{} : found->second->owner->radiance };
}
static Sampled texture(SamplerRef sampler, vec3 direction) { return Sample(sampler, direction, false, 0); }
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

#include "extracted_original.hpp"

static bool Near(float a, float b) { return std::fabs(a - b) <= 0.00001f; }
static bool Near(vec3 a, vec3 b) { return Near(a.x, b.x) && Near(a.y, b.y) && Near(a.z, b.z); }
static void ClearSamples() { SampleEvents.clear(); GatherCalls = 0; }
static int BadSamples()
{
    return static_cast<int>(std::count_if(SampleEvents.begin(), SampleEvents.end(), [](const SampleEvent& event) { return event.incompatible; }));
}
static std::unique_ptr<VulkanImage> ProducedProbe(vec3 color, int levels = 1)
{
    auto image = std::make_unique<VulkanImage>();
    image->width = 32; image->height = 32; image->levels = levels; image->layers = 6;
    image->layout = VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL; image->radiance = color;
    return image;
}
static SampleResult DrawOriginal(int lightmap, int token, vec2 uv = { .25f, .6f }, float roughness = .375f)
{
    return OriginalSampling(lightmap, token, { uv }, { 0, 0, 1 }, { 1, 0, 0 }, roughness);
}
static void ExpectBadFixed(int expected)
{
    Check(BadSamples() == expected, "Original source must reproduce the exact incompatible access count");
    for (const auto& event : SampleEvents) if (event.incompatible)
        Check((event.slot == 0 && !event.explicitLod) || (event.slot == 1 && event.explicitLod), "Bad cube accesses are actual fixed null/BRDF slots");
}
static int ExerciseOriginal()
{
    Framebuffer fb;
    VkTextureManager manager(&fb);
    fb.textures = &manager;
    manager.CreateFixtureInitial();
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
    int originalBad = 0;
    ClearSamples(); DrawOriginal(-1, descriptors.GetLightProbeTextureIndex(1)); ExpectBadFixed(2); originalBad += BadSamples();
    Check(SampleEvents.size() == 2 && GatherCalls == 0, "Missing uniform source enters the original uniform branch");
    ClearSamples(); Gathered = { 0, 0, 0, 0 }; DrawOriginal(3, 0); ExpectBadFixed(8); originalBad += BadSamples();
    Check(SampleEvents.size() == 8 && GatherCalls == 1, "All-zero gather still issues four irradiance then four prefilter calls");

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
        ClearSamples(); DrawOriginal(-1, descriptors.GetLightProbeTextureIndex(1)); ExpectBadFixed(2); originalBad += BadSamples();
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
    ClearSamples(); const auto published = DrawOriginal(-1, authoredOne);
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
    ClearSamples(); const auto golden = DrawOriginal(3, 0);
    Check(BadSamples() == 0 && Near(golden.irradiance, { .9f, .95f, 2.25f }) && Near(golden.prefiltered, { 1.35f, 2.4f, 1.45f }), "Original all-live golden contribution is not ordinal-derived");
    const std::array<float, 4> coefficients = { .30f, .10f, .45f, .15f };
    for (size_t i = 0; i < 4; ++i)
    {
        Check(Near(golden.weights[i], coefficients[i]), "Golden uses actual original bilinear coefficients");
        Check(SampleEvents[i].slot == tokens[i] && !SampleEvents[i].explicitLod, "Original four irradiance sample order");
        Check(SampleEvents[i + 4].slot == tokens[i] + 1 && SampleEvents[i + 4].explicitLod && Near(SampleEvents[i + 4].lod, 1.5f), "Original four prefilter sample order and LOD");
    }
    ClearSamples(); Gathered = { static_cast<uint>(tokens[0]), 0, static_cast<uint>(tokens[2]), 0 }; DrawOriginal(3, 0); ExpectBadFixed(4); originalBad += BadSamples();
    ClearSamples(); Gathered = { static_cast<uint>(tokens[0]), 0, static_cast<uint>(tokens[2]), static_cast<uint>(tokens[3]) };
    DrawOriginal(3, 0, { 1, 1 }); ExpectBadFixed(2); originalBad += BadSamples();
    Check(Near(ObservedWeights[0], 1) && Near(ObservedWeights[1], 0), "Original source samples the missing tap even when its actual coefficient is zero");

    const auto* oldIrr = manager.Irradiancemaps[0].View.get();
    const auto* oldPref = manager.Prefiltermaps[0].View.get();
    manager.ResetLightProbes();
    Check(manager.LightProbeEpoch.invalidations == 2 && oldIrr == manager.Irradiancemaps[0].View.get() && oldPref == manager.Prefiltermaps[0].View.get(), "Actual reset preserves existing sampled owners while invalidating its domain");
    ClearSamples(); const auto cleared = DrawOriginal(-1, authoredZero);
    Check(BadSamples() == 0 && Near(cleared.irradiance, {}) && Near(cleared.prefiltered, {}), "Cleared real authored zero pair remains legal, separate from sentinel zero");
    Check(descriptors.bindings.at(0)->type == VK_IMAGE_VIEW_TYPE_2D && descriptors.bindings.at(1)->type == VK_IMAGE_VIEW_TYPE_2D, "Original fixed 2D users were never repurposed");

    ShaderSelection::probes = { { { 0, 0, 0 }, 0 }, { { 0, 0, 0 }, 0x10000u }, { { 10, 0, 0 }, static_cast<uint>(authoredOne) } };
    ShaderSelection::ProbeCount = static_cast<int>(ShaderSelection::probes.size());
    Check(ShaderSelection::findClosestProbe({ 0, 0, 0 }, 512) == static_cast<uint>(authoredOne), "Actual selector omits fallback and unencodable tokens");
    ShaderSelection::ProbeCount = 2;
    Check(ShaderSelection::findClosestProbe({ 0, 0, 0 }, 512) == 0, "Actual selector with no eligible live candidates emits fallback zero");
    screen = nullptr; SampleOwner = nullptr;
    return originalBad;
}

int main(int argc, char** argv)
{
    try
    {
        Check(argc == 2 && (std::strcmp(argv[1], "--observe-original") == 0 || std::strcmp(argv[1], "--require-safe") == 0),
            "Choose --observe-original (expected defect) or --require-safe (baseline must fail)");
        const int bad = ExerciseOriginal();
        Check(bad == 20, "Exact original defect witnesses cover uniform/all-zero/mixed/initial-order cases");
        if (std::strcmp(argv[1], "--require-safe") == 0) Check(bad == 0, "Original PBR attempts incompatible fixed 2D cube samples");
        std::cout << "ORIGINAL DEFECT REPRODUCED: " << bad << " incompatible sample attempts; " << Checks << " CPU service/source checks. No current repair/GPU claim.\n";
        return 0;
    }
    catch (const std::exception& error)
    {
        std::cerr << "FAIL: " << error.what() << " (CPU draft only)\n";
        return 1;
    }
}
