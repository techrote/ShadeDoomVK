// SPDX-License-Identifier: GPL-3.0-or-later
// Exact production atlas allocator, tile type and extracted producer/consumer
// bodies. No renderer/device. Surface arrays and Vulkan services are CPU sinks.
#include <algorithm>
#include <atomic>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <memory>
#include <new>
#include <set>
#include <stdexcept>
#include <string>
#include <tuple>
#include <type_traits>
#include <vector>
#ifdef __clang__
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wunused-parameter"
#endif
#include "tarray.h"
#ifdef __clang__
#pragma clang diagnostic pop
#endif
#include "engineerrors.h"
// Visibility only: test counter exhaustion and actual same-storage preconditions.
#define private public
#define VALIDATE_RECTPACKER
#include "hw_rectpacker.h"
#undef private
#include "hw_lightmaptile.h"
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
template<class F> static void rejects(F action,const char* text,const char* failure) {
    bool stopped=false;
    try { action(); } catch(const std::runtime_error& error) { stopped=std::string(error.what()).find(text)!=std::string::npos; }
    require(stopped,failure);
}
#include "sdvk156_rectpacker.cpp"
#include "sdvk156_bounds.cpp"

enum class LevelMeshMutationDomain { LightmapProbe=1, Surface=2 };
static LevelMeshMutationDomain operator|(LevelMeshMutationDomain a,LevelMeshMutationDomain b) {
    return LevelMeshMutationDomain(int(a)|int(b));
}
class LevelMesh {
public:
    struct {
        int TextureCount=1,TextureSize=16;
        TArray<LightmapTile> Tiles;
        int UsedTiles=0;
        TArray<int> FreeTiles,AddedTiles,AddedSurfaces;
        std::unique_ptr<RectPacker> AtlasPacker;
    } Lightmap;
    struct Vertex { float lu=0,lv=0,lindex=-1; FVector3 fPos() const { return {2,2,2}; } };
    struct Surface { int LightmapTileIndex=-1; struct {int NumVerts=1,StartVertIndex=0;} MeshLocation; };
    struct {TArray<Surface> Surfaces;TArray<Vertex> Vertices;} Mesh;
    struct Range {int count=0;void Add(int,int n){count+=n;}};
    struct {Range Vertex;} UploadRanges;
    int mutations=0;
    LevelMesh() {Lightmap.AtlasPacker=std::make_unique<RectPacker>(16,16,0);}
    int AllocTile(const LightmapTile&);
    void FreeTile(int);
    void PackLightmapAtlas();
    void ValidateLightmapTile(const LightmapTile&) const;
    const LightmapTile& GetLightmapTile(int) const;
    LightmapTile& GetLightmapTile(int);
    void MarkMutation(LevelMeshMutationDomain) {++mutations;}
};
class DoomLevelMesh:public LevelMesh {
public:
    struct Info {int NextSurface=-1;};TArray<Info> DoomSurfaceInfos;
    void ReleaseTiles(int);
};
#include "sdvk156_selected_type.cpp"
static struct {void Reset(){}} lightmapRaytraceLast;
static uint32_t lastPixelCount;
static int lastSurfaceCount;
class VkLightmapper {
public:
    LevelMesh* mesh=nullptr;
    std::unique_ptr<RectPacker> packer;
    struct {uint16_t maxX=0,maxY=0;} bakeImage;
    enum {bakeImageSize=2048};
    TArray<SelectedTile> selectedTiles;
    TArray<TArray<SelectedTile*>> copylists;
    void SetLevelMesh(LevelMesh*);
    void SelectTiles(const TArray<LightmapTile*>&);
    void ValidateSelectedTile(const SelectedTile&) const;
};
#include "sdvk156_methods.cpp"
static LightmapTile tileFor(RectPacker& owner,RectPackerAllocation allocation,int binding=100) {
    auto p=owner.GetRegion(allocation);
    LightmapTile tile;tile.UseCount=1;tile.Binding.TypeIndex=binding;
    tile.AtlasLocation={p.X,p.Y,p.Width,p.Height,p.PageIndex,allocation};return tile;
}
static int add(DoomLevelMesh& m,int binding,int w=16,int h=16) {
    LightmapTile tile;tile.UseCount=1;tile.Binding.TypeIndex=binding;
    // Model admitted retained extents; geometry transform itself is unchanged.
    tile.NeedsInitialBake=false;tile.GeometryUpdate=false;
    tile.AtlasLocation.Width=w;tile.AtlasLocation.Height=h;
    int index=m.AllocTile(tile);
    m.Lightmap.AddedTiles.Push(index);
    int surface=int(m.Mesh.Surfaces.Size());
    LevelMesh::Surface s;s.LightmapTileIndex=index;s.MeshLocation.StartVertIndex=surface;
    m.Mesh.Surfaces.Push(s);m.Mesh.Vertices.Push({});
    m.DoomSurfaceInfos.Push({});m.Lightmap.AddedSurfaces.Push(surface);
    m.PackLightmapAtlas();
    require(m.GetLightmapTile(index).AtlasLocation.ArrayIndex==int(m.Mesh.Vertices[surface].lindex),"vertex-page-not-published");
    return surface;
}
static void sameRegion(const LightmapTile& a,const LightmapTile& b) {
    const auto& x=a.AtlasLocation;const auto& y=b.AtlasLocation;
    require(x.X==y.X&&x.Y==y.Y&&x.Width==y.Width&&x.Height==y.Height&&x.ArrayIndex==y.ArrayIndex,"same-region-precondition");
}
static void run(const std::string& mode) {
    if(mode=="copied-free-aba") {
        DoomLevelMesh m;int first=add(m,100);auto old=m.Lightmap.Tiles[0];
        auto* storage=m.Lightmap.AtlasPacker->Items[old.AtlasLocation.Allocation.Slot].get();
        m.ReleaseTiles(first);
        require(m.Mesh.Surfaces[first].LightmapTileIndex==-1 && m.Lightmap.Tiles[0].UseCount==0 &&
                !m.Lightmap.Tiles[0].AtlasLocation.Allocation,"current-surface-tombstone-lost");
        add(m,200);auto& live=m.GetLightmapTile(0);sameRegion(old,live);
        require(m.Lightmap.AtlasPacker->Items[live.AtlasLocation.Allocation.Slot].get()==storage,"same-item-precondition");
        require(!old.HasValidAtlasRegion(*m.Lightmap.AtlasPacker,16,1),"stale-atlas-receipt-accepted");
        std::cout<<"same_item=1 same_region=1 old_guard=0 current_guard=1 tombstone=1\n";
    } else if(mode=="copied-clear-aba") {
        RectPacker p(16,16,0);auto old=tileFor(p,p.Alloc(16,16));auto* storage=p.Items[old.AtlasLocation.Allocation.Slot].get();
        p.Clear();require(!p.IsLive(old.AtlasLocation.Allocation),"clear-left-live-allocation");
        auto live=tileFor(p,p.Alloc(16,16),200);sameRegion(old,live);
        require(p.Items[live.AtlasLocation.Allocation.Slot].get()==storage,"same-item-precondition");
        require(!old.HasValidAtlasRegion(p,16,1),"stale-clear-receipt-accepted");
        require(live.HasValidAtlasRegion(p,16,1),"current-clear-receipt-rejected");
        std::cout<<"same_item=1 same_region=1 old_guard=0 current_guard=1\n";
    } else if(mode=="owner-recreation") {
        std::aligned_storage_t<sizeof(RectPacker),alignof(RectPacker)> storage;
        auto* p=new(&storage) RectPacker(16,16,0);auto old=p->Alloc(16,16);p->~RectPacker();
        p=new(&storage) RectPacker(16,16,0);auto live=p->Alloc(16,16);
        require(old.Slot==live.Slot && old.Incarnation==live.Incarnation && old.Owner!=live.Owner,"same-owner-address-precondition");
        require(!p->IsLive(old) && !p->Free(old) && p->IsLive(live),"destroyed-owner-receipt-accepted");p->~RectPacker();
    } else if(mode=="foreign-malformed") {
        RectPacker a(16,16,0),b(16,16,0);auto x=a.Alloc(16,16),y=b.Alloc(16,16);
        require(x.Slot==y.Slot && x.Incarnation==y.Incarnation,"same-slot-generation-precondition");
        require(!a.IsLive(y) && !a.Free(y) && a.IsLive(x),"foreign-owner-receipt-accepted");
        for(int i=0;i<4;++i) {
            auto bad=x;
            if(i==0)bad.Slot=std::numeric_limits<size_t>::max();
            if(i==1)bad.Incarnation=0;
            if(i==2)bad.Owner=0;
            if(i==3)bad.Incarnation++;
            RectPackerRegion untouched{7,8,9,10,11};
            require(!a.TryGetRegion(bad,untouched)&&!a.Free(bad)&&a.IsLive(x),"malformed-receipt-mutated-owner");
            require(untouched.X==7&&untouched.Y==8&&untouched.Width==9&&untouched.Height==10&&untouched.PageIndex==11,"failed-resolution-mutated-output");
        }
        require(!a.Free({})&&!a.IsLive({}),"null-receipt-accepted");
    } else if(mode=="stale-free") {
        RectPacker p(16,16,0);auto old=p.Alloc(16,16);require(p.Free(old),"live-free-failed");
        require(!p.IsLive(old),"retired-receipt-live");auto live=p.Alloc(16,16);
        require(!p.Free(old)&&p.IsLive(live),"stale-free-mutated-live-owner");
        require(p.Free(live)&&!p.Free(live),"duplicate-free-accepted");
    } else if(mode=="coalesced-reuse") {
        RectPacker p(16,16,0);auto a=p.Alloc(8,8),b=p.Alloc(8,8),c=p.Alloc(16,8);
        p.Free(a);p.Free(b);auto live=p.Alloc(16,8);
        require(!p.IsLive(a)&&!p.IsLive(b)&&p.IsLive(c)&&p.IsLive(live),"coalesced-receipt-survived");
        require(!p.Free(a)&&!p.Free(b)&&p.IsLive(live),"coalesced-free-mutated-owner");
    } else if(mode=="multiple-pages") {
        RectPacker p(16,16,0);std::vector<RectPackerAllocation> old;
        for(int i=0;i<3;++i)old.push_back(p.Alloc(16,16));
        p.Free(old[1]);auto replacement=p.Alloc(16,16);
        require(p.GetRegion(replacement).PageIndex==1&&!p.IsLive(old[1])&&p.IsLive(old[0])&&p.IsLive(old[2]),"page-reuse-identity-wrong");
        p.Clear();for(int i=0;i<3;++i)require(p.GetRegion(p.Alloc(16,16)).PageIndex==i,"page-rebuild-order");
        for(auto token:old)require(!p.IsLive(token)&&!p.Free(token),"rebuilt-page-accepted-old-receipt");
        require(!p.IsLive(replacement)&&p.Items.size()==3&&p.GetNumPages()==3,"rebuild-storage-growth");
    } else if(mode=="incremental-pack") {
        DoomLevelMesh m;add(m,100);auto old=m.Lightmap.Tiles[0];add(m,200);m.PackLightmapAtlas();
        require(m.Lightmap.TextureCount==2&&m.GetLightmapTile(0).AtlasLocation.Allocation==old.AtlasLocation.Allocation,"incremental-pack-relocated-live-owner");
        require(m.GetLightmapTile(1).AtlasLocation.ArrayIndex==1&&m.Lightmap.AddedTiles.Size()==0&&m.Lightmap.AddedSurfaces.Size()==0,"added-owner-not-published");
    } else if(mode=="copied-tile-admission") {
        DoomLevelMesh m;add(m,100);auto copy=m.Lightmap.Tiles[0];int used=m.Lightmap.UsedTiles;
        rejects([&]{m.AllocTile(copy);},"Cannot copy","copied-live-receipt-admitted");
        require(m.Lightmap.UsedTiles==used&&m.Lightmap.Tiles.Size()==1,"copy-admission-mutated-pool");
        copy.AtlasLocation.Allocation={0,0,42};
        rejects([&]{m.AllocTile(copy);},"Cannot copy","malformed-receipt-admitted");
    } else if(mode=="repack-requires-retirement") {
        DoomLevelMesh m;add(m,100);auto old=m.Lightmap.Tiles[0];
        m.Lightmap.AddedTiles.Push(0);
        rejects([&]{m.PackLightmapAtlas();},"Cannot repack","live-receipt-overwritten-by-repack");
        require(m.Lightmap.Tiles[0].AtlasLocation.Allocation==old.AtlasLocation.Allocation&&
                old.HasValidAtlasRegion(*m.Lightmap.AtlasPacker,16,1),"rejected-repack-mutated-owner");
    } else if(mode=="duplicate-pending") {
        DoomLevelMesh m;LightmapTile tile;tile.UseCount=1;tile.GeometryUpdate=false;
        tile.AtlasLocation.Width=16;tile.AtlasLocation.Height=16;
        int i=m.AllocTile(tile);m.Lightmap.AddedTiles.Push(i);m.Lightmap.AddedTiles.Push(i);
        rejects([&]{m.PackLightmapAtlas();},"Duplicate pending","duplicate-pending-overwrote-receipt");
        require(m.Lightmap.AtlasPacker->GetNumPages()==1 &&
                m.Lightmap.AtlasPacker->IsLive(m.Lightmap.Tiles[i].AtlasLocation.Allocation),"duplicate-created-orphan-allocation");
    } else if(mode=="malformed-region") {
        DoomLevelMesh m;add(m,100);m.Lightmap.Tiles[0].AtlasLocation.X=1;
        require(!m.Lightmap.Tiles[0].HasValidAtlasRegion(*m.Lightmap.AtlasPacker,16,1),"malformed-region-accepted");
        rejects([&]{m.GetLightmapTile(0);},"atlas receipt","unguarded-tile-consumer");
    } else if(mode=="scratch-repack"||mode=="pending-destination"||mode=="scratch-region"||mode=="selected-tile-mismatch") {
        DoomLevelMesh m;int s=add(m,100,4,4);auto* tile=&m.Lightmap.Tiles[0];
        TArray<LightmapTile*> tiles;tiles.Push(tile);VkLightmapper mapper;mapper.mesh=&m;mapper.SelectTiles(tiles);
        require(mapper.selectedTiles.Size()==1,"missing-selected-tile");auto old=mapper.selectedTiles[0];mapper.ValidateSelectedTile(old);
        if(mode=="scratch-region") {
            old.X++;
            rejects([&]{mapper.ValidateSelectedTile(old);},"scratch region","changed-scratch-region-accepted");
        } else if(mode=="selected-tile-mismatch") {
            LightmapTile other=tileFor(*m.Lightmap.AtlasPacker,m.Lightmap.AtlasPacker->Alloc(4,4),200);
            old.Tile=&other;
            rejects([&]{mapper.ValidateSelectedTile(old);},"destination allocation changed","selected-tile-mismatch-accepted");
        } else if(mode=="scratch-repack") {
            mapper.SelectTiles(tiles);mapper.ValidateSelectedTile(mapper.selectedTiles[0]);
            require(mapper.selectedTiles[0].AtlasAllocation==old.AtlasAllocation,"scratch-repack-changed-destination");
            rejects([&]{mapper.ValidateSelectedTile(old);},"bake allocation receipt","old-scratch-receipt-accepted");
        } else {
            m.ReleaseTiles(s);add(m,200,4,4);
            require(&m.Lightmap.Tiles[0]==tile,"same-tile-storage-precondition");
            rejects([&]{mapper.ValidateSelectedTile(old);},"bake allocation receipt","pending-work-rebound-to-new-destination");
        }
    } else if(mode=="owner-switch-pending") {
        auto original=std::make_unique<DoomLevelMesh>();add(*original,100,4,4);
        VkLightmapper mapper;mapper.SetLevelMesh(original.get());
        TArray<LightmapTile*> tiles;tiles.Push(&original->Lightmap.Tiles[0]);mapper.SelectTiles(tiles);
        auto old=mapper.selectedTiles[0];mapper.copylists.Resize(1);mapper.copylists[0].Push(&mapper.selectedTiles[0]);
        original.reset();DoomLevelMesh next;add(next,200,4,4);mapper.SetLevelMesh(&next);
        require(mapper.selectedTiles.Size()==0&&mapper.copylists[0].Size()==0,"pending-work-survived-owner-switch");
        // old.Tile is now genuinely dangling; rejection must precede dereference.
        rejects([&]{mapper.ValidateSelectedTile(old);},"bake allocation receipt","destroyed-mesh-receipt-accepted");
    } else if(mode=="incarnation-exhaustion") {
        RectPacker p(16,16,0);auto old=p.Alloc(16,16);p.Free(old);
        p.LastIncarnation=std::numeric_limits<uint64_t>::max()-1;
        auto last=p.Alloc(16,16);p.Free(last);p.Clear();size_t n=p.Items.size();
        rejects([&]{p.Alloc(16,16);},"incarnation exhausted","allocation-counter-wrapped");
        require(p.LastIncarnation==std::numeric_limits<uint64_t>::max()&&p.Items.size()==n&&p.GetNumPages()==0,"exhaustion-mutated-owner");
    } else if(mode=="owner-exhaustion") {
        RectPackerOwnerSequence.store(std::numeric_limits<uint64_t>::max()-1);
        RectPacker last(16,16,0);require(last.Alloc(16,16).Owner==std::numeric_limits<uint64_t>::max(),"last-owner-not-issued");
        rejects([]{RectPacker exhausted(16,16,0);},"owner identity exhausted","owner-counter-wrapped");
        require(RectPackerOwnerSequence.load()==std::numeric_limits<uint64_t>::max(),"owner-counter-mutated-after-exhaustion");
    } else if(mode=="bounded-rebuild") {
        DoomLevelMesh m;size_t high=0;std::vector<LightmapTile> previous;
        for(int cycle=0;cycle<128;++cycle) {
            for(int i=0;i<4;++i)add(m,100+i,8,8);
            for(const auto& old:previous)require(!old.HasLiveAtlasAllocation(*m.Lightmap.AtlasPacker),"stale-rebuild-receipt-accepted");
            previous.assign(m.Lightmap.Tiles.begin(),m.Lightmap.Tiles.end());
            for(int i=0;i<4;++i)m.ReleaseTiles(i);
            require(m.Lightmap.UsedTiles==0&&m.Lightmap.Tiles.Size()==4&&m.Lightmap.FreeTiles.Size()==4,"tile-pool-not-bounded");
            if(!cycle)high=m.Lightmap.AtlasPacker->Items.size();
            require(m.Lightmap.AtlasPacker->Items.size()==high&&m.Lightmap.TextureCount==1,"atlas-pool-not-bounded");
            m.Mesh.Surfaces.Clear();m.Mesh.Vertices.Clear();m.DoomSurfaceInfos.Clear();
        }
        std::cout<<"cycles=128 allocations=512 retirements=512 tile_slots=4 pages=1 item_high_water="<<high<<"\n";
    } else throw std::logic_error("unknown-case");
}
int main(int argc,char** argv) {
    if(argc!=2)return 2;
    try {run(argv[1]);std::cout<<"PASS "<<argv[1]<<'\n';return 0;}
    catch(const std::logic_error& e){std::cerr<<"REJECT "<<e.what()<<'\n';return 11;}
    catch(const std::exception& e){std::cerr<<"UNEXPECTED "<<e.what()<<'\n';return 12;}
}
