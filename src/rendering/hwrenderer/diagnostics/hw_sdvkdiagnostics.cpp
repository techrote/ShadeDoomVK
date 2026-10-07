// SDVK-002: bounded reusable observation of actual renderer decisions. All
// diagnostic allocation, formatting and clocks are behind explicit opt-in.
#include "hw_sdvkdiagnostics.h"
#include "hw_sdvkdiagnosticcore.h"
#include "c_dispatch.h"
#include "m_argv.h"
#include "m_misc.h"
#include "printf.h"
#include "version.h"
#include "v_video.h"
#include "d_main.h"
#include "g_levellocals.h"
#include "a_dynlight.h"
#include "hw_clock.h"
#include "hw_shadowmap.h"
#include "hw_cvars.h"
#include "r_utility.h"
#include "hwrenderer/scene/hw_drawinfo.h"
#include "hwrenderer/scene/hw_drawcontext.h"
#include "hwrenderer/scene/hw_portal.h"
#include "vulkan/vk_renderdevice.h"
#include <chrono>
#include <map>
#include <set>
#include <thread>

extern int gametic;
EXTERN_CVAR(Bool, gl_levelmesh)
EXTERN_CVAR(Bool, gl_ubershaders)
EXTERN_CVAR(Bool, gl_lightprobe)
EXTERN_CVAR(Bool, vk_rayquery)
EXTERN_CVAR(Bool, cl_capfps)
EXTERN_CVAR(String, screenshot_type)

namespace SdvkDiagnostics
{
std::atomic<bool> EnabledFlag{false}, StateFlag{false}, GpuFlag{false};
}

