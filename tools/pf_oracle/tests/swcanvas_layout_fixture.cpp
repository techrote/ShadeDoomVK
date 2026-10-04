// #112 CPU-only layout proof. Production definitions are generated verbatim.
// Vulkan builders, containers, palettes, tracing and descriptor execution below
// are bounded recording services, not a renderer or Vulkan validation model.
// Actual layout production/publication is not reimplemented. No image/result,
// native software-frame or fence-retirement acceptance is claimed here.
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

using VkFormat = int;
using VkImageLayout = int;
using VkDeviceSize = std::size_t;
enum { VK_FORMAT_R8_UNORM = 1, VK_FORMAT_B8G8R8A8_UNORM = 2 };
enum { VK_IMAGE_LAYOUT_UNDEFINED = 0, VK_IMAGE_LAYOUT_GENERAL = 1,
    VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL = 2, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL = 3,
    VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL = 4, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL = 5 };
enum { VK_IMAGE_USAGE_SAMPLED_BIT = 1, VK_IMAGE_USAGE_TRANSFER_SRC_BIT = 2 };
enum { VMA_MEMORY_USAGE_UNKNOWN = 0, VMA_ALLOCATION_CREATE_DEDICATED_MEMORY_BIT = 1,
    VMA_ALLOCATION_CREATE_MAPPED_BIT = 2, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT = 1,
    VK_MEMORY_PROPERTY_HOST_COHERENT_BIT = 2, VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT = 4 };
enum { CTF_Indexed = 4, CTF_IndexedRedIsAlpha = 32, CLAMP_NOFILTER_XY = 8 };
enum class MaterialLayerSampling { Default };

