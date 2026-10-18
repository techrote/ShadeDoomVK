// SPDX-License-Identifier: GPL-3.0-or-later
// Actual source-extracted mesh observer, parent and guarded callback. Geometry
// and descriptor payload services are CPU doubles; no renderer/device is made.
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstring>
#include <fstream>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#include "hw_sdvkdiagnostics.h"
#include "hw_sdvkdiagnosticcore.h"
#include "vk_keyidentity.h"
using namespace SdvkObservation;
template<class T> struct Array : std::vector<T> { size_t Size()const{return this->size();} };
struct FVector2 {float X,Y;FVector2(float x,float y):X(x),Y(y){}};
struct FVector3 {float X=0,Y=0,Z=0;FVector3 operator-(const FVector3& b)const{return {X-b.X,Y-b.Y,Z-b.Z};}};
float operator|(const FVector3& a,const FVector3& b){return a.X*b.X+a.Y*b.Y+a.Z*b.Z;}
struct FVector4 {float X=0,Y=0,Z=0,W=0;};
struct FFlatVertex {float x=0,y=0,z=0,lu=0,lv=0,lindex=0;FVector3 fPos()const{return {x,y,z};}};
struct RectPackerAllocation {uint64_t Owner=0,Incarnation=0;size_t Slot=0;};
struct LightmapTile {
 struct {int X=16,Y=16,Width=32,Height=32,ArrayIndex=0;RectPackerAllocation Allocation;} AtlasLocation;
 struct {FVector3 TranslateWorldToLocal{-32,-32,-32},ProjLocalToU{0,0.03125f,0},ProjLocalToV{0,0,0.03125f};} Transform;
 bool HasValidAtlasRegion(int,int size,int pages)const{return size==1024&&pages==1&&AtlasLocation.ArrayIndex==0;}
#include "mesh_witness_to_uv.inc"
};
struct sector_t {enum{floor};int Number=0,PortalGroup=0;int Index()const{return Number;}float GetReflect(int)const{return 0;}};
struct Side {sector_t* sector;int Number=8;int Index()const{return Number;}};
struct Subsector {sector_t* sector;};
using SideType=Side;using SubsectorType=Subsector;
struct Info {int Type=1,TypeIndex=8;SideType* Side=nullptr;SubsectorType* Subsector=nullptr;sector_t* ControlSector=nullptr;};
struct Name {std::string Text;const char* GetChars()const{return Text.c_str();}};
struct MaterialService {Name NameValue;std::string Payload;MaterialService* Source(){return this;}const Name& GetName()const{return NameValue;}};
struct MaterialState {MaterialService* mMaterial=nullptr;};
struct Uniform {int uTextureIndex=0;};
struct Surface {
 struct {size_t StartVertIndex=0;int NumVerts=6;size_t StartElementIndex=0;int NumElements=6;} MeshLocation;
 int LightmapTileIndex=0,PortalIndex=0,SectorGroup=0;bool IsSky=false;FVector4 Plane;
};
class LevelMesh {
public:
 struct {Array<FFlatVertex> Vertices;Array<int> UniformIndexes,Indexes,SurfaceIndexes;
  Array<Surface> Surfaces;Array<Uniform> Uniforms;Array<MaterialState> Materials;
  struct LightUniform{FVector4 uVertexColor{0,0,0,1};};Array<LightUniform> LightUniforms;int IndexCount=0;} Mesh;
 struct {Array<LightmapTile> Tiles;std::unique_ptr<int> AtlasPacker=std::make_unique<int>(1);int TextureSize=1024,TextureCount=1;} Lightmap;
 Info Semantic;int Epoch=1;uint64_t Owner=0;
 uint64_t GetResourceOwner()const{return Owner;}
 const Info* GetSurfaceInfoForObservation(int)const{return &Semantic;}
 struct EpochValue {int Generation;};EpochValue GetResourceEpoch()const{return {Epoch};}
};
struct {LevelMesh* levelMesh=nullptr;Array<sector_t> sectors;} level;
struct Textures {std::vector<int> Lightmaps{0};int Epoch=1;struct EpochValue{int Generation;};EpochValue GetLightmapEpoch()const{return {Epoch};}};
struct Mirror {LevelMesh* Mesh=nullptr;LevelMesh* GetMesh(){return Mesh;}};
class VulkanRenderDevice {public:Mirror Mesh;Textures Texture;Mirror* GetLevelMesh(){return &Mesh;}Textures* GetTextureManager(){return &Texture;}};
struct VkPipelineKey : VkKeyIdentity::PipelineState {VkKeyIdentity::PipelineState CanonicalState()const{return *this;}};
class VkRenderState {public:VulkanRenderDevice* fb=nullptr;VkPipelineKey mPipelineKey;
 struct {int Width=640,Height=480,Format=97,Samples=1,DrawBuffers=1;const void* DepthStencil=this;}mRenderTarget;
};
enum class LevelMeshDrawSurface {Side,Flat};
constexpr int ST_FLOOR=5,ST_CEILING=4;
static std::string Context,Probe,Failure;
static bool Selected=true,FixtureEnabled=true;
static std::vector<std::string> Records;
#include "mesh_witness_serializers.inc"
namespace SdvkDiagnostics {
 std::atomic<bool> EnabledFlag{true},StateFlag{true},GpuFlag{false};
 bool SpecialSurfaceEnabled(){return FixtureEnabled;}
 bool SpecialSurfaceFrameSelected(){return FixtureEnabled&&Selected;}
 std::string CurrentContextJson(){return Context;}
 void Emit(const char* kind,const std::string& value,bool){Records.push_back(Object().Str("kind",kind).Raw("data",value).Json());}
 void Fail(const char* message){Failure=message;}
}
struct FSdvkDiagnosticAccess {
 // Explicit descriptor/probe services deliver the coherent selected bound
 // payloads; the real observer chooses MaterialState/Uniform from each actual
 // indexed triangle. No material-name decision exists in these services.
 static std::string Material(VulkanRenderDevice*,const MaterialState& material,const Uniform&,const std::string&){return material.mMaterial->Payload;}
 static std::string SurfaceProbe(VulkanRenderDevice*,const Uniform&,int,bool){return Probe;}
#include "mesh_witness_access.inc"
};
namespace SdvkDiagnostics {
#include "mesh_witness_callback.inc"
}
int main(int argc,char** argv)try {
 if(argc!=3)throw std::runtime_error("fixture requires input and mode");
 std::ifstream input(argv[1]);std::string line;
 int first,type,side,sector,group,tile,epoch,atlas,owner,incarnation,slot,index0,index1;uint64_t meshOwner;
 input>>first>>type>>side>>sector>>group>>tile>>meshOwner>>epoch>>atlas>>owner>>incarnation>>slot>>index0>>index1;
 std::getline(input,line);std::getline(input,Context);
 MaterialService materials[2];
 for(auto& material:materials){std::getline(input,material.NameValue.Text);std::getline(input,material.Payload);}
 std::getline(input,Probe);
 LevelMesh mesh;mesh.Owner=meshOwner;mesh.Epoch=epoch;level.levelMesh=&mesh;level.sectors.resize(size_t(sector+1));
 for(int i=0;i<=sector;++i){level.sectors[size_t(i)].Number=i;level.sectors[size_t(i)].PortalGroup=group;}
 struct Side sideOwner{&level.sectors[size_t(sector)],side};struct Subsector sub{&level.sectors[size_t(sector)]};
 mesh.Semantic={type,side<0?41:side,side<0?nullptr:&sideOwner,side<0?&sub:nullptr,nullptr};
 mesh.Mesh.Vertices.resize(6);mesh.Mesh.UniformIndexes={};mesh.Mesh.UniformIndexes.resize(6);
 mesh.Mesh.Indexes.resize(size_t(first+6));mesh.Mesh.SurfaceIndexes.resize(size_t((first+6)/3));
 mesh.Mesh.Surfaces.resize(1);mesh.Mesh.Uniforms.resize(2);mesh.Mesh.Materials.resize(2);mesh.Mesh.LightUniforms.resize(2);
 auto& surface=mesh.Mesh.Surfaces[0];surface.MeshLocation.StartElementIndex=size_t(first);surface.LightmapTileIndex=tile;
 mesh.Lightmap.Tiles.resize(size_t(tile+1));auto& current=mesh.Lightmap.Tiles[size_t(tile)];
 current.AtlasLocation.Allocation={uint64_t(owner),uint64_t(incarnation),size_t(slot)};
 surface.Plane=type==4?FVector4{0,0,-1,-160}:group==1?FVector4{0,-1,0,-192}:FVector4{1,0,0,group==2?1024.0f:256.0f};
 const float a[6]{0,32,32,0,32,0},b[6]{0,0,160,0,160,160};
 for(int i=0;i<6;++i){auto& v=mesh.Mesh.Vertices[size_t(i)];
  if(type==4){v.x=a[i];v.y=b[i];v.z=160;current.Transform.ProjLocalToU={0.03125f,0,0};current.Transform.ProjLocalToV={0,0.03125f,0};}
  else if(group==1){v.x=a[i];v.y=192;v.z=b[i];current.Transform.ProjLocalToU={0.03125f,0,0};}
  else{v.x=group==2?1024.0f:256.0f;v.y=a[i];v.z=b[i];}
  const auto uv=current.ToUV(v.fPos(),1024);v.lu=uv.X;v.lv=uv.Y;
  mesh.Mesh.Indexes[size_t(first+i)]=i;mesh.Mesh.UniformIndexes[size_t(i)]=i/3;
 }
 mesh.Mesh.IndexCount=first+6;
 mesh.Mesh.Uniforms[0].uTextureIndex=index0;mesh.Mesh.Uniforms[1].uTextureIndex=index1;
 mesh.Mesh.Materials[0].mMaterial=&materials[0];mesh.Mesh.Materials[1].mMaterial=&materials[1];
 VulkanRenderDevice device;device.Mesh.Mesh=&mesh;device.Texture.Epoch=atlas;
 VkRenderState state;state.fb=&device;state.mPipelineKey.ColorMask=15;state.mPipelineKey.ShaderKey.UseLevelMesh=1;
 const std::string mode=argv[2];
 if(mode=="ordinary")FixtureEnabled=false;
 if(mode=="off")SdvkDiagnostics::StateFlag=false;
 if(mode=="unselected")Selected=false;
 if(mode=="depth")state.mPipelineKey.ShaderKey.NoFragmentShader=1;
 if(mode=="masked")state.mPipelineKey.ShaderKey.AlphaTestOnly=1;
 if(mode=="color-mask")state.mPipelineKey.ColorMask=0;
 SdvkDiagnostics::VulkanLevelMeshDraw(&state,first,6,type==4?LevelMeshDrawSurface::Flat:LevelMeshDrawSurface::Side);
 if(!Failure.empty())throw std::runtime_error(Failure);
 std::cout<<'[';for(size_t i=0;i<Records.size();++i){if(i)std::cout<<',';std::cout<<Records[i];}std::cout<<"]\n";
 return 0;
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 11;}