namespace
{
using namespace SdvkObservation;
struct Observer
{
    bool Initialized = false, StateMode = true, Quit = false, Written = false, InFrame = false;
    bool Screenshot = false, GpuRequested = false;
    unsigned Requested = 1, Warmup = 35, Seen = 0, Collected = 0;
    uint64_t GpuGroups = 0;
    std::atomic<uint64_t> Frame{0};
    std::string Prefix, Build;
    RecordStore Records;
    std::chrono::steady_clock::time_point Started;
    std::map<const FDynamicLight*, std::string> Lights;
    std::set<std::string> GpuReasons;
    std::mutex GpuMutex;
};
Observer& Get() { static Observer observer; return observer; }
std::string& CacheRoot() { static std::string path; return path; }
struct SceneEntry { const HWDrawInfo* Owner; std::string Json; };
thread_local std::vector<SceneEntry> Scenes;

template<class V> std::string Vector(const V& value)
{
    return '[' + Number(value.X) + ',' + Number(value.Y) + ',' + Number(value.Z) + ']';
}

void Require(bool condition, const char* reason)
{
    if (!condition) throw std::runtime_error(reason);
}

const char* Option(const char* name, bool required = false)
{
    const int index = Args ? Args->CheckParm(name) : 0;
    if (!index) { Require(!required, "Missing SDVK observation option"); return nullptr; }
    Require(Args->CheckParm(name, index + 1) == 0, "Duplicate SDVK observation option");
    const char* value = Args->CheckValue(name);
    Require(value && *value && *value != '-', "SDVK observation option needs a value");
    return value;
}

std::string WorkingTree()
{
    const std::string identity = GetBuildIdentity();
    const std::string label = "Working tree: ";
    const auto start = identity.find(label);
    if (start == std::string::npos) return "unknown";
    const auto first = start + label.size();
    return identity.substr(first, identity.find('\n', first) - first);
}

void Initialize()
{
    auto& observer = Get();
    if (observer.Initialized) return;
    observer.Initialized = true;
    if (!Args || !Args->CheckParm("-sdvkobserve")) return;
    try
    {
        observer.Prefix = Option("-sdvkobserve", true);
        Require(SafePrefix(observer.Prefix), "Unsafe/oversized SDVK output prefix");
        // Use one normalized path in file and ordinary console screenshot calls.
        observer.Prefix = std::filesystem::absolute(std::filesystem::u8path(observer.Prefix)).lexically_normal().generic_u8string();
        Require(SafePrefix(observer.Prefix), "Invalid normalized SDVK output prefix");
        Require(!std::filesystem::exists(std::filesystem::u8path(observer.Prefix + ".renderer.json")) &&
                !std::filesystem::exists(std::filesystem::u8path(observer.Prefix + ".png")), "SDVK output prefix must be fresh");
        Require(std::filesystem::is_directory(std::filesystem::u8path(observer.Prefix).parent_path()), "SDVK output parent directory does not exist");
        if (const char* mode = Option("-sdvkobservemode"))
        {
            Require(std::string(mode) == "state" || std::string(mode) == "timing", "SDVK observation mode must be state or timing");
            observer.StateMode = std::string(mode) == "state";
        }
        observer.Requested = observer.StateMode ? 1 : 120;
        if (const char* count = Option("-sdvkobserveframes")) observer.Requested = ParseCount(count, 1, 4096);
        if (const char* count = Option("-sdvkobservewarmup")) observer.Warmup = ParseCount(count, 0, 100000);
        observer.Quit = Args->CheckParm("-sdvkobservequit") != 0;
        Object build;
        build.Str("commit", GetGitHash()).Str("working_tree", WorkingTree()).Str("description", GetGitDescription())
            .Str("identity", GetBuildIdentity()).Str("backend", screen->IsVulkan() ? "vulkan" : "other")
            .Str("renderer", V_IsHardwareRenderer() ? "hardware" : "software")
            .Str("device", screen->DeviceName() ? screen->DeviceName() : "unavailable");
        build.Raw("vulkan", screen->IsVulkan() ? SdvkDiagnostics::VulkanBuild(static_cast<VulkanRenderDevice*>(screen)) : Unavailable("backend is not Vulkan"));
        build.Raw("application_cache", CacheRoot().empty() ? Unavailable("no isolated application cache was requested") :
            Object().Bool("available", true).Str("path", CacheRoot()).Str("policy", "fresh shadercache.zdsc and pipelinecache.zdpc directory; driver-global cache uncontrolled").Json());
        observer.Build = build.Json();
        SdvkDiagnostics::EnabledFlag.store(true, std::memory_order_relaxed);
        observer.GpuRequested = Args->CheckParm("-sdvkobservegpu") != 0;
        SdvkDiagnostics::GpuFlag.store(observer.GpuRequested && screen->IsVulkan(), std::memory_order_relaxed);
        if (!SdvkDiagnostics::GpuTimingRequested()) observer.GpuReasons.insert("GPU timestamp groups were not explicitly requested or backend is not Vulkan");
        Printf(PRINT_HIGH | PRINT_NONOTIFY, "SDVK observation armed: %s frames=%u warmup=%u; %s.renderer.json\n",
            observer.StateMode ? "state" : "timing", observer.Requested, observer.Warmup, observer.Prefix.c_str());
    }
    catch (const std::exception& error)
    {
        observer.Records.Fail(error.what());
        Printf(PRINT_HIGH | PRINT_NONOTIFY, "SDVK_OBSERVATION_REJECTED: %s\n", error.what());
    }
}

std::string LightJson(const FDynamicLight* light, const char* map, unsigned ordinal)
{
    const std::string key = std::string(map) + ":light:" + std::to_string(ordinal);
    Require(light->pArgs && light->pLinearity && light->pSoftShadowRadius && light->pLightFlags,
        "Current light census contains unavailable authored metadata");
    const auto actor = light->target.Get();
    return Object().Str("semantic_key", key).Int("level_list_ordinal", ordinal).Str("map", map)
        .Int("actor_tid", actor ? actor->tid : 0).Raw("position", Vector(light->Pos))
        .Int("portal_group", light->Sector ? light->Sector->PortalGroup : -1).Num("radius", light->GetRadius())
        .Num("strength", light->GetStrength()).Num("linearity", light->GetLinearity()).Num("soft_shadow_radius", light->GetSoftShadowRadius())
        .Int("red", light->GetRed()).Int("green", light->GetGreen()).Int("blue", light->GetBlue()).Int("type", unsigned(light->lighttype))
        .Bool("active", light->IsActive()).Bool("spot", light->IsSpot()).Bool("subtractive", light->IsSubtractive()).Bool("additive", light->IsAdditive()).Json();
}

std::string LightIdentity(const FDynamicLight* light)
{
    const auto& lights = Get().Lights;
    const auto found = lights.find(light);
    return found == lights.end() ? Unavailable("light was not present in the current render-frame census") : found->second;
}

std::string Context(const HWDrawInfo* di)
{
    if (!di || !di->drawctx) return Unavailable("no active HWDrawInfo context");
    const auto& context = di->drawctx->portalState.RenderContext;
    if (!context.epoch || !context.identity) return Unavailable("HWDrawInfo has no classified production render-context identity");
    const auto& vp = di->Viewpoint;
    const std::string position = Vector(vp.Pos);
    const std::string angles = '[' + Number(vp.HWAngles.Yaw.Degrees()) + ',' + Number(vp.HWAngles.Pitch.Degrees()) + ',' + Number(vp.HWAngles.Roll.Degrees()) + ']';
    const std::string kind = di->mCurrentPortal ? di->mCurrentPortal->GetName() : "root";
    const std::string map = di->Level ? di->Level->MapName.GetChars() : "unknown";
    const int group = vp.sector ? vp.sector->PortalGroup : -1;
    // This is a comparison label, never a cache key: numeric view state and
    // renderer-local epoch/identity remain separately retained below.
    const std::string semantic = map + ':' + HWRenderContextTypeName(context.rootType) + ':' +
        std::to_string(context.probeFace) + ':' + std::to_string(context.eyeIndex) + ':' +
        std::to_string(context.recursionDepth) + ':' + kind + ':' + std::to_string(group) + ':' + position + ':' + angles;
    return Object().Bool("available", true).Str("semantic_key", semantic).Str("map", map)
        .Str("type", HWRenderContextTypeName(context.type)).Str("root_type", HWRenderContextTypeName(context.rootType))
        .Int("epoch", context.epoch).Int("identity", context.identity).Int("parent_identity", context.parentIdentity)
        .Int("depth", context.recursionDepth).Int("face", context.probeFace).Int("eye", context.eyeIndex).Int("portal_group", group)
        .Bool("line_mirror", context.lineMirror).Bool("plane_mirror", context.planeMirror).Bool("mirrored", context.mirrored)
        .Bool("history_eligible", context.historyEligible).Bool("postprocess_eligible", context.postprocessEligible)
        .Raw("position", position).Raw("angles", angles).Str("angle_space", "hardware-view")
        .Num("fraction", vp.TicFrac).Int("gametic", gametic).Json();
}

void Dump(bool complete)
{
    auto& observer = Get();
    if (observer.Written || !SdvkDiagnostics::Enabled()) return;
    if (!complete) observer.Records.Fail("Observation ended before the requested frame count");
    SdvkDiagnostics::StateFlag.store(false, std::memory_order_relaxed);
    SdvkDiagnostics::GpuFlag.store(false, std::memory_order_relaxed);
    SdvkDiagnostics::EnabledFlag.store(false, std::memory_order_relaxed);
    try
    {
        std::string reasons = "[";
        for (const auto& reason : observer.GpuReasons) { if (reasons.size() > 1) reasons += ','; reasons += Quote(reason); }
        reasons += ']';
        Object availability;
        availability.Raw("gpu_timing", Object().Bool("available", observer.GpuGroups > 0).Int("groups", observer.GpuGroups)
            .Str("scope", "existing named Vulkan timestamp groups resolved after the graphics fence; groups may nest and are not total GPU frame time")
            .Raw("unavailable_batches", reasons).Json())
            .Raw("cpu_timing", Object().Bool("available", observer.Collected > 0).Str("scope", "steady-clock elapsed RenderView including its canvas, probe and scene work; excludes later presentation/finish and observer end serialization").Json())
            .Raw("state", observer.StateMode && V_IsHardwareRenderer() ? Object().Bool("available", true).Str("scope", "observed immediate scene draws and actor per-pixel/CPU-aggregate light decisions; LevelMesh per-surface state remains unavailable").Json() : Unavailable(observer.StateMode ? "software scene state is covered by retained PF fixtures, not this hardware observer" : "timing mode does not collect per-draw state"))
            .Raw("gpu_total_frame", Unavailable("named timestamp groups are not an independently measured whole-frame duration"));
        const std::string rows = observer.Records.CloseJson();
        const bool pass = complete && observer.Records.Failure().empty() && observer.Records.DroppedCount() == 0;
        Object result;
        result.Str("schema", "sdvk-renderer-observation/v1").Str("status", pass ? "COLLECTED_PENDING_VALIDATION" : "FAIL")
            .Str("error", observer.Records.Failure()).Str("mode", observer.StateMode ? "state" : "timing")
            .Bool("gpu_timing_requested", observer.GpuRequested)
            .Raw("build", observer.Build).Int("requested_frames", observer.Requested).Int("warmup_frames", observer.Warmup)
            .Int("observed_frames", observer.Collected).Int("dropped_records", observer.Records.DroppedCount())
            .Raw("limits", Object().Int("max_frames", 4096).Int("max_records", RecordStore::DefaultMaxRecords)
                .Int("max_record_bytes", RecordStore::MaxRecordBytes).Int("max_retained_bytes", RecordStore::DefaultMaxBytes)
                .Int("retained_records", observer.Records.Size()).Int("retained_bytes", observer.Records.ByteCount()).Json())
            .Raw("availability", availability.Json()).Bool("performance_accepted", false)
            .Raw("screenshot", observer.Screenshot ? Object().Bool("available", true).Str("path", observer.Prefix + ".png")
                .Str("basis", "ordinary screenshot after the recorded render frame presentation; separately hashed by the harness").Json() : Unavailable("no automatic state-mode screenshot requested or capture failed"))
            .Str("light_identity_scope", "current frame census ordinal within each actual level light list, paired with semantic fields; never a durable gameplay identity")
            .Raw("records", rows);
        WriteFresh(std::filesystem::u8path(observer.Prefix + ".renderer.json"), result.Json() + '\n');
        observer.Written = true;
        Printf(PRINT_HIGH | PRINT_NONOTIFY, "SDVK_OBSERVATION_%s: %s.renderer.json\n", pass ? "COLLECTED" : "FAILED", observer.Prefix.c_str());
    }
    catch (const std::exception& error) { Printf(PRINT_HIGH | PRINT_NONOTIFY, "SDVK_OBSERVATION_WRITE_FAILED: %s\n", error.what()); }
}
}

