// #110 production-source-extracted CPU constructor/descriptor regression.
// Generated definitions are the real FMaterial and VkMaterial bodies. Services
// below bound the texture/container/descriptor interfaces and replace GPU work
// with recorded identities. Checked TArray access observes the original invalid
// access without inducing UB. This does not execute Vulkan, upload bytes to a
// device, validate a complete texture manager, or establish visual equivalence.
// Canonical remap pointers are supplied with coherent Palette/Remap contents;
// AddRemap dedup and actual arena allocation are outside these service bounds.
// Queued callbacks replay serially. Recorded retirement is released at a
// simulated fence boundary, and is not a native synchronization result.
#include <array>
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstddef>
#include <cstring>
#include <functional>
#include <iostream>
#include <list>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
#include <unordered_map>
#include <vector>

class MissingLayer : public std::runtime_error
{
public:
    int Index;
    explicit MissingLayer(int index, std::size_t count)
        : std::runtime_error("out-of-range layer " + std::to_string(index) + " of " + std::to_string(count)), Index(index) { }
};

template<class T> class TArray
{
    mutable std::vector<T> Values;
public:
    unsigned int Size() const { return static_cast<unsigned int>(Values.size()); }
    void Push(T value) { Values.push_back(std::move(value)); }
    void ShrinkToFit() { Values.shrink_to_fit(); }
    T& Last() { return Values.back(); }
    T& operator[](int index) const
    {
        if (index < 0 || static_cast<std::size_t>(index) >= Values.size()) throw MissingLayer(index, Values.size());
        return Values[static_cast<std::size_t>(index)];
    }
};

enum { CTF_Expand = 1, CTF_Upscale = 2, CTF_Indexed = 4, CTF_CheckOnly = 8, CTF_ProcessData = 16, CTF_IndexedRedIsAlpha = 32 };
enum { CLAMP_NONE = 0, CLAMP_X = 1, CLAMP_Y = 2, CLAMP_XY = 3, CLAMP_XY_NOMIP = 4, CLAMP_NOFILTER = 5, CLAMP_NOFILTER_X = 6, CLAMP_NOFILTER_Y = 7, CLAMP_NOFILTER_XY = 8, CLAMP_CAMTEX = 9 };
enum { SHADER_Default = 0, SHADER_Specular = 3, SHADER_PBR = 4, SHADER_Paletted = 5, FIRST_USER_SHADER = 15 };
enum { TEXF_Brightmap = 0x10000, TEXF_Detailmap = 0x20000, TEXF_Glowmap = 0x40000 };
enum class MaterialLayerSampling { Default, NearestMipLinear, LinearMipLinear };
enum class MaterialLayerSemantic { Albedo, Normal, LegacySpecular, Metallic, Roughness, AmbientOcclusion, Brightmap, Detail, Glow, Custom };
enum class ETextureType { Normal, SWCanvas };

class FTexture;
FTexture* LastProducedTexture = nullptr;
int LastProducedTranslation = 0, LastProducedFlags = 0;
class FGameTexture;
class FMaterial;
class VkMaterial;
class VkHardwareTexture;
class VulkanRenderDevice;
struct FakeView;
struct FakeTransferCommands;
enum { VK_FORMAT_R8_UNORM = 1, VK_FORMAT_B8G8R8A8_UNORM = 2, VK_FORMAT_R32G32B32A32_SFLOAT = 3, VK_FORMAT_R8G8B8A8_UNORM = 4 };
enum { VK_IMAGE_USAGE_TRANSFER_SRC_BIT = 1, VK_IMAGE_USAGE_TRANSFER_DST_BIT = 2, VK_IMAGE_USAGE_SAMPLED_BIT = 4, VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT = 8 };
enum { VK_IMAGE_LAYOUT_UNDEFINED = 0, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL = 1, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL = 2, VK_IMAGE_ASPECT_COLOR_BIT = 1 };
using VkFormat = int;
struct PalEntry { uint8_t b = 0, g = 0, r = 0, a = 0; };
static_assert(sizeof(PalEntry) == 4, "BGRA source row byte layout");
struct FakeImage
{
    FakeImage* image = this;
    int Width = 0, Height = 0, Mips = 1, Format = 0, Usage = 0;
    int CurrentLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    std::vector<uint8_t> Bytes;
    FakeView* Observer = nullptr;
    std::vector<std::pair<int, bool>> Transitions;
    void Unmap() { }
};
struct FakeView
{
    FTexture* Owner = nullptr;
    int Translation = 0;
    int Flags = 0;
    std::array<uint8_t, 8> Indices{};
    FakeImage* Image = nullptr;
};
struct FakeFramebuffer { };
struct VkTextureImage
{
    std::unique_ptr<FakeImage> Image;
    std::unique_ptr<FakeView> View, DepthOnlyView, LMView;
    std::unique_ptr<FakeFramebuffer> PPFramebuffer, ZMinMaxFramebuffer, LMFramebuffer;
    std::map<int, std::unique_ptr<FakeFramebuffer>> RSFramebuffers;
    int Layout = VK_IMAGE_LAYOUT_UNDEFINED, AspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    void Reset(VulkanRenderDevice* fb);
    // Mipmap generation remains outside this no-mipmap contract fixture.
    void GenerateMipmaps(FakeTransferCommands*) { Layout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL; Image->CurrentLayout = Layout; }
};
class IHardwareTexture { public: virtual ~IHardwareTexture() = default; };

struct FRemapTable { std::array<uint8_t, 256> Remap{}; std::array<PalEntry, 256> Palette{}; int Index = 0; bool Inactive = false; };
struct FakePalette
{
    std::map<int, FRemapTable*> Tables;
    std::array<PalEntry, 256> BaseColors{};
    FRemapTable* GetTranslation(int, int index) const
    {
        auto found = Tables.find(index);
        return found == Tables.end() ? nullptr : found->second;
    }
    FRemapTable* TranslationToTable(int index) const { return GetTranslation(0, index); }
} GPalette;
bool IsLuminosityTranslation(int translation) { return translation >= 10000; }
int GetTranslationType(int) { return 0; }
int GetTranslationIndex(int translation) { return translation; }

