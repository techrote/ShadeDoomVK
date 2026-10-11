"""Execute the production CPU-to-shader collision export without a GPU."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle.fixture_runner import run_fixture


def production_function(source: str, signature: str) -> str:
    start = source.index(signature)
    begin = source.index("{", start)
    depth = 0
    for offset in range(begin, len(source)):
        depth += (source[offset] == "{") - (source[offset] == "}")
        if depth == 0:
            return source[start:offset + 1]
    raise AssertionError("unterminated production function")


PREFIX = r'''
#include <cassert>
#include <memory>
#include <vector>
template<class T> struct Array : std::vector<T> {
    int size() const { return static_cast<int>(std::vector<T>::size()); }
    unsigned Size() const { return static_cast<unsigned>(size()); }
    void Resize(unsigned count) { this->resize(count); }
};
struct FVector3 {
    float X, Y, Z;
    FVector3(float x = 0, float y = 0, float z = 0) : X(x), Y(y), Z(z) {}
};
struct Bounds { FVector3 Center, Extents; };
struct CollisionNode {
    FVector3 center, extents;
    int left = -1, right = -1, element_index = -1;
};
struct BlasNode {
    Bounds aabb;
    int left = -1, right = -1, element_index = -1;
};
struct Blas {
    Array<BlasNode> nodes;
    int root = 0;
    const Array<BlasNode>& GetNodes() const { return nodes; }
    int GetRoot() const { return root; }
};
struct TlasNode {
    Bounds aabb;
    int left = -1, right = -1, blas_index = -1;
};
struct UploadRange {
    int start = -1, count = -1;
    void Clear() { start = count = -1; }
    void Add(int s, int c) { start = s; count = c; }
};
struct LevelMesh {
    struct MeshData { Array<CollisionNode> Nodes; int RootNode = -99; } Mesh;
    struct Ranges { UploadRange Node; } UploadRanges;
};
struct Screen { bool IsRayQueryEnabled() const { return false; } } screenObject;
Screen* screen = &screenObject;
struct CPUAccelStruct {
    LevelMesh mesh;
    LevelMesh* Mesh = &mesh;
    struct { Array<TlasNode> Nodes; int Root = -1; } TLAS;
    Array<std::unique_ptr<Blas>> DynamicBLAS;
    int IndexesPerBLAS = 12;
    void Upload();
};
'''

SUFFIX = r'''
std::unique_ptr<Blas> leaf(int element) {
    auto result = std::make_unique<Blas>();
    BlasNode node;
    node.element_index = element;
    result->nodes.push_back(node);
    return result;
}
std::vector<int> reachableTriangles(const LevelMesh& mesh) {
    std::vector<int> pending{mesh.Mesh.RootNode}, triangles;
    int visits = 0;
    while (!pending.empty()) {
        const int index = pending.back();
        pending.pop_back();
        // The shader indexes these nodes directly; reject bad links before
        // the CPU fixture dereferences them or a renderer can reach a GPU.
        assert(index >= 0 && index < mesh.UploadRanges.Node.count);
        assert(++visits <= mesh.UploadRanges.Node.count);
        const auto& node = mesh.Mesh.Nodes[index];
        if (node.element_index != -1) triangles.push_back(node.element_index);
        else {
            pending.push_back(node.right);
            pending.push_back(node.left);
        }
    }
    return triangles;
}
int main(int argc, char** argv) {
    assert(argc == 2);
    const int scenario = argv[1][0] - '0';
    CPUAccelStruct actual;
    if (scenario == 1 || scenario == 2) {
        TlasNode root;
        root.blas_index = 0;
        actual.TLAS.Nodes.push_back(root);
        actual.TLAS.Root = 0;
        auto blas = leaf(3);
        if (scenario == 2) {
            // Root need not be BLAS node zero: preserve every triangle.
            blas->nodes.push_back(BlasNode{});
            blas->nodes.push_back(BlasNode{});
            blas->nodes[1].element_index = 6;
            blas->nodes[2].left = 0;
            blas->nodes[2].right = 1;
            blas->root = 2;
        }
        actual.DynamicBLAS.push_back(std::move(blas));
        actual.Upload();
        const auto found = reachableTriangles(actual.mesh);
        if (scenario == 1) assert(found == std::vector<int>{3});
        else assert((found == std::vector<int>{3, 6}));
        assert(actual.mesh.Mesh.RootNode == 1 + actual.DynamicBLAS[0]->root);
    } else if (scenario == 3) {
        TlasNode first, second, root;
        first.blas_index = 0;
        second.blas_index = 1;
        root.left = 0;
        root.right = 1;
        actual.TLAS.Nodes.push_back(first);
        actual.TLAS.Nodes.push_back(second);
        actual.TLAS.Nodes.push_back(root);
        actual.TLAS.Root = 2;
        actual.DynamicBLAS.push_back(leaf(3));
        actual.DynamicBLAS.push_back(leaf(6));
        actual.Upload();
        assert((reachableTriangles(actual.mesh) == std::vector<int>{3, 18}));
        assert(actual.mesh.Mesh.RootNode == 2);
    } else {
        assert(scenario == 4);
        actual.Upload();
        assert(actual.mesh.Mesh.RootNode == -1);
        assert(actual.mesh.UploadRanges.Node.count == 0);
    }
}
'''


class CollisionUploadRootTests(unittest.TestCase):
    def test_exported_root_and_links_reach_original_triangles(self):
        source = (ROOT / "src/common/rendering/hwrenderer/data/hw_collision.cpp").read_text()
        actual = production_function(source, "static FVector3 SwapYZ(") + "\n" + production_function(
            source, "void CPUAccelStruct::Upload()")
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "collision_upload.cpp"
            fixture.write_text(PREFIX + actual + SUFFIX)
            for scenario in (1, 2, 3, 4):
                with self.subTest(scenario=scenario):
                    run_fixture(fixture, args=[str(scenario)])


if __name__ == "__main__":
    unittest.main()