namespace SdvkDiagnostics
{
std::string ApplicationCacheFilename(const char* leaf)
{
    if (!Args || !Args->CheckParm("-sdvkobserve") || !Args->CheckParm("-sdvkobservecache")) return {};
    Require(leaf && (std::string(leaf) == "shadercache.zdsc" || std::string(leaf) == "pipelinecache.zdpc"), "Unknown SDVK application cache filename");
    if (CacheRoot().empty())
    {
        Require(!Args->CheckParm("-pf020viewobserve"), "Independent SDVK and PF020 cache protocols cannot be combined");
        const auto requested = std::filesystem::absolute(std::filesystem::u8path(Option("-sdvkobservecache", true))).lexically_normal();
        Require(std::filesystem::is_directory(requested) && !std::filesystem::is_symlink(requested), "SDVK application cache must be an existing fresh directory");
        Require(std::filesystem::weakly_canonical(requested) == requested, "SDVK cache cannot use a symlink/reparse alias");
        Require(std::filesystem::is_empty(requested), "SDVK application cache directory must be empty at startup");
        CacheRoot() = requested.generic_u8string();
    }
    return (std::filesystem::u8path(CacheRoot()) / leaf).generic_u8string();
}

void Fail(const char* message) { Get().Records.Fail(message); }
void Emit(const char* kind, const std::string& object, bool deduplicate)
{
    const uint64_t frame = Get().Frame.load(std::memory_order_relaxed);
    if (Enabled() && frame) Get().Records.Add(kind, frame, object, deduplicate);
}

void BeginFrame()
{
    Initialize();
    if (!Enabled()) return;
    auto& observer = Get();
    try
    {
        Require(!observer.InFrame && Scenes.empty(), "Unbalanced SDVK render-frame/scene observation");
        observer.InFrame = true;
        ++observer.Seen;
        if (observer.Seen <= observer.Warmup) { observer.Frame.store(0, std::memory_order_relaxed); return; }
        Require(observer.Collected < observer.Requested, "SDVK completion hook did not close the requested frame interval");
        observer.Frame.store(uint64_t(observer.Collected) + 1, std::memory_order_relaxed);
        if (observer.StateMode && V_IsHardwareRenderer())
        {
            observer.Lights.clear();
            for (auto current : AllLevels())
            {
                unsigned ordinal = 0;
                for (auto light = current->lights; light; light = light->next)
                {
                    Require(observer.Lights.size() < 65536, "SDVK frame light census limit reached");
                    observer.Lights.emplace(light, LightJson(light, current->MapName.GetChars(), ordinal++));
                }
            }
            StateFlag.store(true, std::memory_order_relaxed);
        }
        observer.Started = std::chrono::steady_clock::now();
    }
    catch (const std::exception& error) { Fail(error.what()); }
}

void EndFrame()
{
    if (!Enabled()) return;
    auto& observer = Get();
    if (!observer.InFrame) { Fail("SDVK render-frame end without begin"); return; }
    observer.InFrame = false;
    if (!observer.Frame.load(std::memory_order_relaxed)) return;
    try
    {
        const double elapsed = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - observer.Started).count();
        Require(elapsed >= 0 && Scenes.empty(), "Invalid elapsed time or unbalanced SDVK scene stack");
        const bool hardware = V_IsHardwareRenderer();
        const auto counter = [hardware](int value) { return hardware ? std::to_string(value) : std::string("null"); };
        ++observer.Collected;
        Emit("frame", Object().Int("gametic", gametic).Str("map", level.MapName.GetChars()).Num("cpu_render_view_ms", elapsed)
            .Raw("camera", Object().Raw("position", Vector(r_viewpoint.Pos))
                .Raw("angles", '[' + Number(r_viewpoint.Angles.Yaw.Degrees()) + ',' + Number(r_viewpoint.Angles.Pitch.Degrees()) + ',' + Number(r_viewpoint.Angles.Roll.Degrees()) + ']')
                .Raw("hardware_angles", '[' + Number(r_viewpoint.HWAngles.Yaw.Degrees()) + ',' + Number(r_viewpoint.HWAngles.Pitch.Degrees()) + ',' + Number(r_viewpoint.HWAngles.Roll.Degrees()) + ']')
                .Num("fraction", r_viewpoint.TicFrac).Num("fov", r_viewpoint.FieldOfView.Degrees()).Json())
            .Raw("settings", Object().Int("vid_rendermode", int(vid_rendermode)).Bool("gl_levelmesh", bool(gl_levelmesh))
                .Bool("gl_ubershaders", bool(gl_ubershaders)).Bool("gl_lightprobe", bool(gl_lightprobe)).Bool("vk_rayquery", bool(vk_rayquery))
                .Bool("cl_capfps", bool(cl_capfps)).Bool("r_nointerpolate", r_NoInterpolate).Int("gl_texture_filter", int(gl_texture_filter))
                .Num("gl_texture_filter_anisotropic", double(gl_texture_filter_anisotropic)).Int("gl_multisample", int(gl_multisample))
                .Int("gl_light_shadows", int(gl_light_shadows)).Int("gl_light_shadow_filter", int(gl_light_shadow_filter))
                .Int("effective_sprite_light_mode", get_gl_spritelight())
                .Bool("gl_bloom", bool(gl_bloom)).Int("gl_ssao", int(gl_ssao)).Int("gl_tonemap", int(gl_tonemap)).Json())
            .Str("cpu_scope", "RenderView steady-clock interval; excludes later finish/presentation")
            .Bool("state_instrumentation", observer.StateMode).Bool("hardware_renderer", V_IsHardwareRenderer())
            .Int("width", screen->GetWidth()).Int("height", screen->GetHeight())
            .Raw("walls", counter(rendered_lines)).Raw("flats", counter(rendered_flats)).Raw("sprites", counter(rendered_sprites))
            .Raw("decals", counter(rendered_decals)).Raw("portals", counter(rendered_portals)).Raw("vertices", counter(vertexcount))
            .Raw("light_wall_considered", counter(iter_dlight)).Raw("light_wall_rendered", counter(draw_dlight))
            .Raw("light_flat_considered", counter(iter_dlightf)).Raw("light_flat_rendered", counter(draw_dlightf))
            .Raw("shadow_candidates", counter(ShadowMap::LightsCandidates)).Raw("shadow_selected", counter(ShadowMap::LightsShadowmapped))
            .Raw("shadow_dropped", counter(ShadowMap::LightsDropped)).Json());
        if (screen->IsVulkan()) VulkanResources(static_cast<VulkanRenderDevice*>(screen));
    }
    catch (const std::exception& error) { Fail(error.what()); }
}

