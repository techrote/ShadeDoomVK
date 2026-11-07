// SPDX-License-Identifier: GPL-3.0-or-later
// Actual descriptor/filter/precache/candidate/Step/Full bodies + real PF-003
// allocator and PF-012 selector. Symbolic images/samplers/writes/fences only;
// no Vulkan device, engine executable, or ZScript VM is instantiated.
#include <algorithm>
#include <climits>
#include <cstdint>
#include <cstdlib>
#include <functional>
#include <iostream>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#ifdef __clang__
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wunused-parameter"
#endif
#include "tarray.h"
#ifdef __clang__
#pragma clang diagnostic pop
#endif
#include "hw_lightprobe.h"
#include "hw_probe_selection.h"
#include "vk_bindless.h"
void* M_Malloc(size_t n) { auto p=std::malloc(n); if(!p)throw std::bad_alloc(); return p; }
void* M_Realloc(void* p,size_t n) { auto q=std::realloc(p,n); if(!q)throw std::bad_alloc(); return q; }
void M_Free(void* p) { std::free(p); }
void* M_Calloc(size_t n,size_t s) { auto p=std::calloc(n,s); if(!p)throw std::bad_alloc(); return p; }
static void require(bool value, const char* reason) { if(!value)throw std::logic_error(reason); }