class FakeSystemTextures
{
public:
    std::map<std::pair<int, int>, std::unique_ptr<IHardwareTexture>> Owners;
    IHardwareTexture* GetHardwareTexture(int translation, int flags)
    {
        auto found = Owners.find({translation, flags});
        return found == Owners.end() ? nullptr : found->second.get();
    }
    void AddHardwareTexture(int translation, int flags, IHardwareTexture* owner)
    {
        Owners[{translation, flags}].reset(owner);
    }
};
struct FTextureBuffer
{
    uint8_t* mBuffer = nullptr;
    int mWidth = 0, mHeight = 0, mContentId = 0;
    FTextureBuffer() = default;
    FTextureBuffer(const FTextureBuffer&) = delete;
    FTextureBuffer(FTextureBuffer&& other) noexcept
        : mBuffer(other.mBuffer), mWidth(other.mWidth), mHeight(other.mHeight), mContentId(other.mContentId) { other.mBuffer = nullptr; }
    ~FTextureBuffer() { delete[] mBuffer; }
};
struct FakePixels { const uint8_t* Pixels; const uint8_t* Data() const { return Pixels; } };
namespace ImageHelpers
{
    // All fixture images are 8x1; only the inherited no-op orientation case is
    // modelled. No rectangular/transposition or pixel resampling claim is made.
    void FlipNonSquareBlock(uint8_t* dest, const uint8_t* source, int h, int w, int)
    {
        assert(h == 1 && w == 8);
        for (int i = 0; i < w; ++i) dest[i] = source[i];
    }
}
class FTexture
{
public:
    FakeSystemTextures SystemTextures;
    std::array<uint8_t, 8> Pixels{0, 1, 2, 15, 63, 127, 200, 255};
    std::array<uint8_t, 8> Alpha{0, 3, 17, 64, 128, 190, 230, 255};
    int GetWidth() const { return 8; }
    int GetHeight() const { return 1; }
    FakePixels Get8BitPixels(bool alpha) const { return {alpha ? Alpha.data() : Pixels.data()}; }
    bool isHardwareCanvas() const { return false; }
    bool IsHDR() const { return false; }
    const void* GetImage() const { return this; }
    IHardwareTexture* GetHardwareTexture(int translation, int scaleflags);
    FTextureBuffer CreateTexBuffer(int translation, int flags);
    virtual ~FTexture() = default;
};
class FWrapperTexture : public FTexture { public: int Format = 0; int GetColorFormat() const { return Format; } };
struct FakeLayers
{
    std::shared_ptr<FTexture> Normal, Specular, Metallic, Roughness, AmbientOcclusion, Detailmap, Glowmap;
    std::array<std::shared_ptr<FTexture>, 15> CustomShaderTextures{};
    std::array<MaterialLayerSampling, 15> CustomShaderTextureSampling{};
};
class FGameTexture
{
public:
    FTexture* Texture;
    ETextureType Use = ETextureType::Normal;
    FakeLayers* Layers = nullptr;
    std::shared_ptr<FTexture> Brightmap;
    std::map<int, FMaterial*> Material;
    bool Valid = true;
    explicit FGameTexture(FTexture* texture) : Texture(texture) { }
    FTexture* GetTexture() const { return Texture; }
    ETextureType GetUseType() const { return Use; }
    bool isHardwareCanvas() const { return false; }
    int isWarped() const { return 0; }
    int GetShaderIndex() const { return 0; }
    int GetClampMode(int mode) const { return mode; }
    bool isValid() const { return Valid; }
    bool expandSprites() const { return true; }
    void CreateDefaultBrightmap() { }
};
struct FakeTextureManager
{
    FGameTexture* Placeholder = nullptr;
    FGameTexture* GameByIndex(int index) const { assert(index == 1); return Placeholder; }
} TexMan;
struct GlobalShaderAddr
{
    int type = 0, index = 0, custom = 0;
    bool operator==(const GlobalShaderAddr& other) const { return type == other.type && index == other.index && custom == other.custom; }
};
struct GlobalShaderDesc
{
    int shaderindex = -1;
    std::array<std::shared_ptr<FTexture>, 15> CustomShaderTextures{};
    std::array<MaterialLayerSampling, 15> CustomShaderTextureSampling{};
    explicit operator bool() const { return shaderindex >= 0; }
};
std::array<GlobalShaderDesc, FIRST_USER_SHADER> globalshaders;
GlobalShaderDesc nullglobalshader;
const GlobalShaderDesc* GetGlobalShader(GlobalShaderAddr) { return &nullglobalshader; }
struct UserShaderDesc { int shaderType = 0; };
std::vector<UserShaderDesc> usershaders;
bool gl_customshader = false;

