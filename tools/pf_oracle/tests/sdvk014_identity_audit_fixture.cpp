// SPDX-License-Identifier: GPL-3.0-or-later
// Source-owned CPU audit. Real packer/allocator/selection and extracted producer
// bodies; only Vulkan objects, writes, samplers and material services are sinks.
// Exit 11 means the claimed clean invariant FAILS. Python tests retain that
// counterexample deliberately; an exit-0 test suite is NOT renderer acceptance.
#include <algorithm>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <functional>
#include <iostream>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
// The inherited unused ENoInit parameter is outside this fixture's source.
// Keep strict diagnostics for every extracted producer and audit assertion.
#ifdef __clang__
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wunused-parameter"
#endif
#include "tarray.h"
#ifdef __clang__
#pragma clang diagnostic pop
#endif
#include "engineerrors.h"
#include "hw_lightmaptile.h"
#include "hw_probe_selection.h"
#include "vk_bindless.h"
void* M_Malloc(size_t n) { auto p=std::malloc(n); if(!p)throw std::bad_alloc(); return p; }
void* M_Realloc(void* p,size_t n) { auto q=std::realloc(p,n); if(!q)throw std::bad_alloc(); return q; }
void M_Free(void* p) { std::free(p); }
void* M_Calloc(size_t n,size_t s) { auto p=std::calloc(n,s); if(!p)throw std::bad_alloc(); return p; }
[[noreturn]] void I_FatalError(const char* fmt, ...) {
    char message[512]; va_list args; va_start(args,fmt);
    std::vsnprintf(message,sizeof(message),fmt,args); va_end(args);
    throw std::runtime_error(message);
}
static void require(bool ok,const char* reason) { if(!ok)throw std::logic_error(reason); }
#include "audit_bounds.cpp"
#include "audit_rectpacker.cpp"

struct View { int Owner; int Family; };
using ViewObject = View;
struct Image { std::unique_ptr<ViewObject> View; }; // explicit symbolic view identity only
struct TextureServices {
    std::vector<Image> Irradiancemaps, Prefiltermaps;
    View Null{-1,0}, Brdf{-1,1}, Palette{-1,2};
    View* GetNullTextureView() { return &Null; }
    View* GetBrdfLutTextureView() { return &Brdf; }
    View* GetGamePaletteView() { return &Palette; }
};
constexpr int CLAMP_XY_NOMIP=0;
struct SamplerServices {
    std::unique_ptr<int> IrradiancemapSampler=std::make_unique<int>(1);
    std::unique_ptr<int> PrefiltermapSampler=std::make_unique<int>(2);
    int Hardware=0, Resets=0;
    int* Get(int) { return &Hardware; }
    void ResetHWSamplers() { ++Resets; }
};
struct MaterialService { void DeleteDescriptors() {} };
struct FSWColormap { struct { int bindIndex=-1; } Renderdev; };
class VkDescriptorSetManager;
class VulkanRenderDevice {
public:
    TextureServices Textures;
    SamplerServices Samplers;
    SamplerServices* mSamplerManager=&Samplers;
    VkDescriptorSetManager* mDescriptorSetManager=nullptr;
    TextureServices* GetTextureManager() { return &Textures; }
    SamplerServices* GetSamplerManager() { return &Samplers; }
    VkDescriptorSetManager* GetDescriptorSetManager() { return mDescriptorSetManager; }
    void SetTextureFilterMode();
};
class VkDescriptorSetManager {
public:
    VulkanRenderDevice* fb;
    VkBindlessSlotAllocator Allocator;
    std::vector<int> LightProbes;
    std::vector<MaterialService*> Materials;
    std::vector<FSWColormap*> Colormaps;
    std::map<int,View*> Published;
    explicit VkDescriptorSetManager(VulkanRenderDevice* owner):fb(owner) {
        Allocator.Configure(VkBindlessLayout::DynamicStart,1024);
    }
    int AllocBindlessSlot(int count) {
        int value=Allocator.Allocate(count); require(value>0,"allocation-exhausted"); return value;
    }
    void FreeBindlessSlot(int index) {
        if(index>0)require(Allocator.Free(index),"invalid-free");
    }
    void SetBindlessTexture(int index,View* view,int*) {
        require(index>=0 && index<Allocator.GetCapacity(),"out-of-range-publication");
        Published[index]=view; // pending writes treated as submitted at this CPU boundary
    }
    int GetLightProbeTextureIndex(int);
    void ResetHWTextureSets();
};
struct LightProbe { FVector3 position; int index; };
struct LevelMesh {};
struct { LevelMesh* levelMesh=nullptr; TArray<LightProbe> lightProbes; } level;
class VkLightmapper {
public:
    VulkanRenderDevice* fb;
    LevelMesh* mesh;
    struct { HWProbeSelection::Candidate* Entries; int BufferSize; } probeSelection;
    int UploadProbeSelection();
};
#include "audit_producer_methods.cpp"

