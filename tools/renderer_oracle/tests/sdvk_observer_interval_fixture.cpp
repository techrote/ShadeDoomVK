// SPDX-License-Identifier: GPL-3.0-or-later
// CPU service doubles for exact production observer functions. No renderer,
// Vulkan device, command submission, screenshot or native evidence is created.
#include <atomic>
#include <chrono>
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <vector>
#include "hw_sdvkdiagnostics.h"
#include "hw_sdvkdiagnosticcore.h"

using namespace SdvkObservation;
struct Name { const char* GetChars() const { return "INTERVAL"; } };
struct FDynamicLight
{
    FDynamicLight* next = nullptr;
    bool IsActive() const { return true; }
    bool IsSpot() const { return false; }
    bool IsSubtractive() const { return false; }
    bool IsAdditive() const { return false; }
};
struct FLevelLocals { Name MapName; FDynamicLight* lights = nullptr; };
static FLevelLocals level;
static std::vector<FLevelLocals*> AllLevels() { return {&level}; }
static bool V_IsHardwareRenderer() { return true; }
static std::string LightJson(const FDynamicLight*, const char*, unsigned ordinal)
{
    return Object().Int("ordinal", ordinal).Json();
}
struct TextureService
{
    struct Epoch { uint64_t Generation = 7; };
    Epoch GetLightProbeEpoch() const { return {}; }
    std::vector<int> Irradiancemaps = {0, 1}, Prefiltermaps = {0, 1};
};
struct CommandService { void FinishPublicationWitness() {} };
class VulkanRenderDevice
{
public:
    bool IsVulkan() const { return true; }
    int GetWidth() const { return 640; }
    int GetHeight() const { return 480; }
    TextureService* GetTextureManager() { return &Textures; }
    CommandService* GetCommands() { return &Commands; }
private:
    TextureService Textures;
    CommandService Commands;
};
static VulkanRenderDevice Device;
static VulkanRenderDevice* screen = &Device;
struct Angle { double Degrees() const { return 0; } };
struct Angles { Angle Yaw, Pitch, Roll; };
struct Position { double X = 0, Y = 0, Z = 0; };
struct Viewpoint
{
    Position Pos;
    struct Angles Angles, HWAngles;
    Angle FieldOfView;
    double TicFrac = 0;
};
static Viewpoint r_viewpoint;
namespace RenderVisualTime
{
struct SnapshotValue
{
    double DeltaSeconds = 0, AccumulatedSeconds = 0;
    uint64_t Generation = 1, MainFrame = 1;
    bool DeltaValid = true, InterpolationValid = true, Clamped = false;
    int Discontinuity = 0;
};
struct Clock { SnapshotValue Snapshot() const { return {}; } };
static Clock RuntimeClock() { return {}; }
static const char* ReasonName(int) { return "none"; }
}
static int gametic = 0, vid_rendermode = 4;
static int gl_texture_filter = 0, gl_multisample = 0;
static int gl_light_shadows = 0, gl_light_shadow_filter = 0;
static int gl_ssao = 0, gl_tonemap = 0;
static double gl_texture_filter_anisotropic = 1;
static bool gl_levelmesh = true, gl_ubershaders = true, gl_lightprobe = true;
static bool lm_dynlights = false;
static bool vk_rayquery = false, cl_capfps = false, r_NoInterpolate = false, gl_bloom = false;
static int rendered_lines = 0, rendered_flats = 0, rendered_sprites = 0;
static int rendered_decals = 0, rendered_portals = 0, vertexcount = 0;
static int iter_dlight = 0, draw_dlight = 0, iter_dlightf = 0, draw_dlightf = 0;
static int get_gl_spritelight() { return 0; }
struct ShadowMap { static constexpr int LightsCandidates = 0, LightsShadowmapped = 0, LightsDropped = 0; };
static const char* screenshot_type = "png";
static bool screenshot_quiet = true;
static void M_ScreenShot(const char*) { throw std::logic_error("CPU fixture cannot take screenshots"); }
static void AddCommandString(const char*) { throw std::logic_error("CPU fixture cannot run console commands"); }
static constexpr int PRINT_HIGH = 1, PRINT_NONOTIFY = 2;
template<class... Args> void Printf(int, const char*, Args...) {} // passive log sink
namespace CfxTrace
{
static bool WitnessEnabled() { return false; }
static void WitnessMark(const char*, const char*) {}
static void WitnessFail(const char*) {}
}

#include "observer_state.inc"
namespace
{
static std::vector<int> Scenes;
void Initialize() { Require(Get().Initialized, "CPU observer must be preinitialized"); }
void WitnessObserverFrame(const char*, const Observer&) {}
void DriveSamplerResetInput(const Observer&) {}
void DriveLightmapTransitionInput(const Observer&) {}
void DriveSpecialSurfaceInput(const Observer&) {}
}
#include "observer_dump.inc"

