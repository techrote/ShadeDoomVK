// SPDX-License-Identifier: GPL-3.0-or-later
// Production reset, dirty scheduler, range/allocation lifecycle and uploader.
// Vulkan images/samplers/material lookup and command execution are explicit CPU
// services; no renderer/device/native rendering evidence is created here.
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>
#ifdef __clang__
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wunused-parameter"
#endif
#include "tarray.h"
#ifdef __clang__
#pragma clang diagnostic pop
#endif
#include "vectors.h"
#include "hw_levelmesh_contract.h"
#include "vk_bindless.h"
void* M_Malloc(size_t n) { auto p=std::malloc(n); if(!p)throw std::bad_alloc(); return p; }
void* M_Realloc(void* p,size_t n) { auto q=std::realloc(p,n); if(!q)throw std::bad_alloc(); return q; }
void M_Free(void* p) { std::free(p); }
void* M_Calloc(size_t n,size_t s) { auto p=std::calloc(n,s); if(!p)throw std::bad_alloc(); return p; }
static void require(bool condition,const char* reason) { if(!condition)throw std::logic_error(reason); }
template<class... T> [[noreturn]] void I_FatalError(const char* message,T...) { throw std::logic_error(message); }
#include "material_reset_declarations.inc"
struct FGameTexture;
class FMaterial {
public:
    FGameTexture* Texture=nullptr;
    bool Alive=true;
    FGameTexture* Source(){require(Alive,"retired-uniform-hole-uploaded");return Texture;}
    static FMaterial* ValidateTexture(FGameTexture*,int);
};
struct FGameTexture {
    FMaterial* Material=nullptr;
    float GetGlossiness() const{return 0.375f;}
    float GetSpecularLevel() const{return 0.625f;}
    float GetDepthFadeThreshold() const{return 0.125f;}
};
FMaterial* FMaterial::ValidateTexture(FGameTexture* texture,int){return texture->Material;}
struct FMaterialState { FMaterial* mMaterial=nullptr; int mClampMode=0,mTranslation=0; };
// CPU source fields consumed by the unmodified surface serializer.
struct LevelMeshSurface {
    FVector4 Plane{0,0,1,0};
    uint32_t PortalIndex=0;
    float IsSky=0,Alpha=1;
    FGameTexture* Texture=nullptr;
    struct { int Pos=0,Count=0; } LightList;
};
class LevelMesh {
public:
    struct { TArray<LevelMeshSurface> Surfaces; TArray<SurfaceUniforms> Uniforms;
             TArray<FMaterialState> Materials; TArray<int> LightUniforms; } Mesh;
    struct { MeshBufferAllocator Uniforms,Surface; } FreeLists;
    struct { MeshBufferUploads Vertex,Index,Node,SurfaceIndex,Surface,UniformIndexes,
             Uniforms,LightUniforms,Portals,Light,LightIndex,DynLight; } UploadRanges;
    LevelMeshMutationEpochs Mutations;
    FRendererEpoch Epoch;
    void MarkMutation(LevelMeshMutationDomain domain){Mutations.Mark(domain);}
    void InvalidateMaterialBindings();
    UniformsAllocInfo AllocUniforms(int);
    SurfaceAllocInfo AllocSurface(int=1);
    void FreeUniforms(int,int);
    void FreeSurface(unsigned int,int=1);
};
struct FSWColormap { struct { int bindIndex=-1; } Renderdev; };
class VkDescriptorSetManager;
class VkMaterial;
struct Samplers {
    int Generation=1;
    void ResetHWSamplers(){++Generation;}
};
class VulkanRenderDevice {
public:
    Samplers Sampler;
    Samplers* mSamplerManager=&Sampler;
    VkDescriptorSetManager* mDescriptorSetManager=nullptr;
    LevelMesh* levelMesh=nullptr;
    // Deliberately lagged/dead mirror sentinel for the wrong-owner mutant.
    LevelMesh* mirrorMesh=nullptr;
    void SetTextureFilterMode();
    void StartPrecaching();
    void InvalidateMaterialBindings();
    int GetBindlessTextureIndex(FMaterial*,int,int,bool);
    int GetBindlessHeightLayerIndex(FMaterial*,int,int,bool);
    VkDescriptorSetManager* GetDescriptorSetManager(){return mDescriptorSetManager;}
};
struct Binding {
    VkMaterial* Owner=nullptr;
    int Clamp=0,Translation=0,Sampler=0,Height=-1;
};
class VkDescriptorSetManager {
public:
    VulkanRenderDevice* fb;
    VkBindlessSlotAllocator Allocator;
    std::vector<VkMaterial*> Materials;
    std::vector<FSWColormap*> Colormaps;
    std::map<int,Binding> Bindings;
    int Lookups=0,FixedPublications=0;
    explicit VkDescriptorSetManager(VulkanRenderDevice* device):fb(device){
        fb->mDescriptorSetManager=this;Allocator.Configure(VkBindlessLayout::DynamicStart,4096);
    }
    void ResetHWTextureSets();
    void UpdateFixedTextureDescriptors(){++FixedPublications;}
    void FreeBindlessSlot(int index){require(Allocator.Free(index),"invalid-descriptor-free");Bindings.erase(index);}
};
struct Palette { void Reset(VulkanRenderDevice*){} };
class VkMaterial : public FMaterial {
public:
    struct Set { int bindlessIndex; int Clamp,Translation; std::unique_ptr<Palette> IndexedPalette; };
    std::vector<Set> mDescriptorSets;
    VulkanRenderDevice* fb;
    int Span,Height;
    FGameTexture SourceTexture;
    VkMaterial(VulkanRenderDevice* device,int span,int height):fb(device),Span(span),Height(height){
        Texture=&SourceTexture;SourceTexture.Material=this;device->mDescriptorSetManager->Materials.push_back(this);
    }
    void DeleteDescriptors();
    int Lookup(int clamp,int translation){
        auto& manager=*fb->mDescriptorSetManager;++manager.Lookups;
        for(const auto& set:mDescriptorSets)if(set.Clamp==clamp&&set.Translation==translation)return set.bindlessIndex;
        int index=manager.Allocator.Allocate(Span);require(index>0,"descriptor-capacity-exhausted");
        mDescriptorSets.push_back({index,clamp,translation,{}});
        manager.Bindings[index]={this,clamp,translation,fb->Sampler.Generation,Height};return index;
    }
};
int VulkanRenderDevice::GetBindlessTextureIndex(FMaterial* material,int clamp,int translation,bool){
    require(material->Alive,"retired-uniform-hole-uploaded");
    return static_cast<VkMaterial*>(material)->Lookup(clamp,translation);
}
int VulkanRenderDevice::GetBindlessHeightLayerIndex(FMaterial* material,int clamp,int translation,bool){
    auto* vk=static_cast<VkMaterial*>(material);vk->Lookup(clamp,translation);return vk->Height;
}
constexpr int CLAMP_NONE=0;
struct VulkanBuffer {
    size_t size=0;
    uint64_t diagnosticId=0;
    std::vector<uint8_t> Bytes;
    explicit VulkanBuffer(size_t count):size(count),Bytes(count,0){}
    void Unmap(){}
};
namespace CfxTrace { inline void Upload(uint64_t,uint64_t,size_t,size_t,const void*,size_t){} }
struct VkLevelMesh {
    LevelMesh* Mesh;
    VulkanRenderDevice* fb;
    bool useRayQuery=true;
    std::unique_ptr<VulkanBuffer> SurfaceBuffer,UniformsBuffer;
};
// Unaffected ranges stay empty: these stand-ins exist solely to compile the
// production transfer-size expression; no geometry/node/light bytes are tested.
struct CollisionNodeBufferHeader {};
struct CollisionNode {};
struct FFlatVertex {};
struct SurfaceLightUniforms {};
struct PortalInfo {};
struct LightInfo {};
class VkLevelMeshUploader {
public:
    VkLevelMesh* Mesh;
    uint8_t* data=nullptr;
    size_t datapos=0,datasize=0;
    std::unique_ptr<VulkanBuffer> transferBuffer;
    struct Copy { VulkanBuffer* Src; VulkanBuffer* Dst; size_t SrcOffset,DstOffset,Size;
        Copy(VulkanBuffer* s,VulkanBuffer* d,size_t so,size_t dso,size_t n):Src(s),Dst(d),SrcOffset(so),DstOffset(dso),Size(n){} };
    std::vector<Copy> copyCommands;
    void UploadSurfaces();void UploadUniforms();void ClearRanges();size_t GetTransferSize();
    void* GetUploadPtr(size_t);void UploadData(VulkanBuffer*,size_t,const void*,size_t,const char*);
    void EndTransfer(size_t);
    size_t RunCpuTransfer(){
        size_t count=GetTransferSize();
        transferBuffer=std::make_unique<VulkanBuffer>(count);data=transferBuffer->Bytes.data();datasize=count;datapos=0;
        UploadSurfaces();UploadUniforms();EndTransfer(count);
        for(const auto& copy:copyCommands)
            std::memcpy(copy.Dst->Bytes.data()+copy.DstOffset,copy.Src->Bytes.data()+copy.SrcOffset,copy.Size);
        copyCommands.clear();ClearRanges();return count;
    }
};
#include "material_reset_production.inc"

