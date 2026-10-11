// CPU-only adapter; collision.cpp and all production function bodies are copied
// unchanged by collision_replay.py. No renderer/backend is linked or launched.
#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <limits>
#include <map>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#define SDVK_COLLISION_REPLAY_BUILD
// Inherited engine source has conversion/unused warnings under stricter fixture
// flags. Suppression covers only unmodified production source and math headers;
// adapter logic below retains the fixture's warning and assertion policy.
#ifdef _MSC_VER
#pragma warning(push)
#pragma warning(disable: 4018 4100 4189 4244 4267 4458)
#elif defined(__GNUC__)
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wsign-compare"
#pragma GCC diagnostic ignored "-Wunused-variable"
#pragma GCC diagnostic ignored "-Wunused-parameter"
#endif
#include "common/utility/vectors.h"
#define private public
#include "hw_collision.h"
#undef private
#include "collision_replay_mesh.h"
#include "printf.h"
#include "hw_collision.cpp"
#include "collision_replay_ranges.inc"
#ifdef _MSC_VER
#pragma warning(pop)
#elif defined(__GNUC__)
#pragma GCC diagnostic pop
#endif

// Building/exporting collision trees never calls this query-only external.
// Fail closed if a future production change unexpectedly starts doing so.
extern "C" double c_sqrt(double)
{
    std::fputs("query-only custom sqrt is outside snapshot replay\n", stderr);
    std::abort();
}

static_assert(sizeof(FFlatVertex) == 32 && sizeof(CollisionNode) == 48, "production collision shader layout changed");

