/* PF020: newly authored bounded scene diagnostics. Opt-in fixture only. */
#include "hw_pfviewdiagnostics.h"
#include "c_dispatch.h"
#include "m_argv.h"
#include "printf.h"
#include "g_levellocals.h"
#include "gametexture.h"
#include "flatvertices.h"
#include "portal.h"
#include "hwrenderer/scene/hw_drawinfo.h"
#include "hwrenderer/scene/hw_drawstructs.h"
#include "hwrenderer/scene/hw_drawcontext.h"
#include "hwrenderer/scene/hw_portal.h"
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

extern int gametic;
extern bool singletics;

namespace
{
struct Scene
{
    const HWDrawInfo* Owner = nullptr;
    uint64_t Identity = 0;
    std::string Path;
};
struct State
{
    bool Checked = false, Enabled = false, Fixture = false, FixedFraction = false;
    bool Written = false, DestinationValidated = false;
    bool ClockRequested = false, ClockStarted = false;
    int ClockStartTic = -1;
    std::string Prefix, Error, RootType, Phase = "startup", CompletedKey;
    int Side = -1, Eye = 0;
    uint64_t Root = 0, Next = 0, Scenes = 0, Sprites = 0, Restores = 0, Postprocess = 0;
    std::vector<Scene> Stack;
    std::set<std::string> Seen;
    std::vector<std::string> Records;
} Observer;

void Require(bool value, const char* message)
{
    if (!value) throw std::runtime_error(message);
}
std::string Quote(const char* value)
{
    std::ostringstream out;
    out << '"';
    for (const unsigned char* p = reinterpret_cast<const unsigned char*>(value ? value : ""); *p; ++p)
    {
        if (*p == '"' || *p == '\\') out << '\\' << char(*p);
        else if (*p < 32 || *p >= 127) out << "\\u00" << std::hex << std::setw(2) << std::setfill('0') << unsigned(*p) << std::dec;
        else out << char(*p);
    }
    out << '"';
    return out.str();
}
void Number(std::ostream& out, double value)
{
    Require(std::isfinite(value), "Nonfinite native scene field");
    out << std::setprecision(17) << value;
}
template<class V> void Vector(std::ostream& out, const V& value)
{
    out << '['; Number(out, value.X); out << ','; Number(out, value.Y); out << ','; Number(out, value.Z); out << ']';
}
template<class R> void Angles(std::ostream& out, const R& value)
{
    out << '['; Number(out, value.Yaw.Degrees()); out << ',';
    Number(out, value.Pitch.Degrees()); out << ','; Number(out, value.Roll.Degrees()); out << ']';
}
void Matrix(std::ostream& out, const float* value)
{
    out << '[';
    for (int i = 0; i < 16; ++i) { if (i) out << ','; Number(out, value[i]); }
    out << ']';
}
bool Active()
{
    return Observer.Enabled && Observer.Fixture && !Observer.Written && Observer.Error.empty();
}
std::string Key(const HWDrawInfo* di)
{
    return Observer.RootType + ":" + std::to_string(Observer.Side) + ":" + std::to_string(Observer.Eye) +
        (Observer.Stack.empty() ? ":root" : Observer.Stack.back().Path) +
        ":group" + std::to_string(di->Viewpoint.sector ? di->Viewpoint.sector->PortalGroup : -1);
}
void Add(const std::string& key, const std::string& json)
{
    const auto phasedKey = Observer.Phase + ":" + key;
    if (Observer.Seen.count(phasedKey)) return;
    Require(Observer.Records.size() < 2048 && json.size() < 16384, "PF020 bounded record limit reached");
    const auto phasedJson = "{\"phase\":" + Quote(Observer.Phase.c_str()) + "," + json.substr(1);
    Require(phasedJson.size() < 16384, "PF020 bounded phased record limit reached");
    Observer.Seen.insert(phasedKey);
    Observer.Records.push_back(phasedJson);
}
std::string SceneKey(const HWDrawInfo* di, bool invocation = true)
{
    Require(di && !Observer.Stack.empty(), "No completed native scene key");
    const auto& scene = Observer.Stack.back();
    std::ostringstream out;
    out << "{\"phase\":" << Quote(Observer.Phase.c_str()) << ",\"semanticKey\":" << Quote(Key(di).c_str());
    if (invocation)
        out << ",\"diagnosticRoot\":" << Observer.Root << ",\"diagnosticIdentity\":" << scene.Identity
            << ",\"diagnosticParent\":" << (Observer.Stack.size() > 1 ? Observer.Stack[Observer.Stack.size()-2].Identity : 0);
    out << ",\"rootType\":" << Quote(Observer.RootType.c_str()) << ",\"face\":" << Observer.Side
        << ",\"eye\":" << Observer.Eye << ",\"path\":" << Quote(scene.Path.c_str())
        << ",\"sectorGroup\":" << (di->Viewpoint.sector ? di->Viewpoint.sector->PortalGroup : -1) << '}';
    return out.str();
}
void Portal(std::ostream& out, const HWDrawInfo* di)
{
    const auto* linePortal = dynamic_cast<const HWLineToLinePortal*>(di->mCurrentPortal);
    if (!linePortal) { out << ",\"linePortalAvailable\":false"; return; }
    Require(linePortal->glport && linePortal->glport->lines.Size() <= 64, "Invalid/beyond-limit native line portal span");
    out << ",\"linePortalAvailable\":true,\"linePortalSpan\":[";
    for (unsigned i = 0; i < linePortal->glport->lines.Size(); ++i)
    {
        if (i) out << ',';
        const auto* portal = linePortal->glport->lines[i];
        Require(portal && portal->mOrigin && portal->mDestination, "Native line portal missing its endpoints");
        const auto* origin = portal->mOrigin;
        const auto* destination = portal->mDestination;
        out << "{\"type\":" << unsigned(portal->mType) << ",\"flags\":" << unsigned(portal->mFlags)
            << ",\"linked\":" << (portal->mType == PORTT_LINKED ? "true" : "false")
            << ",\"originLineIndex\":" << origin->Index() << ",\"destinationLineIndex\":" << destination->Index()
            << ",\"originPortalIndex\":" << origin->portalindex << ",\"destinationPortalIndex\":" << destination->portalindex
            << ",\"destinationLinksBack\":" << (destination->getPortalDestination() == origin ? "true" : "false")
            << ",\"destinationPortalType\":" << destination->getPortalType()
            << ",\"sourceGroup\":" << (origin->frontsector ? origin->frontsector->PortalGroup : -1)
            << ",\"destinationGroup\":" << (destination->frontsector ? destination->frontsector->PortalGroup : -1)
            << ",\"displacementXY\":[";
        Number(out, portal->mDisplacement.X); out << ','; Number(out, portal->mDisplacement.Y);
        out << "],\"angleDifference\":"; Number(out, portal->mAngleDiff.Degrees()); out << '}';
    }
    out << ']';
}
void View(std::ostream& out, const HWDrawInfo* di)
{
    const auto& vp = di->Viewpoint;
    const auto& portal = di->drawctx->portalState;
    out << "\"tic\":" << gametic << ",\"fraction\":";
    Number(out, vp.TicFrac);
    out << ",\"position\":"; Vector(out, vp.Pos);
    out << ",\"hardwareAngles\":["; Number(out, vp.HWAngles.Yaw.Degrees()); out << ',';
    Number(out, vp.HWAngles.Pitch.Degrees()); out << ','; Number(out, vp.HWAngles.Roll.Degrees()); out << ']';
    out << ",\"viewpointIndex\":" << di->vpIndex
        << ",\"sectorGroup\":" << (vp.sector ? vp.sector->PortalGroup : -1)
        << ",\"lineMirrorFlag\":" << portal.MirrorFlag << ",\"planeMirrorFlag\":" << portal.PlaneMirrorFlag
        << ",\"mirrored\":" << (portal.isMirrored() ? "true" : "false")
        << ",\"viewMatrix\":"; Matrix(out, di->VPUniforms.mViewMatrix.get());
    out << ",\"projectionMatrix\":"; Matrix(out, di->VPUniforms.mProjectionMatrix.get());
    out << ",\"cameraPositionUniform\":[";
    for (int i = 0; i < 4; ++i) { if (i) out << ','; Number(out, di->VPUniforms.mCameraPos[i]); }
    out << ']';
#ifdef PF020_ORIGINAL_SEAMS
    out << ",\"productionContextAvailable\":false";
#else
    const auto& context = portal.RenderContext;
    out << ",\"productionContextAvailable\":true,\"productionContext\":{\"type\":"
        << Quote(HWRenderContextTypeName(context.type)) << ",\"rootType\":" << Quote(HWRenderContextTypeName(context.rootType))
        << ",\"epoch\":" << context.epoch << ",\"identity\":" << context.identity << ",\"parentIdentity\":" << context.parentIdentity
        << ",\"depth\":" << context.recursionDepth << ",\"face\":" << context.probeFace << ",\"eye\":" << context.eyeIndex
        << ",\"lineMirror\":" << (context.lineMirror ? "true" : "false")
        << ",\"planeMirror\":" << (context.planeMirror ? "true" : "false")
        << ",\"mirrored\":" << (context.mirrored ? "true" : "false")
        << ",\"postprocessEligible\":" << (context.postprocessEligible ? "true" : "false")
        << ",\"historyEligible\":" << (context.historyEligible ? "true" : "false") << '}';
#endif
}
void Fail(const std::exception& error) { Observer.Error = error.what(); }
}

