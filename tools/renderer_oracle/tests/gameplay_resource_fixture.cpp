// CPU services for the actual VulkanResources mesh snapshot block and flags.
// No Vulkan device, renderer, authored owner insertion or simulation is used.
#include "hw_sdvkdiagnosticcore.h"
#include <iostream>
#include <vector>
using namespace SdvkObservation;
struct Observer { bool SpecialSurfaceInput=false, GameplayInput=false; } observer;
bool enabled=true;
bool Enabled() { return enabled; }
Observer& Get() { return observer; }
#include "gameplay_resource_flags.inc"
struct Epoch { uint64_t Generation=1; };
struct Mutations { uint64_t Geometry=1, Surface=1, Lights=1, Query=1, Portals=1, LightmapProbe=1, Resets=0; };
struct Mesh
{
    uint64_t owner=100;
    Mutations epochs;
    const Mutations& GetMutationEpochs() const { return epochs; }
    Epoch GetResourceEpoch() const { return {}; }
    uint64_t GetResourceOwner() const { return owner; }
} mesh;
struct Level { Mesh* levelMesh=&mesh; } level;
struct Textures { std::vector<int> Lightmaps; } textureManager;
struct Device { int GetFrameTileUpdates() const { return 0; } int GetFrameTileCompletions() const { return 0; } } rendererDevice;
std::string LightmapLifecycle(Mesh*, size_t, int, int) { return "{}"; }
int main(int argc, char** argv)
{
    if (argc != 3) return 2;
    const std::string mode=argv[1];
    observer.GameplayInput=mode=="gameplay" || mode=="disabled";
    observer.SpecialSurfaceInput=mode=="special" || mode=="disabled";
    enabled=mode!="disabled";
    mesh.owner=std::stoull(argv[2]);
    auto textures=&textureManager;
    auto device=&rendererDevice;
    Object result;
#include "gameplay_resource_mesh.inc"
    std::cout << result.Json() << '\n';
}