struct Section
{
    uint32_t count = 0, stride = 0;
    std::vector<unsigned char> bytes;
};
struct Input
{
    std::array<uint32_t, 16> h{};
    std::map<std::string, Section> sections;
};
static uint32_t readU32(std::istream& stream)
{
    unsigned char bytes[4];
    if (!stream.read(reinterpret_cast<char*>(bytes), 4)) throw std::runtime_error("truncated integer");
    return uint32_t(bytes[0]) | uint32_t(bytes[1]) << 8 | uint32_t(bytes[2]) << 16 | uint32_t(bytes[3]) << 24;
}
static void appendU32(Section& s, uint32_t value)
{
    for (unsigned shift = 0; shift < 32; shift += 8) s.bytes.push_back(static_cast<unsigned char>(value >> shift));
}
static void appendFloat(Section& s, float value)
{
    uint32_t bits;
    std::memcpy(&bits, &value, sizeof(bits));
    appendU32(s, bits);
}
static uint32_t word(const Section& s, size_t index)
{
    const size_t offset = index * 4;
    if (offset + 4 > s.bytes.size()) throw std::runtime_error("section access bounds");
    return uint32_t(s.bytes[offset]) | uint32_t(s.bytes[offset + 1]) << 8 |
        uint32_t(s.bytes[offset + 2]) << 16 | uint32_t(s.bytes[offset + 3]) << 24;
}
static float floating(const Section& s, size_t index)
{
    const uint32_t bits = word(s, index);
    float result;
    std::memcpy(&result, &bits, sizeof(result));
    return result;
}
static Input readInput(const char* path)
{
    std::ifstream stream(path, std::ios::binary);
    char magic[8];
    if (!stream.read(magic, 8) || std::memcmp(magic, "SDVKCL01", 8)) throw std::runtime_error("bad magic");
    Input result;
    for (auto& value : result.h) value = readU32(stream);
    if (result.h[0] != 1 || result.h[4] != 32 || result.h[15] != 11) throw std::runtime_error("bad header");
    for (size_t i = 5; i < 15; ++i)
        if (i != 12 && i != 14 && result.h[i] > 1000000) throw std::runtime_error("bounded input exceeded");
    for (uint32_t i = 0; i < result.h[15]; ++i)
    {
        char tag[4];
        if (!stream.read(tag, 4)) throw std::runtime_error("truncated tag");
        Section s;
        s.count = readU32(stream); s.stride = readU32(stream);
        if (s.count > 1000000 || s.stride > 60) throw std::runtime_error("bounded section exceeded");
        s.bytes.resize(size_t(s.count) * s.stride);
        if (!stream.read(reinterpret_cast<char*>(s.bytes.data()), static_cast<std::streamsize>(s.bytes.size()))) throw std::runtime_error("truncated section");
        if (!result.sections.emplace(std::string(tag, 4), std::move(s)).second) throw std::runtime_error("duplicate section");
    }
    return result;
}
static void loadMesh(LevelMesh& mesh, const Input& in)
{
    const float poison = std::numeric_limits<float>::quiet_NaN();
    mesh.Mesh.Vertices.resize(in.h[5], FFlatVertex{poison, poison, poison, poison, poison, poison, poison, poison});
    mesh.Mesh.Indexes.resize(in.h[6], 0xdeadbeefu);
    mesh.Mesh.IndexCount = static_cast<int>(in.h[7]);
    mesh.Mesh.Nodes.resize(in.h[13]);
    const auto& vertices = in.sections.at("VERT");
    for (uint32_t i = 0; i < vertices.count; ++i)
    {
        auto& v = mesh.Mesh.Vertices.at(word(vertices, i * 4));
        v.x = floating(vertices, i * 4 + 1); v.z = floating(vertices, i * 4 + 2); v.y = floating(vertices, i * 4 + 3);
    }
    const auto& indexes = in.sections.at("INDX");
    if (indexes.count != in.h[7]) throw std::runtime_error("index count mismatch");
    for (uint32_t i = 0; i < indexes.count; ++i) mesh.Mesh.Indexes.at(i) = word(indexes, i);
    const auto loadRanges = [&in](const char* tag, MeshBufferUploads& ranges)
    {
        ranges.Ranges.clear();
        const auto& s = in.sections.at(tag);
        for (uint32_t i = 0; i < s.count; ++i)
            ranges.Ranges.push_back({static_cast<int32_t>(word(s, i * 2)), static_cast<int32_t>(word(s, i * 2 + 1))});
    };
    loadRanges("VDIR", mesh.UploadRanges.Vertex);
    loadRanges("IDIR", mesh.UploadRanges.Index);
    loadRanges("NDIR", mesh.UploadRanges.Node);
}
template<class Node> static void treeNode(Section& s, const Node& node, int identity)
{
    for (const auto& v : {node.aabb.min, node.aabb.max, node.aabb.Center, node.aabb.Extents})
    {
        appendFloat(s, v.X); appendFloat(s, v.Y); appendFloat(s, v.Z);
    }
    appendU32(s, static_cast<uint32_t>(node.left)); appendU32(s, static_cast<uint32_t>(node.right));
    appendU32(s, static_cast<uint32_t>(identity));
}
static void writeOutput(Input in, const CPUAccelStruct& a, const LevelMesh& mesh, const std::string& path)
{
    auto replace = [&in](const char* tag, uint32_t stride) -> Section&
    {
        auto& s = in.sections[tag]; s = Section{}; s.stride = stride; return s;
    };
    in.h[8] = static_cast<uint32_t>(a.IndexesPerBLAS); in.h[9] = static_cast<uint32_t>(a.InstanceCount);
    in.h[10] = static_cast<uint32_t>(a.DynamicBLAS.size()); in.h[11] = static_cast<uint32_t>(a.TLAS.Nodes.size());
    in.h[12] = static_cast<uint32_t>(a.TLAS.Root); in.h[13] = mesh.Mesh.Nodes.Size(); in.h[14] = static_cast<uint32_t>(mesh.Mesh.RootNode);
    auto& tlas = replace("TLAS", 60);
    for (const auto& n : a.TLAS.Nodes) treeNode(tlas, n, n.blas_index);
    auto& slots = replace("SLOT", 20);
    auto& blas = replace("BLAS", 60);
    uint32_t cursor = 0;
    for (uint32_t slot = 0; slot < a.DynamicBLAS.size(); ++slot)
    {
        const auto& b = a.DynamicBLAS[slot];
        const auto count = b ? static_cast<uint32_t>(b->GetNodes().size()) : 0u;
        appendU32(slots, slot); appendU32(slots, static_cast<uint32_t>(b ? b->GetRoot() : -1));
        appendU32(slots, cursor); appendU32(slots, count); appendU32(slots, slot * static_cast<uint32_t>(a.IndexesPerBLAS));
        if (b) for (const auto& n : b->GetNodes()) treeNode(blas, n, n.element_index);
        cursor += count;
    }
    auto& nodes = replace("NODE", 36);
    const auto count = std::max(1u, in.h[11] + cursor);
    for (uint32_t i = 0; i < count; ++i)
    {
        const auto& n = mesh.Mesh.Nodes.at(i);
        appendFloat(nodes, n.center.X); appendFloat(nodes, n.center.Y); appendFloat(nodes, n.center.Z);
        appendFloat(nodes, n.extents.X); appendFloat(nodes, n.extents.Y); appendFloat(nodes, n.extents.Z);
        appendU32(nodes, static_cast<uint32_t>(n.left)); appendU32(nodes, static_cast<uint32_t>(n.right)); appendU32(nodes, static_cast<uint32_t>(n.element_index));
    }
    auto& dirty = replace("NDIR", 8);
    for (const auto& range : mesh.UploadRanges.Node.GetRanges())
    {
        appendU32(dirty, static_cast<uint32_t>(range.Start)); appendU32(dirty, static_cast<uint32_t>(range.End));
    }
    std::ofstream out(path, std::ios::binary);
    out.write("SDVKCL01", 8);
    const auto writeU32 = [&out](uint32_t value)
    {
        char bytes[4];
        for (unsigned i = 0; i < 4; ++i) bytes[i] = static_cast<char>(value >> (i * 8));
        out.write(bytes, 4);
    };
    for (const auto value : in.h) writeU32(value);
    for (auto& entry : in.sections)
    {
        auto& s = entry.second;
        s.count = static_cast<uint32_t>(s.bytes.size() / s.stride);
        out.write(entry.first.data(), 4); writeU32(s.count); writeU32(s.stride);
        out.write(reinterpret_cast<const char*>(s.bytes.data()), static_cast<std::streamsize>(s.bytes.size()));
    }
    if (!out) throw std::runtime_error("output write failed");
}
struct ReplayObject
{
    LevelMesh mesh;
    std::unique_ptr<CPUAccelStruct> collision;
};
int main(int argc, char** argv)
{
    try
    {
        if (argc < 3) throw std::runtime_error("output directory and input snapshots required");
        std::map<uint32_t, std::unique_ptr<ReplayObject>> objects;
        for (int i = 2; i < argc; ++i)
        {
            const auto in = readInput(argv[i]);
            const auto object = in.h[2], phase = in.h[3];
            if (phase == 0)
            {
                if (objects.count(object)) throw std::runtime_error("duplicate constructor");
                objects[object] = std::make_unique<ReplayObject>();
            }
            const auto found = objects.find(object);
            if (found == objects.end()) throw std::runtime_error("missing constructor");
            auto& state = *found->second;
            loadMesh(state.mesh, in);
            if (phase == 0) state.collision = std::make_unique<CPUAccelStruct>(&state.mesh);
            else state.collision->Update();
            const auto path = std::string(argv[1]) + "/replayed-" + std::to_string(i - 2) + ".bin";
            writeOutput(in, *state.collision, state.mesh, path);
        }
        return 0;
    }
    catch (const std::exception& error)
    {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
