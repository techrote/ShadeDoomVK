// Exact v5 admission/mutation loops and actual tile allocation/free methods.
// CPU only: pixel copying is an admission witness, not a renderer or WAD loader.
#include <algorithm>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <map>
#include <memory>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>
#include "tarray.h"
#include "engineerrors.h"
#include "hw_lightmaptile.h"

void* M_Malloc(size_t n) { auto p = std::malloc(n); if (!p) throw std::bad_alloc(); return p; }
void* M_Realloc(void* p, size_t n) { auto q = std::realloc(p, n); if (!q) throw std::bad_alloc(); return q; }
void M_Free(void* p) { std::free(p); }
void* M_Calloc(size_t n, size_t s) { auto p = std::calloc(n, s); if (!p) throw std::bad_alloc(); return p; }
[[noreturn]] void I_FatalError(const char* format, ...)
{
    char message[512]; va_list args; va_start(args, format);
    std::vsnprintf(message, sizeof(message), format, args); va_end(args);
    throw std::runtime_error(message);
}
void Printf(const char*, ...) {}
constexpr int developer = 0;
enum class LevelMeshMutationDomain { LightmapProbe };
class LevelMesh
{
public:
    struct
    {
        int UsedTiles = 0;
        TArray<LightmapTile> Tiles;
        TArray<int> FreeTiles;
    } Lightmap;
    void MarkMutation(LevelMeshMutationDomain) {}
    int AllocTile(const LightmapTile&);
    void FreeTile(int);
};
// @PRODUCTION_METHODS@
// @PRODUCTION_BOUNDS@
// @PRODUCTION_SPAN@

struct FLevelLocals {};
struct TileEntry
{
    uint32_t type = 5, typeIndex = 0, controlSector = 23, pixelsOffset = 0;
    uint16_t width = 2, height = 2;
    FVector3 translateWorldToLocal{777, 888, 999}, projLocalToU{1, 0, 0}, projLocalToV{0, 1, 0};
    bool IsValid(const FLevelLocals&) const { return true; }
    bool HasFiniteTransform() const { return true; }
    const char* GetTypeName() const { return "floor"; }
};

static bool admission(bool runtimeOnly)
{
    LevelMesh mesh;
    LightmapTile current;
    current.UseCount = 1;
    current.RuntimeBakeOnly = runtimeOnly;
    current.Transform.TranslateWorldToLocal = {11, 22, 33};
    current.NeedsInitialBake = true;
    const int index = mesh.AllocTile(current);
    LightmapTile* tile = &mesh.Lightmap.Tiles[index];
    FLevelLocals state;
    FLevelLocals* Level = &state;
    constexpr int textureSize = 1024;
    constexpr uint32_t numTexPixels = 4;
    int errors = 0;
    TileEntry entry;
    TArray<TileEntry> tileEntries; tileEntries.Push(entry);
    std::map<LightmapTileBinding, LightmapTile*> levelTiles;
    LightmapTileBinding key; key.Type = entry.type; key.TypeIndex = entry.typeIndex; key.ControlSector = entry.controlSector;
    levelTiles.emplace(key, tile);
    TArray<std::pair<const TileEntry*, LightmapTile*>> foundBindings;
    std::set<LightmapTile*> foundTiles;
    unsigned int runtimeBakeOnlyTiles = 0;
    // @PRODUCTION_ADMISSION@
    // @PRODUCTION_MUTATION@
    if (errors != 0) { std::cerr << "valid-v5-structure-rejected\n"; return false; }
    if (runtimeOnly)
    {
        if (foundBindings.Size() != 0 || runtimeBakeOnlyTiles != 1 || !foundTiles.empty() ||
            tile->Transform.TranslateWorldToLocal.X != 11 || !tile->NeedsInitialBake ||
            !tile->GeometryUpdate || !tile->ReceivedNewLight)
        { std::cerr << "wrong-plane-retained-payload-admitted\n"; return false; }
    }
    else if (foundBindings.Size() != 1 || runtimeBakeOnlyTiles != 0 || foundTiles.size() != 1 ||
             tile->Transform.TranslateWorldToLocal.X != 777 || tile->NeedsInitialBake ||
             tile->GeometryUpdate || tile->ReceivedNewLight)
    { std::cerr << "ordinary-v5-admission-changed\n"; return false; }
    return true;
}

static bool pool()
{
    LevelMesh mesh;
    LightmapTile runtime;
    runtime.RuntimeBakeOnly = true;
    const int slot = mesh.AllocTile(runtime);
    mesh.FreeTile(slot);
    if (mesh.Lightmap.Tiles[slot].RuntimeBakeOnly)
    { std::cerr << "retired-runtime-plane-policy\n"; return false; }
    LightmapTile ordinary;
    const int reused = mesh.AllocTile(ordinary);
    if (reused != slot || mesh.Lightmap.Tiles[slot].RuntimeBakeOnly)
    { std::cerr << "runtime-plane-policy-aliased-reused-slot\n"; return false; }
    return true;
}

int main(int argc, char** argv)
{
    if (argc != 2) return 2;
    const std::string test = argv[1];
    const bool ok = test == "ordinary-v5" ? admission(false) : test == "inverted-v5" ? admission(true) : test == "pool-reset" ? pool() : false;
    if (!ok) return 11;
    std::cout << "PASS " << test << '\n';
}
