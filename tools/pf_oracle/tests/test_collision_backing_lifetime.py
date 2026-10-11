"""Production CPU collision backing/reset regressions; never creates a renderer.

Forced legal TArray relocation quarantines old blocks. A pointer-generation
check stops triangle queries before stale storage is read; an input-span check
likewise stops an invalid BLAS construction before out-of-range pointer access.
"""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.test_collision_centroid_identity import block, PREFIX

FIXTURES = Path(__file__).resolve().parent / 'fixtures'
OLD = FIXTURES / 'collision_backing_lifetime_pre_fix.cpp'
SIGNATURES = ('CPUAccelStruct::CPUAccelStruct(', 'void CPUAccelStruct::Update()',
              'void LevelMesh::Reset()')

BACKING = r'''
#include <cstdint>
#include <cstring>
#include <functional>
#include <cfloat>
#include <memory>
#include <unordered_map>
#include <cstdlib>
#define NO_SSE
// Diagnostics/replay use the production no-op hook in extracted CPU fixtures.
#define SDVK_COLLISION_REPLAY_BUILD
#include "@TARRAY@"
#include "@CONTRACT@"
// realloc is permitted to move. Quarantine keeps old storage allocated so the
// fixture detects stale ownership without performing undefined-memory reads.
static std::unordered_map<void*,size_t> sizes;
static std::vector<void*> quarantine;
void* M_Malloc(size_t n) { void* p=std::malloc(n);assert(p);sizes[p]=n;return p; }
void* M_Realloc(void* p,size_t n) {
    void* q=M_Malloc(n);
    if(p) {std::memcpy(q,p,std::min(sizes.at(p),n));quarantine.push_back(p);sizes.erase(p);}
    return q;
}
void M_Free(void* p) {if(p) {sizes.erase(p);std::free(p);}}
void* M_Calloc(size_t n,size_t m) {void* p=M_Malloc(n*m);std::memset(p,0,n*m);return p;}
template<class... T> void I_FatalError(const char*,T...) {throw std::runtime_error("fatal");}
template<class... T> void Printf(const char*,T...) {}
'''