void FramePresented()
{
    if (!Enabled()) return;
    auto& observer = Get();
    if (observer.Collected < observer.Requested && observer.Records.Failure().empty()) return;
    const bool complete = observer.Collected == observer.Requested;
    // Ordinary screenshot drawing is a separate producer and must not append
    // its own draw calls to the scene interval it is capturing.
    StateFlag.store(false, std::memory_order_relaxed);
    GpuFlag.store(false, std::memory_order_relaxed);
    if (observer.Quit && observer.StateMode && complete && observer.Records.Failure().empty())
    {
        try
        {
            const auto path = std::filesystem::u8path(observer.Prefix + ".png");
            Require(!std::filesystem::exists(path), "SDVK screenshot output already exists");
            Require(std::string(static_cast<const char*>(screenshot_type)) == "png", "SDVK automatic capture requires configured screenshot_type=png");
            // The console command schedules a future gameaction. Calling its
            // existing production writer here captures the completed frame
            // without introducing another simulation tic or view render.
            M_ScreenShot((observer.Prefix + ".png").c_str());
            observer.Screenshot = std::filesystem::is_regular_file(path) && std::filesystem::file_size(path) > 0;
            Require(observer.Screenshot, "Ordinary SDVK screenshot did not produce its requested file");
        }
        catch (const std::exception& error) { Fail(error.what()); }
    }
    Dump(complete);
    if (observer.Quit) AddCommandString("quit");
}

