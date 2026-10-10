#pragma once
#include <atomic>
#include <cstdint>
#include <string>

struct HWDrawInfo;
struct HWSpriteRenderSurfaceState;
struct HWSpriteTangentBasis;
struct FDynamicLight;
class AActor;
struct FLevelLocals;
class FMaterial;
class VkRenderState;
class VulkanRenderDevice;
class VulkanSampler;

// SDVK-002 default-off, bounded observation only. Hot callers perform one
// relaxed flag load before constructing records or examining diagnostic state.
namespace SdvkDiagnostics
{
extern std::atomic<bool> EnabledFlag, StateFlag, GpuFlag;
inline bool Enabled() { return EnabledFlag.load(std::memory_order_relaxed); }
inline bool StateEnabled() { return StateFlag.load(std::memory_order_relaxed); }
inline bool GpuTimingRequested() { return GpuFlag.load(std::memory_order_relaxed); }

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
std::string CurrentSpriteBasisJson();
void VulkanDraw(VkRenderState* state, int count, bool indexed);
void VulkanResources(VulkanRenderDevice* device);
std::string VulkanBuild(VulkanRenderDevice* device);
void GpuGroup(const char* name, double milliseconds);
void GpuUnavailable(const char* reason);
void Emit(const char* kind, const std::string& object, bool deduplicate = false);
void Fail(const char* message);
}
