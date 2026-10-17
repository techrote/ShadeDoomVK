#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include "src/rendering/hwrenderer/diagnostics/hw_specialsurfacecontract.h"

struct FVector2 { float X, Y; FVector2(float x, float y) : X(x), Y(y) {} };
struct FVector3
{
    float X = 0, Y = 0, Z = 0;
    FVector3 operator-(const FVector3& other) const { return {X - other.X, Y - other.Y, Z - other.Z}; }
    float operator|(const FVector3& other) const { return X * other.X + Y * other.Y + Z * other.Z; }
};
struct Tile
{
    struct { int X = 16, Y = 24, Width = 32, Height = 32, ArrayIndex = 0; } AtlasLocation;
    struct { FVector3 TranslateWorldToLocal{-3.9f, -3.9f, -3.9f}, ProjLocalToU{0.25f, 0, 0}, ProjLocalToV{0, 0.25f, 0}; } Transform;
    // Exact current production LightmapTile::ToUV, extracted by the CPU runner.
#include "current_to_uv.inc"
};
struct Vertex
{
    float x = 0, y = 0, z = 0, lu = 0, lv = 0;
    FVector3 fPos() const { return {x, y, z}; }
};
void require(bool value) { if (!value) throw std::runtime_error("current lightmap UV contract failed"); }

int main()
{
    using namespace SdvkSurfaceObservation;
    Tile tile;
    Vertex actual{12, 20, 0, 0, 0};
    auto publish = [&] {
        const auto uv = tile.ToUV(actual.fPos(), 1024.0f);
        actual.lu = uv.X; actual.lv = uv.Y;
    };
    publish();
    require(CurrentVertexUV(tile, 1024, actual));
    // Accepted float-writer precision, preregistered before native execution.
    auto nearby = actual;
    nearby.lu = std::nextafter(nearby.lu, 1.0f);
    require(CurrentVertexUV(tile, 1024, nearby));
    // A live current receipt/page can be valid after recycling/repacking the
    // region. The retained old lu/lv must still fail against its new location.
    tile.AtlasLocation.X += 64;
    require(tile.AtlasLocation.ArrayIndex == 0);
    require(!CurrentVertexUV(tile, 1024, actual));
    publish();
    require(CurrentVertexUV(tile, 1024, actual));
    tile.AtlasLocation.Y += 1;
    require(!CurrentVertexUV(tile, 1024, actual));
    publish();
    require(CurrentVertexUV(tile, 1024, actual));
    tile.Transform.ProjLocalToU = {0.5f, 0, 0};
    require(!CurrentVertexUV(tile, 1024, actual));
    publish();
    require(CurrentVertexUV(tile, 1024, actual));
    auto bad = actual; bad.lu = std::numeric_limits<float>::quiet_NaN();
    require(!CurrentVertexUV(tile, 1024, bad));
    bad = actual; bad.lv = std::numeric_limits<float>::infinity();
    require(!CurrentVertexUV(tile, 1024, bad));
    bad = actual; bad.x = std::numeric_limits<float>::infinity();
    require(!CurrentVertexUV(tile, 1024, bad));
    require(!CurrentVertexUV(tile, 0, actual));
    require(!CurrentVertexUV(tile, -1, actual));
    // World-to-local border clamping is the production writer's behavior.
    actual.x = -10000; actual.y = 10000;
    publish();
    require(CurrentVertexUV(tile, 1024, actual));
}