struct VulkanRenderDevice;
struct FakeCommands { int Transitions = 0; FakeCommands* GetTransferCommands() { return this; } };
struct FakeImage
{
    int width = 0, height = 0, Format = 0, Usage = 0;
    bool Linear = false;
    std::vector<uint8_t> Bytes;
    void* Map(std::size_t offset, std::size_t) { return Bytes.data() + offset; }
};
struct VulkanImageView { uint64_t view = 1; FakeImage* Image = nullptr; };
struct VulkanSampler { uint64_t sampler = 2; };
struct VkTextureImage
{
    std::unique_ptr<FakeImage> Image;
    std::unique_ptr<VulkanImageView> View;
    VkImageLayout Layout = VK_IMAGE_LAYOUT_UNDEFINED;
};
struct ImageBuilder
{
    int Width = 0, Height = 0, FormatValue = 0, UsageValue = 0;
    bool Linear = false;
    ImageBuilder& Format(int value) { FormatValue = value; return *this; }
    ImageBuilder& Size(int w, int h) { Width = w; Height = h; return *this; }
    ImageBuilder& LinearTiling() { Linear = true; return *this; }
    ImageBuilder& Usage(int value, int, int) { UsageValue = value; return *this; }
    ImageBuilder& MemoryType(int, int) { return *this; }
    ImageBuilder& DebugName(const char*) { return *this; }
    std::unique_ptr<FakeImage> Create(VulkanRenderDevice*, VkDeviceSize* size)
    {
        auto image = std::make_unique<FakeImage>();
        image->width = Width; image->height = Height; image->Format = FormatValue;
        image->Usage = UsageValue; image->Linear = Linear;
        const int texels = FormatValue == VK_FORMAT_R8_UNORM ? 1 : 4;
        // Deterministic padded allocation; not a Vulkan row-pitch guarantee.
        image->Bytes.resize(static_cast<std::size_t>((Width + 8) * Height * texels));
        *size = image->Bytes.size(); return image;
    }
};
struct ImageViewBuilder
{
    FakeImage* Source = nullptr;
    ImageViewBuilder& Image(FakeImage* image, int format) { assert(image->Format == format); Source = image; return *this; }
    ImageViewBuilder& DebugName(const char*) { return *this; }
    std::unique_ptr<VulkanImageView> Create(VulkanRenderDevice*)
    { auto view = std::make_unique<VulkanImageView>(); view->Image = Source; return view; }
};
struct VkImageTransition
{
    VkTextureImage* Image = nullptr;
    int Layout = 0;
    VkImageTransition& AddImage(VkTextureImage* image, int layout, bool)
    { Image = image; Layout = layout; return *this; }
    void Execute(FakeCommands* commands) { assert(Image && Image->Image); Image->Layout = Layout; ++commands->Transitions; }
};
struct IHardwareTexture { virtual ~IHardwareTexture() = default; };
struct FTexture
{
    IHardwareTexture* GetHardwareTexture(int, int) { throw std::runtime_error("global shader texture outside SWCanvas fixture"); }
};
struct VkHardwareTexture : IHardwareTexture
{
    VulkanRenderDevice* fb;
    VkTextureImage mImage, mPaletteImage, mAlphaImage;
    int mTexelsize = 4, bufferpitch = -1, Resets = 0, Copies = 0, Produced = 0;
    uint8_t* mappedSWFB = nullptr;
    explicit VkHardwareTexture(VulkanRenderDevice* device) : fb(device) { }
    void Reset() { ++Resets; mImage = {}; mappedSWFB = nullptr; }
    void AllocateBuffer(int w, int h, int texelsize);
    uint8_t* MapBuffer();
    unsigned int CreateTexture(unsigned char* buffer, int w, int h, int texunit, bool mipmap, const char* name);
    VkTextureImage* GetImage(FTexture* tex, int translation, int flags);
    VkTextureImage* GetIndexedMaterialImage(FTexture*, int, int) { throw std::runtime_error("public indexed route outside SWCanvas fixture"); }
    void CreateTexture(VkTextureImage*, int, int, int, VkFormat, const void*, bool) { ++Copies; }
    void CreateImage(VkTextureImage*, FTexture*, int, int) { ++Produced; throw std::runtime_error("missing pre-existing image"); }
};
struct TraceIdentity { int Generation = 0, Epoch = 0, Span = 0; };
struct FakeAllocator { TraceIdentity CurrentIdentity(int) { return {}; } };
struct FakeDescriptorSet { uint64_t diagnosticId = 1; };
struct FakeWrite { int Index; VulkanImageView* View; VulkanSampler* Sampler; VkImageLayout Layout; };
struct FakeWriter
{
    std::vector<FakeWrite> Writes;
    void AddCombinedImageSampler(FakeDescriptorSet*, int, int index, VulkanImageView* view, VulkanSampler* sampler, VkImageLayout layout)
    { assert(view && sampler); Writes.push_back({ index, view, sampler, layout }); }
};
namespace CfxTrace { bool ResourcesEnabled() { return false; } void ResourceMark(const char*, const char*) { } }
template<class... Args> [[noreturn]] void I_FatalError(const char* message, Args...)
{ throw std::runtime_error(message); }