namespace Pf020ViewDiagnostics
{
bool FixtureActive() { return Active(); }
const char* OutputPrefix() { return Observer.DestinationValidated ? Observer.Prefix.c_str() : nullptr; }
std::string CurrentSceneKeyJson() { return Active() ? Observer.CompletedKey : std::string(); }
std::string ActiveSceneKeyJson()
{
    if (!Active() || Observer.Stack.empty()) return std::string();
    try { return SceneKey(Observer.Stack.back().Owner); }
    catch (const std::exception& error) { Fail(error); return std::string(); }
}
std::string ActiveSemanticKeyJson()
{
    if (!Active() || Observer.Stack.empty()) return std::string();
    try { return SceneKey(Observer.Stack.back().Owner, false); }
    catch (const std::exception& error) { Fail(error); return std::string(); }
}
bool Enabled()
{
    if (!Observer.Checked)
    {
        Observer.Checked = true;
        if (Args && Args->CheckParm("-pf020viewobserve"))
        {
            Observer.Enabled = true;
            try
            {
                const char* prefix = Args->CheckValue("-pf020viewobserve");
                Require(prefix && *prefix && Args->CheckParm("-pf020viewobserve", Args->CheckParm("-pf020viewobserve") + 1) == 0,
                        "Exactly one fresh -pf020viewobserve prefix is required");
                Observer.Prefix = prefix;
                Require(Observer.Prefix.size() <= 1024 && !std::filesystem::exists(Observer.Prefix + ".scene.json"), "Existing/invalid scene output prefix");
                Observer.DestinationValidated = true;
                if (Args->CheckParm("-pf020viewfraction"))
                {
                    const char* fraction = Args->CheckValue("-pf020viewfraction");
                    Require(fraction && std::string(fraction) == "0.5" && Args->CheckParm("-pf020viewfraction", Args->CheckParm("-pf020viewfraction") + 1) == 0,
                            "The only supported explicit fixture actor fraction is0.5");
                    Observer.FixedFraction = true;
                }
            }
            catch (const std::exception& error) { Fail(error); }
        }
    }
    return Observer.Enabled && Observer.Error.empty() && !Observer.Written;
}
bool BeginFixtureClock(const char* map, bool ordinarySinglePlayer)
{
    if (!Args || !Args->CheckParm("-pf020viewclock")) return false;
    Observer.ClockRequested = true;
    try
    {
        Require(Enabled() && Observer.FixedFraction && Observer.DestinationValidated,
                "The fixture clock requires fresh scene observations and the explicit actor fraction");
        const char* mode = Args->CheckValue("-pf020viewclock");
        Require(mode && std::string(mode) == "single-tic" &&
                Args->CheckParm("-pf020viewclock", Args->CheckParm("-pf020viewclock") + 1) == 0,
                "Exactly one -pf020viewclock single-tic request is required");
        Require(ordinarySinglePlayer && !singletics && map && std::string(map) == "PFVTEST" &&
                gametic == 0 && !Observer.ClockStarted && Observer.Stack.empty(),
                "The fixture clock requires the loaded PFVTEST single-player map before its first tic");
        Observer.ClockStartTic = gametic;
        Observer.ClockStarted = true;
        Printf("PF020_VIEW_CLOCK single-tic start=%d\n", gametic);
        return true;
    }
    catch (const std::exception& error) { Fail(error); return false; }
}
void BeginRoot(bool mainview, bool toscreen, int side, const char* map)
{
    if (!Enabled()) return;
    Observer.Fixture = map && std::string(map) == "PFVTEST";
    if (!Active()) return;
    if (!Observer.Stack.empty()) { Observer.Error = "Previous native scene stack was not balanced"; return; }
    Observer.CompletedKey.clear();
    if (side < -1 || side > 5) { Observer.Error = "Native probe face is outside the six-face range"; return; }
    Observer.Side = side; Observer.Eye = 0; ++Observer.Root;
    Observer.RootType = side >= 0 ? "light-probe" : mainview ? toscreen ? "main" : "save-picture" : "camera-texture";
}
double SetupFraction(double inherited, int side, const char* map)
{
    return Enabled() && Observer.FixedFraction && side == -1 && map && std::string(map) == "PFVTEST" ? 0.5 : inherited;
}
double ActorFraction(double inherited)
{
    return Active() && Observer.FixedFraction && Observer.Side < 0 ? 0.5 : inherited;
}
void BeginEye(int eye) { if (Active()) Observer.Eye = eye; }
void SceneBegin(const HWDrawInfo* di, int drawmode)
{
    if (!Active()) return;
    try
    {
        Require(di && di->drawctx && Observer.Stack.size() < 32, "Invalid/beyond-limit native scene stack");
        Scene scene;
        scene.Owner = di; scene.Identity = ++Observer.Next;
        scene.Path = Observer.Stack.empty() ? ":root" : Observer.Stack.back().Path + "/" +
            (di->mCurrentPortal ? di->mCurrentPortal->GetName() : "unknown-portal");
        const auto parent = Observer.Stack.empty() ? 0 : Observer.Stack.back().Identity;
        Observer.Stack.push_back(scene); ++Observer.Scenes;
        std::ostringstream out;
        out << "{\"event\":\"scene\",\"semanticKey\":" << Quote(Key(di).c_str()) << ",\"rootType\":" << Quote(Observer.RootType.c_str())
            << ",\"face\":" << Observer.Side << ",\"eye\":" << Observer.Eye << ",\"drawmode\":" << drawmode
            << ",\"diagnosticRoot\":" << Observer.Root << ",\"diagnosticIdentity\":" << scene.Identity
            << ",\"diagnosticParent\":" << parent << ",\"depth\":" << Observer.Stack.size() - 1 << ',';
        View(out, di); Portal(out, di); out << '}'; Add("scene:" + Key(di), out.str());
    }
    catch (const std::exception& error) { Fail(error); }
}
void SceneEnd(const HWDrawInfo* di)
{
    // Pop even after a record failure, so diagnostics never change traversal.
    if (Observer.Enabled && Observer.Fixture && !Observer.Stack.empty())
    {
        if (Observer.Stack.back().Owner != di) Observer.Error = "Native scene stack owner mismatch";
        else
        {
            if (Active())
            {
                try
                {
                    // Deduplicated scene rows may belong to an earlier frame.
                    // A producer must carry its own actual completed view.
                    const auto key = SceneKey(di);
                    std::ostringstream completed;
                    completed << key.substr(0, key.size() - 1) << ",\"completedView\":{\"depth\":"
                        << Observer.Stack.size() - 1 << ',';
                    View(completed, di);
                    completed << "}}";
                    Require(completed.str().size() < 16384, "PF020 completed view snapshot limit reached");
                    Observer.CompletedKey = completed.str();
                }
                catch (const std::exception& error) { Fail(error); }
            }
            Observer.Stack.pop_back();
        }
    }
}
void Restored(const HWDrawInfo* di)
{
    if (!Active()) return;
    try
    {
        Require(!Observer.Stack.empty() && Observer.Stack.back().Owner == di, "Native portal restoration has no matching parent");
        ++Observer.Restores;
        std::ostringstream out;
        out << "{\"event\":\"restored\",\"semanticKey\":" << Quote(Key(di).c_str()) << ',';
        View(out, di); out << '}'; Add("restored:" + Key(di), out.str());
    }
    catch (const std::exception& error) { Fail(error); }
}
void SpriteVertices(const HWDrawInfo* di, const HWSprite* sprite, const FFlatVertex* vertices)
{
    if (!Active() || !sprite || !sprite->actor || sprite->actor->tid < 4200 || sprite->actor->tid > 4599) return;
    try
    {
        Require(vertices && !Observer.Stack.empty() && Observer.Stack.back().Owner == di, "Emitted sprite has no actual scene owner or vertices");
        const auto* actor = sprite->actor; ++Observer.Sprites;
        std::ostringstream out;
        out << "{\"event\":\"sprite-vertices\",\"semanticKey\":" << Quote(Key(di).c_str()) << ",\"tid\":" << actor->tid
            << ",\"sprite\":" << actor->sprite << ",\"frame\":" << unsigned(actor->frame)
            << ",\"renderflags\":" << uint32_t(actor->renderflags) << ",\"renderflags2\":" << uint32_t(actor->renderflags2)
            << ",\"texture\":" << Quote(sprite->texture ? sprite->texture->GetName().GetChars() : "")
            << ",\"translation\":" << sprite->translation.index() << ",\"shaderOverride\":" << sprite->OverrideShader
            << ",\"renderStyle\":[" << unsigned(sprite->RenderStyle.BlendOp) << ',' << unsigned(sprite->RenderStyle.SrcAlpha) << ','
            << unsigned(sprite->RenderStyle.DestAlpha) << ',' << unsigned(sprite->RenderStyle.Flags) << ']'
            << ",\"polyoffset\":" << (sprite->polyoffset ? "true" : "false") << ",\"actorPosition\":"; Vector(out, actor->Pos());
        out << ",\"previousPosition\":"; Vector(out, actor->Prev);
        out << ",\"interpolatedPosition\":"; Vector(out, actor->InterpolatedPosition(di->Viewpoint.TicFrac));
        out << ",\"previousAngles\":"; Angles(out, actor->PrevAngles);
        out << ",\"actorAngles\":"; Angles(out, actor->Angles);
        out << ",\"interpolatedAngles\":"; Angles(out, actor->InterpolatedAngles(di->Viewpoint.TicFrac));
        out << ",\"effectiveSpriteAngles\":"; Angles(out, sprite->Angles);
        out << ",\"fraction\":"; Number(out, di->Viewpoint.TicFrac);
        out << ",\"sourceGroup\":" << (actor->Sector ? actor->Sector->PortalGroup : -1)
            << ",\"verticesXYZUV\":[";
        for (int i = 0; i < 4; ++i)
        {
            if (i) out << ',';
            out << '['; Number(out, vertices[i].x); out << ','; Number(out, vertices[i].y); out << ',';
            Number(out, vertices[i].z); out << ','; Number(out, vertices[i].u); out << ','; Number(out, vertices[i].v); out << ']';
        }
        out << ']';
#ifdef PF020_ORIGINAL_SEAMS
        out << ",\"productionSurfaceAvailable\":false";
#else
        const auto& surface = sprite->RenderSurface;
        out << ",\"productionSurfaceAvailable\":true,\"productionSurface\":{\"presentation\":" << unsigned(surface.presentation)
            << ",\"spriteType\":" << surface.spriteType << ",\"xyBillboard\":" << (surface.xyBillboard ? "true" : "false")
            << ",\"facesCamera\":" << (surface.facesCamera ? "true" : "false")
            << ",\"frameMirrored\":" << (surface.frameMirrored ? "true" : "false")
            << ",\"uvMirrorX\":" << (surface.uvMirrorX ? "true" : "false") << ",\"uvMirrorY\":" << (surface.uvMirrorY ? "true" : "false")
            << ",\"sourceGroup\":" << surface.sourcePortalGroup << ",\"renderGroup\":" << surface.renderPortalGroup
            << ",\"throughPortal\":" << surface.throughPortalMode << '}';
#endif
        out << '}'; Add("sprite:" + Key(di) + ":" + std::to_string(actor->tid), out.str());
    }
    catch (const std::exception& error) { Fail(error); }
}
void PostprocessCompleted(const HWDrawInfo* di)
{
    if (!Active()) return;
    try
    {
        ++Observer.Postprocess;
        std::ostringstream out;
        out << "{\"event\":\"postprocess-completed\",\"semanticKey\":" << Quote(Key(di).c_str())
            << ",\"rootType\":" << Quote(Observer.RootType.c_str()) << ",\"face\":" << Observer.Side << '}';
        Add("postprocess:" + Key(di), out.str());
    }
    catch (const std::exception& error) { Fail(error); }
}
}

