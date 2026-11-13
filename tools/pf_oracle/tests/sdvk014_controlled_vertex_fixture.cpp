// CPU storage adapter around actual indexed-flat creation, height updates and
// immediate UV publication. No renderer, Vulkan or gameplay ticker is linked.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
template<class T> struct TArray : std::vector<T>
{
    using std::vector<T>::vector;
    unsigned Size() const { return unsigned(this->size()); }
    void Push(const T& value) { this->push_back(value); }
};
struct FVector2 { float X,Y; FVector2(float x,float y):X(x),Y(y){} };
struct FVector3
{
    float X,Y,Z;
    FVector3(float x,float y,float z):X(x),Y(y),Z(z){}
    FVector3 operator-(const FVector3& b)const{return {X-b.X,Y-b.Y,Z-b.Z};}
    float operator|(const FVector3& b)const{return X*b.X+Y*b.Y+Z*b.Z;}
};
struct LightmapTile
{
    struct { float X=0,Y=0,Width=16,Height=16; int ArrayIndex=0; } AtlasLocation;
    struct { FVector3 TranslateWorldToLocal{0,0,0},ProjLocalToU{1,0,0},ProjLocalToV{0,1,0}; } Transform;
    // @PRODUCTION_TO_UV@
};
struct LevelMesh
{
    struct { float TextureSize=128; TArray<LightmapTile> Tiles{8}; } Lightmap;
    const LightmapTile& GetLightmapTile(int index)const{return Lightmap.Tiles.at(size_t(index));}
};
struct { bool lightmaps=true; LevelMesh* levelMesh=nullptr; } level;
struct secplane_t { float Height=0; float ZatPoint(float,float)const{return Height;} };
struct FFlatVertex { float x=2,y=3,z=0,lu=0,lv=0,lindex=-1; };
struct F3DFloor;
struct Ext
{
    struct { TArray<struct sector_t*> Sectors; } FakeFloor;
    struct { TArray<struct sector_t*> attached; TArray<F3DFloor*> ffloors; } XFloor;
};
struct subsector_t { TArray<int> LightmapTiles[2]{{-1,1,2},{-1,3,4}}; } targetSub;
struct sector_t
{
    enum { floor=0,ceiling=1 };
    int id=0, vboindex[2]{},vbocount[2]{},iboindex[4]{},ibocount=0;
    float vboheight[2]{};
    bool transdoor=false;
    decltype(level)* Level=&level;
    Ext storage; Ext* e=&storage;
    secplane_t planes[2]{{32},{80}};
    int Index()const{return id;}
    float GetPlaneTexZ(int h)const{return planes[h].Height;}
    secplane_t& GetSecPlane(int h){return planes[h];}
};
enum { FF_RENDERPLANES=8,FF_BOTHPLANES=0x200,FF_INVERTPLANES=0x2000,FF_THISINSIDE=0x40000000 };
struct F3DFloor
{
    struct planeref
    {
        sector_t* model=nullptr; int isceiling=0;
#ifdef SDVK014_LEGACY_VERTEX
        int vindex=-1;
#else
        int vindex[2]{-1,-1};
#endif
    } top,bottom;
    unsigned flags=FF_RENDERPLANES;
    sector_t* model=nullptr;
};
struct VertexContainer { TArray<int> indices{0,1,2}; };
using VertexContainers=TArray<VertexContainer>;
struct SectorVertexOrigin
{
    subsector_t* sub=nullptr; int plane=0,lightmapSlot=0;
};
static TArray<FFlatVertex> sector_vertices;
static TArray<SectorVertexOrigin> sector_origins;
static TArray<uint32_t> sector_indexes;
struct FRenderState
{
    int uploads=0;
    void UpdateShadowData(int,const FFlatVertex*,int){++uploads;}
};
// Geometry storage only: three real distinct XY positions and source heights.
// Production code below chooses every source axis, facing slot and owner span.
static int CreateIndexedSectorVertices(sector_t* sec,const secplane_t& plane,int,
    VertexContainer&,int h,int slot)
{
    const int start=int(sector_indexes.Size());
    for(int corner=0;corner<3;corner++)
    {
        FFlatVertex point;point.x+=float(corner);point.z=plane.Height;
        sector_indexes.Push(sector_vertices.Size());sector_vertices.Push(point);
        sector_origins.Push({sec->id==0 ? nullptr : &targetSub,h,slot});
    }
    return start;
}
// @PRODUCTION_FIND_3D_FLOOR@
// @PRODUCTION_CREATE_INDEXED_VERTICES@
// @PRODUCTION_UPDATE_PLANE_VERTICES@
// @PRODUCTION_UPDATE_PLANE_LIGHTMAP@
static int stream(const F3DFloor::planeref& plane,int facing)
{
#ifdef SDVK014_LEGACY_VERTEX
    (void)facing;return plane.vindex;
#else
    return plane.vindex[facing];
#endif
}
static bool close(float a,float b){return std::abs(a-b)<0.000001f;}
static bool fail(const char* error){std::cerr<<error<<'\n';return false;}
static bool run(const std::string& name)
{
    const bool noLightmap=name=="unlightmapped-both",self=name=="self-source-height-span";
    const bool inverted=name=="inverted" || name=="inverted-both";
    const bool both=name=="both" || name=="inverted-both" || noLightmap || self;
    sector_t model,target;target.id=1;
    F3DFloor rover;rover.model=&model;rover.top.model=&model;rover.top.isceiling=1;
    rover.bottom.model=&model;rover.bottom.isceiling=0;
    rover.flags|=(both ? FF_BOTHPLANES : 0) | (inverted ? FF_INVERTPLANES : 0);
    target.e->XFloor.ffloors.Push(&rover);model.e->XFloor.attached.Push(&target);
    if(self)
    {
        // Source model is also receiving sector. Its extra streams must remain
        // inside the model's existing per-plane update spans.
        model.id=1;model.e->XFloor.ffloors.Push(&rover);
        model.e->XFloor.attached.clear();
    }
    LevelMesh mesh;level.levelMesh=&mesh;level.lightmaps=!noLightmap;
    for(int i=1;i<=4;i++)
    {
        auto& tile=mesh.Lightmap.Tiles[size_t(i)];
        tile.AtlasLocation.X=float(i*16);tile.AtlasLocation.Y=float(i*8);tile.AtlasLocation.ArrayIndex=i;
    }
    VertexContainers verts(2);FRenderState renderstate;
    for(int h=0;h<2;h++)
    {
        CreateIndexedVertices(h,&model,model.GetSecPlane(h),h==0,verts);
        model.planes[h].Height+=float(8*(h+1));
        UpdatePlaneVertices(renderstate,&model,h);
        if(!noLightmap)UpdatePlaneLightmap(renderstate,&model,h);
    }
    for(int h=0;h<2;h++)
    {
        const auto& plane=h ? rover.top : rover.bottom;
        for(int facing=0;facing<2;facing++)
        {
            const bool enabled=h ? (facing ? inverted||both : !inverted) : (facing ? !inverted : inverted||both);
            if(!enabled)continue;
            const int index=stream(plane,facing);
            if(index<0)return fail("required-facing-stream-missing");
            const int vertex=int(sector_indexes[size_t(index)]);
            if(vertex<model.vboindex[h] || vertex+3>model.vboindex[h]+model.vbocount[h])return fail("source-height-update-span");
            for(int corner=0;corner<3;corner++)
            {
                const auto& point=sector_vertices[size_t(vertex+corner)];
                if(!close(point.z,model.planes[h].Height))return fail("opposite-facing-height-stale");
                if(noLightmap)
                {
                    if(point.lindex!=-1)return fail("unlightmapped-path-changed");
                    continue;
                }
                const int expected=1+h*2+facing;
                const float u=(float(expected*16)+point.x)/128.0f,v=(float(expected*8)+point.y)/128.0f;
                if(point.lindex!=float(expected) || !close(point.lu,u) || !close(point.lv,v))
                    return fail("opposite-facing-tile-overwrite");
            }
        }
        if(both && !inverted && !noLightmap && stream(plane,0)==stream(plane,1))return fail("opposite-facing-shared-vertices");
        if(noLightmap && stream(plane,0)!=stream(plane,1))return fail("unlightmapped-stream-duplicated");
    }
    if(renderstate.uploads!=(noLightmap ? 2 : 4))return fail("height-or-UV-publication-missing");
    return true;
}
int main(int argc,char** argv)
{
    if(argc!=2)return 2;
    if(!run(argv[1]))return 11;
    std::cout<<"PASS "<<argv[1]<<'\n';
}