struct MaterialLayerInfo
{
    FTexture* layerTexture;
    int scaleFlags, clampflags;
    MaterialLayerSampling layerFiltering;
    MaterialLayerSemantic semantic;
    int customIndex;
};
class FMaterial
{
public:
    TArray<MaterialLayerInfo> mTextureLayers;
    int mShaderIndex = 0, mLayerFlags = 0, mScaleFlags = 0, mNumNonMaterialLayers = 0;
    FGameTexture* sourcetex = nullptr;
    FMaterial(FGameTexture* tex, int flags);
    virtual ~FMaterial() = default;
    virtual void DeleteDescriptors() { }
    FGameTexture* Source() const { return sourcetex; }
    int NumLayers() const { return static_cast<int>(mTextureLayers.Size()); }
    int NumNonMaterialLayers() const { return mNumNonMaterialLayers; }
    int GetShaderIndex() const { return mShaderIndex; }
    int GetScaleFlags() const { return mScaleFlags; }
    MaterialLayerSampling GetLayerFilter(int index) const { return mTextureLayers[index].layerFiltering; }
    void AddTextureLayer(FTexture* texture, bool scale, MaterialLayerSampling filter)
    {
        mTextureLayers.Push({texture, scale ? 1 : 0, -1, filter, MaterialLayerSemantic::Custom, -1});
    }
    IHardwareTexture* GetLayer(int index, int translation, MaterialLayerInfo** layer = nullptr) const;
    static FMaterial* ValidateTexture(FGameTexture* tex, int flags, bool create = true);
};
struct FMaterialState
{
    int mClampMode = CLAMP_XY_NOMIP, mTranslation = 0;
    GlobalShaderAddr globalShaderAddr;
    bool mPaletteMode = false, mRedIsAlpha = false;
};
struct FakeSampler { MaterialLayerSampling Filter = MaterialLayerSampling::Default; int Clamp = 0; };
class FakeSamplerManager
{
    std::map<std::pair<int, int>, FakeSampler> Samplers;
public:
    FakeSampler* Get(int clamp) { return Get(MaterialLayerSampling::Default, clamp); }
    FakeSampler* Get(MaterialLayerSampling filter, int clamp)
    {
        auto& sampler = Samplers[{static_cast<int>(filter), clamp}];
        sampler.Filter = filter; sampler.Clamp = clamp; return &sampler;
    }
};
struct FakeBinding { int Index; FakeView* View; FakeSampler* Sampler; int Layout; };
class VkDescriptorSetManager
{
public:
    std::list<VkMaterial*> Materials;
    std::vector<int> AllocationCounts, Freed;
    std::vector<FakeBinding> Writes;
    std::map<int, int> Live;
    int Next = 259;
    int AllocBindlessSlot(int count)
    {
        assert(count > 0); int start = Next; Next += count;
        Live[start] = count; AllocationCounts.push_back(count); return start;
    }
    void FreeBindlessSlot(int start)
    {
        if (Live.erase(start) != 1) throw std::runtime_error("invalid/double descriptor free");
        Freed.push_back(start);
    }
    void SetBindlessTexture(int index, FakeView* view, FakeSampler* sampler, int layout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL)
    {
        assert(view && sampler); Writes.push_back({index, view, sampler, layout});
    }
    void AddMaterial(VkMaterial* texture);
    void RemoveMaterial(VkMaterial* texture);
};
struct FakeBuffer
{
    FakeBuffer* buffer = this;
    std::vector<uint8_t> Bytes;
};
struct VkBufferImageCopy
{
    std::size_t bufferOffset = 0;
    struct { int aspectMask = 0, layerCount = 0; } imageSubresource;
    struct Extent { int width = 0, height = 0, depth = 0; } imageExtent;
};
struct FakeTransferCommands
{
    int Copies = 0;
    std::vector<std::size_t> Offsets;
    void copyBufferToImage(FakeBuffer* buffer, FakeImage* image, int layout, int count, const VkBufferImageCopy* region)
    {
        assert(layout == VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL && count == 1);
        assert(region->imageSubresource.aspectMask == VK_IMAGE_ASPECT_COLOR_BIT && region->imageSubresource.layerCount == 1);
        assert(region->imageExtent.width == image->Width && region->imageExtent.height == image->Height && region->imageExtent.depth == 1);
        const int pixelSize = image->Format == VK_FORMAT_R8_UNORM ? 1 : 4;
        const auto size = static_cast<std::size_t>(image->Width * image->Height * pixelSize);
        assert(region->bufferOffset + size <= buffer->Bytes.size());
        image->Bytes.assign(buffer->Bytes.begin() + static_cast<std::ptrdiff_t>(region->bufferOffset),
                            buffer->Bytes.begin() + static_cast<std::ptrdiff_t>(region->bufferOffset + size));
        if (pixelSize == 1 && size == 8) std::copy(image->Bytes.begin(), image->Bytes.end(), image->Observer->Indices.begin());
        ++Copies; Offsets.push_back(region->bufferOffset);
    }
};
struct FakeDeleteList
{
    std::vector<std::unique_ptr<FakeImage>> Images;
    std::vector<std::unique_ptr<FakeView>> Views;
    std::vector<std::unique_ptr<FakeFramebuffer>> Framebuffers;
    const std::vector<int>* Freed = nullptr;
    std::vector<std::size_t> FreedAtRetirement;
    void Add(std::unique_ptr<FakeImage> image)
    {
        if (image) { FreedAtRetirement.push_back(Freed ? Freed->size() : 0); Images.push_back(std::move(image)); }
    }
    void Add(std::unique_ptr<FakeView> view) { if (view) Views.push_back(std::move(view)); }
    void Add(std::unique_ptr<FakeFramebuffer> framebuffer) { if (framebuffer) Framebuffers.push_back(std::move(framebuffer)); }
};
struct FakeCommands
{
    FakeTransferCommands Transfer;
    std::unique_ptr<FakeDeleteList> DrawDeleteList = std::make_unique<FakeDeleteList>();
    FakeTransferCommands* GetTransferCommands() { return &Transfer; }
};
struct FakeUploadTicket { uint64_t TargetEpoch = 0; };
struct FakeTextureManagerBackend
{
    struct FUploadStagingAllocation { FakeBuffer* Buffer = nullptr; std::size_t Offset = 0; };
    FakeBuffer Staging;
    int Stages = 0, Finishes = 0, Completed = 0, Stale = 0;
    std::vector<std::function<void()>> Workers, Main;
    FUploadStagingAllocation StageTextureUpload(const void* pixels, std::size_t size)
    {
        ++Stages; const std::size_t offset = 32;
        Staging.Bytes.assign(offset + size, 0xab);
        std::memcpy(Staging.Bytes.data() + offset, pixels, size);
        return {&Staging, offset};
    }
    void FinishTextureUpload(const FUploadStagingAllocation&) { ++Finishes; }
    FakeUploadTicket CreateUploadTicket(VkHardwareTexture*, uint64_t epoch) { return {epoch}; }
    bool CheckUploadTicket(const FakeUploadTicket&) const { return true; }
    void RunOnWorkerThread(std::function<void()> work) { Workers.push_back(std::move(work)); }
    void RunOnMainThread(std::function<void()> work) { Main.push_back(std::move(work)); }
    void RecordUploadCompleted() { ++Completed; }
    void RecordTargetUploadStale() { ++Stale; }
    void RunPending()
    {
        auto workers = std::move(Workers); Workers.clear();
        for (auto& work : workers) work();
        auto main = std::move(Main); Main.clear();
        for (auto& work : main) work();
    }
};
class VulkanRenderDevice
{
public:
    VkDescriptorSetManager Descriptors;
    FakeSamplerManager Samplers;
    FakeCommands Commands;
    FakeTextureManagerBackend Textures;
    VulkanRenderDevice() { Commands.DrawDeleteList->Freed = &Descriptors.Freed; }
    VkDescriptorSetManager* GetDescriptorSetManager() { return &Descriptors; }
    FakeSamplerManager* GetSamplerManager() { return &Samplers; }
    FakeCommands* GetCommands() { return &Commands; }
    FakeTextureManagerBackend* GetTextureManager() { return &Textures; }
    VulkanRenderDevice* GetDevice() { return this; }
};
struct ImageBuilder
{
    int ImageFormat = 0, Width = 0, Height = 0, Mips = 1, ImageUsage = 0;
    ImageBuilder& Format(int format) { ImageFormat = format; return *this; }
    ImageBuilder& Size(int width, int height, int mips = 1) { Width = width; Height = height; Mips = mips; return *this; }
    ImageBuilder& Usage(int usage) { ImageUsage = usage; return *this; }
    ImageBuilder& DebugName(const char*) { return *this; }
    std::unique_ptr<FakeImage> Create(VulkanRenderDevice*) const
    {
        auto image = std::make_unique<FakeImage>();
        image->Format = ImageFormat; image->Width = Width; image->Height = Height;
        image->Mips = Mips; image->Usage = ImageUsage; return image;
    }
};
struct ImageViewBuilder
{
    FakeImage* Source = nullptr;
    ImageViewBuilder& Image(FakeImage* image, int format) { assert(image->Format == format); Source = image; return *this; }
    ImageViewBuilder& DebugName(const char*) { return *this; }
    std::unique_ptr<FakeView> Create(VulkanRenderDevice*) const
    {
        auto view = std::make_unique<FakeView>(); view->Image = Source; Source->Observer = view.get();
        view->Owner = LastProducedTexture; view->Translation = LastProducedTranslation; view->Flags = LastProducedFlags;
        return view;
    }
};
struct VkImageTransition
{
    VkTextureImage* Image = nullptr;
    int Target = 0;
    bool Undefined = false;
    VkImageTransition& AddImage(VkTextureImage* image, int target, bool undefined)
    {
        if (!undefined) assert(image->Layout == VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL);
        Image = image; Target = target; Undefined = undefined; return *this;
    }
    void Execute(FakeTransferCommands*) { assert(Image); Image->Layout = Target; Image->Image->CurrentLayout = Target; Image->Image->Transitions.push_back({Target, Undefined}); }
};
struct FRendererEpoch
{
    uint64_t Generation = 1;
    uint64_t Snapshot() const { return Generation; }
    void Invalidate() { ++Generation; }
    bool Validate(uint64_t generation) const { return Generation == generation; }
};
bool gl_async_textures = true;
using std::max;
class CVulkanError : public std::runtime_error { public: explicit CVulkanError(const char* message) : std::runtime_error(message) { } };
class VkHardwareTexture : public IHardwareTexture
{
public:
    VkTextureImage mImage, mPaletteImage, mAlphaImage;
    VkTextureImage mDepthStencil;
    VulkanRenderDevice* fb = nullptr;
    FRendererEpoch mUploadEpoch;
    uint8_t* mappedSWFB = nullptr;
    std::unordered_map<const FRemapTable*, std::unique_ptr<VkTextureImage>> IndexedPaletteImages, IndexedAlphaImages;
    VkTextureImage* GetImage(FTexture* tex, int translation, int flags);
    VkTextureImage* GetIndexedMaterialImage(FTexture* tex, int translation, int flags);
    void Reset();
    void CreateImage(VkTextureImage* image, FTexture* tex, int translation, int flags, bool allowAsync = true);
    void CreateTexture(VkTextureImage* image, int width, int height, int pixelSize, int format, const void* pixels, bool mipmap);
    void UploadTexture(VkTextureImage* image, int width, int height, int pixelSize, int format, const void* pixels, bool mipmap);
    static int GetMipLevels(int width, int height);
};
class VkMaterial : public FMaterial
{
public:
    struct DescriptorEntry
    {
        int clampmode;
        intptr_t remap;
        int bindlessIndex;
        GlobalShaderAddr globalShaderAddr;
        bool indexed, redIsAlpha;
        std::unique_ptr<VkTextureImage> IndexedPalette;
        DescriptorEntry(int clamp, intptr_t table, int start, GlobalShaderAddr global, bool palette, bool alpha)
            : clampmode(clamp), remap(table), bindlessIndex(start), globalShaderAddr(global), indexed(palette), redIsAlpha(alpha) { }
    };
    VulkanRenderDevice* fb;
    std::list<VkMaterial*>::iterator it;
    std::vector<DescriptorEntry> mDescriptorSets;
    VkMaterial(VulkanRenderDevice* device, FGameTexture* texture, int flags);
    ~VkMaterial() override;
    void DeleteDescriptors() override;
    int GetBindlessIndex(const FMaterialState& state);
    DescriptorEntry& GetDescriptorEntry(const FMaterialState& state);
    std::unique_ptr<VkTextureImage> CreateIndexedPalette();
};
class FakeScreen
{
public:
    VulkanRenderDevice* Device = nullptr;
    IHardwareTexture* CreateHardwareTexture(int) { auto texture = new VkHardwareTexture(); texture->fb = Device; return texture; }
    FMaterial* CreateMaterial(FGameTexture* tex, int flags) { return new VkMaterial(Device, tex, flags); }
} Screen;
FakeScreen* screen = &Screen;
void I_FatalError(const char* message) { throw std::runtime_error(message); }
struct vec4
{
    double r, g, b, a;
    vec4(double red, double green, double blue, double alpha) : r(red), g(green), b(blue), a(alpha) { }
};

