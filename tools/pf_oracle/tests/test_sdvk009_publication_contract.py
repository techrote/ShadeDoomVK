"""SDVK-009 production packing and descriptor contract controls; CPU/static only."""
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
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <memory>
#include <vector>

template<class T> struct Array : std::vector<T> {
    unsigned Size() const { return static_cast<unsigned>(std::vector<T>::size()); }
};
struct MeshBufferRange {
    int Start = 0, End = 0;
    int Count() const { return End - Start; }
};
struct MeshBufferUploads {
    Array<MeshBufferRange> Ranges;
    const Array<MeshBufferRange>& GetRanges() const { return Ranges; }
    void Add(int start, int count) { Ranges.push_back({start, start + count}); }
};
struct CollisionNodeBufferHeader { int root, padding1, padding2, padding3; };
struct CollisionNode {
    float center[3]; float padding1;
    float extents[3]; float padding2;
    int left, right, element_index, padding3;
};
struct FFlatVertex { float x, z, y, lindex, u, v, lu, lv; };
static_assert(sizeof(CollisionNodeBufferHeader) == 16);
static_assert(sizeof(CollisionNode) == 48);
static_assert(sizeof(FFlatVertex) == 32);

struct VulkanBuffer { size_t size = 4096; };
struct LevelMesh {
    struct MeshData { Array<CollisionNode> Nodes; int RootNode = -1; } Mesh;
    struct Ranges { MeshBufferUploads Node; } UploadRanges;
};
struct VkLevelMesh {
    bool useRayQuery = false;
    LevelMesh* Mesh = nullptr;
    std::unique_ptr<VulkanBuffer> NodeBuffer = std::make_unique<VulkanBuffer>();
};
struct Write {
    size_t offset = 0;
    std::vector<unsigned char> bytes;
};
class VkLevelMeshUploader {
public:
    explicit VkLevelMeshUploader(VkLevelMesh* mesh) : Mesh(mesh) {}
    void UploadNodes();
    template<typename T>
    void UploadRanges(const MeshBufferUploads& ranges, const T* srcbuffer, VulkanBuffer* destbuffer, const char* buffername);
    void UploadData(VulkanBuffer* dest, size_t destOffset, const void* src, size_t size, const char*) {
        assert(dest && destOffset + size <= dest->size);
        Write write;
        write.offset = destOffset;
        const auto* first = static_cast<const unsigned char*>(src);
        write.bytes.assign(first, first + size);
        writes.push_back(std::move(write));
    }
    VkLevelMesh* Mesh = nullptr;
    std::vector<Write> writes;
};
'''

SUFFIX = r'''
int main() {
    LevelMesh mesh;
    mesh.Mesh.RootNode = 37;
    mesh.Mesh.Nodes.resize(4);
    for (size_t i = 0; i < mesh.Mesh.Nodes.size(); ++i) {
        std::memset(&mesh.Mesh.Nodes[i], int(0x20 + i), sizeof(CollisionNode));
    }
    mesh.UploadRanges.Node.Add(1, 2);

    VkLevelMesh vk;
    vk.Mesh = &mesh;
    VkLevelMeshUploader uploader(&vk);
    uploader.UploadNodes();
    assert(uploader.writes.size() == 2);
    assert(uploader.writes[0].offset == 0 && uploader.writes[0].bytes.size() == sizeof(CollisionNodeBufferHeader));
    CollisionNodeBufferHeader header{};
    std::memcpy(&header, uploader.writes[0].bytes.data(), sizeof(header));
    assert(header.root == 37);
    assert(header.padding1 == 0 && header.padding2 == 0 && header.padding3 == 0);
    assert(uploader.writes[1].offset == sizeof(CollisionNodeBufferHeader) + sizeof(CollisionNode));
    assert(uploader.writes[1].bytes.size() == 2 * sizeof(CollisionNode));
    assert(std::memcmp(uploader.writes[1].bytes.data(), &mesh.Mesh.Nodes[1], 2 * sizeof(CollisionNode)) == 0);

    MeshBufferUploads vertexRanges;
    vertexRanges.Add(2, 2);
    std::vector<FFlatVertex> vertices(5);
    const size_t beforeVertex = uploader.writes.size();
    uploader.UploadRanges(vertexRanges, vertices.data(), vk.NodeBuffer.get(), "VertexBuffer");
    assert(uploader.writes.size() == beforeVertex + 1);
    assert(uploader.writes.back().offset == 2 * sizeof(FFlatVertex));
    assert(uploader.writes.back().bytes.size() == 2 * sizeof(FFlatVertex));

    MeshBufferUploads indexRanges;
    indexRanges.Add(3, 3);
    std::vector<uint32_t> indexes(8);
    const size_t beforeIndex = uploader.writes.size();
    uploader.UploadRanges(indexRanges, indexes.data(), vk.NodeBuffer.get(), "IndexBuffer");
    assert(uploader.writes.size() == beforeIndex + 1);
    assert(uploader.writes.back().offset == 3 * sizeof(uint32_t));
    assert(uploader.writes.back().bytes.size() == 3 * sizeof(uint32_t));

    mesh.UploadRanges.Node.Ranges.clear();
    const size_t beforeEmpty = uploader.writes.size();
    uploader.UploadNodes();
    assert(uploader.writes.size() == beforeEmpty);

    mesh.UploadRanges.Node.Add(0, 1);
    vk.useRayQuery = true;
    uploader.UploadNodes();
    assert(uploader.writes.size() == beforeEmpty);
}
'''


class ProductionPackingTests(unittest.TestCase):
    def test_actual_upload_nodes_and_typed_ranges_pack_expected_bytes(self):
        source = (ROOT / "src/common/rendering/vulkan/vk_levelmesh.cpp").read_text(encoding="utf-8")
        actual = production_function(source, "void VkLevelMeshUploader::UploadNodes()") + "\n" + production_function(
            source, "template<typename T>\nvoid VkLevelMeshUploader::UploadRanges")
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "sdvk009_publication.cpp"
            fixture.write_text(PREFIX + actual + SUFFIX, encoding="utf-8")
            run_fixture(fixture)

    def test_layout_is_pinned_to_shader_visible_strides(self):
        header = (ROOT / "src/common/rendering/vulkan/vk_levelmesh.h").read_text(encoding="utf-8")
        self.assertIn("sizeof(CollisionNodeBufferHeader) == sizeof(int) * 4", header)
        self.assertIn("sizeof(CollisionNode) == sizeof(float) * 12", header)
        self.assertIn("sizeof(FFlatVertex) == sizeof(float) * 8", header)


class PublicationNegativeControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.level = (ROOT / "src/common/rendering/vulkan/vk_levelmesh.cpp").read_text(encoding="utf-8")
        cls.descriptors = (ROOT / "src/common/rendering/vulkan/descriptorsets/vk_descriptorset.cpp").read_text(encoding="utf-8")
        cls.builders = (ROOT / "libraries/ZVulkan/src/vulkanbuilders.cpp").read_text(encoding="utf-8")
        cls.objects = (ROOT / "libraries/ZVulkan/include/zvulkan/vulkanobjects.h").read_text(encoding="utf-8")
        cls.shader = (ROOT / "wadsrc/static/shaders/scene/binding_fixed.glsl").read_text(encoding="utf-8")
        cls.structs = (ROOT / "wadsrc/static/shaders/binding_struct_definitions.glsl").read_text(encoding="utf-8")

    def check(self, level=None, descriptors=None, builders=None, objects=None, shader=None):
        level = self.level if level is None else level
        descriptors = self.descriptors if descriptors is None else descriptors
        builders = self.builders if builders is None else builders
        objects = self.objects if objects is None else objects
        shader = self.shader if shader is None else shader

        # Root/header and typed offset/extent publication.
        self.assertIn("CollisionNodeBufferHeader nodesHeader = {};", level)
        self.assertIn("sizeof(CollisionNodeBufferHeader) + range.Start * sizeof(CollisionNode)", level)
        self.assertIn("range.Count() * sizeof(CollisionNode)", level)
        self.assertIn("range.Start * sizeof(T)", level)
        self.assertIn("range.Count() * sizeof(T)", level)

        # The bytes fingerprinted are the bytes copied, and allocation identity
        # is the actual per-object diagnostic ID rather than a reusable handle.
        self.assertIn("CfxTrace::Upload(transferBuffer->diagnosticId, dest->diagnosticId", level)
        self.assertIn("copyCommands.emplace_back(transferBuffer.get(), dest, datapos, destOffset, size)", level)
        self.assertIn("diagnosticId = CfxTrace::NewResourceId();", objects)
        self.assertIn("extra->diagnosticBufferId = buffer->diagnosticId;", builders)

        # Production scene bindings consumed by light_shadow -> light_trace.
        expected = {
            2: ("GetNodeBuffer()", "NodeBuffer"),
            3: ("GetVertexBuffer()", "VertexBuffer"),
            4: ("GetIndexBuffer()", "ElementBuffer"),
            5: ("GetSurfaceIndexBuffer()", "SurfaceIndexBuffer"),
            6: ("GetSurfaceBuffer()", "SurfaceBuffer"),
            7: ("GetPortalBuffer()", "PortalBuffer"),
        }
        for binding, (getter, block) in expected.items():
            if binding == 2:
                self.assertIn(f"update.AddBuffer(Fixed.Set.get(), {binding}, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, fb->GetLevelMesh()->{getter})", descriptors)
            else:
                self.assertIn(f"update.AddBuffer(Fixed.Set.get(), {binding}, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, fb->GetLevelMesh()->{getter})", descriptors)
            self.assertIn(f"binding = {binding}", shader)
            self.assertIn(block, shader)
        self.assertIn("struct CollisionNode", self.structs)
        self.assertIn("struct SurfaceVertex", self.structs)

    def test_current_contract_positive(self):
        self.check()

    def test_bad_header_prefix_is_rejected(self):
        bad = self.level.replace("CollisionNodeBufferHeader nodesHeader = {};", "CollisionNodeBufferHeader nodesHeader;")
        with self.assertRaises(AssertionError):
            self.check(level=bad)

    def test_bad_node_offset_is_rejected(self):
        bad = self.level.replace(
            "sizeof(CollisionNodeBufferHeader) + range.Start * sizeof(CollisionNode)",
            "range.Start * sizeof(CollisionNode)")
        with self.assertRaises(AssertionError):
            self.check(level=bad)

    def test_bad_typed_stride_is_rejected(self):
        bad = self.level.replace("range.Start * sizeof(T)", "range.Start")
        with self.assertRaises(AssertionError):
            self.check(level=bad)

    def test_missing_copy_is_rejected(self):
        bad = self.level.replace(
            "copyCommands.emplace_back(transferBuffer.get(), dest, datapos, destOffset, size)",
            "/* synthetic missing copy */")
        with self.assertRaises(AssertionError):
            self.check(level=bad)

    def test_stale_or_unidentified_buffer_generation_is_rejected(self):
        bad = self.builders.replace("extra->diagnosticBufferId = buffer->diagnosticId;", "extra->diagnosticBufferId = 0;")
        with self.assertRaises(AssertionError):
            self.check(builders=bad)

    def test_wrong_shader_binding_is_rejected(self):
        bad = self.shader.replace("layout(set = 0, binding = 3, std430) buffer readonly VertexBuffer",
                                  "layout(set = 0, binding = 8, std430) buffer readonly VertexBuffer")
        with self.assertRaises(AssertionError):
            self.check(shader=bad)


if __name__ == "__main__":
    unittest.main()