void SceneBegin(const HWDrawInfo* di, int drawmode)
{
    if (!StateEnabled()) return;
    try
    {
        Require(Scenes.size() < 32, "SDVK scene recursion observation limit reached");
        const auto value = Context(di);
        Scenes.push_back({di, value});
        Emit("context", Object().Raw("context", value).Int("drawmode", drawmode).Json());
    }
    catch (const std::exception& error) { Fail(error.what()); }
}

void SceneEnd(const HWDrawInfo* di)
{
    if (!StateEnabled()) return;
    if (Scenes.empty() || Scenes.back().Owner != di) { Fail("SDVK scene stack owner mismatch"); return; }
    Scenes.pop_back();
}

std::string CurrentContextJson()
{
    return Scenes.empty() ? Unavailable("draw is outside an observed HWDrawInfo scene") : Scenes.back().Json;
}

void LightDecision(const HWDrawInfo* di, const AActor* actor, const FDynamicLight* light,
    int group, double x, double y, double z, const char* source, const char* decision, const char* path)
{
    if (!StateEnabled()) return;
    try
    {
        const std::string query = '[' + Number(x) + ',' + Number(y) + ',' + Number(z) + ']';
        Emit("light-query", Object().Raw("context", Context(di)).Str("path", path)
            .Int("actor_tid", actor ? actor->tid : 0).Str("actor_class", actor ? actor->GetClass()->TypeName.GetChars() : "particle")
            .Raw("query_position", query).Int("portal_group", group).Str("candidate_source", source)
            .Str("decision", decision).Raw("light", light ? LightIdentity(light) : Unavailable("empty query has no light candidate")).Json(), true);
    }
    catch (const std::exception& error) { Fail(error.what()); }
}