#include "production_swcanvas_layout.h"
struct VkDescriptorSetManager
{
    struct
    {
        struct { int Effective = 1024; } Plan;
        FakeAllocator Allocator;
        std::unique_ptr<FakeDescriptorSet> Set = std::make_unique<FakeDescriptorSet>();
        FakeWriter Writer;
    } Bindless;
    PF_SET_BINDLESS_DECL
};
struct FakeSamplers
{
    VulkanSampler Sampler;
    VulkanSampler* Get(MaterialLayerSampling, int) { return &Sampler; }
    VulkanSampler* Get(int) { return &Sampler; }
};
struct VulkanRenderDevice
{
    FakeCommands Commands;
    VkDescriptorSetManager Descriptors;
    FakeSamplers Samplers;
    VulkanRenderDevice* GetDevice() { return this; }
    FakeCommands* GetCommands() { return &Commands; }
    VkDescriptorSetManager* GetDescriptorSetManager() { return &Descriptors; }
    FakeSamplers* GetSamplerManager() { return &Samplers; }
};
struct MaterialLayerInfo { FTexture* layerTexture; int scaleFlags; VkHardwareTexture* Owner; };
struct FMaterialState { int mTranslation = 0; };
struct GlobalShaderDesc
{
    std::vector<std::unique_ptr<FTexture>> CustomShaderTextures;
    std::vector<MaterialLayerSampling> CustomShaderTextureSampling;
    explicit operator bool() const { return false; }
};
struct VkMaterial
{
    VulkanRenderDevice* fb;
    std::vector<MaterialLayerInfo> Layers;
    explicit VkMaterial(VulkanRenderDevice* device) : fb(device) { }
    int NumLayers() const { return static_cast<int>(Layers.size()); }
    MaterialLayerSampling GetLayerFilter(int) const { return MaterialLayerSampling::Default; }
    IHardwareTexture* GetLayer(int i, int, MaterialLayerInfo** layer)
    { *layer = &Layers.at(static_cast<std::size_t>(i)); return (*layer)->Owner; }
    std::unique_ptr<VkTextureImage> CreateIndexedPalette() { throw std::runtime_error("public indexed palette outside SWCanvas fixture"); }
    int PublishOrdinary();
};
#define PF_LAYOUT_DEFINITIONS
#include "production_swcanvas_layout.h"

static void SeedRead(VkTextureImage& image, int format)
{
    image.Image = std::make_unique<FakeImage>();
    image.Image->width = 256; image.Image->height = 1; image.Image->Format = format;
    image.View = std::make_unique<VulkanImageView>(); image.View->Image = image.Image.get();
    image.Layout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
}

static void CheckWrites(VulkanRenderDevice& device, VkHardwareTexture& mapped, VkHardwareTexture& palette)
{
    const auto& writes = device.Descriptors.Bindless.Writer.Writes;
    assert(writes.size() >= 2);
    const auto& first = writes[writes.size() - 2];
    const auto& second = writes.back();
    assert(first.Index == 259 && second.Index == 260);
    assert(first.View == mapped.mImage.View.get() && second.View == palette.mImage.View.get());
    assert(mapped.mImage.Layout == VK_IMAGE_LAYOUT_GENERAL);
    assert(second.Layout == VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL);
    if (PF_ORIGINAL) assert(first.Layout == VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL);
    else assert(first.Layout == mapped.mImage.Layout);
}

static void Mapped(int texels, bool repeat, bool resize)
{
    VulkanRenderDevice device;
    VkHardwareTexture mapped(&device), palette(&device);
    FTexture source, paletteSource;
    SeedRead(palette.mImage, VK_FORMAT_B8G8R8A8_UNORM);
    VkMaterial material(&device);
    material.Layers = { { &source, 0, &mapped }, { &paletteSource, 0, &palette } };
    mapped.AllocateBuffer(16, 4, texels);
    const auto originalImage = mapped.mImage.Image.get();
    const int initialTransitions = device.Commands.Transitions;
    const int frames = repeat ? 5 : 1;
    for (int frame = 0; frame < frames; ++frame)
    {
        mapped.AllocateBuffer(16, 4, texels);
        auto* bytes = mapped.MapBuffer();
        assert(bytes && mapped.bufferpitch == 24);
        for (int y = 0; y < 4; ++y) for (int x = 0; x < 16 * texels; ++x)
            bytes[y * mapped.bufferpitch * texels + x] = static_cast<uint8_t>(frame + x + y);
        const auto before = mapped.mImage.Image->Bytes;
        assert(mapped.CreateTexture(nullptr, 16, 4, 0, false, "swbuffer") == 0);
        assert(material.PublishOrdinary() == 2);
        CheckWrites(device, mapped, palette);
        assert(mapped.mImage.Image.get() == originalImage && mapped.mImage.Image->Bytes == before);
        assert(mapped.Copies == 0 && mapped.Produced == 0 && mapped.Resets == 0);
        assert(mapped.mImage.Image->Linear && mapped.mImage.Image->Usage == VK_IMAGE_USAGE_SAMPLED_BIT);
        assert(mapped.mImage.Image->Format == (texels == 1 ? VK_FORMAT_R8_UNORM : VK_FORMAT_B8G8R8A8_UNORM));
        assert(device.Commands.Transitions == initialTransitions);
    }
    if (resize)
    {
        mapped.AllocateBuffer(9, 3, texels == 1 ? 4 : 1);
        assert(mapped.Resets == 1 && mapped.mImage.Image->width == 9 && mapped.mImage.Image->height == 3);
        assert(mapped.mTexelsize != texels && mapped.bufferpitch == 17);
        assert(material.PublishOrdinary() == 2);
        CheckWrites(device, mapped, palette);
    }
    if (PF_ORIGINAL) std::cout << "actual=GENERAL declared=READ ";
}