MESH = r'''
struct GeometryAllocInfo {int VertexStart=0,VertexCount=0,IndexStart=0,IndexCount=0;};
class MeshBufferUploads {
public:
    TArray<MeshBufferRange> Ranges;
    void Clear();void Add(int,int);
    const auto& GetRanges() const {return Ranges;}
};
class LevelMesh {
public:
    struct {
        TArray<int> Surfaces,Uniforms,LightUniforms,Materials,Lights,LightIndexes;
        TArray<uint8_t> DynLights;
        TArray<FFlatVertex> Vertices;
        TArray<int> UniformIndexes;
        TArray<unsigned int> Indexes;
        TArray<int> SurfaceIndexes;
        TArray<CollisionNode> Nodes;
        int IndexCount=0,RootNode=-1;
    } Mesh;
    struct {MeshBufferAllocator Vertex,Index,Uniforms,Surface,LightIndex,Light;} FreeLists;
    struct {
        MeshBufferUploads Vertex,UniformIndexes,Index,SurfaceIndex,Node,Portals;
        MeshBufferUploads Surface,Uniforms,LightUniforms,Light,LightIndex,DynLight;
    } UploadRanges;
    FRendererEpoch ResourceEpoch;
    LevelMeshMutationEpochs MutationEpochs;
    GeometryAllocInfo AllocGeometry(int,int);
    void Reset();
    void AddEmptyMesh();
    FFlatVertex* GetVertices(const GeometryAllocInfo& g) {return &Mesh.Vertices[g.VertexStart];}
    unsigned int* GetIndexes(const GeometryAllocInfo& g) {return &Mesh.Indexes[g.IndexStart];}
    void UploadPortals() {UploadRanges.Portals.Add(0,1);}
    void MarkMutation(LevelMeshMutationDomain) {}
};
struct Screen {bool IsRayQueryEnabled() const {return false;}} screenObject;
Screen* screen=&screenObject;
cycle_t DynamicBLASTime;
static constexpr int MAX_LIGHT_DATA=1;
struct FDynLightInfo {int value;};
static CPUAccelStruct* auditOwner;
static void queryPointerGuard(const CPUBottomLevelAccelStruct* b) {
    for(size_t i=0;i<auditOwner->DynamicBLAS.size();++i) {
        if(auditOwner->DynamicBLAS[i].get()!=b) continue;
        if(b->vertices!=auditOwner->Mesh->Mesh.Vertices.Data()) throw std::runtime_error("stale vertices");
        if(b->elements!=auditOwner->Mesh->Mesh.Indexes.Data()+i*auditOwner->IndexesPerBLAS) throw std::runtime_error("stale indexes");
        return;
    }
    throw std::runtime_error("missing BLAS owner");
}
static void checkedUpload(const void*,size_t) {}
// Exact production UploadRanges is adapted only at its byte-copy sink. Check
// the populated source span before invoking it, without skipping/clamping.
struct SourceSpan {const void* data;size_t bytes;};
static SourceSpan activeSpan;
void UploadData(void*,size_t,const void* p,size_t n,const char*) {
    const auto base=reinterpret_cast<uintptr_t>(activeSpan.data);
    const auto at=reinterpret_cast<uintptr_t>(p);
    if(at<base || at-base>activeSpan.bytes || n>activeSpan.bytes-(at-base))
        throw std::runtime_error("upload outside populated source extent");
    checkedUpload(p,n);
}
template<class T> void UploadRanges(const MeshBufferUploads&,const T*,void*,const char*);
template<class T> static bool uploadSpan(const MeshBufferUploads& ranges,const TArray<T>& data) {
    // Stop before even forming a pointer outside the populated source extent.
    for(const auto& r:ranges.GetRanges())
        if(r.Start<0 || r.End<r.Start || r.End>static_cast<int>(data.Size())) return false;
    activeSpan={data.Data(),data.Size()*sizeof(T)};
    try {UploadRanges(ranges,data.Data(),nullptr,"probe");return true;}
    catch(const std::runtime_error&) {return false;}
}
'''