struct View {
    int Ordinal=-1, Family=-1, ContentOwner=-1;
    static int Alive;
    View(int ordinal,int family):Ordinal(ordinal),Family(family){++Alive;}
    ~View(){--Alive;}
};
int View::Alive=0;
struct Image { std::unique_ptr<View> ViewObject; };
// Production member spelling is View; use an alias to avoid the type/member collision.
using ViewType=View;
struct Texture { std::unique_ptr<ViewType> View; };
struct TextureServices {
    std::vector<Texture> Irradiancemaps, Prefiltermaps;
    View Null{-1,-1}, Brdf{-1,-2}, Palette{-1,-3};
    int Epoch=1, Resets=0;
    View* GetNullTextureView(){return &Null;}
    View* GetBrdfLutTextureView(){return &Brdf;}
    View* GetGamePaletteView(){return &Palette;}
    void Grow(int count) {
        while(Irradiancemaps.size()<static_cast<size_t>(count)) {
            int i=static_cast<int>(Irradiancemaps.size());
            Irradiancemaps.push_back({std::make_unique<View>(i,0)});
        }
        while(Prefiltermaps.size()<static_cast<size_t>(count)) {
            int i=static_cast<int>(Prefiltermaps.size());
            Prefiltermaps.push_back({std::make_unique<View>(i,1)});
        }
    }
    // Symbolic reset service; exact real reset's in-place image ownership is
    // separately source-pinned. This is not GPU clear/submission evidence.
    void ResetLightProbes() {
        ++Epoch; ++Resets;
        for(auto& t:Irradiancemaps)if(t.View)t.View->ContentOwner=-1;
        for(auto& t:Prefiltermaps)if(t.View)t.View->ContentOwner=-1;
    }
};
constexpr int CLAMP_XY_NOMIP=0;
struct SamplerServices {
    std::unique_ptr<int> Hardware=std::make_unique<int>(1);
    std::unique_ptr<int> IrradiancemapSampler=std::make_unique<int>(100);
    std::unique_ptr<int> PrefiltermapSampler=std::make_unique<int>(200);
    std::vector<std::unique_ptr<int>> Retired;
    int Resets=0;
    std::function<void()> BeforeReset;
    int* Get(int){return Hardware.get();}
    void ResetHWSamplers(){
        if(BeforeReset)BeforeReset();
        Retired.push_back(std::move(Hardware));
        Hardware=std::make_unique<int>(++Resets+1);
    }
    void CompleteFence(){Retired.clear();}
};
struct MaterialService;
struct FSWColormap { struct { int bindIndex=-1; } Renderdev; };
class VkDescriptorSetManager;
class VulkanRenderDevice {
public:
    TextureServices Textures;
    SamplerServices Samplers;
    SamplerServices* mSamplerManager=&Samplers;
    VkDescriptorSetManager* mDescriptorSetManager=nullptr;
    TextureServices* GetTextureManager(){return &Textures;}
    SamplerServices* GetSamplerManager(){return &Samplers;}
    VkDescriptorSetManager* GetDescriptorSetManager(){return mDescriptorSetManager;}
    void SetTextureFilterMode();
    void StartPrecaching();
    // SDVK-161 mesh dirty scheduling is qualified by its separate production
    // uploader fixture. This descriptor/probe-only service has no mesh buffers.
    void InvalidateMaterialBindings() {}
    void ResetLightProbes(){Textures.ResetLightProbes();}
    int Passes=0, ActiveContent=0, ActiveCount=0;
    void EndLightProbePass(){
        ++Passes;
        for(int i=0;i<ActiveCount;++i){
            Textures.Irradiancemaps[i].View->ContentOwner=ActiveContent;
            Textures.Prefiltermaps[i].View->ContentOwner=ActiveContent;
        }
    }
};
struct Binding { View* Image; int* Sampler; };
class VkDescriptorSetManager {
public:
    VulkanRenderDevice* fb;
    VkBindlessSlotAllocator Allocator;
    std::vector<int> LightProbes;
    std::vector<MaterialService*> Materials;
    std::vector<FSWColormap*> Colormaps;
    std::map<int,Binding> Published;
    int Writes=0;
    explicit VkDescriptorSetManager(VulkanRenderDevice* owner):fb(owner) {
        Allocator.Configure(VkBindlessLayout::DynamicStart,1024);
        owner->mDescriptorSetManager=this;
    }
    int AllocBindlessSlot(int count){int v=Allocator.Allocate(count);require(v>0,"allocation-exhausted");return v;}
    void FreeBindlessSlot(int index){if(index>0)require(Allocator.Free(index),"invalid-free");}
    void SetBindlessTexture(int index,View* view,int* sampler){
        require(index>=0 && index<Allocator.GetCapacity(),"out-of-range-write");
        Published[index]={view,sampler};++Writes;
    }
    int GetLightProbeTextureIndex(int);
    void ResetHWTextureSets();
    void UpdateFixedTextureDescriptors();
};
struct MaterialService {
    VkDescriptorSetManager& Owner;
    int Index=-1, Span, Deletes=0;
    View Image{900,3};
    MaterialService(VkDescriptorSetManager& owner,int span):Owner(owner),Span(span){}
    void Publish(){
        require(Index==-1,"material-double-publish");
        Index=Owner.AllocBindlessSlot(Span);
        for(int i=0;i<Span;++i)Owner.SetBindlessTexture(Index+i,&Image,Owner.fb->Samplers.Hardware.get());
    }
    void DeleteDescriptors(){++Deletes;if(Index!=-1){Owner.FreeBindlessSlot(Index);Index=-1;}}
};
class LevelMesh {};
struct { LevelMesh* levelMesh=nullptr; TArray<LightProbe> lightProbes; } level;
class VkLightmapper {
public:
    VulkanRenderDevice* fb;
    LevelMesh* mesh;
    struct { HWProbeSelection::Candidate* Entries; int BufferSize; } probeSelection;
    int UploadProbeSelection();
};
static VulkanRenderDevice* screen=nullptr;
#include "sdvk153_producers.cpp"
// Keep the accepted int/TArray size_t comparisons exact, isolate inherited warning only.
#ifdef _MSC_VER
#pragma warning(push)
#pragma warning(disable:4018)
#else
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wsign-compare"
#endif
#include "sdvk153_builder.cpp"
#ifdef _MSC_VER
#pragma warning(pop)
#else
#pragma GCC diagnostic pop
#endif

