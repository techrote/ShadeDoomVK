#pragma once
#include <atomic>
#include <cstdint>
#include <string>
#include "hw_specialsurfacecontract.h"

struct HWDrawInfo;
struct FFlatVertex;
class LevelMesh;
struct HWSpriteRenderSurfaceState;
struct HWSpriteTangentBasis;
namespace HWActorProbeSelection { struct Result; }
struct FDynamicLight;
class AActor;
struct FLevelLocals;
class FMaterial;
class VkRenderState;
class VulkanRenderDevice;
class VulkanSampler;
enum class LevelMeshDrawSurface;

// SDVK-002 default-off, bounded observation only. Hot callers perform one
// relaxed flag load before constructing records or examining diagnostic state.
namespace SdvkDiagnostics
{
extern std::atomic<bool> EnabledFlag, StateFlag, GpuFlag;
inline bool Enabled() { return EnabledFlag.load(std::memory_order_relaxed); }
inline bool StateEnabled() { return StateFlag.load(std::memory_order_relaxed); }
inline bool GpuTimingRequested() { return GpuFlag.load(std::memory_order_relaxed); }
// Explicit SDVK-161 fixture requests twelve bounded submitted-work snapshots;
// frame/resource/lifecycle evidence still covers every retained frame.
bool SpecialSurfaceEnabled();
bool SpecialSurfaceFrameSelected();

void BeginFrame();
void EndFrame();
void FramePresented();
// Empty means use the inherited/PF cache path. A requested invalid isolated
// cache throws before any shared-cache fallback or renderer initialization.
std::string ApplicationCacheFilename(const char* leaf);
void SceneBegin(const HWDrawInfo* di, int drawmode);
void SceneEnd(const HWDrawInfo* di);
std::string CurrentContextJson();
void LightDecision(const HWDrawInfo* di, const AActor* actor, const FDynamicLight* light,
    int group, double x, double y, double z, const char* source, const char* decision,
    const char* path = "actor-per-pixel-light-list");
void LightQuerySummary(const HWDrawInfo* di, const AActor* actor, double x, double y, double z,
    const char* source, uint64_t candidates, uint64_t filtered, uint64_t duplicates, uint64_t traces);
void ShadowDecision(const FLevelLocals* level, const FDynamicLight* light, const char* decision, int row);
// State-only PF-009 provenance is coupled with actual draw uniforms on emission.
void SpriteBasisSelected(const HWSpriteRenderSurfaceState& surface, const HWSpriteTangentBasis& basis);
void ClearSpriteBasis();
// Read-only source-space actor probe selection attached to emitted draws.
void ActorProbeSelected(const HWActorProbeSelection::Result& selected, const HWSpriteRenderSurfaceState& surface,
    int actorTid, int portalGroupCount, int sourceSector, int renderSector, double x, double y, double z,
    double presentationX, double presentationY, double presentationZ);
void ClearActorProbeSelection();
// Bounded state-only trace of the actual incremental probe builder lifecycle.
// Used only with explicit -sdvkprobeownertrace; never changes bake decisions.
void ProbeBuilderLifecycle(const char* event, uint64_t ownerRevision, int probeCount,
    int iteration, int nextIndex, int collected);
// Per-sprite packed sun proxy snapshot, emitted only with the actual Vulkan card.
void ActorSunPacked(const AActor* actor, int packedSunCount, int tracedSunCount,
    int lightIndex, const HWSpriteRenderSurfaceState& surface);
void ClearActorSun();
std::string CurrentActorSunJson();
std::string CurrentActorProbeSelectionJson();
std::string CurrentSpriteBasisJson();
// Transient producer provenance; the observer emits it only after an actual
// Vulkan draw. Scopes restore the parent so recursion cannot inherit a decal.
struct SpecialSurfaceMetadata
{
    const char* Class = nullptr;
    int Type = 0, Side = -1, Sector = -1, ControlSector = -1, PortalGroup = -1;
    int Tile = -1, VertexLightmapPage = -1;
    int VertexFirst = -1, VertexCount = 0;
    double Plane[4] = {};
    bool HasPlane = false;
    bool FirstDrawOnly = false;
    SdvkSurfaceObservation::WrittenVertices WrittenUV;
    const char* UvScope = "no receiving atlas UV validation is available for this producer";
};
// Frame-owned copies of the actual writer output; collection is default-off.
void CaptureWrittenVertices(const LevelMesh* mesh, int first, int count, int tile, const FFlatVertex* written);
void ApplyWrittenVertices(SpecialSurfaceMetadata& value);
const SpecialSurfaceMetadata& CurrentSpecialSurfaceMetadata();
class SpecialSurfaceScope
{
public:
    explicit SpecialSurfaceScope(const SpecialSurfaceMetadata& value);
    ~SpecialSurfaceScope();
    SpecialSurfaceScope(const SpecialSurfaceScope&) = delete;
    SpecialSurfaceScope& operator=(const SpecialSurfaceScope&) = delete;
private:
    SpecialSurfaceMetadata Previous;
    bool Active = false;
};
void VulkanDraw(VkRenderState* state, int count, bool indexed, int firstIndex = 0);
// Actual LevelMesh indexed submission only; per-surface material/probe state
// comes from mesh storage and must not be borrowed from immediate uniforms.
void VulkanLevelMeshDraw(VkRenderState* state, int firstIndex, int count, LevelMeshDrawSurface surface);
void VulkanResources(VulkanRenderDevice* device);
std::string VulkanBuild(VulkanRenderDevice* device);
void GpuGroup(const char* name, double milliseconds);
void GpuUnavailable(const char* reason);
void Emit(const char* kind, const std::string& object, bool deduplicate = false);
void Fail(const char* message);
}