POINTER_MAIN = r'''
static void initialize(LevelMesh& m,int verticesCapacity,int indexCapacity) {
    m.Mesh.Vertices.Resize(verticesCapacity);m.Mesh.UniformIndexes.Resize(verticesCapacity);
    m.Mesh.Indexes.Resize(indexCapacity);m.Mesh.SurfaceIndexes.Resize(indexCapacity/3+1);
    m.FreeLists.Vertex.Reset(verticesCapacity);m.FreeLists.Index.Reset(indexCapacity);
    const auto g=m.AllocGeometry(12,96);
    for(int i=0;i<g.VertexCount;++i) m.Mesh.Vertices[g.VertexStart+i].Set(float(i%3==1),0,float(i%3==2),0,0);
    for(int i=0;i<g.IndexCount;++i) m.Mesh.Indexes[g.IndexStart+i]=static_cast<unsigned>(i%3);
    m.UploadRanges.Index.Clear();m.UploadRanges.Vertex.Clear();
}
static std::vector<float> graph(const CPUBottomLevelAccelStruct& b) {
    std::vector<float> v{float(b.GetRoot())};
    for(const auto& n:b.GetNodes()) {
        v.insert(v.end(),{n.aabb.min.X,n.aabb.min.Y,n.aabb.min.Z,n.aabb.max.X,n.aabb.max.Y,n.aabb.max.Z,
            float(n.left),float(n.right),float(n.element_index)});
    }
    return v;
}
int main(int argc,char** argv) {
    assert(argc==3);int s=argv[1][0]-'0';assert(s>=0 && s<=6);const bool repaired=argv[2][0]=='1';
    const char* names[]={"unchanged","dirty-no-relocation","vertex-relocation","index-relocation",
        "both-relocations","full-repartition","vertex-only-no-index-dirty"};
    LevelMesh m;initialize(m,(s==2 || s==4 || s==5)?12:18,(s==3 || s==4 || s==5)?96:120);
    CPUAccelStruct a(&m);auditOwner=&a;
    std::vector<std::vector<float>> before;
    for(int i=0;i<a.InstanceCount;++i) before.push_back(graph(*a.DynamicBLAS[i]));
    const auto oldVertices=m.Mesh.Vertices.Data();const auto oldIndexes=m.Mesh.Indexes.Data();
    const auto oldPartition=a.IndexesPerBLAS;
    if(s==1) m.UploadRanges.Index.Add(0,3);
    else if(s==6) {m.Mesh.Vertices.Resize(100);m.UploadRanges.Vertex.Add(18,82);}
    else if(s>=2) {
        const auto g=m.AllocGeometry(3,s==5?180:3);
        for(int i=0;i<g.VertexCount;++i) m.Mesh.Vertices[g.VertexStart+i].Set(10.0f+float(i==1),0,float(i==2),0,0);
        for(int i=0;i<g.IndexCount;++i) m.Mesh.Indexes[g.IndexStart+i]=static_cast<unsigned>(g.VertexStart+i%3);
    }
    a.Update();
    int staleVertices=0,staleIndexes=0,live=0;
    for(int i=0;i<a.InstanceCount;++i) {
        const auto& b=a.DynamicBLAS[i];if(!b)continue;++live;
        staleVertices+=b->vertices!=m.Mesh.Vertices.Data();
        staleIndexes+=b->elements!=m.Mesh.Indexes.Data()+i*a.IndexesPerBLAS;
        if(repaired) assert(b->num_vertices==static_cast<int>(m.Mesh.Vertices.Size()));
        if(s!=5 && i<16) assert(graph(*b)==before[i]);
    }
    bool stopped=false;std::string reason="none";TraceHit hit;
    try {hit=a.FindFirstHit({0.2f,0.2f,-1},{0.2f,0.2f,1});}
    catch(const std::runtime_error& e) {stopped=true;reason=e.what();}
    std::cout<<"CASE "<<names[s]<<" repaired="<<repaired<<" vertex_relocated="<<(oldVertices!=m.Mesh.Vertices.Data())
        <<" index_relocated="<<(oldIndexes!=m.Mesh.Indexes.Data())<<" old_partition="<<oldPartition
        <<" partition="<<a.IndexesPerBLAS<<" live="<<live<<" stale_vertex_blas="<<staleVertices
        <<" stale_index_blas="<<staleIndexes<<" guarded_query_stop="<<stopped<<" reason="<<reason<<" hit="<<hit.triangle<<'\n';
    if(!repaired && (s==2 || s==3 || s==4 || s==6)) {
        assert(stopped);assert(staleVertices==(s==2 || s==4 || s==6?16:0));
        assert(staleIndexes==(s==3 || s==4?16:0));
    } else {assert(!stopped && staleVertices==0 && staleIndexes==0 && hit.triangle>=0);}
}
'''