static LightmapTile tileFor(RectPackerItem* item,int binding) {
    LightmapTile tile; tile.UseCount=1; tile.Binding.TypeIndex=binding;
    tile.AtlasLocation={item->X,item->Y,item->Width,item->Height,item->PageIndex,item};
    return tile;
}
static void atlas(const std::string& mode) {
    RectPacker packer(16,16,0);
    auto old=tileFor(packer.Alloc(16,16),100);
    require(old.HasValidAtlasRegion(16,1),"live-region-control-failed");
    if(mode=="atlas-live-control")return;
    if(mode=="atlas-coordinate-negative") {
        old.AtlasLocation.X=1;
        require(!old.HasValidAtlasRegion(16,1),"bad-coordinate-not-rejected"); return;
    }
    if(mode=="atlas-clear-reuse")packer.Clear();
    else { require(mode=="atlas-free-reuse","unknown-atlas-case"); packer.Free(old.AtlasLocation.Item); }
    auto replacement=tileFor(packer.Alloc(16,16),200);
    require(old.AtlasLocation.Item==replacement.AtlasLocation.Item,"same-address-precondition");
    require(replacement.HasValidAtlasRegion(16,1),"replacement-region-invalid");
    std::cout << "old_binding=100 new_binding=200 same_item=1 same_region=1 old_guard="
              << old.HasValidAtlasRegion(16,1) << '\n';
    require(!old.HasValidAtlasRegion(16,1),"stale-atlas-receipt-accepted");
}
static void descriptor(const std::string& mode) {
    VulkanRenderDevice fb; VkDescriptorSetManager manager(&fb); fb.mDescriptorSetManager=&manager;
    for(int ordinal=0;ordinal<2;++ordinal) {
        fb.Textures.Irradiancemaps.push_back({std::make_unique<View>(View{ordinal,0})});
        fb.Textures.Prefiltermaps.push_back({std::make_unique<View>(View{ordinal,1})});
    }
    LevelMesh mesh; level.levelMesh=&mesh;
    level.lightProbes.Push({FVector3(0,0,0),0});
    level.lightProbes.Push({FVector3(100,0,0),1});
    HWProbeSelection::Candidate entries[2];
    VkLightmapper mapper{&fb,&mesh,{entries,2}};
    require(mapper.UploadProbeSelection()==2,"missing-producer-candidates");
    const uint16_t texel=static_cast<uint16_t>(HWProbeSelection::FindClosest(entries,2,0,0,0));
    const auto identity=manager.Allocator.CurrentIdentity(texel);
    require(texel==259 && manager.Published.at(texel)->Owner==0,"initial-published-owner");
    if(mode=="probe-no-reset-control") {
        require(manager.GetLightProbeTextureIndex(0)==texel && manager.Allocator.ValidateIdentity(identity),
                "unchanged-owner-unstable"); return;
    }
    fb.SetTextureFilterMode(); // EXACT production owner call and descriptor reset
    require(fb.Samplers.Resets==1,"missing-sampler-reset");
    if(mode=="probe-filter-reset") {
        require(!manager.Allocator.ValidateIdentity(identity),"retained-token-not-stale");
    }
    const int new0=manager.GetLightProbeTextureIndex(0);
    const int new1=manager.GetLightProbeTextureIndex(1);
    require(manager.Published.at(new0)->Owner==0 && manager.Published.at(new1)->Owner==1,
            "new-pair-publication-wrong");
    const auto now=manager.Allocator.CurrentIdentity(texel);
    require(now.IsSet() && now.Span==2 && manager.Published.at(texel)->Family==0 &&
            manager.Published.at(texel+1)->Family==1,"stale-but-plausible-pair-precondition");
    std::cout << "retained_texel=" << texel << " fresh_ordinal0=" << new0
              << " fresh_ordinal1=" << new1 << " retained_texel_owner="
              << manager.Published.at(texel)->Owner << " live_span=" << now.Span << '\n';
    require(manager.Published.at(texel)->Owner==0,"retained-probemap-texel-rebound-to-other-owner");
}
static void pageControl() {
    auto plan=VkPlanLightmapDescriptorPublication(128,1,1024);
    require(plan.IsValid() && plan.WritePages==128 && plan.NextPublishedPages==1 &&
            plan.EndDescriptor==259,"removed-page-publication-plan");
    for(int i=0;i<128;++i)require(plan.UsesFallback(i)==(i>0),"removed-page-fallback-hole");
    require(!VkPlanLightmapDescriptorPublication(128,129,1024).IsValid(),"page-limit-not-checked");
    FRendererEpoch epoch; auto old=epoch.Snapshot(); epoch.Invalidate();
    require(!epoch.Validate(old) && epoch.Validate(epoch.Snapshot()),"epoch-stale-acceptance");
}
int main(int argc,char** argv) {
    if(argc!=2)return 2;
    try {
        std::string mode=argv[1];
        if(mode.rfind("atlas-",0)==0)atlas(mode);
        else if(mode=="reserved-page-control")pageControl();
        else {
            require(mode=="probe-no-reset-control" || mode=="probe-filter-reset" ||
                    mode=="probe-preserve-control","unknown-probe-case");
            descriptor(mode);
        }
        std::cout << "PASS " << mode << '\n'; return 0;
    } catch(const std::logic_error& error) {
        std::cerr << "BLOCKED " << error.what() << '\n'; return 11;
    } catch(const std::exception& error) {
        std::cerr << "UNEXPECTED " << error.what() << '\n'; return 12;
    }
}