#include "production_indexed_material.h"

void Check(bool value, const char* message)
{
    if (!value) throw std::runtime_error(message);
}
void CheckPublishedReadLayouts(const VulkanRenderDevice& device)
{
    Check(!device.Descriptors.Writes.empty(), "positive sampled-layout control must publish actual production bindings");
    for (const auto& write : device.Descriptors.Writes)
    {
        Check(write.View && write.View->Image, "sampled-layout control requires its selected resident image");
        Check(write.Layout == VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL && write.Layout == write.View->Image->CurrentLayout,
            "actual material publication agrees with selected uploaded image's READ layout");
    }
}
void LegacyMissingLayer()
{
    VulkanRenderDevice device; Screen.Device = &device;
    FTexture source; FGameTexture game(&source); VkMaterial material(&device, &game, CTF_Indexed);
    Check(material.NumLayers() == 1, "production indexed constructor no longer has one layer");
    FMaterialState state;
    bool caught = false;
    try { material.GetBindlessIndex(state); }
    catch (const MissingLayer& error) { caught = error.Index == 1; }
    Check(caught, "original three-binding consumer did not reach missing layer 1");
    Check(device.Descriptors.AllocationCounts == std::vector<int>{3}, "actual consumer did not allocate three descriptors");
    Check(device.Descriptors.Writes.size() == 1, "original consumer should publish only albedo before missing-layer access");
    std::cout << "preserved original: layers=1 allocation=3 writes=1 missing=1\n";
}
void CurrentIndexed()
{
    VulkanRenderDevice device; Screen.Device = &device;
    FTexture source; FGameTexture game(&source); VkMaterial material(&device, &game, CTF_Indexed);
    Check(material.GetShaderIndex() == SHADER_Paletted, "indexed constructor shader");
    FMaterialState state;
    const int first = material.GetBindlessIndex(state);
    Check(material.GetBindlessIndex(state) == first, "repeat indexed descriptor identity");
    Check(device.Descriptors.AllocationCounts == std::vector<int>{2}, "indexed shader requires actual albedo + palette resources");
    Check(device.Descriptors.Writes.size() == 2, "indexed descriptor publication count");
    Check(device.Descriptors.Writes[0].View->Owner == &source, "indexed albedo source owner");
    Check(device.Descriptors.Writes[0].View->Translation == 0, "indexed albedo must upload neutral raw indices");
    Check(device.Descriptors.Writes[0].Sampler->Clamp >= CLAMP_NOFILTER, "indexed albedo nearest/no-filter clamp");
    Check(device.Descriptors.Writes[1].View != device.Descriptors.Writes[0].View, "palette must be a distinct real resource");
    CheckPublishedReadLayouts(device);
}
void OrdinaryAndPaletteState()
{
    VulkanRenderDevice device; Screen.Device = &device;
    FTexture source; FGameTexture game(&source); VkMaterial material(&device, &game, 0);
    Check(material.NumLayers() == 4 && material.GetShaderIndex() == SHADER_Default, "ordinary four-layer constructor");
    FMaterialState state;
    int ordinary = material.GetBindlessIndex(state);
    Check(material.GetBindlessIndex(state) == ordinary, "ordinary cached descriptor");
    state.mPaletteMode = true;
    int indexedMode = material.GetBindlessIndex(state);
    Check(indexedMode != ordinary, "palette mode must partition descriptor identity");
    Check(material.mDescriptorSets.back().indexed && !material.mDescriptorSets.back().redIsAlpha, "ordinary palette index interpretation");
    state.mRedIsAlpha = true;
    int alpha = material.GetBindlessIndex(state);
    Check(alpha != indexedMode && material.mDescriptorSets.back().redIsAlpha, "RedIsAlpha descriptor interpretation");
    auto owner = static_cast<VkHardwareTexture*>(material.GetLayer(0, 0));
    Check(owner->mPaletteImage.View != owner->mAlphaImage.View, "R8 palette/luminance image owner separation");
    for (int count : device.Descriptors.AllocationCounts) Check(count == 4, "ordinary/palette-mode layer ABI");
    CheckPublishedReadLayouts(device);
}
void SWCanvas()
{
    VulkanRenderDevice device; Screen.Device = &device;
    FWrapperTexture source; FGameTexture game(&source); game.Use = ETextureType::SWCanvas;
    VkMaterial material(&device, &game, 0);
    Check(material.NumLayers() == 1 && material.GetShaderIndex() == SHADER_Paletted, "SWCanvas constructor path");
    FTexture palette;
    SourceAppendSWPalette(&material, &palette);
    Check(material.NumLayers() == 2, "production software presentation appends its palette");
    FMaterialState state; material.GetBindlessIndex(state);
    Check(device.Descriptors.AllocationCounts == std::vector<int>{2}, "SWCanvas real two-layer descriptor count");
    Check(device.Descriptors.Writes[1].View->Owner == &palette, "SWCanvas keeps its own palette owner");
    // This bounded inherited fixture creates uploaded images. Actual mapped
    // GENERAL software frames are covered by swcanvas_layout_fixture.cpp.
    CheckPublishedReadLayouts(device);
}
void MissingInput()
{
    Check(FMaterial::ValidateTexture(nullptr, CTF_Indexed) == nullptr, "null texture validation");
    FTexture source; FGameTexture invalid(&source); invalid.Valid = false;
    Check(FMaterial::ValidateTexture(&invalid, CTF_Indexed) == nullptr, "invalid texture validation");
    FGameTexture valid(&source);
    Check(FMaterial::ValidateTexture(&valid, CTF_Indexed, false) == nullptr, "missing uncreated variant");
}
void CleanupRecreation()
{
    VulkanRenderDevice device; Screen.Device = &device;
    for (int cycle = 0; cycle < 3; ++cycle)
    {
        FTexture source; FGameTexture game(&source);
        {
            VkMaterial material(&device, &game, 0); FMaterialState state;
            int first = material.GetBindlessIndex(state);
            material.DeleteDescriptors();
            Check(device.Descriptors.Live.empty(), "range cleanup");
            int second = material.GetBindlessIndex(state);
            Check(first != second, "recreated descriptor range");
        }
        Check(device.Descriptors.Live.empty() && device.Descriptors.Materials.empty(), "material destruction cleanup");
    }
    Check(device.Descriptors.Freed.size() == 6, "each descriptor range freed once");
}
void ExistingImageOwnerWitness()
{
    VulkanRenderDevice device; Screen.Device = &device;
    FRemapTable first, second;
    for (std::size_t i = 0; i < 256; ++i)
    {
        first.Remap[i] = static_cast<uint8_t>((i + 1) % 256);
        second.Remap[i] = static_cast<uint8_t>((i + 2) % 256);
        first.Palette[i] = GPalette.BaseColors[first.Remap[i]];
        second.Palette[i] = GPalette.BaseColors[second.Remap[i]];
    }
    first.Index = 1; second.Index = 2;
    GPalette.Tables[1] = &first; GPalette.Tables[2] = &second;
    FTexture source;
    auto firstOwner = static_cast<VkHardwareTexture*>(source.GetHardwareTexture(1, CTF_Indexed));
    auto secondOwner = static_cast<VkHardwareTexture*>(source.GetHardwareTexture(2, CTF_Indexed));
    Check(firstOwner == secondOwner, "actual indexed cache forces translation -1 owner");
    auto firstImage = firstOwner->GetImage(&source, 1, CTF_Indexed);
    auto secondImage = secondOwner->GetImage(&source, 2, CTF_Indexed);
    auto secondProduced = source.CreateTexBuffer(2, CTF_Indexed);
    Check(firstImage == secondImage && device.Textures.Stages == 1, "actual single palette image caches first upload");
    Check(firstImage->View->Indices[0] == first.Remap[0], "actual first remap producer");
    Check(secondProduced.mBuffer[0] == second.Remap[0], "actual second remap producer");
    Check(firstImage->View->Indices[0] != secondProduced.mBuffer[0], "preserved owner contamination counterexample");
    std::cout << "existing owner witness: forced=-1 first=1 requested-second=2 upload-count=1\n";
    GPalette.Tables.clear();
}
void InitializeBasePalette()
{
    for (std::size_t i = 0; i < 256; ++i)
        GPalette.BaseColors[i] = {static_cast<uint8_t>(i), static_cast<uint8_t>(i ^ 85), static_cast<uint8_t>(255 - i), static_cast<uint8_t>(i / 2)};
}
FRemapTable CoherentRemap(int shift, int index)
{
    FRemapTable remap; remap.Index = index;
    for (std::size_t i = 0; i < 256; ++i)
    {
        remap.Remap[i] = static_cast<uint8_t>((static_cast<int>(i) + shift) % 256);
        remap.Palette[i] = GPalette.BaseColors[remap.Remap[i]];
    }
    return remap;
}
void CheckIndexedBytes(const FakeView* view, const FTexture& source, const FRemapTable* remap, bool alpha = false)
{
    for (std::size_t i = 0; i < 8; ++i)
    {
        const uint8_t byte = alpha ? source.Alpha[i] : source.Pixels[i];
        Check(view->Indices[i] == (remap ? remap->Remap[byte] : byte), "actual indexed byte producer content");
    }
    Check(view->Image->Format == VK_FORMAT_R8_UNORM && view->Image->Mips == 1, "indexed upload R8/one mip");
}
void CheckPalette(const FakeView* view)
{
    Check(view->Image && view->Image->Width == 256 && view->Image->Height == 1 && view->Image->Mips == 1, "palette row extent/mips");
    Check(view->Image->Format == VK_FORMAT_B8G8R8A8_UNORM, "palette BGRA format");
    Check(view->Image->Bytes.size() == 1024, "actual palette source byte count");
    for (std::size_t i = 0; i < 256; ++i)
    {
        const auto& bytes = view->Image->Bytes;
        Check(bytes[4 * i] == GPalette.BaseColors[i].b && bytes[4 * i + 1] == GPalette.BaseColors[i].g
              && bytes[4 * i + 2] == GPalette.BaseColors[i].r && bytes[4 * i + 3] == 255, "actual base palette BGRA/opaque row content");
    }
}
void PaletteUpload()
{
    VulkanRenderDevice device; Screen.Device = &device;
    FTexture source; FGameTexture game(&source); VkMaterial material(&device, &game, CTF_Indexed);
    FMaterialState state; material.GetBindlessIndex(state);
    CheckPalette(device.Descriptors.Writes[1].View);
    Check(material.mDescriptorSets[0].IndexedPalette->View.get() == device.Descriptors.Writes[1].View, "descriptor owns actual palette row");
    Check(material.mDescriptorSets[0].IndexedPalette->Layout == VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL, "palette final sampled layout");
    Check(device.Commands.Transfer.Copies == 2 && device.Commands.Transfer.Offsets == std::vector<std::size_t>{32, 32}, "index and palette actual copies consume staging offsets");
    Check(device.Textures.Stages == 2 && device.Textures.Finishes == 2, "index and palette use existing staging finish path");
    Check(device.Descriptors.Writes[1].Sampler->Clamp == CLAMP_NOFILTER_XY, "palette discrete clamped sampler");
    CheckPublishedReadLayouts(device);
}
void TranslationVariants()
{
    VulkanRenderDevice device; Screen.Device = &device;
    auto a = CoherentRemap(1, 1), b = CoherentRemap(2, 2), replacement = CoherentRemap(3, 3);
    GPalette.Tables[1] = &a; GPalette.Tables[2] = &b;
    // The bounded palette service supplies canonical pointers. Palette bytes
    // are coherent and distinct; AddRemap dedup itself is not simulated.
    Check(a.Palette[0].b != b.Palette[0].b, "distinct coherent canonical remaps");
    FTexture source; FGameTexture game(&source); VkMaterial material(&device, &game, CTF_Indexed);
    FMaterialState state; state.mTranslation = 1;
    const int first = material.GetBindlessIndex(state);
    auto* firstView = device.Descriptors.Writes[0].View;
    state.mTranslation = 2; const int second = material.GetBindlessIndex(state);
    auto* secondView = device.Descriptors.Writes[2].View;
    Check(first != second && firstView != secondView, "A/B resource identities");
    state.mTranslation = 1; Check(material.GetBindlessIndex(state) == first, "A/B/A cache reuse");
    state.mTranslation = 2; Check(material.GetBindlessIndex(state) == second, "B/A/B cache reuse");
    CheckIndexedBytes(firstView, source, &a); CheckIndexedBytes(secondView, source, &b);
    auto* owner = static_cast<VkHardwareTexture*>(material.GetLayer(0, 1));
    Check(owner == material.GetLayer(0, 2) && owner->IndexedPaletteImages.size() == 2, "forced -1 owner with canonical image variants");
    Check(device.Textures.Stages == 4 && device.Textures.Workers.empty(), "one synchronous production and row per canonical variant");
    GPalette.Tables[1] = &replacement; state.mTranslation = 1;
    const int changed = material.GetBindlessIndex(state);
    Check(changed != first && changed != second, "numerical translation ID replacement changes descriptor identity");
    CheckIndexedBytes(device.Descriptors.Writes[4].View, source, &replacement);
    CheckIndexedBytes(firstView, source, &a); CheckIndexedBytes(secondView, source, &b);
    GPalette.Tables[3] = &replacement; state.mTranslation = 3;
    Check(material.GetBindlessIndex(state) == changed, "canonical alias pointer reuses descriptor");
    GPalette.Tables[1] = &a; state.mTranslation = 1;
    Check(material.GetBindlessIndex(state) == first && owner->IndexedPaletteImages.size() == 3, "canonical A remains resident after replacement");
    for (std::size_t i = 1; i < device.Descriptors.Writes.size(); i += 2) CheckPalette(device.Descriptors.Writes[i].View);
    GPalette.Tables.clear();
}
void DefaultPolicy()
{
    VulkanRenderDevice device; Screen.Device = &device;
    auto inactive = CoherentRemap(7, 4); inactive.Inactive = true; GPalette.Tables[4] = &inactive;
    FTexture source; FGameTexture game(&source); VkMaterial material(&device, &game, CTF_Indexed);
    FMaterialState state; const int neutral = material.GetBindlessIndex(state);
    for (int translation : {-1, -2, 999, 10000, 4})
    {
        state.mTranslation = translation;
        Check(material.GetBindlessIndex(state) == neutral, "effective null remap descriptor equivalence");
    }
    CheckIndexedBytes(device.Descriptors.Writes[0].View, source, nullptr);
    auto* owner = static_cast<VkHardwareTexture*>(material.GetLayer(0, 0));
    Check(owner->IndexedPaletteImages.empty() && device.Textures.Stages == 2 && material.mDescriptorSets.size() == 1, "untranslated variants share one index resource and row");
    GPalette.Tables.clear();
}
void AlphaVariants()
{
    VulkanRenderDevice device; Screen.Device = &device;
    auto remap = CoherentRemap(5, 1); GPalette.Tables[1] = &remap;
    FTexture source; auto* owner = static_cast<VkHardwareTexture*>(source.GetHardwareTexture(1, CTF_Indexed));
    auto* indexed = owner->GetIndexedMaterialImage(&source, 1, CTF_Indexed);
    auto* alpha = owner->GetIndexedMaterialImage(&source, 1, CTF_Indexed | CTF_IndexedRedIsAlpha);
    Check(indexed != alpha && owner->IndexedPaletteImages.size() == 1 && owner->IndexedAlphaImages.size() == 1, "indexed/RedIsAlpha canonical maps separate");
    CheckIndexedBytes(indexed->View.get(), source, &remap); CheckIndexedBytes(alpha->View.get(), source, &remap, true);
    Check(owner->GetIndexedMaterialImage(&source, 1, CTF_Indexed) == indexed, "indexed canonical reuse");
    Check(owner->GetIndexedMaterialImage(&source, 1, CTF_Indexed | CTF_IndexedRedIsAlpha) == alpha, "alpha canonical reuse");
    Check(device.Textures.Stages == 2 && device.Textures.Workers.empty(), "both material R8 interpretations synchronous");
    GPalette.Tables.clear();
}
void Sampling()
{
    VulkanRenderDevice device; Screen.Device = &device;
    FTexture source; FGameTexture game(&source); VkMaterial material(&device, &game, CTF_Indexed);
    const std::array<int, 10> expected{5, 6, 7, 8, 8, 5, 6, 7, 8, 5};
    FMaterialState state;
    for (int clamp = 0; clamp < 10; ++clamp)
    {
        state.mClampMode = clamp; material.GetBindlessIndex(state);
        Check(material.GetDescriptorEntry(state).clampmode == expected[static_cast<std::size_t>(clamp)], "index clamp axes and XY_NOMIP no CAMTEX overflow");
    }
    for (const auto& write : device.Descriptors.Writes) Check(write.Sampler->Clamp >= CLAMP_NOFILTER && write.Sampler->Clamp <= CLAMP_NOFILTER_XY, "discrete index/palette sampler");
    FTexture ordinarySource; FGameTexture ordinaryGame(&ordinarySource); VkMaterial ordinary(&device, &ordinaryGame, 0);
    state.mPaletteMode = true; state.mClampMode = CLAMP_XY_NOMIP;
    Check(ordinary.GetDescriptorEntry(state).clampmode == CLAMP_NOFILTER_XY, "state palette XY_NOMIP mapping");
    state.mPaletteMode = false;
    Check(ordinary.GetDescriptorEntry(state).clampmode == CLAMP_XY_NOMIP, "ordinary no-mip clamp preserved");
}
void StyleOrder()
{
    VulkanRenderDevice device; Screen.Device = &device;
    auto remap = CoherentRemap(0, 1); remap.Remap[5] = 10; remap.Remap[250] = 20;
    remap.Palette[5] = GPalette.BaseColors[10]; remap.Palette[250] = GPalette.BaseColors[20]; GPalette.Tables[1] = &remap;
    FTexture source; source.Pixels[0] = 5; FGameTexture game(&source); VkMaterial material(&device, &game, CTF_Indexed);
    FMaterialState state; state.mTranslation = 1; material.GetBindlessIndex(state);
    const auto produced = device.Descriptors.Writes[0].View->Indices[0];
    Check(produced == 10, "source producer remaps before actual shader operations");
    const auto inverse = SourceShaderOrderIndex(produced, true, 0.0, 1.0);
    const auto movedInverse = remap.Remap[SourceShaderOrderIndex(source.Pixels[0], true, 0.0, 1.0)];
    Check(inverse == 245 && movedInverse == 20, "exact source inverse noncommuting witness");
    const auto tint = SourceShaderOrderIndex(produced, false, 0.125, 0.5);
    const auto movedTint = remap.Remap[SourceShaderOrderIndex(source.Pixels[0], false, 0.125, 0.5)];
    Check(tint != movedTint, "source additive/object red tint noncommuting witness");
    CheckPalette(device.Descriptors.Writes[1].View);
    const auto& colors = device.Descriptors.Writes[1].View->Image->Bytes;
    Check(colors[4 * inverse] != colors[4 * movedInverse] && colors[4 * tint] != colors[4 * movedTint], "noncommuting indices select unequal real base-palette bytes");
    std::cout << "source style order: inverse=" << static_cast<int>(inverse) << " moved-row=" << static_cast<int>(movedInverse)
              << " tint=" << static_cast<int>(tint) << " moved-row=" << static_cast<int>(movedTint) << '\n';
    GPalette.Tables.clear();
}
void Retirement()
{
    VulkanRenderDevice device; Screen.Device = &device;
    auto a = CoherentRemap(1, 1), b = CoherentRemap(2, 2); GPalette.Tables[1] = &a; GPalette.Tables[2] = &b;
    FTexture source; FGameTexture game(&source); VkMaterial material(&device, &game, CTF_Indexed);
    FMaterialState state; state.mTranslation = 1; const int first = material.GetBindlessIndex(state);
    auto* firstView = device.Descriptors.Writes[0].View;
    state.mTranslation = 2; material.GetBindlessIndex(state);
    auto* owner = static_cast<VkHardwareTexture*>(material.GetLayer(0, 1));
    owner->GetIndexedMaterialImage(&source, 1, CTF_Indexed | CTF_IndexedRedIsAlpha);
    owner->GetIndexedMaterialImage(&source, 0, CTF_Indexed);
    material.DeleteDescriptors();
    auto* retirement = device.Commands.DrawDeleteList.get();
    Check(device.Descriptors.Live.empty() && retirement->Images.size() == 2 && retirement->Views.size() == 2, "descriptor rows retire through actual Reset");
    Check(retirement->FreedAtRetirement == std::vector<std::size_t>{1, 2}, "free each descriptor range before its image retirement");
    const auto epoch = owner->mUploadEpoch.Snapshot(); owner->Reset();
    Check(owner->mUploadEpoch.Snapshot() == epoch + 1 && owner->IndexedPaletteImages.empty() && owner->IndexedAlphaImages.empty(), "hardware reset clears all maps and epoch");
    Check(!owner->mPaletteImage.Image && retirement->Images.size() == 6 && retirement->Views.size() == 6, "all palette/alpha/null material images retire");
    Check(firstView->Indices[0] == a.Remap[source.Pixels[0]], "retirement services retain old view until simulated fence cleanup");
    state.mTranslation = 1; const int second = material.GetBindlessIndex(state);
    Check(first != second && device.Descriptors.Writes[4].View != firstView, "recreation gets fresh descriptor and view");
    CheckIndexedBytes(device.Descriptors.Writes[4].View, source, &a);
    material.DeleteDescriptors(); owner->Reset();
    retirement->Views.clear(); retirement->Images.clear();
    Check(retirement->Views.empty() && retirement->Images.empty(), "bounded service fence cleanup releases retired resources");
    GPalette.Tables.clear();
}
void AsyncScope()
{
    VulkanRenderDevice device; Screen.Device = &device;
    auto a = CoherentRemap(1, 1), b = CoherentRemap(2, 2); GPalette.Tables[1] = &a;
    FTexture source; FGameTexture game(&source); VkMaterial material(&device, &game, CTF_Indexed);
    FMaterialState state; state.mTranslation = 1; material.GetBindlessIndex(state);
    auto* old = device.Descriptors.Writes[0].View;
    GPalette.Tables[1] = &b; material.GetBindlessIndex(state);
    Check(device.Textures.Workers.empty() && device.Textures.Main.empty(), "public indexed material cannot defer numerical ID re-resolution");
    CheckIndexedBytes(old, source, &a); CheckIndexedBytes(device.Descriptors.Writes[2].View, source, &b);
    FTexture ordinarySource;
    auto* ordinary = static_cast<VkHardwareTexture*>(ordinarySource.GetHardwareTexture(1, 0));
    ordinary->GetImage(&ordinarySource, 1, CTF_Indexed);
    Check(device.Textures.Workers.size() == 1, "unrelated generic async path remains enabled");
    ordinary->Reset(); device.Textures.RunPending();
    Check(device.Textures.Stale == 1 && device.Textures.Completed == 0, "actual deferred main callback rejects reset epoch");
    GPalette.Tables.clear();
}
void UploadLayout(bool original)
{
    VulkanRenderDevice device; Screen.Device = &device;
    VkHardwareTexture owner; owner.fb = &device;
    VkTextureImage image;
    const std::array<uint8_t, 8> first{0, 1, 2, 4, 8, 16, 128, 255}, second{255, 128, 16, 8, 4, 2, 1, 0};
    owner.CreateTexture(&image, 8, 1, 1, VK_FORMAT_R8_UNORM, first.data(), false);
    const int expected = original ? VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL : VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
    Check(image.Layout == expected, "actual no-mipmap creation layout");
    Check(image.Image->Bytes == std::vector<uint8_t>(first.begin(), first.end()), "actual create copy source bytes");
    Check(image.Image->Mips == 1 && image.Image->Format == VK_FORMAT_R8_UNORM, "actual create R8 one mip");
    const std::vector<std::pair<int, bool>> createTransitions = original
        ? std::vector<std::pair<int, bool>>{{VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, true}}
        : std::vector<std::pair<int, bool>>{{VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, true}, {VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL, false}};
    Check(image.Image->Transitions == createTransitions, "create actual transfer then sampled transition order");
    owner.UploadTexture(&image, 8, 1, 1, VK_FORMAT_R8_UNORM, second.data(), false);
    Check(image.Layout == expected && image.Image->Bytes == std::vector<uint8_t>(second.begin(), second.end()), "actual update layout and copy bytes");
    auto allTransitions = createTransitions;
    allTransitions.insert(allTransitions.end(), createTransitions.begin(), createTransitions.end());
    Check(image.Image->Transitions == allTransitions, "update actual transfer then sampled transition order");
    Check(device.Commands.Transfer.Offsets == std::vector<std::size_t>{32, 32} && device.Textures.Finishes == 2, "create/update actual staging offsets and finish calls");
    if (original) std::cout << "preserved original nonmip: create=TRANSFER_DST update=TRANSFER_DST\n";
    image.Reset(&device);
}
int main(int argc, char** argv)
{
    try
    {
        FTexture placeholder; FGameTexture gamePlaceholder(&placeholder); TexMan.Placeholder = &gamePlaceholder;
        InitializeBasePalette();
        const std::string mode = argc > 1 ? argv[1] : "indexed";
        if (mode == "legacy") LegacyMissingLayer();
        else if (mode == "indexed") CurrentIndexed();
        else if (mode == "ordinary") OrdinaryAndPaletteState();
        else if (mode == "swcanvas") SWCanvas();
        else if (mode == "missing") MissingInput();
        else if (mode == "cleanup") CleanupRecreation();
        else if (mode == "owner") ExistingImageOwnerWitness();
        else if (mode == "palette") PaletteUpload();
        else if (mode == "variants") TranslationVariants();
        else if (mode == "policy") DefaultPolicy();
        else if (mode == "alpha-variants") AlphaVariants();
        else if (mode == "sampling") Sampling();
        else if (mode == "style") StyleOrder();
        else if (mode == "retirement") Retirement();
        else if (mode == "async") AsyncScope();
        else if (mode == "layout") UploadLayout(false);
        else if (mode == "legacy-layout") UploadLayout(true);
        else if (mode == "descriptor-layout") { CurrentIndexed(); OrdinaryAndPaletteState(); SWCanvas(); PaletteUpload(); }
        else throw std::runtime_error("unknown fixture mode");
        std::cout << mode << " passed\n";
        return 0;
    }
    catch (const std::exception& error)
    {
        std::cerr << "indexed material fixture FAILED: " << error.what() << '\n';
        return 1;
    }
}