static void Ordinary()
{
    VulkanRenderDevice device;
    VkHardwareTexture source(&device), placeholder(&device);
    FTexture texture, auxiliary;
    for (int format : { VK_FORMAT_R8_UNORM, VK_FORMAT_B8G8R8A8_UNORM })
    {
        SeedRead(source.mImage, format); SeedRead(placeholder.mImage, format);
        VkMaterial material(&device);
        material.Layers = { { &texture, 0, &source }, { &auxiliary, 0, &placeholder } };
        assert(material.PublishOrdinary() == 2);
        const auto& writes = device.Descriptors.Bindless.Writer.Writes;
        assert(writes.back().Layout == VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL);
        assert(writes[writes.size() - 2].Layout == VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL);
        device.Descriptors.SetBindlessTexture(7, source.mImage.View.get(), &device.Samplers.Sampler);
        assert(device.Descriptors.Bindless.Writer.Writes.back().Layout == VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL);
    }
}

static void Invalid()
{
    VulkanRenderDevice device;
    VkTextureImage image; SeedRead(image, VK_FORMAT_R8_UNORM);
    for (int index : { -1, 1024 })
    {
        bool threw = false;
        try { device.Descriptors.SetBindlessTexture(index, image.View.get(), &device.Samplers.Sampler); }
        catch (const std::runtime_error&) { threw = true; }
        assert(threw && device.Descriptors.Bindless.Writer.Writes.empty());
    }
    assert(PF_HAS_EXPLICIT_LAYOUT && "repair must expose explicit legal sampled layout");
#if PF_HAS_EXPLICIT_LAYOUT
    for (int layout : { VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
        VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL })
    {
        bool threw = false;
        try { device.Descriptors.SetBindlessTexture(259, image.View.get(), &device.Samplers.Sampler, layout); }
        catch (const std::runtime_error&) { threw = true; }
        assert(threw && device.Descriptors.Bindless.Writer.Writes.empty());
    }
    for (int layout : { VK_IMAGE_LAYOUT_GENERAL, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL })
    {
        device.Descriptors.SetBindlessTexture(259, image.View.get(), &device.Samplers.Sampler, layout);
        assert(device.Descriptors.Bindless.Writer.Writes.back().Layout == layout);
    }
#endif
}

int main(int argc, char** argv)
{
    assert(argc == 2);
    const std::string mode = argv[1];
    if (mode == "mapped-r8") Mapped(1, false, false);
    else if (mode == "mapped-bgra") Mapped(4, false, false);
    else if (mode == "repeated") { Mapped(1, true, false); Mapped(4, true, false); }
    else if (mode == "resize") { Mapped(1, false, true); Mapped(4, false, true); }
    else if (mode == "ordinary") Ordinary();
    else if (mode == "invalid") Invalid();
    else throw std::runtime_error("unknown fixture mode");
    std::cout << mode << " passed\n";
}