struct Environment {
    VulkanRenderDevice Device;
    VkDescriptorSetManager Manager{&Device};
    LevelMesh Mesh;
    HWProbeSelection::Candidate Entries[16]{};
    VkLightmapper Mapper{&Device,&Mesh,{Entries,16}};
    Environment(){
        screen=&Device;level.levelMesh=&Mesh;Author(2);Device.Textures.Grow(2);
        Device.Samplers.BeforeReset=[&](){
            for(auto material:Manager.Materials)
                require(material->Index==-1,"sampler-rebuilt-before-consumer-retirement");
            for(auto colormap:Manager.Colormaps)
                require(colormap->Renderdev.bindIndex==-1,"sampler-rebuilt-before-consumer-retirement");
        };
    }
    ~Environment(){level.levelMesh=nullptr;level.lightProbes.Clear();screen=nullptr;}
    void Author(int count){
        Device.ActiveCount=count;
        level.lightProbes.Clear();
        for(int i=0;i<count;++i)level.lightProbes.Push({FVector3(float(i*100),0,0),i});
    }
    uint16_t StoredTexel(int ordinal){
        int count=Mapper.UploadProbeSelection();
        require(count==static_cast<int>(level.lightProbes.size()),"candidate-count");
        return static_cast<uint16_t>(HWProbeSelection::FindClosest(Entries,count,float(ordinal*100),0,0));
    }
    void CheckRaw(uint16_t texel,int ordinal){
        auto token=Manager.Allocator.CurrentIdentity(texel);
        require(token.IsSet() && token.Span==2,"retained-pair-not-live");
        auto& a=Manager.Published.at(texel);auto& b=Manager.Published.at(texel+1);
        require(a.Image->Family==0 && b.Image->Family==1,"retained-probe-mapped-to-material");
        require(a.Image->Ordinal==ordinal && b.Image->Ordinal==ordinal,"retained-probemap-texel-rebound-to-other-owner");
        require(a.Sampler==Device.Samplers.IrradiancemapSampler.get() &&
                b.Sampler==Device.Samplers.PrefiltermapSampler.get(),"probe-sampler-owner-changed");
    }
    void CheckFixed(){
        for(int i=0;i<3;++i)require(Manager.Published.at(i).Sampler==Device.Samplers.Hardware.get(),
                                  "fixed-descriptor-retired-hw-sampler");
    }
};

static void resetCase(const std::string& mode){
    Environment e;
    const uint16_t texel=e.StoredTexel(0), texel1=e.StoredTexel(1);
    auto& m=e.Manager;auto& d=e.Device;
    auto token=m.Allocator.CurrentIdentity(texel),token1=m.Allocator.CurrentIdentity(texel1);
    const int epoch=d.Textures.Epoch;
    if(mode=="no-reset"){
        e.CheckRaw(texel,0);require(m.GetLightProbeTextureIndex(0)==texel,"unchanged-owner-moved");return;
    }
    if(mode=="precache")d.StartPrecaching();else d.SetTextureFilterMode();
    if(mode=="fixed-samplers") {e.CheckFixed();return;}
    if(mode=="material-pressure"){
        MaterialService a(m,2),b(m,2);a.Publish();b.Publish();
        e.CheckRaw(texel,0);e.CheckRaw(texel1,1);
        a.DeleteDescriptors();b.DeleteDescriptors();
    }else{
        if(mode=="reverse-lookup") {m.GetLightProbeTextureIndex(1);m.GetLightProbeTextureIndex(0);}
        else{m.GetLightProbeTextureIndex(0);m.GetLightProbeTextureIndex(1);}
        std::cout<<"retained_texel="<<texel<<" fresh_ordinal0="<<m.GetLightProbeTextureIndex(0)
                 <<" fresh_ordinal1="<<m.GetLightProbeTextureIndex(1)
                 <<" retained_owner="<<m.Published.at(texel).Image->Ordinal<<'\n';
        e.CheckRaw(texel,0);e.CheckRaw(texel1,1);
    }
    require(m.Allocator.ValidateIdentity(token) && m.Allocator.ValidateIdentity(token1),"probe-pair-token-retired");
    require(d.Textures.Epoch==epoch && d.Textures.Resets==0,"unrelated-reset-cleared-probe-content");
    e.CheckFixed();
    d.Samplers.CompleteFence(); // no stale symbolic retired sampler is dereferenced
    e.CheckFixed();e.CheckRaw(texel,0);
}

