#pragma once
#include <cmath>
#include <cstddef>
#include <limits>
#include <cstdint>
#include <map>
#include <mutex>
#include <stdexcept>
#include <vector>
#include <utility>

// Read-only join of a submitted triangle to its current mesh surface/uniform.
// Kept independent of Vulkan so deliberate corrupt mappings can be replayed
// without creating a renderer/device. A surface inventory is not a draw witness.
namespace SdvkSurfaceObservation
{
struct Triangle
{
    int Surface = -1;
    int Uniform = -1;
};

// The writer and observer use float coordinates. Four normalized float epsilons
// admit arithmetic contraction/reassociation at the separate compilation units,
// while remaining far below one texel even on the 1024-wide fixture atlas.
constexpr float CurrentUvTolerance = 4.0f * std::numeric_limits<float>::epsilon();

template<class Tile, class Vertex>
bool CurrentVertexUV(const Tile& tile, int textureSize, const Vertex& vertex)
{
    if (textureSize <= 0 || !std::isfinite(vertex.x) || !std::isfinite(vertex.y) || !std::isfinite(vertex.z)
        || !std::isfinite(vertex.lu) || !std::isfinite(vertex.lv)) return false;
    const auto expected = tile.ToUV(vertex.fPos(), float(textureSize));
    return std::isfinite(expected.X) && std::isfinite(expected.Y)
        && std::abs(vertex.lu - expected.X) <= CurrentUvTolerance
        && std::abs(vertex.lv - expected.Y) <= CurrentUvTolerance;
}

// These values are COPIED from the writer's actual CPU allocation after all
// split/interpolated vertices are written. No allocation pointer escapes.
struct WrittenVertex
{
    float X, Y, Z, U, V, Page;
};
struct WrittenVertices
{
    int First = -1, Tile = -1;
    uint64_t AtlasOwner = 0, AtlasIncarnation = 0;
    size_t AtlasSlot = 0;
    std::vector<WrittenVertex> Vertices;
};
class WrittenVertexStore
{
public:
    static constexpr size_t MaxVertices = 4096;
    // RenderBSP joins its worker before main-thread draw submission, and the
    // next BeginFrame clears all previous-frame data. Protect capture/copy/
    // clear as one ownership domain, rather than separating worker TLS stores.
    void Clear()
    {
        std::lock_guard<std::mutex> lock(Mutex);
        Rows.clear(); VertexCount = 0;
    }
    template<class Vertex, class Receipt>
    void Capture(int first, int count, int tile, const Receipt& receipt, const Vertex* written)
    {
        std::lock_guard<std::mutex> lock(Mutex);
        if (!written || first < 0 || count <= 0 || tile < 0 || size_t(count) > MaxVertices)
            throw std::runtime_error("Invalid SDVK written vertex snapshot");
        auto found = Rows.find(first);
        const size_t previous = found == Rows.end() ? 0 : found->second.Vertices.size();
        if (size_t(count) > MaxVertices - (VertexCount - previous))
            throw std::runtime_error("SDVK written vertex snapshot limit reached");
        WrittenVertices snapshot;
        snapshot.First = first; snapshot.Tile = tile;
        snapshot.AtlasOwner = receipt.Owner; snapshot.AtlasIncarnation = receipt.Incarnation;
        snapshot.AtlasSlot = receipt.Slot;
        snapshot.Vertices.reserve(size_t(count));
        for (int i = 0; i < count; ++i)
            snapshot.Vertices.push_back({written[i].x, written[i].y, written[i].z,
                written[i].lu, written[i].lv, written[i].lindex});
        Rows[first] = std::move(snapshot);
        VertexCount = VertexCount - previous + size_t(count);
    }
    bool Copy(int first, int count, int tile, WrittenVertices& output) const
    {
        std::lock_guard<std::mutex> lock(Mutex);
        auto found = Rows.find(first);
        if (found == Rows.end() || count <= 0 || found->second.Tile != tile
            || found->second.Vertices.size() != size_t(count)) return false;
        output = found->second;
        return true;
    }
private:
    mutable std::mutex Mutex;
    std::map<int, WrittenVertices> Rows;
    size_t VertexCount = 0;
};

// Runs in the precise Vulkan translation unit, never the fast-math writer.
// Only the actually submitted subrange is inspected; the writer can split a
// wall into more than four vertices. The receipt joins that writer allocation
// to the current live tile, including same-page/same-rectangle reuse.
template<class Vertex, class Tile>
bool CurrentWrittenUV(const WrittenVertices& snapshot, const Tile& tile, int textureSize,
    int first, int count)
{
    const auto& receipt = tile.AtlasLocation.Allocation;
    if (first < snapshot.First || count <= 0 || snapshot.First < 0
        || size_t(first - snapshot.First) > snapshot.Vertices.size()
        || size_t(count) > snapshot.Vertices.size() - size_t(first - snapshot.First)
        || snapshot.AtlasOwner != receipt.Owner || snapshot.AtlasIncarnation != receipt.Incarnation
        || snapshot.AtlasSlot != receipt.Slot) return false;
    for (size_t i = size_t(first - snapshot.First), end = i + size_t(count); i < end; ++i)
    {
        const auto& observed = snapshot.Vertices[i];
        if (!std::isfinite(observed.Page) || observed.Page != float(tile.AtlasLocation.ArrayIndex)) return false;
        Vertex actual;
        actual.Set(observed.X, observed.Z, observed.Y, 0, 0, observed.U, observed.V, observed.Page);
        if (!CurrentVertexUV(tile, textureSize, actual)) return false;
    }
    return true;
}

inline bool Contains(size_t extent, int first, int count)
{
    return first >= 0 && count > 0 && size_t(first) <= extent && size_t(count) <= extent - size_t(first);
}

template<class MeshData>
bool ResolveTriangle(const MeshData& data, int first, Triangle& output)
{
    if (first < 0 || first % 3 || !Contains(data.Indexes.size(), first, 3)
        || size_t(first / 3) >= data.SurfaceIndexes.size()) return false;
    const int surfaceIndex = data.SurfaceIndexes[first / 3];
    if (surfaceIndex < 0 || size_t(surfaceIndex) >= data.Surfaces.size()) return false;
    const auto& surface = data.Surfaces[surfaceIndex];
    const auto& location = surface.MeshLocation;
    if (size_t(first) < location.StartElementIndex || location.NumElements <= 0
        || size_t(first) + 3 > size_t(location.StartElementIndex) + size_t(location.NumElements)) return false;
    int uniform = -1;
    for (int corner = 0; corner < 3; ++corner)
    {
        const size_t vertexIndex = data.Indexes[first + corner];
        if (vertexIndex >= data.Vertices.size() || vertexIndex >= data.UniformIndexes.size()
            || vertexIndex < location.StartVertIndex || location.NumVerts <= 0
            || vertexIndex >= size_t(location.StartVertIndex) + size_t(location.NumVerts)) return false;
        const int candidate = data.UniformIndexes[vertexIndex];
        if (candidate < 0 || size_t(candidate) >= data.Uniforms.size()
            || size_t(candidate) >= data.Materials.size() || (corner && candidate != uniform)) return false;
        uniform = candidate;
        const auto& vertex = data.Vertices[vertexIndex];
        if (!std::isfinite(vertex.x) || !std::isfinite(vertex.y) || !std::isfinite(vertex.z)
            || !std::isfinite(vertex.lindex)) return false;
    }
    output.Surface = surfaceIndex;
    output.Uniform = uniform;
    return true;
}
}