void ShadowDecision(const FLevelLocals* owner, const FDynamicLight* light, const char* decision, int row)
{
    if (!StateEnabled()) return;
    try
    {
        Emit("shadow", Object().Str("map", owner ? owner->MapName.GetChars() : "unknown").Raw("light", LightIdentity(light))
            .Str("decision", decision).Int("row", row).Str("caster", "world-geometry")
            .Str("mode", "dynamic-1d-shadow-map").Str("scope", "actual central-view shadow candidate/row selection").Json(), true);
    }
    catch (const std::exception& error) { Fail(error.what()); }
}

void LightQuerySummary(const HWDrawInfo* di, const AActor* actor, double x, double y, double z,
    const char* source, uint64_t candidates, uint64_t filtered, uint64_t duplicates, uint64_t traces)
{
    if (!StateEnabled()) return;
    try
    {
        Require(filtered <= candidates && duplicates <= candidates - filtered, "Invalid native light-query partition");
        Emit("light-query", Object().Raw("context", Context(di)).Str("path", "actor-per-pixel-light-list")
            .Int("actor_tid", actor ? actor->tid : 0).Str("actor_class", actor ? actor->GetClass()->TypeName.GetChars() : "particle")
            .Raw("query_position", '[' + Number(x) + ',' + Number(y) + ',' + Number(z) + ']')
            .Str("candidate_source", source).Str("decision", "query-summary").Int("considered", candidates)
            .Int("selected", candidates - filtered - duplicates).Int("filtered", filtered).Int("duplicates", duplicates).Int("traces", traces).Json(), true);
    }
    catch (const std::exception& error) { Fail(error.what()); }
}