static void materialRetirement(){
    Environment e;auto& m=e.Manager;
    auto texel=e.StoredTexel(0);auto probeToken=m.Allocator.CurrentIdentity(texel);
    MaterialService a(m,2),b(m,5);a.Publish();b.Publish();
    auto at=m.Allocator.CurrentIdentity(a.Index),bt=m.Allocator.CurrentIdentity(b.Index);
    m.Materials={&a,&b};
    FSWColormap color;color.Renderdev.bindIndex=m.AllocBindlessSlot(1);m.Colormaps.push_back(&color);
    auto ct=m.Allocator.CurrentIdentity(color.Renderdev.bindIndex);
    e.Device.SetTextureFilterMode();
    require(a.Deletes==1 && b.Deletes==1 && a.Index==-1 && b.Index==-1,"material-cache-not-retired");
    require(!m.Allocator.ValidateIdentity(at) && !m.Allocator.ValidateIdentity(bt) &&
            !m.Allocator.ValidateIdentity(ct),"material-token-still-live");
    require(color.Renderdev.bindIndex==-1 && m.Colormaps.empty(),"colormap-cache-not-retired");
    a.Publish();b.Publish();e.CheckRaw(texel,0);e.CheckFixed();
    require(m.Allocator.ValidateIdentity(probeToken),"probe-retired-with-materials");
    for(int i=0;i<b.Span;++i)require(m.Published.at(b.Index+i).Sampler==e.Device.Samplers.Hardware.get(),"material-rebind-stale-sampler");
    a.DeleteDescriptors();b.DeleteDescriptors();m.Materials.clear();
}

static void admission(const std::string& mode){
    Environment e;auto& m=e.Manager;
    if(mode=="bounded-ordinal"){
        auto before=m.LightProbes.size();
        require(m.GetLightProbeTextureIndex(512)==0,"out-of-range-not-fallback");
        require(m.LightProbes.size()==before,"out-of-range-grew-persistent-cache");
        return;
    }
    require(m.GetLightProbeTextureIndex(-1)==0 && m.GetLightProbeTextureIndex(INT_MAX)==0,"invalid-ordinal-not-fallback");
    e.Device.Textures.Prefiltermaps[1].View.reset();
    require(m.GetLightProbeTextureIndex(1)==0 && m.LightProbes.empty(),"half-pair-grew-cache");
    int zero=m.GetLightProbeTextureIndex(0);require(zero>0,"authored-zero-conflated-with-runtime-zero");
    e.CheckRaw(static_cast<uint16_t>(zero),0);
    require(m.Allocator.GetStats().CurrentDescriptors==2,"invalid-ordinal-allocation");
    require(m.GetLightProbeTextureIndex(1)==0 && m.LightProbes.size()==1,"half-pair-cache-growth");
    e.Device.Textures.Prefiltermaps[1].View=std::make_unique<View>(1,1);
    require(m.GetLightProbeTextureIndex(1)>0 && m.LightProbes.size()==2,"late-pair-not-published");
}

static void exhaustion(){
    Environment e;auto& m=e.Manager;
    m.Allocator.Configure(VkBindlessLayout::DynamicStart,VkBindlessLayout::DynamicStart+4);
    auto zero=e.StoredTexel(0),one=e.StoredTexel(1);
    auto zt=m.Allocator.CurrentIdentity(zero),ot=m.Allocator.CurrentIdentity(one);
    e.Device.Textures.Grow(3);
    const auto writes=m.Writes;
    bool rejected=false;
    try { m.GetLightProbeTextureIndex(2); }
    catch(const std::logic_error& error) { rejected=std::string(error.what())=="allocation-exhausted"; }
    require(rejected,"exhaustion-not-rejected");
    require(m.Writes==writes,"exhaustion-published-partial-pair");
    require(m.LightProbes[2]==-1,"exhaustion-published-cache-entry");
    require(m.Allocator.ValidateIdentity(zt) && m.Allocator.ValidateIdentity(ot),"exhaustion-flushed-probe-owners");
    e.Device.SetTextureFilterMode();e.Device.StartPrecaching();
    e.CheckRaw(zero,0);e.CheckRaw(one,1);
    require(m.Allocator.GetStats().CurrentDescriptors==4,"exhaustion-changed-live-count");
}

