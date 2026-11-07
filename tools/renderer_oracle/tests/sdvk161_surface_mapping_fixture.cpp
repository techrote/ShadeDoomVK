#include <vector>
#include <limits>
#include <stdexcept>
#include "src/rendering/hwrenderer/diagnostics/hw_specialsurfacecontract.h"

struct Vertex { float x = 0, y = 0, z = 0, lindex = 0; };
struct Surface
{
    struct { unsigned StartElementIndex = 0, StartVertIndex = 0; int NumElements = 0, NumVerts = 0; } MeshLocation;
};
struct Mesh
{
    std::vector<unsigned> Indexes;
    std::vector<int> SurfaceIndexes, UniformIndexes, Uniforms, Materials;
    std::vector<Vertex> Vertices;
    std::vector<Surface> Surfaces;
};

Mesh good()
{
    Mesh mesh;
    mesh.Indexes = {0, 1, 2, 0, 2, 3, 4, 5, 6, 4, 6, 7};
    mesh.SurfaceIndexes = {0, 0, 1, 1};
    mesh.UniformIndexes = {0, 0, 0, 0, 1, 1, 1, 1};
    mesh.Uniforms = mesh.Materials = {10, 20};
    mesh.Vertices.resize(8);
    mesh.Surfaces.resize(2);
    mesh.Surfaces[0].MeshLocation = {0, 0, 6, 4};
    mesh.Surfaces[1].MeshLocation = {6, 4, 6, 4};
    return mesh;
}

void require(bool value) { if (!value) throw std::runtime_error("submitted surface mapping contract failed"); }

int main()
{
    using namespace SdvkSurfaceObservation;
    auto mesh = good();
    Triangle value;
    for (int first = 0; first < 12; first += 3)
    {
        require(ResolveTriangle(mesh, first, value));
        require(value.Surface == first / 6 && value.Uniform == first / 6);
    }
    // Exact old flat writer mistake: an earlier subsector maps to the last
    // allocated surface, although that owner has a disjoint geometry range.
    mesh = good(); mesh.SurfaceIndexes[0] = mesh.SurfaceIndexes[1] = 1;
    require(!ResolveTriangle(mesh, 0, value));
    require(!ResolveTriangle(mesh, 3, value));
    require(ResolveTriangle(mesh, 6, value));
    mesh = good(); mesh.Indexes[6] = 3;
    require(!ResolveTriangle(mesh, 6, value));
    mesh = good(); mesh.UniformIndexes[6] = 0;
    require(!ResolveTriangle(mesh, 6, value));
    mesh = good(); mesh.UniformIndexes[6] = 2;
    require(!ResolveTriangle(mesh, 6, value));
    mesh = good(); mesh.SurfaceIndexes[2] = 100;
    require(!ResolveTriangle(mesh, 6, value));
    mesh = good(); mesh.Indexes[6] = 100;
    require(!ResolveTriangle(mesh, 6, value));
    mesh = good(); mesh.Materials.resize(1);
    require(!ResolveTriangle(mesh, 6, value));
    mesh = good(); mesh.Vertices[4].x = std::numeric_limits<float>::infinity();
    require(!ResolveTriangle(mesh, 6, value));
    mesh = good(); mesh.Vertices[4].lindex = std::numeric_limits<float>::quiet_NaN();
    require(!ResolveTriangle(mesh, 6, value));
    mesh = good();
    require(!ResolveTriangle(mesh, -3, value));
    require(!ResolveTriangle(mesh, 1, value));
    require(!ResolveTriangle(mesh, 12, value));
    require(Contains(12, 6, 6));
    require(!Contains(12, 6, 7));
    require(!Contains(12, -1, 3));
    require(!Contains(12, 12, 1));
    require(!Contains(12, 0, 0));
}
