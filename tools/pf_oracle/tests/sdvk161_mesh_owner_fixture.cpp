// Execute actual constructor/reset/owner allocator, with storage services only.
#include <atomic>
#include <iostream>
#include <limits>
#include <memory>
#include <new>
#include <stdexcept>
#include <string>
#include <thread>
#include <type_traits>
#include <vector>
#include "hw_levelmesh_contract.h"
#include "hw_sdvkdiagnosticcore.h"
[[noreturn]] void I_FatalError(const char* error){throw std::runtime_error(error);}
#include "mesh_owner_sequence.inc"
struct Array {
 size_t Count=0;void Clear(){Count=0;}void Resize(size_t count){Count=count;}
 size_t Size()const{return Count;}template<class T>void Push(T){++Count;}
};
struct RectPacker {RectPacker(int,int,int){}};
struct LevelMeshPortal{};struct FDynLightInfo{int Value;};
constexpr int MAX_LIGHT_DATA=8;
class LevelMesh {
public:
 LevelMesh();virtual ~LevelMesh()=default;void Reset();
#include "mesh_owner_getter.inc"
#include "mesh_owner_mutations.inc"
 FRendererEpochToken GetResourceEpoch()const{return ResourceEpoch.Snapshot();}
 void AddEmptyMesh(){}void CreateCollision(){}
 struct {int TextureSize=1024;std::unique_ptr<RectPacker> AtlasPacker;}Lightmap;
 Array Portals;
 struct {Array Vertices,UniformIndexes,Surfaces,Uniforms,LightUniforms,Materials,Lights,LightIndexes,DynLights,Indexes,SurfaceIndexes;int IndexCount=0;}Mesh;
 struct {Array Vertex,UniformIndexes,Index,SurfaceIndex,Surface,Uniforms,LightUniforms,Light,LightIndex,DynLight;}UploadRanges;
 struct {MeshBufferAllocator Vertex,Index,Uniforms,Surface,LightIndex,Light;}FreeLists;
private:
#include "mesh_owner_member.inc"
 FRendererEpoch ResourceEpoch;
 LevelMeshMutationEpochs MutationEpochs;
};
#include "mesh_owner_constructor.inc"
#include "mesh_owner_reset.inc"
// Actual resource builder consumes only these explicit lifecycle services here.
static bool Special=false;
static bool SpecialSurfaceEnabled(){return Special;}
static std::string LightmapLifecycle(LevelMesh*,size_t,int,int){return "{}";}
struct ResourceTextures {std::vector<int> Lightmaps{0};};
struct ResourceDevice {int GetFrameTileUpdates(){return 0;}int GetFrameTileCompletions(){return 0;}};
static std::string ResourceState(LevelMesh* mesh,bool original=false){
 using namespace SdvkObservation;
 struct {LevelMesh* levelMesh;}level{mesh};
 ResourceTextures texturesValue;auto textures=&texturesValue;
 ResourceDevice deviceValue;auto device=&deviceValue;
 Object result;
 if(original){
#include "mesh_owner_resource_original.inc"
 }else{
#include "mesh_owner_resource.inc"
 }
 return result.Json();
}
static void Check(bool good,const char* error){if(!good)throw std::runtime_error(error);}
int main(int argc,char** argv){try{
 static_assert(!std::is_copy_constructible<LevelMesh>::value,"mesh owners cannot copy");
 static_assert(!std::is_move_constructible<LevelMesh>::value,"mesh owners cannot move");
 if(argc>1&&std::string(argv[1])=="serialization"){
  LevelMesh first,other;first.Reset();other.Reset();
  using namespace SdvkObservation;
  Object value;Special=false;
  value.Str("original_json",ResourceState(&first,true)).Str("ordinary_json",ResourceState(&first)).Str("other_ordinary_json",ResourceState(&other));
  Special=true;value.Str("special_json",ResourceState(&first)).Str("other_special_json",ResourceState(&other));
  std::cout<<value.Json()<<'\n';
 }else if(argc>1&&std::string(argv[1])=="exhaustion"){
  LevelMeshOwnerSequence.store(std::numeric_limits<uint64_t>::max()-1);
  LevelMesh last;Check(last.GetResourceOwner()==std::numeric_limits<uint64_t>::max(),"last identity missing");
  for(int i=0;i<2;++i){bool rejected=false;try{LevelMesh exhausted;}catch(const std::runtime_error& error){rejected=std::string(error.what())=="LevelMesh owner identity exhausted";}Check(rejected,"exhaustion wrapped/reused");}
  std::cout<<"PASS exhausted constructor identity fails closed without wrapping\n";
 }else{
  alignas(LevelMesh) unsigned char storage[sizeof(LevelMesh)];
  auto first=new(storage)LevelMesh;first->Reset();const auto oldOwner=first->GetResourceOwner();const auto oldEpoch=first->GetResourceEpoch();
  Check(oldOwner>0&&oldEpoch.Generation==3,"first production epoch");
  for(int i=0;i<128;++i){first->Mesh.IndexCount=17;first->Mesh.Vertices.Resize(8);first->Reset();Check(first->GetResourceOwner()==oldOwner&&first->Mesh.IndexCount==0&&first->Mesh.Vertices.Size()==0,"reset changed owner or skipped production reset");}
  first->~LevelMesh();auto second=new(storage)LevelMesh;second->Reset();
  Check(second->GetResourceEpoch().Generation==oldEpoch.Generation,"local epoch no longer repeats normally");
  Check(second->GetResourceOwner()>oldOwner,"same-address owner reused");second->~LevelMesh();
  std::vector<std::vector<uint64_t>> owners(8);std::vector<std::thread> workers;
  for(size_t i=0;i<owners.size();++i)workers.emplace_back([&,i]{for(int n=0;n<64;++n){LevelMesh mesh;owners[i].push_back(mesh.GetResourceOwner());}});
  for(auto& worker:workers)worker.join();
  std::set<uint64_t> unique;
  for(auto& part:owners)for(auto owner:part)Check(owner>oldOwner&&unique.insert(owner).second,"concurrent constructor owner reused");
  Check(unique.size()==512,"constructor count");
  std::cout<<"PASS same-address epoch3 negative / 128 ordinary resets / 512 concurrent constructor identities\n";
 }
 return 0;
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}}