RESET_MAIN = r'''
int main(int argc,char** argv) {
    assert(argc==3);int s=argv[1][0]-'0';assert(s>=0 && s<=3);const bool repaired=argv[2][0]=='1';
    LevelMesh m;
    // Execute production base constructor order: Reset -> AddEmptyMesh ->
    // CreateCollision, then DoomLevelMesh::SetLimits -> Reset -> real surfaces.
    m.Reset();m.AddEmptyMesh();CPUAccelStruct initial(&m);auditOwner=&initial;
    assert(m.Mesh.IndexCount==12 && m.UploadRanges.Index.GetRanges().Size()!=0);
    m.UploadRanges.Surface.Add(0,20);m.UploadRanges.Uniforms.Add(0,20);
    m.UploadRanges.LightUniforms.Add(0,20);m.UploadRanges.Light.Add(20000,1);
    m.UploadRanges.LightIndex.Add(0,20);m.UploadRanges.DynLight.Add(1000,1);
    m.UploadRanges.Node.Clear();m.UploadRanges.Node.Add(0,1);
    m.UploadRanges.Portals.Clear();m.UploadRanges.Portals.Add(0,1);
    if(s==3) {
        m.UploadRanges.Vertex.Clear();m.UploadRanges.Index.Clear();
        m.UploadRanges.UniformIndexes.Clear();m.UploadRanges.SurfaceIndex.Clear();
    }
    m.Reset();
    assert(m.Mesh.Indexes.Size()==0 && m.Mesh.Vertices.Size()==0);
    const int afterReset=m.Mesh.IndexCount;
    assert(m.UploadRanges.Node.GetRanges().Size()==1 && m.UploadRanges.Portals.GetRanges().Size()==1);
    if(repaired) {
        assert(afterReset==0);
        assert(m.UploadRanges.Surface.GetRanges().Size()==0 && m.UploadRanges.Uniforms.GetRanges().Size()==0);
        assert(m.UploadRanges.LightUniforms.GetRanges().Size()==0 && m.UploadRanges.Light.GetRanges().Size()==0);
        assert(m.UploadRanges.LightIndex.GetRanges().Size()==0 && m.UploadRanges.DynLight.GetRanges().Size()==0);
    }
    const int otherBadSpans=int(!uploadSpan(m.UploadRanges.Surface,m.Mesh.Surfaces))
        + int(!uploadSpan(m.UploadRanges.Uniforms,m.Mesh.Uniforms))
        + int(!uploadSpan(m.UploadRanges.LightUniforms,m.Mesh.LightUniforms))
        + int(!uploadSpan(m.UploadRanges.Light,m.Mesh.Lights))
        + int(!uploadSpan(m.UploadRanges.LightIndex,m.Mesh.LightIndexes))
        + int(!uploadSpan(m.UploadRanges.DynLight,m.Mesh.DynLights));
    assert(otherBadSpans==(repaired?0:6));
    if(s==1 || s==2) {
        auto g=m.AllocGeometry(s==1?3:12,s==1?3:12);
        for(int i=0;i<g.VertexCount;++i) m.Mesh.Vertices[i].Set(float(i%3==1),0,float(i%3==2),0,0);
        for(int i=0;i<g.IndexCount;++i) m.Mesh.Indexes[i]=static_cast<unsigned>(i%3);
    }
    const bool vertexSpan=uploadSpan(m.UploadRanges.Vertex,m.Mesh.Vertices);
    const bool indexSpan=uploadSpan(m.UploadRanges.Index,m.Mesh.Indexes);
    const bool uniformSpan=uploadSpan(m.UploadRanges.UniformIndexes,m.Mesh.UniformIndexes);
    const bool surfaceSpan=uploadSpan(m.UploadRanges.SurfaceIndex,m.Mesh.SurfaceIndexes);
    bool guarded=false;std::string reason="none";int hitTriangle=-1;
    try {CPUAccelStruct a(&m);auditOwner=&a;hitTriangle=a.FindFirstHit({0.2f,0.2f,-1},{0.2f,0.2f,1}).triangle;}
    catch(const std::runtime_error& e) {guarded=true;reason=e.what();}
    std::cout<<"CASE reset-"<<(s==0?"empty":s==1?"smaller":s==2?"same-size":"empty-clean-ranges")
        <<" repaired="<<repaired<<" after_reset_index_count="<<afterReset<<" rebuilt_index_count="<<m.Mesh.IndexCount
        <<" populated_indexes="<<m.Mesh.Indexes.Size()<<" guard="<<guarded<<" reason="<<reason
        <<" vertex_span="<<vertexSpan<<" index_span="<<indexSpan<<" uniform_span="<<uniformSpan
        <<" surface_span="<<surfaceSpan<<" other_bad_spans="<<otherBadSpans<<" hit="<<hitTriangle<<'\n';
    if(repaired) {
        assert(!guarded && vertexSpan && indexSpan && uniformSpan && surfaceSpan);
        assert((s==0 || s==3)?hitTriangle==-1:hitTriangle>=0);
    } else {
        assert(afterReset==12);
        if(s==2) assert(!guarded && vertexSpan && indexSpan && uniformSpan && surfaceSpan);
        else {assert(guarded);if(s!=3) assert(!vertexSpan && !indexSpan && !uniformSpan);}
    }
}
'''