void GpuGroup(const char* name, double milliseconds)
{
    if (!GpuTimingRequested() || !Get().Frame.load(std::memory_order_relaxed)) return;
    try
    {
        Require(milliseconds >= 0, "Negative SDVK GPU group duration");
        Emit("timing", Object().Str("clock", "gpu").Str("name", name ? name : "")
            .Str("source", "vulkan-timestamp-query")
            .Num("milliseconds", milliseconds).Str("scope", "named group resolved after graphics fence; may nest; not GPU whole-frame duration").Json());
        ++Get().GpuGroups;
    }
    catch (const std::exception& error) { Fail(error.what()); }
}

void GpuUnavailable(const char* reason)
{
    if (!GpuTimingRequested()) return;
    auto& observer = Get();
    std::lock_guard<std::mutex> lock(observer.GpuMutex);
    const std::string value = reason ? reason : "unknown timestamp unavailability";
    if (observer.GpuReasons.size() < 32 || observer.GpuReasons.count(value)) observer.GpuReasons.insert(value);
    else Fail("SDVK GPU unavailability-reason limit reached");
    if (observer.Frame.load(std::memory_order_relaxed)) Emit("timing", Unavailable(reason ? reason : "unknown timestamp unavailability"), true);
}
}

CCMD(sdvk_observe_dump)
{
    if (!SdvkDiagnostics::Enabled() || Get().InFrame || !Scenes.empty()) { Printf(PRINT_HIGH | PRINT_NONOTIFY, "SDVK_OBSERVATION_DUMP_REJECTED\n"); return; }
    Dump(Get().Collected == Get().Requested);
}