namespace SdvkDiagnostics
{
std::atomic<bool> EnabledFlag{false}, StateFlag{false}, GpuFlag{false};
bool SpecialSurfaceEnabled() { return false; }
bool SpecialSurfaceFrameSelected() { return false; }
const SpecialSurfaceMetadata& CurrentSpecialSurfaceMetadata()
{
    static const SpecialSurfaceMetadata value;
    return value;
}
}
class VkRenderState
{
public:
    const char* Phase = "main";
};
static int WarmupDraws = 0, MainDraws = 0, CanvasDraws = 0, LateDraws = 0;
static bool SnapshotFailure = false;
struct FSdvkDiagnosticAccess
{
    static void Draw(VkRenderState* state, int count, bool indexed, int)
    {
        const std::string phase = state->Phase;
        if (phase == "warmup") ++WarmupDraws;
        else if (phase == "canvas") ++CanvasDraws;
        else if (phase == "late") ++LateDraws;
        else ++MainDraws;
        // The real VulkanDraw guard dispatches to this payload service. Four
        // ordinary interleaved channels cannot coalesce across draw boundaries.
        // Keep the real default record and byte bounds; do not shrink capacity.
        // A bounded diagnostic payload makes the retained native failure's
        // 16 MiB byte cap bind before the separate 65,536-record cap.
        const auto value = Object().Str("phase", phase).Int("draw_count", count)
            .Bool("indexed", indexed).Str("diagnostic_text", std::string(1024, 'x')).Json();
        for (const char* kind : {"pipeline", "material", "probe", "shadow"})
            SdvkDiagnostics::Emit(kind, value, true);
    }
};
namespace SdvkDiagnostics
{
void VulkanResources(VulkanRenderDevice*)
{
    if (SnapshotFailure) throw std::runtime_error("fixture resource snapshot failure");
    Emit("resource", Object().Bool("state_enabled", StateEnabled()).Json());
}
}
#include "observer_methods.inc"

static void draw(const char* phase, int count)
{
    VkRenderState state;
    state.Phase = phase;
    for (int ordinal = 0; ordinal < count; ++ordinal)
        SdvkDiagnostics::VulkanDraw(&state, ordinal, false);
}

int main(int argc, char** argv)
{
    if (argc != 3) return 2;
    try
    {
        const std::string scenario = argv[1];
        Require(scenario == "state" || scenario == "timing" || scenario == "overflow" ||
            scenario == "snapshot-failure", "Unknown CPU fixture scenario");
        auto& observer = Get();
        observer.Initialized = true;
        observer.StateMode = scenario != "timing";
        observer.ProbeBuilderTrace = observer.StateMode;
        observer.GpuRequested = true;
        observer.Warmup = 2;
        observer.Requested = 3;
        observer.Prefix = argv[2];
        observer.Build = "{}";
        SnapshotFailure = scenario == "snapshot-failure";
        SdvkDiagnostics::EnabledFlag.store(true);
        SdvkDiagnostics::GpuFlag.store(true);
        if (observer.ProbeBuilderTrace)
            SdvkDiagnostics::ProbeBuilderLifecycle("warmup-reset", 7, 2, 0, 0, 0);
        const int flood = int(RecordStore::DefaultMaxRecords / 4) + 1;
        for (unsigned ordinal = 0; ordinal < observer.Warmup + observer.Requested; ++ordinal)
        {
            SdvkDiagnostics::BeginFrame();
            if (ordinal < observer.Warmup) draw("warmup", 3);
            else
            {
                // A canvas/off-scene producer within RenderView is in scope.
                draw("canvas", 1);
                draw("main", scenario == "overflow" ? flood : 1);
            }
            SdvkDiagnostics::EndFrame();
            // D_Display can perform arbitrarily many HUD/wipe draws before
            // presentation. Only the actual production guard admits payloads.
            draw("late", flood);
            if (ordinal == observer.Warmup && observer.ProbeBuilderTrace)
                SdvkDiagnostics::ProbeBuilderLifecycle("between-view-publication", 7, 2, 1, 0, 2);
            // Existing fence readback resolves named groups after RenderView;
            // Frame ID, Enabled and GpuFlag must remain live until presentation.
            SdvkDiagnostics::GpuGroup("after-render-view", 0.125);
            SdvkDiagnostics::FramePresented();
            if (!SdvkDiagnostics::Enabled()) break;
        }
        Require(observer.Written, "Production completion did not write an envelope");
        observer.ProbeBuilderEvents.clear();
        SdvkDiagnostics::ProbeBuilderLifecycle("after-close", 7, 2, 1, 0, 2);
        // Disabled callbacks must not grow collection after the written envelope.
        draw("late", 1);
        SdvkDiagnostics::GpuGroup("after-close", 0.125);
        std::cout << Object().Int("warmup_draw_payloads", WarmupDraws)
            .Int("main_draw_payloads", MainDraws).Int("canvas_draw_payloads", CanvasDraws)
            .Int("late_draw_payloads", LateDraws)
            .Int("lifecycle_events_after_close", observer.ProbeBuilderEvents.size())
            .Bool("enabled_after_presentation", SdvkDiagnostics::Enabled())
            .Bool("state_after_presentation", SdvkDiagnostics::StateEnabled())
            .Bool("gpu_after_presentation", SdvkDiagnostics::GpuTimingRequested()).Json() << '\n';
        return 0;
    }
    catch (const std::exception& error)
    {
        std::cerr << error.what() << '\n';
        return 11;
    }
}
