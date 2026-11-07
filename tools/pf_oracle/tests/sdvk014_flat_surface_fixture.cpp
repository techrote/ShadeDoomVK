// CPU-only adapter for the exact production CreateFlatSurface definition.
// No renderer/device is linked. Mocks supply storage and preselected HWFlat input;
// the triangle, plane, vertex and material publication below is production code.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

template<class... Args> [[noreturn]] void I_FatalError(const char* message, Args...)
{ throw std::runtime_error(message); }

template<class T> struct TArray : std::vector<T>
{
    using std::vector<T>::vector;
    void Clear() { this->clear(); }
    void Push(const T& value) { this->push_back(value); }
    unsigned int Size() const { return static_cast<unsigned int>(this->size()); }
    T& Last() { return this->back(); }
    void Pop() { this->pop_back(); }
};
struct FVector3
{
    float X = 0, Y = 0, Z = 0;
    FVector3() = default;
    FVector3(float x, float y, float z) : X(x), Y(y), Z(z) {}
};
struct FVector4
{
    float X = 0, Y = 0, Z = 0, W = 0;
    FVector4() = default;
    FVector4(float x, float y, float z, float w) : X(x), Y(y), Z(z), W(w) {}
    FVector4 operator-() const { return {-X, -Y, -Z, -W}; }
};
struct VSMatrix
{
    void loadIdentity() {}
    FVector4 operator*(const FVector4& value) const { return value; }
};
struct vertex_t { float X, Y; float fX() const { return X; } float fY() const { return Y; } };
struct secplane_t
{
    FVector3 normal;
    float D;
    FVector3 Normal() const { return normal; }
    float ZatPoint(const vertex_t* point) const
    { return (-D - normal.X * point->X - normal.Y * point->Y) / normal.Z; }
    void FlipVert() { normal = {-normal.X, -normal.Y, -normal.Z}; D = -D; }
    bool operator==(const secplane_t& other) const
    { return normal.X == other.normal.X && normal.Y == other.normal.Y && normal.Z == other.normal.Z && D == other.D; }
};
struct FGameTexture { bool masked = false; bool isMasked() const { return masked; } };
struct FSectorPortal { int mType = 0; };
constexpr int PORTS_SKYVIEWPOINT = 1;
constexpr int skyflatnum = 91;
constexpr int EFF_PORTAL = 1, EFF_NONE = 0, STYLE_Normal = 0, Alpha_GEqual = 1;
constexpr int SECF_LM_DYNAMIC = 1;
constexpr float gl_mask_threshold = 0.5f;
enum class LevelMeshDrawType { Opaque, Portal, Translucent };
enum { ST_CEILING = 4, ST_FLOOR = 5 };
struct F3DFloor;
struct TestSectorExt { struct { TArray<F3DFloor*> ffloors; } XFloor; };
struct sector_t
{
    enum { floor = 0, ceiling = 1 };
    struct { uint16_t LightmapSampleDistance = 8; } planes[2];
    int Flags = 0;
    int id = 0;
    TestSectorExt storage;
    TestSectorExt* e = &storage;
    secplane_t sourcePlanes[2]{{{0, 0, 1}, 0}, {{0, 0, -1}, 128}};
    int Index() const { return id; }
    FSectorPortal* GetPortal(int) { return nullptr; }
    secplane_t GetSecPlane(bool isceiling) const { return sourcePlanes[isceiling]; }
};
struct F3DFloor { sector_t* model = nullptr; };
struct seg_t { vertex_t* v1; };
struct subsector_t
{
    int numlines;
    seg_t* firstline;
    int id;
    sector_t* sector;
    TArray<int> LightmapTiles[2]{{-1, -1}, {-1, -1}};
    int Index() const { return id; }
};
struct FSection { TArray<subsector_t*> subsectors; };
struct SurfaceUniforms { float uVertexColor = 1, uDesaturationFactor = 0, uLightLevel = 1; };
// Distinct fields let the oracle check unmodified whole material state copying.
struct FMaterialState { int albedo = 17, normal = 29, height = 41, sampler = 53; };
struct MeshApplyState
{
    int applyData = 3;
    SurfaceUniforms surfaceUniforms;
    FMaterialState material;
    VSMatrix textureMatrix;
};
struct FFlatVertex { float x, y, z, u, v, lu, lv, lindex; };
struct MeshBuilder
{
    std::vector<std::pair<MeshApplyState, int>> mSortedLists;
    TArray<int> mVertices, mIndexes;
    void SetEffect(int) {}
    void EnableTexture(bool) {}
    void SetRenderStyle(int) {}
    void AlphaFunc(int, float) {}
};
struct TestLevel { bool lightmaps = true; };
struct HWFlatDispatcher { TestLevel* Level; };
struct HWFlat
{
    bool ceiling = false;
    int lightmapPlane = -1;
    sector_t* sector = nullptr;
    F3DFloor* controlsector = nullptr;
    FSection* section = nullptr;
    FGameTexture* texture = nullptr;
    float alpha = 1;
    struct { int texture = 0; secplane_t plane; } plane;
    void DrawSubsectors(HWFlatDispatcher*, MeshBuilder& state)
    { state.mSortedLists.push_back({MeshApplyState{}, 0}); }
    void DrawFlat(HWFlatDispatcher* dispatcher, MeshBuilder& state, bool)
    { DrawSubsectors(dispatcher, state); }
};
struct GeometryAllocInfo { int VertexStart, VertexCount, IndexStart, IndexCount; };
struct UniformsAllocInfo { int Start; };
struct SurfaceAllocInfo { int Index; };
struct LightListAllocInfo { int Start = 0, Count = 0; };
struct DoomSurfaceInfo
{
    int Type = 0, TypeIndex = -1, LightListSection = -1, NextSurface = -1;
    sector_t* ControlSector = nullptr;
    int LightmapPlane = -1;
    bool RuntimeBakeOnly = false;
    subsector_t* Subsector = nullptr;
};
struct TestBounds { FVector3 min, max; };
// @PRODUCTION_LIGHTMAP_BINDING@
struct LightmapTile
{
    struct { bool Allocation = false; } AtlasLocation;
    LightmapTileBinding Binding;
    TestBounds Bounds;
    FVector4 Plane;
    uint16_t SampleDimension = 0;
    int UseCount = 0;
    bool UseXYAxis = false;
    bool RuntimeBakeOnly = false;
    bool GeometryUpdate = true, ReceivedNewLight = true;
};
struct LevelMeshSurface
{
    int SectorGroup = 0, PipelineID = 0, PortalIndex = 0, LightmapTileIndex = -1;
    float Alpha = 1;
    FGameTexture* Texture = nullptr;
    bool IsSky = false;
    FVector4 Plane;
    struct { int StartVertIndex, StartElementIndex, NumVerts, NumElements; } MeshLocation;
    struct { int Pos = 0, Count = 0; } LightList;
    TestBounds Bounds;
};
struct Screen
{
    int GetLevelMeshPipelineID(int data, const SurfaceUniforms&, const FMaterialState&) { return data; }
} screenObject;
Screen* screen = &screenObject;
enum class LevelMeshMutationDomain { LightmapProbe };
struct TestPacker { bool Free(bool) { return true; } } packer;
class DoomLevelMesh
{
public:
    struct
    {
        TArray<FFlatVertex> Vertices;
        TArray<int> SurfaceIndexes, UniformIndexes;
        TArray<uint32_t> Indexes;
        TArray<LevelMeshSurface> Surfaces;
    } Mesh;
    TArray<SurfaceUniforms> Uniforms, LightUniforms;
    TArray<FMaterialState> Materials;
    TArray<DoomSurfaceInfo> DoomSurfaceInfos;
    struct FlatBlock
    {
        TArray<GeometryAllocInfo> Geometries;
        TArray<UniformsAllocInfo> Uniforms;
        TArray<int> DrawRanges;
        int FirstSurface = -1;
    };
    TArray<FlatBlock> Flats{1};
    TArray<int> sectorGroup{5};
    int sectorPortals[2][1]{{7}, {11}};
    struct
    {
        TArray<int> AddedSurfaces, AddedTiles, FreeTiles;
        TArray<LightmapTile> Tiles;
        int UsedTiles = 0;
        TestPacker* AtlasPacker = &packer;
    } Lightmap;
    std::map<LightmapTileBinding, int> TileBindings;
    int subsectorLightmapWrites = 0;
    GeometryAllocInfo AllocGeometry(int vertices, int indexes)
    {
        GeometryAllocInfo result{static_cast<int>(Mesh.Vertices.size()), vertices,
            static_cast<int>(Mesh.Indexes.size()), indexes};
        Mesh.Vertices.resize(Mesh.Vertices.size() + vertices);
        Mesh.UniformIndexes.resize(Mesh.Vertices.size());
        Mesh.Indexes.resize(Mesh.Indexes.size() + indexes);
        Mesh.SurfaceIndexes.resize(Mesh.Indexes.size() / 3, -1);
        return result;
    }
    UniformsAllocInfo AllocUniforms(int)
    {
        int start = static_cast<int>(Uniforms.size());
        Uniforms.resize(start + 1); Materials.resize(start + 1); LightUniforms.resize(start + 1);
        return {start};
    }
    SurfaceAllocInfo AllocSurface()
    {
        int index = static_cast<int>(Mesh.Surfaces.size());
        Mesh.Surfaces.resize(index + 1); DoomSurfaceInfos.resize(index + 1);
        return {index};
    }
    SurfaceUniforms* GetUniforms(UniformsAllocInfo info) { return &Uniforms[info.Start]; }
    FMaterialState* GetMaterials(UniformsAllocInfo info) { return &Materials[info.Start]; }
    SurfaceUniforms* GetLightUniforms(UniformsAllocInfo info) { return &LightUniforms[info.Start]; }
    FFlatVertex* GetVertices(GeometryAllocInfo info) { return &Mesh.Vertices[info.VertexStart]; }
    int* GetUniformIndexes(GeometryAllocInfo info) { return &Mesh.UniformIndexes[info.VertexStart]; }
    uint32_t* GetIndexes(GeometryAllocInfo info) { return &Mesh.Indexes[info.IndexStart]; }
    LevelMeshSurface* GetSurface(SurfaceAllocInfo info) { return &Mesh.Surfaces[info.Index]; }
    DoomSurfaceInfo* GetDoomSurface(SurfaceAllocInfo info) { return &DoomSurfaceInfos[info.Index]; }
    TestBounds GetBoundsFromSurface(const LevelMeshSurface& surf)
    {
        auto location = surf.MeshLocation;
        auto first = Mesh.Vertices[location.StartVertIndex];
        TestBounds bounds{{first.x, first.y, first.z}, {first.x, first.y, first.z}};
        for (int i = location.StartVertIndex; i < location.StartVertIndex + location.NumVerts; ++i)
        {
            const auto& vertex = Mesh.Vertices[i];
            bounds.min.X = std::min(bounds.min.X, vertex.x); bounds.max.X = std::max(bounds.max.X, vertex.x);
            bounds.min.Y = std::min(bounds.min.Y, vertex.y); bounds.max.Y = std::max(bounds.max.Y, vertex.y);
            bounds.min.Z = std::min(bounds.min.Z, vertex.z); bounds.max.Z = std::max(bounds.max.Z, vertex.z);
        }
        return bounds;
    }
    int AllocTile(const LightmapTile&);
    void FreeTile(int);
    void ReleaseTiles(int);
    void MarkMutation(LevelMeshMutationDomain) {}
    int GetSampleDimension(uint16_t dimension) { return dimension; }
    int AddSurfaceToTile(const DoomSurfaceInfo&, const LevelMeshSurface&, uint16_t, uint8_t);
    void SetSubsectorLightmap(int);
    void AddToDrawList(TArray<int>& list, LevelMeshDrawType, int, int, int) { list.Push(1); }
    void CreateFlatSurface(HWFlatDispatcher&, MeshBuilder&, TArray<HWFlat>&, LevelMeshDrawType,
        bool, unsigned int, const LightListAllocInfo&, int);
};