struct Environment {
    VulkanRenderDevice Device;
    VkDescriptorSetManager Manager{&Device};
    LevelMesh Mesh;
    VkMaterial Rich{&Device,9,8},Plain{&Device,4,-1};
    FMaterial Retired;
    VkLevelMesh Mirror{&Mesh,&Device,true,{},{}};
    VkLevelMeshUploader Uploader{&Mirror,nullptr,0,0,{},{}};
    std::vector<int> Slots;
    std::vector<int> Surfaces;
    int ProbeIndex;
    FRendererResourceIdentity ProbeToken;
    Environment(){
        Device.levelMesh=&Mesh;Device.mirrorMesh=&Mesh;
        // A stable live probe pair shares the real allocator with material spans.
        ProbeIndex=Manager.Allocator.Allocate(2);ProbeToken=Manager.Allocator.CurrentIdentity(ProbeIndex);
        for(int i=0;i<4;++i){
            auto u=Mesh.AllocUniforms(1);Slots.push_back(u.Start);
            auto s=Mesh.AllocSurface();Surfaces.push_back(s.Index);
            auto* material=i%2?&Plain:&Rich;
            Mesh.Mesh.Materials[u.Start]={material,i%2?7:0,i%2?3:0};
            Mesh.Mesh.Uniforms[u.Start]={};Mesh.Mesh.Uniforms[u.Start].uFogDensity=17.5f+static_cast<float>(i);
            Mesh.Mesh.Surfaces[s.Index].Texture=material->Texture;
        }
        // A null-material live entry exercises the existing zero/-1 fallback.
        auto u=Mesh.AllocUniforms(1);Slots.push_back(u.Start);Mesh.Mesh.Uniforms[u.Start]={};
        auto s=Mesh.AllocSurface();Surfaces.push_back(s.Index);
        Mirror.SurfaceBuffer=std::make_unique<VulkanBuffer>(Mesh.Mesh.Surfaces.Size()*sizeof(SurfaceInfo));
        Mirror.UniformsBuffer=std::make_unique<VulkanBuffer>(Mesh.Mesh.Uniforms.Size()*sizeof(SurfaceUniforms));
        Mesh.UploadRanges.LightUniforms.Clear(); // unrelated allocation upload is outside this fixture
        Uploader.RunCpuTransfer();Check();
    }
    SurfaceInfo Trace(int index) const{
        SurfaceInfo value;std::memcpy(&value,Mirror.SurfaceBuffer->Bytes.data()+index*sizeof(value),sizeof(value));return value;
    }
    void Check(){
        for(size_t i=0;i<Slots.size();++i){
            int slot=Slots[i],surface=Surfaces[i];if(slot<0)continue;
            const auto& uniforms=Mesh.Mesh.Uniforms[slot];auto& state=Mesh.Mesh.Materials[slot];
            if(state.mMaterial){
                auto entry=Manager.Bindings.find(uniforms.uTextureIndex);
                require(entry!=Manager.Bindings.end()&&entry->second.Owner==state.mMaterial&&
                        entry->second.Clamp==state.mClampMode&&entry->second.Translation==state.mTranslation&&
                        entry->second.Sampler==Device.Sampler.Generation,"raster-material-index-stale");
                require(uniforms.uHeightTextureIndex==entry->second.Height,"height-semantic-not-refreshed");
                require(uniforms.uFogDensity==17.5f+static_cast<float>(i),"unrelated-uniform-changed");
                SurfaceUniforms uploaded;
                std::memcpy(&uploaded,Mirror.UniformsBuffer->Bytes.data()+slot*sizeof(uploaded),sizeof(uploaded));
                require(std::memcmp(&uploaded,&uniforms,sizeof(uploaded))==0,"raster-transfer-bytes-stale");
                auto trace=Manager.Bindings.find(Trace(surface).TextureIndex);
                require(trace!=Manager.Bindings.end()&&trace->second.Owner==state.mMaterial&&
                        trace->second.Clamp==CLAMP_NONE&&trace->second.Translation==0&&
                        trace->second.Sampler==Device.Sampler.Generation,"tracer-material-index-stale");
            }else{
                require(uniforms.uTextureIndex==0&&uniforms.uHeightTextureIndex==-1&&Trace(surface).TextureIndex==0,
                        "null-material-fallback-changed");
            }
        }
        require(Manager.Allocator.ValidateIdentity(ProbeToken),"probe-pair-retired");
    }
    void Reset(bool precache=false){
        int before=Manager.Lookups;
        if(precache)Device.StartPrecaching();else Device.SetTextureFilterMode();
        require(before==Manager.Lookups,"reset-created-descriptors-before-new-samplers");
    }
    void Refresh(){
        size_t expected=0;
        for(const auto& range:Mesh.UploadRanges.Uniforms.GetRanges())expected+=range.Count()*sizeof(SurfaceUniforms);
        for(const auto& range:Mesh.UploadRanges.Surface.GetRanges())expected+=range.Count()*sizeof(SurfaceInfo);
        require(Uploader.RunCpuTransfer()==expected,"material-transfer-size-mismatch");Check();
        require(Uploader.GetTransferSize()==0,"dirty-ranges-not-consumed");
    }
};
static void run(const std::string& scenario){
    Environment e;
    if(scenario=="no-reset"){e.Check();return;}
    if(scenario=="no-owner"){
        e.Device.levelMesh=nullptr;e.Reset();
        require(e.Uploader.GetTransferSize()==0,"null-owner-marked-mirror");return;
    }
    if(scenario=="owner"){
        LevelMesh next;
        auto u=next.AllocUniforms(1);(void)u;auto s=next.AllocSurface();(void)s;
        next.UploadRanges.Uniforms.Clear();next.UploadRanges.Surface.Clear();next.UploadRanges.LightUniforms.Clear();
        e.Device.levelMesh=&next;e.Reset();
        require(next.UploadRanges.Uniforms.GetRanges().Size()==1&&next.UploadRanges.Surface.GetRanges().Size()==1&&
                e.Uploader.GetTransferSize()==0,"wrong-mesh-owner-dirtied");return;
    }
    if(scenario=="holes"){
        // Retired middle spans retain a poison old material pointer. An unused
        // geometric-growth tail also stays outside the scheduled live ranges.
        int slot=e.Slots[1],surface=e.Surfaces[1];
        e.Mesh.FreeUniforms(slot,1);e.Mesh.FreeSurface(surface);
        e.Retired.Alive=false;e.Mesh.Mesh.Materials[slot].mMaterial=&e.Retired;
        e.Mesh.Mesh.Surfaces[surface].Texture=nullptr;e.Slots[1]=-1;
    }
    int cycles=scenario=="repeat"?128:1;
    auto mutations=e.Mesh.Mutations.Snapshot();auto epoch=e.Mesh.Epoch.Snapshot();
    int highwater=0,addressExtent=0;
    for(int i=0;i<cycles;++i){
        std::vector<FRendererResourceIdentity> old;
        for(int slot:e.Slots)if(slot>=0&&e.Mesh.Mesh.Materials[slot].mMaterial)
            old.push_back(e.Manager.Allocator.CurrentIdentity(e.Mesh.Mesh.Uniforms[slot].uTextureIndex));
        e.Reset(scenario=="precache"||(scenario=="repeat"&&i%3==2));
        for(const auto& token:old)require(!e.Manager.Allocator.ValidateIdentity(token),"old-material-token-live");
        // Reuse every retired exact-size material span before refresh, ensuring
        // a stale numeric slot can name a different real allocator owner.
        int rich=e.Manager.Allocator.Allocate(9),plain=e.Manager.Allocator.Allocate(4);
        int more=e.Manager.Allocator.Allocate(4);require(rich>0&&plain>0&&more>0,"pressure-allocation-failed");
        e.Refresh();
        require(e.Manager.Allocator.Free(rich)&&e.Manager.Allocator.Free(plain)&&e.Manager.Allocator.Free(more),"pressure-free-failed");
        auto stats=e.Manager.Allocator.GetStats();
        if(i==2){highwater=stats.HighWaterDescriptors;addressExtent=e.Manager.Allocator.GetNextIndex();}
        if(i>2)require(stats.HighWaterDescriptors==highwater&&e.Manager.Allocator.GetNextIndex()==addressExtent,
                       "repeated-reset-highwater-grew");
    }
    auto now=e.Mesh.Mutations.Snapshot();
    require(now.Geometry==mutations.Geometry&&now.Query==mutations.Query&&now.LightmapProbe==mutations.LightmapProbe,
            "material-reset-mutated-geometry-or-atlas-domain");
    require(e.Mesh.Epoch.Validate(epoch),"material-reset-retired-mesh-owner");
}
int main(int argc,char** argv){
    try{require(argc==2,"missing-case");run(argv[1]);std::cout<<"PASS "<<argv[1]<<'\n';return 0;}
    catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 11;}
}