def build_program(directory, repaired, mode):
    collision_path = ROOT/'src/common/rendering/hwrenderer/data/hw_collision.cpp'
    collision = collision_path.read_text()
    header = collision_path.with_suffix('.h').read_text()
    mesh_cpp = (ROOT/'src/common/rendering/hwrenderer/data/hw_levelmesh.cpp').read_text()
    mesh_h = (ROOT/'src/common/rendering/hwrenderer/data/hw_levelmesh.h').read_text()
    old = OLD.read_text()
    if not repaired:
        for sig in SIGNATURES[:2]:
            collision = collision.replace(block(collision, sig), block(old, sig))
        mesh_cpp = mesh_cpp.replace(block(mesh_cpp, SIGNATURES[2]), block(old, SIGNATURES[2]))
    vectors = PREFIX.replace('    FVector3& operator+=', '''    float Length() const {return std::sqrt(X*X+Y*Y+Z*Z);}
    FVector3 operator^(const FVector3& b) const {return {Y*b.Z-Z*b.Y,Z*b.X-X*b.Z,X*b.Y-Y*b.X};}
    FVector3& operator+=''' )
    backing = BACKING.replace('@TARRAY@', (ROOT/'src/common/utility/tarray.h').as_posix()).replace(
        '@CONTRACT@', (ROOT/'src/common/rendering/hwrenderer/data/hw_levelmesh_contract.h').as_posix())
    flat = (ROOT/'src/common/rendering/hwrenderer/data/flatvertices.h').read_text().replace('#pragma once','')
    declarations = '\n'.join(block(header, sig)+';' for sig in (
        'struct TraceHit\n','struct CollisionNode\n','class CollisionBBox\n','class RayBBox\n',
        'class AccelStructScratchBuffer\n','class CPUAccelStruct\n','class CPUBottomLevelAccelStruct\n','class IntersectionTest\n'))
    declarations = 'class LevelMesh;\nclass CPUBottomLevelAccelStruct;\n'+declarations.replace('private:', 'public:')
    functions = re.sub(r'^#include[^\n]*\n', '', collision, flags=re.M)
    query = 'float CPUBottomLevelAccelStruct::IntersectTriangleRay(const RayBBox &ray, int a, float &barycentricB, float &barycentricC)\n{'
    assert functions.count(query)==1
    functions = functions.replace(query, query+'\n\tqueryPointerGuard(this);')
    create = 'std::unique_ptr<CPUBottomLevelAccelStruct> CPUAccelStruct::CreateBLAS(int indexStart, int indexCount)\n{'
    assert functions.count(create)==1
    functions = functions.replace(create, create+'''
	if (indexStart<0 || indexCount<0 || indexStart>static_cast<int>(Mesh->Mesh.Indexes.Size()) || indexCount>static_cast<int>(Mesh->Mesh.Indexes.Size())-indexStart)
	{
		throw std::runtime_error("BLAS input outside populated index extent");
	}''')
    functions = functions.replace('extern cycle_t DynamicBLASTime;', '')
    mesh_functions = '\n'.join([block(mesh_h,'inline GeometryAllocInfo LevelMesh::AllocGeometry('),
        block(mesh_cpp,'void MeshBufferUploads::Clear()'),block(mesh_cpp,'void MeshBufferUploads::Add('),
        block(mesh_cpp,'void LevelMesh::Reset()')])
    # The unchanged production default mesh intentionally initializes position
    # only; C++ value-initializes its remaining aggregate fields to zero. Scope
    # this inherited GCC warning to that exact production function alone.
    empty_mesh = block(mesh_cpp,'void LevelMesh::AddEmptyMesh()')
    mesh_functions += '\n#if defined(__GNUC__)\n#pragma GCC diagnostic push\n#pragma GCC diagnostic ignored "-Wmissing-field-initializers"\n#endif\n'
    mesh_functions += empty_mesh
    mesh_functions += '\n#if defined(__GNUC__)\n#pragma GCC diagnostic pop\n#endif\n'
    uploader = block((ROOT/'src/common/rendering/vulkan/vk_levelmesh.cpp').read_text(),
        'void VkLevelMeshUploader::UploadRanges(').replace('void VkLevelMeshUploader::UploadRanges(', 'void UploadRanges(')
    uploader = 'template<typename T>\n'+uploader.replace('VulkanBuffer* destbuffer', 'void* destbuffer')
    # Exact legacy production source has unused subdivision locals and mixed
    # signed/count comparisons. Match the existing extracted collision fixtures.
    warning_start = '\n#ifdef _MSC_VER\n#pragma warning(push)\n#pragma warning(disable: 4189 4458 4018 4267 4244 4127)\n#else\n#pragma GCC diagnostic push\n#pragma GCC diagnostic ignored "-Wunused-variable"\n#pragma GCC diagnostic ignored "-Wsign-compare"\n#endif\n'
    warning_end = '\n#ifdef _MSC_VER\n#pragma warning(pop)\n#else\n#pragma GCC diagnostic pop\n#endif\n'
    unit = directory/f'{mode}-{int(repaired)}.cpp'
    unit.write_text(warning_start+vectors+backing+flat+declarations+MESH+mesh_functions+uploader+functions+
        warning_end+(POINTER_MAIN if mode=='pointer' else RESET_MAIN))
    return unit


