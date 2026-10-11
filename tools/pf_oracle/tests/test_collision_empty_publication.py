"""CPU-only empty-root publication through exact range and uploader functions."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.test_collision_upload_root import PREFIX, production_function

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).resolve().parent / "fixtures"

RANGES = r'''
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <iostream>
struct MeshBufferRange { int Start,End; int Count() const { return End-Start; } };
template<class T> struct RangeArray : Array<T> {
    void Clear() { this->clear(); }
    void Insert(std::ptrdiff_t i,const T& value) { this->insert(this->begin()+i,value); }
    void Delete(std::ptrdiff_t i,std::ptrdiff_t count) { this->erase(this->begin()+i,this->begin()+i+count); }
};
struct MeshBufferUploads {
    RangeArray<MeshBufferRange> Ranges;
    const auto& GetRanges() const { return Ranges; }
    void Clear();void Add(int,int);
};
struct LevelMesh {
    struct { Array<CollisionNode> Nodes; int RootNode=-99; } Mesh;
    struct {
        MeshBufferUploads Node,Vertex,UniformIndexes,Index,SurfaceIndex,Surface,Uniforms,
            LightUniforms,Portals,LightIndex,Light,DynLight;
    } UploadRanges;
};
'''

UPLOADER = r'''
struct VulkanBuffer {};
using FFlatVertex=int;
using SurfaceInfo=int;
using SurfaceUniforms=int;
using SurfaceLightUniforms=int;
using PortalInfo=int;
using LightInfo=int;
struct VkLevelMesh {
    bool useRayQuery=false;
    LevelMesh* Mesh=nullptr;
    std::unique_ptr<VulkanBuffer> NodeBuffer=std::make_unique<VulkanBuffer>();
};
struct VkLevelMeshUploader {
    VkLevelMesh* Mesh;
    int publishedRoot=137,headers=0,nodeWrites=0;
    size_t bytes=0;
    void UploadNodes();size_t GetTransferSize();
    void UploadData(VulkanBuffer*,size_t offset,const void* src,size_t size,const char*) {
        assert(src && size>0);
        if (offset==0) {
            assert(size==sizeof(CollisionNodeBufferHeader));
            std::memcpy(&publishedRoot,src,sizeof(publishedRoot));++headers;
        } else {
            assert(offset>=sizeof(CollisionNodeBufferHeader));
            assert((offset-sizeof(CollisionNodeBufferHeader))%sizeof(CollisionNode)==0);
            assert(size%sizeof(CollisionNode)==0);
            const size_t first=(offset-sizeof(CollisionNodeBufferHeader))/sizeof(CollisionNode);
            assert(first+size/sizeof(CollisionNode)<=Mesh->Mesh->Mesh.Nodes.Size());
            nodeWrites+=static_cast<int>(size/sizeof(CollisionNode));
        }
        bytes+=size;
    }
    void Publish() {
        const size_t planned=GetTransferSize();
        const size_t before=bytes;
        // The exact uploader Upload returns before UploadNodes when size is zero.
        if (planned!=0) UploadNodes();
        assert(bytes-before==planned);
        Mesh->Mesh->UploadRanges.Node.Clear();
    }
};
'''

SUFFIX = r'''
static void live(CPUAccelStruct& cpu) {
    TlasNode root;root.blas_index=0;
    cpu.TLAS.Nodes.push_back(root);cpu.TLAS.Root=0;
    auto blas=std::make_unique<Blas>();
    BlasNode leaf;leaf.element_index=3;
    blas->nodes.push_back(leaf);cpu.DynamicBLAS.push_back(std::move(blas));
}
static void empty(CPUAccelStruct& cpu) {
    cpu.TLAS.Nodes.clear();cpu.TLAS.Root=-1;cpu.DynamicBLAS.clear();
}
int main(int argc,char** argv) {
    assert(argc==3);
    const bool repaired=argv[1][0]=='1';
    const int scenario=argv[2][0]-'0';
    assert(scenario>=0 && scenario<=3);
    CPUAccelStruct cpu;
    VkLevelMesh mesh;mesh.Mesh=&cpu.mesh;
    VkLevelMeshUploader upload{&mesh};
    // Prove the actual production range semantics, unlike a zero-count recording stub.
    cpu.mesh.UploadRanges.Node.Add(0,0);
    assert(cpu.mesh.UploadRanges.Node.GetRanges().Size()==0);
    if (scenario==1 || scenario==3) {
        live(cpu);cpu.Upload();upload.Publish();
        assert(upload.publishedRoot==1 && upload.headers==1 && upload.nodeWrites==2);
        assert(upload.bytes==sizeof(CollisionNodeBufferHeader)+2*sizeof(CollisionNode));
        empty(cpu);
    }
    if (scenario==3) mesh.useRayQuery=true;
    cpu.Upload();
    if (scenario==2) {
        // Initial empty followed by live then empty verifies both publication directions.
        upload.Publish();
        assert(upload.publishedRoot==(repaired?-1:137));
        live(cpu);cpu.Upload();upload.Publish();assert(upload.publishedRoot==1);
        empty(cpu);cpu.Upload();
    }
    const int oldRoot=upload.publishedRoot;
    const int oldHeaders=upload.headers;
    const size_t planned=upload.GetTransferSize();
    if (scenario==3) assert(planned==0);
    else assert(planned==(repaired?sizeof(CollisionNodeBufferHeader)+sizeof(CollisionNode):0));
    upload.Publish();
    assert(upload.publishedRoot==((repaired && scenario!=3)?-1:oldRoot));
    assert(upload.headers==oldHeaders+((repaired && scenario!=3)?1:0));
    if (repaired) {
        assert(cpu.mesh.Mesh.RootNode==-1);
        const auto& dummy=cpu.mesh.Mesh.Nodes[0];
        assert(dummy.left==-1 && dummy.right==-1 && dummy.element_index==-1);
        assert(dummy.center.X==0 && dummy.center.Y==0 && dummy.center.Z==0);
        assert(dummy.extents.X==0 && dummy.extents.Y==0 && dummy.extents.Z==0);
    }
    std::cout << "scenario=" << scenario << " repaired=" << repaired
        << " cpuRoot=" << cpu.mesh.Mesh.RootNode << " publishedRoot=" << upload.publishedRoot
        << " planned=" << planned << " headers=" << upload.headers << '\n';
}
'''


class CollisionEmptyPublicationTests(unittest.TestCase):
    def test_real_zero_ranges_and_empty_header_publication(self):
        level = (ROOT / "src/common/rendering/hwrenderer/data/hw_levelmesh.cpp").read_text()
        vulkan = (ROOT / "src/common/rendering/vulkan/vk_levelmesh.cpp").read_text()
        header = (ROOT / "src/common/rendering/vulkan/vk_levelmesh.h").read_text()
        collision_header = (ROOT / "src/common/rendering/hwrenderer/data/hw_collision.h").read_text()
        prefix = PREFIX.replace(PREFIX[PREFIX.index("struct UploadRange {"):
                                      PREFIX.index("struct Screen {")], RANGES)
        # Use the actual CPU/shader ABI node/header member definitions.
        start = prefix.index("struct CollisionNode {")
        end = prefix.index("struct BlasNode {", start)
        prefix = prefix[:start] + production_function(collision_header, "struct CollisionNode\n") + ";\n" + prefix[end:]
        common = "\n".join(production_function(level, s) for s in (
            "void MeshBufferUploads::Clear()", "void MeshBufferUploads::Add("))
        common += "\n" + production_function(header, "struct CollisionNodeBufferHeader\n") + ";\n" + UPLOADER
        common += "\n" + "\n".join(production_function(vulkan, s) for s in (
            "void VkLevelMeshUploader::UploadNodes()", "size_t VkLevelMeshUploader::GetTransferSize()"))
        old = (FIXTURES / "collision_sparse_slots_pre_fix.cpp").read_text()
        current = (ROOT / "src/common/rendering/hwrenderer/data/hw_collision.cpp").read_text()
        with tempfile.TemporaryDirectory() as directory:
            for repaired, source in ((False, old), (True, current)):
                actual = "\n".join(production_function(source, s) for s in (
                    "static FVector3 SwapYZ(", "void CPUAccelStruct::Upload()"))
                unit = Path(directory) / f"publication_{int(repaired)}.cpp"
                unit.write_text(prefix + common + actual + SUFFIX)
                exe = compile_fixture(unit, output_dir=directory)
                for scenario in range(4):
                    with self.subTest(repaired=repaired, scenario=scenario):
                        subprocess.run([str(exe), str(int(repaired)), str(scenario)],
                                       check=True, capture_output=True, text=True, timeout=10)


if __name__ == "__main__":
    unittest.main()
