"""Execute exact production sparse TLAS construction/export on CPU only.

Checked containers/BLAS handles and graph walkers stop before invalid accesses.
No renderer, Vulkan, or undefined-memory reproduction is involved.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.test_collision_upload_root import production_function
from tools.pf_oracle.tests.test_collision_centroid_identity import PREFIX as VECTOR_PREFIX

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SIGNATURES = ["static FVector3 SwapYZ(", "void CPUAccelStruct::Upload()",
              "void CPUAccelStruct::CreateTLAS()", "int CPUAccelStruct::Subdivide(",
              "TraceHit CPUAccelStruct::FindFirstHit(const FVector3&"]

PREFIX = VECTOR_PREFIX + r'''
#include <memory>
#include <sstream>
#include <string>
struct Guard : std::runtime_error { using std::runtime_error::runtime_error; };
template<class T> struct Array : std::vector<T> {
    int size() const { return static_cast<int>(std::vector<T>::size()); }
    unsigned Size() const { return static_cast<unsigned>(size()); }
    void Resize(unsigned n) { this->resize(n); }
    T& operator[](size_t i) {
        if (i>=std::vector<T>::size()) throw Guard("container bounds");
        return std::vector<T>::operator[](i);
    }
    const T& operator[](size_t i) const {
        if (i>=std::vector<T>::size()) throw Guard("container bounds");
        return std::vector<T>::operator[](i);
    }
};
struct CollisionBBox {
    FVector3 min, max, Center, Extents;
    CollisionBBox(FVector3 lo={}, FVector3 hi={}) : min(lo),max(hi),
        Center((lo+hi)*0.5f),Extents((hi-lo)*0.5f) {}
};
struct CollisionNode {
    FVector3 center, extents;
    int left=-1, right=-1, element_index=-1;
};
struct BlasNode {
    CollisionBBox aabb;
    int left=-1, right=-1, element_index=-1;
};
struct Blas {
    CollisionBBox bbox;
    Array<BlasNode> nodes;
    int root=0;
    const auto& GetNodes() const { return nodes; }
    int GetRoot() const { return root; }
    const CollisionBBox& GetBBox() const { return bbox; }
};
struct BlasHandle {
    std::unique_ptr<Blas> value;
    explicit operator bool() const { return static_cast<bool>(value); }
    Blas* operator->() const {
        if (!value) throw Guard("null BLAS access");
        return value.get();
    }
};
struct UploadRange {
    int start=-1,count=-1;
    void Clear() { start=count=-1; }
    void Add(int s,int c) { start=s;count=c; }
};
struct LevelMesh {
    struct { Array<CollisionNode> Nodes; int RootNode=-99; } Mesh;
    struct { UploadRange Node; } UploadRanges;
};
struct Screen { bool IsRayQueryEnabled() const { return false; } } screenObject;
Screen* screen=&screenObject;
struct TraceHit { float fraction=1; int triangle=-1; float b=0,c=0; };
class RayBBox { public: RayBBox(const FVector3&, const FVector3&) {} };
struct CPUAccelStruct {
    struct Node {
        CollisionBBox aabb;
        int left=-1,right=-1,blas_index=-1;
        Node(FVector3 lo,FVector3 hi,int slot):aabb(lo,hi),blas_index(slot) {}
        Node(FVector3 lo,FVector3 hi,int l,int r):aabb(lo,hi),left(l),right(r) {}
    };
    LevelMesh mesh;
    LevelMesh* Mesh=&mesh;
    struct { Array<Node> Nodes; int Root=-1; } TLAS;
    Array<BlasHandle> DynamicBLAS;
    int IndexesPerBLAS=12,InstanceCount=0;
    struct {
        std::vector<int> leafs,workbuffer;
        std::vector<FVector4> centroids;
    } Scratch;
    int queryCalls=0;
    void Upload();
    void CreateTLAS();
    int Subdivide(int*,int,const FVector4*,int*);
    TraceHit FindFirstHit(const FVector3&,const FVector3&);
    void FindFirstHit(const RayBBox&,int i,TraceHit*) {
        ++queryCalls;
        (void)TLAS.Nodes[static_cast<size_t>(i)];
    }
};
'''

SUFFIX = r'''
static void setup(CPUAccelStruct& a,int scenario,std::vector<int>& expected) {
    a.InstanceCount=scenario==5?0:3;
    a.DynamicBLAS.resize(5); // capacity beyond occupied slots is normally null
    for (int i=0;i<a.InstanceCount;++i) {
        const bool absent=scenario==3 || (scenario==1 && i==0)
            || (scenario==2 && i==1) || (scenario==4 && i==2)
            || (scenario==6 && i!=2);
        if (absent) continue;
        auto b=std::make_unique<Blas>();
        b->bbox=CollisionBBox({20.0f*i,0,0},{20.0f*i+2,2,2});
        BlasNode first,second,root;
        first.aabb=second.aabb=root.aabb=b->bbox;
        first.element_index=3;second.element_index=6;
        root.left=0;root.right=1;
        b->nodes.push_back(first);b->nodes.push_back(second);b->nodes.push_back(root);
        b->root=2; // never assume BLAS root zero
        a.DynamicBLAS[i].value=std::move(b);
        expected.push_back(i);
    }
    // Exercise reused scratch, distinct from populated extent.
    a.Scratch.centroids.resize(9,FVector4(777,777,777,777));
}
static void validateTLAS(const CPUAccelStruct& a,const std::vector<int>& expected) {
    if (expected.empty()) {
        if (a.TLAS.Root!=-1 || !a.TLAS.Nodes.empty()) throw Guard("nonempty TLAS");
        return;
    }
    std::vector<int> pending{a.TLAS.Root},seen,found;
    while (!pending.empty()) {
        const int i=pending.back();pending.pop_back();
        if (i<0 || i>=a.TLAS.Nodes.size()) throw Guard("TLAS link bounds");
        if (std::find(seen.begin(),seen.end(),i)!=seen.end()) throw Guard("TLAS cycle");
        seen.push_back(i);
        const auto& n=a.TLAS.Nodes[i];
        if (n.blas_index!=-1) {
            if (!a.DynamicBLAS[n.blas_index]) throw Guard("absent TLAS member");
            found.push_back(n.blas_index);
        } else { pending.push_back(n.left);pending.push_back(n.right); }
    }
    std::sort(found.begin(),found.end());
    if (found!=expected) throw Guard("TLAS membership mismatch");
    for (int i:expected) {
        if (static_cast<size_t>(i)>=a.Scratch.centroids.size()) throw Guard("centroid bounds");
        const auto& c=a.Scratch.centroids[i];
        const auto& center=a.DynamicBLAS[i]->GetBBox().Center;
        if (c.X!=center.X || c.Y!=center.Y || c.Z!=center.Z || c.W!=1)
            throw Guard("centroid identity mismatch");
    }
}
static void independentTLAS(CPUAccelStruct& a,const std::vector<int>& expected) {
    for (int slot:expected) {
        a.TLAS.Nodes.push_back(CPUAccelStruct::Node({}, {}, slot));
        if (a.TLAS.Root==-1) a.TLAS.Root=0;
        else {
            const int leaf=a.TLAS.Nodes.size()-1;
            a.TLAS.Nodes.push_back(CPUAccelStruct::Node({}, {}, a.TLAS.Root,leaf));
            a.TLAS.Root=a.TLAS.Nodes.size()-1;
        }
    }
}
static void validateExport(const CPUAccelStruct& a,const std::vector<int>& expected,bool repaired) {
    if (expected.empty()) {
        if (a.mesh.Mesh.RootNode!=-1 || a.mesh.UploadRanges.Node.count!=(repaired?1:0))
            throw Guard("nonempty export");
        if (repaired) {
            const auto& d=a.mesh.Mesh.Nodes[0];
            assert(d.left==-1 && d.right==-1 && d.element_index==-1);
            assert(d.center.X==0 && d.center.Y==0 && d.center.Z==0);
            assert(d.extents.X==0 && d.extents.Y==0 && d.extents.Z==0);
        }
        return;
    }
    std::vector<int> pending{a.mesh.Mesh.RootNode},seen,found,want;
    for (int slot:expected) { want.push_back(slot*12+3);want.push_back(slot*12+6); }
    while (!pending.empty()) {
        int i=pending.back();pending.pop_back();
        if (i<0 || i>=a.mesh.UploadRanges.Node.count) throw Guard("export link bounds");
        if (std::find(seen.begin(),seen.end(),i)!=seen.end()) throw Guard("export cycle/alias");
        seen.push_back(i);
        const auto& n=a.mesh.Mesh.Nodes[i];
        if (n.element_index!=-1) found.push_back(n.element_index);
        else { pending.push_back(n.left);pending.push_back(n.right); }
    }
    std::sort(found.begin(),found.end());
    if (found!=want) throw Guard("original triangle offsets mismatch");
}
int main(int argc,char** argv) {
    assert(argc==4);
    const int scenario=argv[1][0]-'0';
    const bool repaired=argv[2][0]=='1';
    const char mode=argv[3][0];
    const char* names[]={"no-hole","leading-null","interior-null","all-null",
                         "trailing-null","zero-instances","only-slot2"};
    assert(scenario>=0 && scenario<=6);
    CPUAccelStruct actual;
    std::vector<int> expected;
    setup(actual,scenario,expected);
    bool blocked=false;
    std::string reason="none";
    try {
        if (mode=='e') independentTLAS(actual,expected);
        else {
            actual.CreateTLAS();validateTLAS(actual,expected);
            if (repaired) {
                assert(actual.Scratch.centroids.size()==static_cast<size_t>(actual.InstanceCount));
                for (int i=0;i<actual.InstanceCount;++i) {
                    if (actual.DynamicBLAS[i]) continue;
                    const auto& c=actual.Scratch.centroids[i];
                    assert(c.X==0 && c.Y==0 && c.Z==0 && c.W==0);
                }
            }
        }
        if (mode=='e' || mode=='c') {
            actual.Upload();
            // Verify copied original element offsets independently of traversal.
            // An invalid TLAS link must not mask the separate compressed-offset defect.
            int offset=actual.TLAS.Nodes.size(),wrongOffsets=0;
            for (int slot:expected) {
                for (const auto& n:actual.DynamicBLAS[slot]->GetNodes()) {
                    if (n.element_index!=-1 && actual.mesh.Mesh.Nodes[offset].element_index
                        !=slot*actual.IndexesPerBLAS+n.element_index) ++wrongOffsets;
                    ++offset;
                }
            }
            const int oldWrong=scenario==1?4:((scenario==2 || scenario==6)?2:0);
            assert(wrongOffsets==(repaired?0:oldWrong));
            std::cout << "EXPORTED wrong_original_offsets=" << wrongOffsets << '\n';
            validateExport(actual,expected,repaired);
        }
        if (mode=='q') {
            const TraceHit h=actual.FindFirstHit(FVector3(),FVector3(1,0,0));
            assert(h.fraction==1 && h.triangle==-1 && h.b==0 && h.c==0);
            assert(actual.queryCalls==(expected.empty()?0:1));
        }
    } catch (const Guard& error) { blocked=true;reason=error.what(); }
    const bool oldFailure=mode=='e' ? (scenario==1 || scenario==2 || scenario==6)
        : (scenario==1 || scenario==2 || scenario==3 || scenario==4 || scenario==6
           || (mode=='q' && scenario==5));
    assert(blocked==(!repaired && oldFailure));
    std::cout << names[scenario] << " mode=" << mode << " repaired=" << repaired
        << " guarded_stop=" << blocked << " reason=" << reason << '\n';
    if (!blocked) {
        std::ostringstream snapshot;
        snapshot << actual.TLAS.Root << ':' << actual.mesh.Mesh.RootNode << ':';
        for (const auto& n:actual.TLAS.Nodes)
            snapshot << n.blas_index << ',' << n.left << ',' << n.right << ','
                << n.aabb.Center.X << ',' << n.aabb.Center.Y << ',' << n.aabb.Center.Z << ','
                << n.aabb.Extents.X << ',' << n.aabb.Extents.Y << ',' << n.aabb.Extents.Z << ';';
        snapshot << '|';
        for (int i=0;i<actual.mesh.UploadRanges.Node.count;++i) {
            const auto& n=actual.mesh.Mesh.Nodes[i];
            snapshot << n.element_index << ',' << n.left << ',' << n.right << ','
                << n.center.X << ',' << n.center.Y << ',' << n.center.Z << ','
                << n.extents.X << ',' << n.extents.Y << ',' << n.extents.Z << ';';
        }
        std::cout << "SNAPSHOT " << snapshot.str() << '\n';
    }
}
'''

WARNING_BEGIN = r'''
#ifdef _MSC_VER
#pragma warning(push)
#pragma warning(disable: 4458)
#endif
'''
WARNING_END = r'''
#ifdef _MSC_VER
#pragma warning(pop)
#endif
'''


def extracted(source):
    return "\n\n".join(production_function(source, s) for s in SIGNATURES)


def reproduce(directory):
    """Retain generated CPU units, binaries and individual logical-check logs."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    old = (FIXTURES / "collision_sparse_slots_pre_fix.cpp").read_text()
    current = (ROOT / "src/common/rendering/hwrenderer/data/hw_collision.cpp").read_text()
    results = []
    for repaired, functions in ((False, extracted(old)), (True, extracted(current))):
        unit = directory / f"sparse_{int(repaired)}.cpp"
        unit.write_text(PREFIX + WARNING_BEGIN + functions + WARNING_END + SUFFIX)
        exe = compile_fixture(unit, output_dir=directory)
        for mode in ("membership", "export", "combined", "query"):
            for scenario in range(7):
                result = subprocess.run([str(exe), str(scenario), str(int(repaired)), mode],
                                        text=True, capture_output=True, timeout=10)
                (directory / f"{int(repaired)}-{mode}-{scenario}.log").write_text(
                    result.stdout + result.stderr)
                results.append(dict(repaired=repaired, mode=mode, scenario=scenario,
                                    returncode=result.returncode, stdout=result.stdout))
    (directory / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    return results


class CollisionSparseSlotsTests(unittest.TestCase):
    def test_retained_original_and_repaired_production(self):
        evidence = json.loads((FIXTURES / "collision_sparse_slots_evidence.json").read_text())
        old = (FIXTURES / "collision_sparse_slots_pre_fix.cpp").read_text()
        self.assertEqual(hashlib.sha256(old.encode()).hexdigest(), evidence["retained_sha256"])
        with tempfile.TemporaryDirectory() as directory:
            results = reproduce(directory)
        for result in results:
            with self.subTest(**{k: result[k] for k in ("repaired", "mode", "scenario")}):
                self.assertEqual(result["returncode"], 0, result["stdout"])
                self.assertIn("guarded_stop=", result["stdout"])
        for mode in ("membership", "export", "combined", "query"):
            snapshots = [r["stdout"].split("SNAPSHOT ", 1)[1] for r in results
                         if r["scenario"] == 0 and r["mode"] == mode]
            self.assertEqual(len(snapshots), 2)
            self.assertEqual(*snapshots, f"no-hole {mode} graph changed")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--retain":
        outcomes = reproduce(Path(sys.argv[2]).resolve())
        raise SystemExit(0 if all(r["returncode"] == 0 for r in outcomes) else 1)
    unittest.main()