def reproduce(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    runs = []
    for mode, cases in [('pointer',7),('reset',4)]:
        for repaired in [False,True]:
            unit = build_program(directory,repaired,mode)
            exe = compile_fixture(unit,output_dir=directory)
            for scenario in range(cases):
                result = subprocess.run([str(exe),str(scenario),str(int(repaired))],
                    capture_output=True,text=True,timeout=15,check=True)
                log = directory/f'{mode}-{int(repaired)}-{scenario}.log'
                log.write_text(result.stdout+result.stderr)
                runs.append({'mode':mode,'repaired':repaired,'scenario':scenario,'result':result.stdout.strip()})
    files = [{'path':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
             for p in sorted(directory.iterdir()) if p.is_file()]
    evidence = {'schema':'sdvk009-collision-backing-reset-cpu/v1','runs':runs,'files':files,
        'physical_fault_causality':False,'physical_resume_authorized':False,
        'limits':'Exact production scalar functions with pre-access guards, real TArray/allocation/range behavior and quarantined relocation. Vector/backend shape stubs. CPU upload source-span planning, no Vulkan device/submission/GPU execution or actual failed runtime graph.'}
    (directory/'evidence.json').write_text(json.dumps(evidence,indent=2))
    return evidence


class CollisionBackingLifetimeTests(unittest.TestCase):
    def test_original_negative_and_repaired_lifecycle(self):
        pins = json.loads((FIXTURES/'collision_backing_lifetime_pre_fix.json').read_text())
        source = OLD.read_text()
        for sig in SIGNATURES:
            self.assertEqual(hashlib.sha256(block(source,sig).encode()).hexdigest(),pins['functions'][sig])
        with tempfile.TemporaryDirectory(prefix='collision-backing-') as directory:
            evidence = reproduce(directory)
            self.assertEqual(len(evidence['runs']),22)


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--retain':
        result = reproduce(sys.argv[2])
        print(json.dumps({'scenarios':len(result['runs']),'path':str(Path(sys.argv[2]).resolve())}))
    else:
        unittest.main()