CCMD(pf020view_begin)
{
    if (!Pf020ViewDiagnostics::Enabled() || !Observer.Stack.empty() || argv.argc() != 2)
    { Printf("PF020_VIEW_BEGIN_REJECTED\n"); return; }
    const std::string phase = argv[1];
    if (phase.empty() || phase.size() > 32 || phase.find_first_not_of("abcdefghijklmnopqrstuvwxyz0123456789-") != std::string::npos)
    { Printf("PF020_VIEW_BEGIN_REJECTED\n"); return; }
    Observer.Phase = phase;
    // Preserve one-time startup probe production and its original phase identity.
    // Phase is part of deduplication, so later observations remain independent.
    Observer.CompletedKey.clear();
    Printf("PF020_VIEW_BEGIN %s\n", phase.c_str());
}

CCMD(pf020view_dump)
{
    Pf020ViewDiagnostics::Enabled();
    if (!Observer.Enabled || Observer.Written) { Printf("PF020_VIEW_DUMP_REJECTED\n"); return; }
    try
    {
        Require(Observer.Stack.empty(), "Dump attempted during a native scene");
        Require(Observer.DestinationValidated, "No validated fresh scene output destination");
        Require(!std::filesystem::exists(Observer.Prefix + ".scene.json"), "Scene output already exists");
        std::ofstream file(Observer.Prefix + ".scene.json", std::ios::binary | std::ios::out);
        Require(bool(file), "Scene output cannot be created");
        file << "{\"schema\":\"pf020-native-scene-observation/v1\",\"status\":"
             << Quote(Observer.Error.empty() && Observer.Scenes && Observer.Sprites ? "COLLECTED_STATE_ONLY" : "FAIL")
             << ",\"error\":" << Quote(Observer.Error.c_str()) << ",\"phase\":" << Quote(Observer.Phase.c_str())
             << ",\"sceneCalls\":" << Observer.Scenes << ",\"spriteVertexCalls\":" << Observer.Sprites
             << ",\"restorationCalls\":" << Observer.Restores << ",\"fixedActorFractionRequested\":" << (Observer.FixedFraction ? "true" : "false")
             << ",\"fixtureClock\":{\"requested\":" << (Observer.ClockRequested ? "true" : "false")
             << ",\"activated\":" << (Observer.ClockStarted ? "true" : "false")
             << ",\"mode\":" << Quote(Observer.ClockStarted ? "single-tic-per-display" : "adaptive")
             << ",\"startTic\":" << Observer.ClockStartTic << ",\"endTic\":" << gametic
             << ",\"singletics\":" << (singletics ? "true" : "false") << '}'
             << ",\"postprocessSceneCalls\":" << Observer.Postprocess
             << ",\"imagesCapturedByThisObserver\":false,\"freezeAccepted\":false,\"records\":[";
        for (size_t i = 0; i < Observer.Records.size(); ++i) { if (i) file << ','; file << Observer.Records[i]; }
        file << "]}\n"; file.flush(); Require(bool(file), "Scene output write failed");
        Observer.Written = true;
        Printf("PF020_VIEW_STATE_WRITTEN\n");
    }
    catch (const std::exception& error) { Fail(error); Printf("PF020_VIEW_DUMP_FAILED: %s\n", error.what()); }
}