static void stress(){
    Environment e;auto& m=e.Manager;auto& d=e.Device;
    LightProbeIncrementalBuilder builder;
    std::vector<FRendererResourceIdentity> tokens;
    std::vector<int> starts;
    int resets=0, publications=0;
    const int counts[]={2,8,0,3,8,1};
    for(int cycle=0;cycle<128;++cycle){
        int count=counts[cycle%6];e.Author(count);d.Textures.Grow(count);d.ActiveContent=cycle;
        auto step=builder.Step(level.lightProbes,static_cast<uint64_t>(cycle+1),{});
        require(step.Event==LightProbeBuilderEvent::OwnerReset,"missing-owner-reset");++resets;
        for(auto& t:d.Textures.Irradiancemaps)require(t.View->ContentOwner==-1,"old-content-survived-owner-reset");
        int captured=0;
        auto render=[&](int i,const LightProbe& p){require(i==p.index,"wrong-probe-ordinal");++captured;};
        for(int call=0;call<64;++call){
            auto state=builder.Step(level.lightProbes,static_cast<uint64_t>(cycle+1),render);
            if(state.Event==LightProbeBuilderEvent::PassPublished)++publications;
        }
        require(captured==(count?count*5:0),"owner-bake-count");
        for(size_t i=0;i<d.Textures.Irradiancemaps.size();++i)
            require(d.Textures.Irradiancemaps[i].View->ContentOwner==(i<static_cast<size_t>(count)?cycle:-1),
                    "inactive-probe-content-not-neutral");
        for(int ordinal=count-1;ordinal>=0;--ordinal){
            int start=m.GetLightProbeTextureIndex(ordinal);require(start>0,"missing-published-pair");
            if(starts.size()<=static_cast<size_t>(ordinal)){starts.resize(ordinal+1,-1);tokens.resize(ordinal+1);}
            if(starts[ordinal]==-1){starts[ordinal]=start;tokens[ordinal]=m.Allocator.CurrentIdentity(start);}
            else require(starts[ordinal]==start && m.Allocator.ValidateIdentity(tokens[ordinal]),"same-view-pair-identity-changed");
        }
        MaterialService a(m,2),b(m,7);a.Publish();b.Publish();m.Materials={&a,&b};
        d.SetTextureFilterMode(); // both live filter and anisotropy CVars use this exact route
        d.StartPrecaching();
        for(int i=0;i<static_cast<int>(starts.size());++i)if(starts[i]!=-1){
            e.CheckRaw(static_cast<uint16_t>(starts[i]),i);
            require(m.Allocator.ValidateIdentity(tokens[i]),"persistent-pair-generation-changed");
        }
        a.Publish();b.Publish();a.DeleteDescriptors();b.DeleteDescriptors();m.Materials.clear();
        e.CheckFixed();d.Samplers.CompleteFence();
        require(m.Allocator.GetStats().CurrentDescriptors==static_cast<int>(d.Textures.Irradiancemaps.size())*2,
                "unexpected-descriptor-accumulation");
        require(m.Allocator.GetStats().HighWaterDescriptors<=25,"unbounded-descriptor-high-water");
    }
    require(m.LightProbes.size()==8 && m.Allocator.GetStats().CurrentDescriptors==16,"wrong-final-resource-bound");
    std::cout<<"cycles=128 max_probe_pairs=8 live_descriptors="<<m.Allocator.GetStats().CurrentDescriptors
             <<" high_water_descriptors="<<m.Allocator.GetStats().HighWaterDescriptors
             <<" owner_resets="<<resets<<" publications="<<publications
             <<" filter_resets="<<d.Samplers.Resets<<" sampler_retirement_backlog="<<d.Samplers.Retired.size()<<'\n';
}

int main(int argc,char** argv){
    if(argc!=2)return 2;
    try{
        std::string mode=argv[1];
        if(mode=="material-retirement")materialRetirement();
        else if(mode=="admission" || mode=="bounded-ordinal")admission(mode);
        else if(mode=="stress")stress();
        else if(mode=="exhaustion")exhaustion();
        else if(mode=="no-reset" || mode=="filter" || mode=="anisotropy" || mode=="precache" ||
                mode=="reverse-lookup" || mode=="material-pressure" || mode=="fixed-samplers")resetCase(mode);
        else throw std::logic_error("unknown-case");
        require(View::Alive==0,"symbolic-owner-leak-at-teardown");
        std::cout<<"PASS "<<mode<<'\n';return 0;
    }catch(const std::exception& e){std::cerr<<"REJECT "<<e.what()<<'\n';return 11;}
}