// @PRODUCTION_CREATE_FLAT_SURFACE@
// @PRODUCTION_ADD_SURFACE_TO_TILE@
// @PRODUCTION_SET_SUBSECTOR_LIGHTMAP@
// @PRODUCTION_TILE_POOL_METHODS@
// @PRODUCTION_RELEASE_TILES@

static bool close(float left, float right) { return std::abs(left - right) < 0.0001f; }
static bool fail(const char* message) { std::cerr << message << '\n'; return false; }

static bool run(const std::string& test)
{
    const bool rebuild = test == "control-top-rebuild" || test == "control-bottom-rebuild" || test == "inverted-rebuild";
    const bool inverted = test == "inverted-selected-plane" || test == "inverted-rebuild";
    const bool ceiling = test == "ceiling" || test == "3dfloor-bottom" || test == "control-bottom-rebuild";
    const bool ambiguous = test == "both-planes-ambiguous";
    const bool control = test == "3dfloor-top" || test == "3dfloor-bottom" || inverted || ambiguous || rebuild;
    const bool sky = test == "sky-no-tile";
    const bool one = test == "one-subsector" || ambiguous;
    if (!(ceiling || control || sky || one || test == "floor" || test == "repeated")) return fail("unknown-case");
    sector_t sector, model;
    model.id = 23;
    model.sourcePlanes[0] = {{0, 0, 1}, -32};
    model.sourcePlanes[1] = {{0, 0, -1}, 80};
    F3DFloor rover{&model};
    if (control) sector.e->XFloor.ffloors.Push(&rover);
    vertex_t points[]{{0, 0}, {0, 8}, {8, 8}, {8, 0}, {20, 0}, {20, 8}, {28, 8}, {28, 0}};
    seg_t edges[]{{&points[0]}, {&points[1]}, {&points[2]}, {&points[3]},
        {&points[4]}, {&points[5]}, {&points[6]}, {&points[7]}};
    subsector_t first{4, edges, 101, &sector}, skipped{2, edges, 102, &sector}, second{4, edges + 4, 103, &sector};
    FSection section;
    section.subsectors.Push(&first);
    if (!one) { section.subsectors.Push(&skipped); section.subsectors.Push(&second); }
    FGameTexture texture;
    HWFlat flat;
    flat.ceiling = ceiling; flat.sector = &sector; flat.controlsector = control ? &rover : nullptr;
    flat.lightmapPlane = control ? (inverted ? 0 : int(!ceiling)) : int(ceiling);
    flat.section = &section; flat.texture = &texture;
    flat.plane.texture = sky ? skyflatnum : 0;
    const float sourceHeight = control ? (ceiling ? 32.0f : 80.0f) : (ceiling ? 128.0f : 0.0f);
    float height = inverted ? 32.0f : sourceHeight;
    const float normalZ = ceiling ? -1.0f : 1.0f;
    flat.plane.plane = {{0, 0, normalZ}, -height * normalZ};
    // This is the already selected/flipped HWFlat::Process result. For an
    // inverted bottom-facing floor it comes from model floor, not ceiling.
    TArray<HWFlat> list; list.Push(flat);
    if (ambiguous)
    {
        HWFlat secondFace = flat;
        secondFace.lightmapPlane = 0;
        secondFace.plane.plane.D = -32.0f;
        list.Push(secondFace);
    }
    TestLevel level;
    HWFlatDispatcher dispatcher{&level};
    MeshBuilder state;
    DoomLevelMesh mesh;
    // Nonzero prefixes detect writes outside the actual allocation as well.
    mesh.Mesh.Vertices.resize(3);
    mesh.Mesh.Indexes.resize(3);
    mesh.Mesh.SurfaceIndexes.Push(888);
    mesh.Mesh.Surfaces.resize(2);
    mesh.DoomSurfaceInfos.resize(2);
    const auto draw = sky ? LevelMeshDrawType::Portal : LevelMeshDrawType::Opaque;
    const int iterations = test == "repeated" || rebuild ? 3 : 1;
    for (int repeat = 0; repeat < iterations; ++repeat)
    {
        if (rebuild && repeat != 0)
        {
            const int retiredFirst = mesh.Flats[0].FirstSurface;
            // Exact production retirement below must invalidate old current
            // associations before the CPU storage sink reuses those ranges.
            mesh.ReleaseTiles(retiredFirst);
            for (int old = 2; old < static_cast<int>(mesh.Mesh.Surfaces.size()); ++old)
                if (mesh.Mesh.Surfaces[old].LightmapTileIndex != -1) return fail("retired-surface-tile-survived");
            if (mesh.Lightmap.UsedTiles != 0 || mesh.Lightmap.FreeTiles.size() != 2)
                return fail("control-rebuild-tile-retirement");
            // BeginFrame clears frame bindings before any CreateFlat; geometry
            // allocation/free storage is a bounded reusable CPU adapter here.
            mesh.TileBindings.clear();
            mesh.Mesh.Vertices.resize(3); mesh.Mesh.UniformIndexes.resize(3);
            mesh.Mesh.Indexes.resize(3); mesh.Mesh.SurfaceIndexes.resize(1);
            mesh.Mesh.Surfaces.resize(2); mesh.DoomSurfaceInfos.resize(2);
            mesh.Flats[0] = DoomLevelMesh::FlatBlock{};
            mesh.Lightmap.AddedSurfaces.Clear(); mesh.Lightmap.AddedTiles.Clear();
            height = (inverted ? 32.0f : sourceHeight) + (repeat == 1 ? 16.0f : -8.0f);
            const int source = flat.lightmapPlane;
            const float sourceNormal = source ? -1.0f : 1.0f;
            model.sourcePlanes[source] = {{0,0,sourceNormal}, -height * sourceNormal};
            list[0].plane.plane = {{0,0,normalZ}, -height * normalZ};
        }
        const int oldSurfaces = static_cast<int>(mesh.Mesh.Surfaces.size());
        try { mesh.CreateFlatSurface(dispatcher, state, list, draw, false, 0, {37, 2}, 5); }
        catch (const std::runtime_error& error)
        {
            if (!ambiguous || std::string(error.what()).find("Unsupported ambiguous flat lightmap binding") != 0)
                return fail("unexpected-plane-rejection");
            if (mesh.Lightmap.Tiles.size() != 1 || mesh.Lightmap.Tiles[0].UseCount != 1 ||
                !close(mesh.Lightmap.Tiles[0].Bounds.max.Z, height)) return fail("ambiguous-owner-mutated");
            return true;
        }
        if (ambiguous) return fail("plane-binding-alias");
        const int expectedCount = one ? 1 : 2;
        if (static_cast<int>(mesh.Mesh.Surfaces.size()) != oldSurfaces + expectedCount) return fail("surface-count");
        for (int surface = oldSurfaces; surface < oldSurfaces + expectedCount; ++surface)
        {
            const auto& surf = mesh.Mesh.Surfaces[surface];
            const auto& info = mesh.DoomSurfaceInfos[surface];
            auto location = surf.MeshLocation;
            if (info.TypeIndex != (surface == oldSurfaces ? 101 : 103)) return fail("subsector-owner");
            if (info.ControlSector != (control ? &model : nullptr)) return fail("control-owner");
            if (surf.PortalIndex != (sky ? (ceiling ? 11 : 7) : 0) || surf.SectorGroup != 5) return fail("portal-owner");
            for (int element = location.StartElementIndex; element < location.StartElementIndex + location.NumElements; element += 3)
            {
                // Independent oracle: each triangle must resolve to the one
                // surface whose own element span contains that triangle.
                if (mesh.Mesh.SurfaceIndexes[element / 3] != surface) return fail("triangle-surface-owner");
                for (int corner = 0; corner < 3; ++corner)
                {
                    const int vertex = static_cast<int>(mesh.Mesh.Indexes[element + corner]);
                    if (vertex < location.StartVertIndex || vertex >= location.StartVertIndex + location.NumVerts)
                        return fail("triangle-vertex-owner");
                    const auto& point = mesh.Mesh.Vertices[vertex];
                    if (!close(point.z, sky ? (ceiling ? 32768.0f : -32768.0f) : height)) return fail("selected-plane-height");
                }
            }
            if (!close(surf.Plane.Z, normalZ) || !close(surf.Plane.W, height * normalZ)) return fail("selected-plane-normal");
            if (sky ? surf.LightmapTileIndex != -1 : surf.LightmapTileIndex < 0) return fail("tile-capability");
            if (!sky && mesh.Lightmap.Tiles[surf.LightmapTileIndex].Binding.TypeIndex != static_cast<uint32_t>(info.TypeIndex))
                return fail("tile-owner");
            if (!sky && mesh.Lightmap.Tiles[surf.LightmapTileIndex].RuntimeBakeOnly != inverted)
                return fail("retained-plane-interpretation");
            const int sourceAxis = control ? flat.lightmapPlane : int(ceiling);
            if (info.Subsector->LightmapTiles[sourceAxis][control ? 1 : 0] != surf.LightmapTileIndex)
                return fail("source-plane-table-owner");
            if (rebuild && (!close(surf.Bounds.min.Z, height) || !close(surf.Bounds.max.Z, height) ||
                !close(mesh.Lightmap.Tiles[surf.LightmapTileIndex].Plane.W, height * normalZ)))
                return fail("stale-control-height-reconstruction");
        }
        if (rebuild && (mesh.Mesh.Vertices.size() != 11 || mesh.Mesh.Indexes.size() != 15 ||
            mesh.Lightmap.Tiles.size() != 2 || mesh.Lightmap.UsedTiles != 2 || !mesh.Lightmap.FreeTiles.empty()))
            return fail("control-rebuild-range-or-slot-growth");
        const auto& material = mesh.Materials.back();
        if (material.albedo != 17 || material.normal != 29 || material.height != 41 || material.sampler != 53)
            return fail("whole-material-state");
    }
    if (mesh.Mesh.SurfaceIndexes[0] != 888) return fail("prefix-overwrite");
    return true;
}

int main(int argc, char** argv)
{
    if (argc != 2) return 2;
    if (!run(argv[1])) return 11;
    std::cout << "PASS " << argv[1] << '\n';
}
