#pragma once
#include <cmath>
#include <cstddef>
#include <limits>

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
