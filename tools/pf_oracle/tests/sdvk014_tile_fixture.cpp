// SPDX-License-Identifier: GPL-3.0-or-later
// Exact production tile allocation/retirement, scheduling and LIGHTMAP encoding.
// GPU readback/upload and final WAD filesystem replacement are explicit CPU sinks.
#include <algorithm>
#include <cassert>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
#include "tarray.h"
#include "engineerrors.h"
#include "hw_lightmaptile.h"
#include "hw_rectpacker.h"
void* M_Malloc(size_t n) { auto p=std::malloc(n); if(!p) throw std::bad_alloc(); return p; }
void* M_Realloc(void* p,size_t n) { auto q=std::realloc(p,n); if(!q) throw std::bad_alloc(); return q; }
void M_Free(void* p) { std::free(p); }
void* M_Calloc(size_t n,size_t m) { auto p=std::calloc(n,m); if(!p) throw std::bad_alloc(); return p; }
[[noreturn]] void I_FatalError(const char* format,...) {
    char message[512]; va_list args; va_start(args,format);
    std::vsnprintf(message,sizeof(message),format,args); va_end(args);
    throw std::runtime_error(message);
}
[[noreturn]] void I_Error(const char* format,...) { throw std::runtime_error(format); }
static void require(bool ok,const char* reason) { if(!ok) throw std::logic_error(reason); }
#include "sdvk014_bounds_under_test.cpp"
#include "sdvk014_rectpacker_under_test.cpp"
enum class LevelMeshMutationDomain { LightmapProbe };
struct LevelMeshTileStats {
    struct Stats { uint32_t total=0,dirty=0; };
    Stats tiles,pixels;
};
class LevelMesh {
public:
    struct {
        int TextureCount=1,TextureSize=16;
        TArray<uint16_t> TextureData;
        TArray<LightmapTile> Tiles;
        int UsedTiles=0;
        TArray<int> FreeTiles;
        std::unique_ptr<RectPacker> AtlasPacker;
    } Lightmap;
    struct Surface { int LightmapTileIndex=-1; };
    struct { TArray<Surface> Surfaces; } Mesh;
    int mutations=0;
    LevelMesh() { Lightmap.AtlasPacker=std::make_unique<RectPacker>(16,16,0); }
    int AllocTile(const LightmapTile&);
    void FreeTile(int);
    LevelMeshTileStats GatherTilePixelStats();
    void MarkMutation(LevelMeshMutationDomain) { ++mutations; }
};
struct FLevelLocals { uint8_t md5[16] = {}; };
class DoomLevelMesh: public LevelMesh {
public:
    struct Info { int NextSurface=-1; };
    TArray<Info> DoomSurfaceInfos;
    std::vector<uint8_t> saved;
    void ReleaseTiles(int);
    void SavePrefix();
};
struct { DoomLevelMesh* levelMesh=nullptr; } level;
static constexpr int LIGHTMAPVER=5;
struct Screen {
    int downloads=0;
    std::vector<int> baked;
    void DownloadLightmap(int page,uint16_t* out) {
        ++downloads;
        const int size=level.levelMesh->Lightmap.TextureSize;
        // Independent literal channel pattern; alpha deliberately not RGB.
        for(int y=0;y<size;++y) for(int x=0;x<size;++x) {
            auto p=out+4*(y*size+x);
            p[0]=uint16_t(1000+page*100);p[1]=uint16_t(2000+x);p[2]=uint16_t(3000+y);p[3]=65500;
        }
    }
    void UpdateLightmaps(const TArray<LightmapTile*>& tiles) {
        baked.clear();for(auto tile:tiles) baked.push_back(int(tile->Binding.TypeIndex));
    }
} screenObject;
static Screen* screen=&screenObject;
static int lm_max_updates=128,lm_background_updates=8;
class HWDrawInfo {
public:
    HWDrawInfo* outer=nullptr;
    int TileSeenCounter=42;
    struct { TArray<LightmapTile*> Geometry,Background,ReceivedNewLight,Result; } VisibleTiles;
    void UpdateLightmaps();
};
struct OwnerSink { int calls=0; void SetLevelMesh(LevelMesh*) { ++calls; } };
struct TextureSink {
    bool fail=false;int calls=0;std::vector<uint16_t> uploaded;
    void CreateLightmap(int size,int pages,const TArray<uint16_t>& data) {
        if(fail) throw std::runtime_error("injected upload failure");
        require(data.Size()==0 || data.Size()==unsigned(size*size*pages*3),"wrong-upload-domain");
        uploaded.assign(data.begin(),data.end());++calls;
    }
};
class VulkanRenderDevice {
public:
    bool levelMeshChanged=true;LevelMesh* levelMesh;
    OwnerSink meshSink,mapper;OwnerSink* mLevelMesh=&meshSink;TextureSink textures;
    explicit VulkanRenderDevice(LevelMesh* p):levelMesh(p) {}
    TextureSink* GetTextureManager() {return &textures;}
    OwnerSink* GetLightmapper() {return &mapper;}
    void PublishMesh();
};
#include "sdvk014_tile_methods.cpp"
static int allocate(DoomLevelMesh& m,int binding,int w=4,int h=4) {
    LightmapTile tile;tile.UseCount=1;tile.Binding.Type=1;tile.Binding.TypeIndex=binding;
    tile.NeedsInitialBake=true;
    int i=m.AllocTile(tile);
    auto allocation=m.Lightmap.AtlasPacker->Alloc(w,h);
    const auto p=m.Lightmap.AtlasPacker->GetRegion(allocation);
    m.Lightmap.Tiles[i].AtlasLocation={p.X,p.Y,p.Width,p.Height,p.PageIndex,allocation};
    m.Lightmap.TextureCount=m.Lightmap.AtlasPacker->GetNumPages();
    int s=int(m.Mesh.Surfaces.Size());m.Mesh.Surfaces.Push(LevelMesh::Surface{i});
    m.DoomSurfaceInfos.Push(DoomLevelMesh::Info{});return s;
}
static uint32_t u32(const std::vector<uint8_t>& v,size_t at) {
    require(at+4<=v.size(),"short-encoded-lump");
    return uint32_t(v[at])|(uint32_t(v[at+1])<<8)|(uint32_t(v[at+2])<<16)|(uint32_t(v[at+3])<<24);
}
static uint16_t u16(const std::vector<uint8_t>& v,size_t at) {
    require(at+2<=v.size(),"short-encoded-pixel");return uint16_t(v[at])|(uint16_t(v[at+1])<<8);
}
static void setupGhost(DoomLevelMesh& m) {
    allocate(m,100);int b=allocate(m,200),c=allocate(m,300);
    m.ReleaseTiles(b);m.ReleaseTiles(c);
    allocate(m,400,8,4); // Reuses C's tile ordinal, and B+C's coalesced rectangle.
    require(m.Lightmap.Tiles.Size()==3 && m.Lightmap.UsedTiles==2,"ghost-precondition");
}
static void run(const std::string& mode) {
    DoomLevelMesh m;level.levelMesh=&m;
    if(mode=="shared-retirement") {
        int s=allocate(m,100);auto& t=m.Lightmap.Tiles[0];++t.UseCount;
        m.Mesh.Surfaces.Push(LevelMesh::Surface{0});m.DoomSurfaceInfos.Push(DoomLevelMesh::Info{});
        m.ReleaseTiles(s);require(t.UseCount==1 && t.HasLiveAtlasAllocation(*m.Lightmap.AtlasPacker),"premature-shared-retirement");
        m.ReleaseTiles(1);
        require(m.Lightmap.UsedTiles==0 && m.Lightmap.FreeTiles.Size()==1,"retirement-count");
        require(t.AtlasLocation.ArrayIndex==-1 && !t.NeedsInitialBake && !t.GeometryUpdate && !t.ReceivedNewLight,
                "retired-tile-still-publishable");
    } else if(mode=="background") {
        setupGhost(m);InvalidateLightmap();HWDrawInfo d;d.UpdateLightmaps();
        require(screen->baked==std::vector<int>({100,400}),"retired-background-binding");
    } else if(mode=="stats") {
        setupGhost(m);auto s=m.GatherTilePixelStats();
        require(s.tiles.total==2 && s.tiles.dirty==2 && s.pixels.total==48 && s.pixels.dirty==48,"retired-statistics");
    } else if(mode=="save-bindings") {
        setupGhost(m);m.SavePrefix();
        require(u32(m.saved,0)==5 && u32(m.saved,4)==2 && u32(m.saved,8)==48,"ghost-binding-serialized");
        for(size_t i=12;i<28;++i) require(m.saved[i]==0,"wrong-source-digest");
        require(u32(m.saved,32)==100 && u32(m.saved,88)==400,"wrong-semantic-owner");
        require(u32(m.saved,44)==0 && u32(m.saved,100)==48,"wrong-rgb-offset");
        // Header 28 (including source digest) + 2*56 entries; row-major RGB uses A at x0 and D at x4.
        size_t at=140;
        for(int which=0;which<2;++which) for(int y=0;y<4;++y) for(int x=0;x<(which?8:4);++x) {
            require(u16(m.saved,at)==1000 && u16(m.saved,at+2)==2000+x+(which?4:0) &&
                    u16(m.saved,at+4)==3000+y,"wrong-owner-pixels");at+=6;
        }
        require(at==m.saved.size(),"wrong-encoded-size");
    } else if(mode=="readback-isolation") {
        allocate(m,100);m.Lightmap.TextureData.Resize(16*16*3);
        for(auto& x:m.Lightmap.TextureData) x=1234;
        m.SavePrefix();
        require(m.Lightmap.TextureData.Size()==16*16*3,"readback-overwrote-upload-shape");
        for(auto x:m.Lightmap.TextureData) require(x==1234,"readback-overwrote-upload-bytes");
        require(screen->downloads==1,"missing-readback");
    } else if(mode=="upload-consumption") {
        m.Lightmap.TextureData.Resize(16*16*3);for(auto& x:m.Lightmap.TextureData) x=1234;
        VulkanRenderDevice v(&m);v.PublishMesh();
        require(v.textures.uploaded.size()==16*16*3 && v.textures.uploaded[0]==1234,"missing-original-upload");
        require(m.Lightmap.TextureData.Size()==0,"successful-upload-not-consumed");
        m.Lightmap.TextureCount=2;v.levelMeshChanged=true;v.PublishMesh();
        require(v.textures.uploaded.empty() && v.textures.calls==2,"stale-upload-replayed");
    } else if(mode=="failed-upload-retained") {
        m.Lightmap.TextureData.Resize(16*16*3);m.Lightmap.TextureData[0]=1234;
        VulkanRenderDevice v(&m);v.textures.fail=true;bool failed=false;
        try {v.PublishMesh();} catch(const std::runtime_error&) {failed=true;}
        require(failed && m.Lightmap.TextureData.Size()==16*16*3 && m.Lightmap.TextureData[0]==1234,
                "failed-upload-lost-input");
        require(v.mapper.calls==0,"failed-upload-published-mapper");
    } else if(mode=="invalid-owner") {
        allocate(m,100);auto& t=m.Lightmap.Tiles[0];auto p=t.AtlasLocation.Allocation;
        t.AtlasLocation.Allocation={};bool rejected=false;
        try {m.SavePrefix();} catch(const std::runtime_error& e) {
            rejected=std::string(e.what()).find("valid atlas region")!=std::string::npos;
        }
        t.AtlasLocation.Allocation=p;
        require(rejected && screen->downloads==0,"invalid-owner-reached-readback");
    } else if(mode=="live-free") {
        allocate(m,100);bool rejected=false;
        try {m.FreeTile(0);} catch(const std::runtime_error& e) {
            rejected=std::string(e.what()).find("still owns")!=std::string::npos;
        }
        require(rejected && m.Lightmap.UsedTiles==1 && m.Lightmap.FreeTiles.Size()==0,"live-tile-retired");
    } else if(mode=="region-negatives") {
        allocate(m,100);auto good=m.Lightmap.Tiles[0];
        for(int i=0;i<11;++i) {
            auto& t=m.Lightmap.Tiles[0];t=good;
            switch(i) {case 0:t.AtlasLocation.ArrayIndex=1;break;case 1:t.AtlasLocation.X=-1;break;
            case 2:t.AtlasLocation.Y=15;break;case 3:t.AtlasLocation.Width=17;break;
            case 4:t.AtlasLocation.Height=0;break;case 5:t.AtlasLocation.Allocation={};break;
            case 6:t.AtlasLocation.X=std::numeric_limits<int>::max();break;case 7:t.AtlasLocation.Height=-1;break;
            case 8:t.AtlasLocation.X=4;break;case 9:t.AtlasLocation.Y=4;break;
            case 10:m.Lightmap.TextureCount=2;t.AtlasLocation.ArrayIndex=1;break;}
            bool stopped=false;try {m.SavePrefix();} catch(const std::runtime_error&) {stopped=true;}
            require(stopped && screen->downloads==0,"malformed-region-reached-readback");
        }
        m.Lightmap.Tiles[0]=good;
    } else if(mode=="bounded-retirement") {
        for(int cycle=0;cycle<128;++cycle) {
            int a=allocate(m,100),b=allocate(m,200);
            m.ReleaseTiles(a);m.ReleaseTiles(b);InvalidateLightmap();HWDrawInfo d;d.UpdateLightmaps();
            require(screen->baked.empty(),"retired-stress-update");
            require(m.Lightmap.UsedTiles==0 && m.Lightmap.Tiles.Size()==2 && m.Lightmap.FreeTiles.Size()==2,
                    "tile-pool-growth");
            require(m.Lightmap.AtlasPacker->GetNumPages()==1,"atlas-page-growth");
            m.Mesh.Surfaces.Clear();m.DoomSurfaceInfos.Clear();
        }
        std::cout<<"COUNTERS cycles=128 allocations=256 retirements=256 tile_slots=2 free_slots=2 pages=1 mutations="<<m.mutations<<'\n';
    } else throw std::logic_error("unknown-case");
}
int main(int argc,char** argv) {
    if(argc!=2) return 2;
    try {run(argv[1]);std::cout<<"PASS "<<argv[1]<<'\n';return 0;}
    catch(const std::logic_error& e) {std::cerr<<"ORACLE "<<e.what()<<'\n';return 11;}
    catch(const std::runtime_error& e) {std::cerr<<"PRODUCTION "<<e.what()<<'\n';return 10;}
}
