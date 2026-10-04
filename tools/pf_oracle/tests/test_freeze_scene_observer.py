"""Compile the actual passive observer TU with bounded engine-interface stubs.

These are CPU guard/serialization tests, not renderer, Vulkan, view reachability
or GPU evidence. Original-seams mode deliberately has no production context or
surface members. The observer implementation is included unchanged from source.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle.fixture_runner import compile_fixture

OBSERVER = ROOT/"src/rendering/hwrenderer/diagnostics/hw_pfviewdiagnostics.cpp"
HEADERS = ("c_dispatch.h", "m_argv.h", "printf.h", "g_levellocals.h", "gametexture.h",
           "flatvertices.h", "hwrenderer/scene/hw_drawinfo.h", "hwrenderer/scene/hw_drawstructs.h",
           "hwrenderer/scene/hw_drawcontext.h", "hwrenderer/scene/hw_portal.h", "portal.h")

STUBS = r'''#pragma once
#include <array>
#include <cstdarg>
#include <cstdio>
#include <string>
#include <vector>
#include <cstdint>
// Services expose controlled input data only; no observer behavior is copied.
struct FArgs {
    std::vector<std::string> Values;
    int CheckParm(const char* name, int start=1) const {
        for (size_t i=static_cast<size_t>(start); i<Values.size(); ++i)
            if (Values[i]==name) return static_cast<int>(i);
        return 0;
    }
    const char* CheckValue(const char* name) const {
        const int i=CheckParm(name);
        if (i<=0 || static_cast<size_t>(i+1)>=Values.size()) return nullptr;
        const auto& v=Values[static_cast<size_t>(i+1)];
        return !v.empty() && v[0]!='+' && v[0]!='-' ? v.c_str() : nullptr;
    }
};
inline FArgs* Args=nullptr;
struct Commands {
    std::vector<std::string> Values;
    int argc() const { return static_cast<int>(Values.size()); }
    const char* operator[](int index) const { return Values.at(static_cast<size_t>(index)).c_str(); }
};
#define CCMD(name) void name([[maybe_unused]] const Commands& argv)
inline void Printf(const char* format, ...) {
    va_list args; va_start(args, format); std::vprintf(format, args); va_end(args);
}
struct Vec3 { double X=1, Y=2, Z=3; };
struct Angle { double Value=0; double Degrees() const { return Value; } };
struct Rotator { Angle Yaw, Pitch, Roll; };
struct StubSector { int PortalGroup=0; };
struct MatrixValue {
    std::array<float,16> Values{1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1};
    const float* get() const { return Values.data(); }
};
#ifndef PF020_ORIGINAL_SEAMS
enum class ContextType { MainView, Portal, CameraTexture, LightProbe };
inline const char* HWRenderContextTypeName(ContextType type) {
    switch (type) {
    case ContextType::Portal:return "Portal";
    case ContextType::CameraTexture:return "CameraTexture";
    case ContextType::LightProbe:return "LightProbe";
    default:return "MainView";
    }
}
struct Context {
    ContextType type=ContextType::MainView, rootType=ContextType::MainView;
    uint64_t epoch=11, identity=12, parentIdentity=0;
    unsigned recursionDepth=0;
    int probeFace=-1, eyeIndex=0;
    bool lineMirror=false, planeMirror=false, mirrored=false, postprocessEligible=true, historyEligible=true;
};
#endif
struct PortalState {
    int MirrorFlag=0, PlaneMirrorFlag=0;
    bool isMirrored() const { return ((MirrorFlag^PlaneMirrorFlag)&1)!=0; }
#ifndef PF020_ORIGINAL_SEAMS
    Context RenderContext;
#endif
};
struct DrawContext { PortalState portalState; };
struct StubPortal {
    virtual ~StubPortal()=default;
    std::string Name="Mirror";
    virtual const char* GetName() const { return Name.c_str(); }
};
constexpr int PORTT_LINKED=3;
struct StubLine {
    int Number=101, portalindex=0;
    StubSector* frontsector=nullptr;
    StubLine* Destination=nullptr;
    int Index() const { return Number; }
    StubLine* getPortalDestination() const { return Destination; }
    int getPortalType() const { return PORTT_LINKED; }
};
struct FLinePortal {
    StubLine* mOrigin=nullptr;
    StubLine* mDestination=nullptr;
    unsigned mType=PORTT_LINKED, mFlags=7;
    struct { double X=1024, Y=0; } mDisplacement;
    Angle mAngleDiff;
};
template<class T> struct StubArray : std::vector<T> {
    unsigned Size() const { return static_cast<unsigned>(this->size()); }
};
struct StubPortalLines { StubArray<FLinePortal*> lines; };
class HWLineToLinePortal : public StubPortal {
public:
    StubPortalLines* glport=nullptr;
};
struct StubViewpoint { double TicFrac=.375; Vec3 Pos; Rotator HWAngles; StubSector* sector=nullptr; };
struct Uniforms { MatrixValue mViewMatrix, mProjectionMatrix; std::array<float,4> mCameraPos{1,2,3,1}; };
struct HWDrawInfo {
    StubViewpoint Viewpoint;
    DrawContext* drawctx=nullptr;
    Uniforms VPUniforms;
    int vpIndex=7;
    StubPortal* mCurrentPortal=nullptr;
};
struct NameValue { std::string Value="POSSA2A8"; const char* GetChars() const { return Value.c_str(); } };
struct Texture { NameValue Name; const NameValue& GetName() const { return Name; } };
struct StubActor {
    int tid=4400, sprite=3, frame=0;
    uint32_t renderflags=5, renderflags2=6;
    StubSector* Sector=nullptr;
    Vec3 Position{-24,-40,8}, Prev{-32,-48,8}, ControlledInterpolated{-28,-44,8};
    Rotator Angles{{22.5},{1},{2}}, PrevAngles{{0},{3},{4}}, ControlledAngles{{11.25},{2},{3}};
    Vec3 Pos() const { return Position; }
    Vec3 InterpolatedPosition([[maybe_unused]] double fraction) const { return ControlledInterpolated; }
    Rotator InterpolatedAngles([[maybe_unused]] double fraction) const { return ControlledAngles; }
};
struct Translation { int index() const { return 0; } };
struct Style { unsigned char BlendOp=1, SrcAlpha=2, DestAlpha=3, Flags=4; };
#ifndef PF020_ORIGINAL_SEAMS
struct Surface {
    unsigned presentation=1, spriteType=0;
    bool xyBillboard=false, facesCamera=false, frameMirrored=true, uvMirrorX=true, uvMirrorY=false;
    int sourcePortalGroup=0, renderPortalGroup=1, throughPortalMode=0;
};
#endif
class HWSprite {
public:
    StubActor* actor=nullptr;
    Texture* texture=nullptr;
    Translation translation;
    int OverrideShader=0;
    Style RenderStyle;
    bool polyoffset=false;
    Rotator Angles{{11.25},{2},{3}};
#ifndef PF020_ORIGINAL_SEAMS
    Surface RenderSurface;
#endif
};
struct FFlatVertex { float x=0,y=0,z=0,u=0,v=0; };
'''

HARNESS = r'''
#include <cassert>
#include <limits>
int gametic=123;

int main(int argc, char** argv) {
    assert(argc==3);
    const std::string scenario=argv[1], prefix=argv[2];
    FArgs arguments;
    arguments.Values={"fixture","-pf020viewobserve",prefix,"-pf020viewfraction","0.5"};
    Args=&arguments;
    StubSector sector;
    DrawContext context;
    HWDrawInfo root;
    root.drawctx=&context; root.Viewpoint.sector=&sector;
    StubActor actor; actor.Sector=&sector;
    Texture texture;
    HWSprite sprite; sprite.actor=&actor; sprite.texture=&texture;
    FFlatVertex vertices[4]={{1,2,3,.125f,.25f},{4,5,6,.875f,.25f},{7,8,9,.125f,.75f},{10,11,12,.875f,.75f}};
    if (scenario=="off") {
        arguments.Values={"fixture"};
        Pf020ViewDiagnostics::BeginRoot(true,true,-1,"PFVTEST");
        assert(!Pf020ViewDiagnostics::Enabled());
        assert(Pf020ViewDiagnostics::ActorFraction(.375)==.375);
        Pf020ViewDiagnostics::SceneBegin(&root,0);
        assert(Observer.Stack.empty() && Observer.Records.empty());
        assert(!Pf020ViewDiagnostics::FixtureActive());
        assert(Pf020ViewDiagnostics::OutputPrefix()==nullptr);
        assert(Pf020ViewDiagnostics::CurrentSceneKeyJson().empty());
        pf020view_dump({{"pf020view_dump"}});
        return 0;
    }
    if (scenario=="foreign") {
        Pf020ViewDiagnostics::BeginRoot(true,true,-1,"MAP01");
        assert(Pf020ViewDiagnostics::ActorFraction(.375)==.375);
        Pf020ViewDiagnostics::SceneBegin(&root,0);
        assert(Observer.Records.empty() && Observer.Stack.empty());
        pf020view_dump({{"pf020view_dump"}});
        return 0;
    }
    if (scenario=="no-fraction") {
        arguments.Values.resize(3);
        Pf020ViewDiagnostics::BeginRoot(true,true,-1,"PFVTEST");
        assert(Pf020ViewDiagnostics::ActorFraction(.375)==.375);
        Pf020ViewDiagnostics::SceneBegin(&root,0);
        Pf020ViewDiagnostics::SpriteVertices(&root,&sprite,vertices);
        Pf020ViewDiagnostics::SceneEnd(&root);
        pf020view_dump({{"pf020view_dump"}});
        return 0;
    }
    if (scenario=="missing-prefix") arguments.Values={"fixture","-pf020viewobserve"};
    if (scenario=="duplicate-prefix") arguments.Values.insert(arguments.Values.end(),{"-pf020viewobserve",prefix});
    if (scenario=="bad-fraction") arguments.Values.back()="1";
    if (scenario=="duplicate-fraction") arguments.Values.insert(arguments.Values.end(),{"-pf020viewfraction","0.5"});
    if (scenario=="existing") { std::ofstream old(prefix+".scene.json"); old<<"sentinel"; }
    if (scenario=="missing-prefix" || scenario=="duplicate-prefix" || scenario=="bad-fraction" || scenario=="duplicate-fraction" || scenario=="existing") {
        assert(!Pf020ViewDiagnostics::Enabled());
        assert(!Observer.Error.empty());
        assert(Pf020ViewDiagnostics::ActorFraction(.375)==.375);
        pf020view_dump({{"pf020view_dump"}});
        return 0;
    }
    Pf020ViewDiagnostics::BeginRoot(true,true,-1,"PFVTEST");
    assert(Pf020ViewDiagnostics::FixtureActive());
    assert(std::string(Pf020ViewDiagnostics::OutputPrefix())==prefix);
    assert(Pf020ViewDiagnostics::CurrentSceneKeyJson().empty());
    assert(Pf020ViewDiagnostics::ActorFraction(.375)==.5);
    root.Viewpoint.TicFrac=Pf020ViewDiagnostics::ActorFraction(root.Viewpoint.TicFrac);
    if (scenario=="fraction-roots") {
        Pf020ViewDiagnostics::BeginRoot(false,false,-1,"PFVTEST");
        assert(Pf020ViewDiagnostics::ActorFraction(.25)==.5);
        for (int face=0;face<6;++face) {
            Pf020ViewDiagnostics::BeginRoot(false,false,face,"PFVTEST");
            assert(Pf020ViewDiagnostics::ActorFraction(1)==1);
        }
        Pf020ViewDiagnostics::BeginRoot(true,true,-1,"OTHER");
        assert(Pf020ViewDiagnostics::ActorFraction(.25)==.25);
        assert(Observer.Records.empty());
        return 0;
    }
    if (scenario=="bad-face") {
        Pf020ViewDiagnostics::BeginRoot(false,false,6,"PFVTEST");
        assert(!Observer.Error.empty());
        assert(Pf020ViewDiagnostics::ActorFraction(1)==1);
        assert(!Pf020ViewDiagnostics::FixtureActive());
        pf020view_dump({{"pf020view_dump"}});
        return 0;
    }
    if (scenario=="limit-records") {
        for (int i=0;i<2049 && Observer.Error.empty();++i) {
            sector.PortalGroup=i;
            Pf020ViewDiagnostics::SceneBegin(&root,0);
            Pf020ViewDiagnostics::SpriteVertices(&root,&sprite,vertices);
            Pf020ViewDiagnostics::SceneEnd(&root);
        }
        assert(!Observer.Error.empty() && Observer.Records.size()<=2048 && Observer.Stack.empty());
        pf020view_dump({{"pf020view_dump"}});
        return 0;
    }
    Pf020ViewDiagnostics::SceneBegin(&root,0);
    if (scenario=="nested" || scenario=="linked" || scenario=="missing-endpoints" || scenario=="portal-limit") {
        DrawContext childContext;
        childContext.portalState.MirrorFlag=1;
#ifndef PF020_ORIGINAL_SEAMS
        childContext.portalState.RenderContext.type=ContextType::Portal;
        childContext.portalState.RenderContext.identity=13;
        childContext.portalState.RenderContext.parentIdentity=12;
        childContext.portalState.RenderContext.recursionDepth=1;
        childContext.portalState.RenderContext.lineMirror=true;
        childContext.portalState.RenderContext.mirrored=true;
#endif
        StubPortal portal; portal.Name="Mirror";
        StubSector targetSector; targetSector.PortalGroup=1;
        StubLine origin, destination;
        origin.frontsector=&sector; origin.Destination=&destination;
        destination.Number=102; destination.portalindex=1; destination.frontsector=&targetSector; destination.Destination=&origin;
        FLinePortal line; line.mOrigin=&origin; line.mDestination=&destination;
        StubPortalLines lines; lines.lines.push_back(&line);
        HWLineToLinePortal linked; linked.Name="LineToLine"; linked.glport=&lines;
        if (scenario=="missing-endpoints") line.mDestination=nullptr;
        if (scenario=="portal-limit") lines.lines.resize(65,&line);
        HWDrawInfo child=root; child.drawctx=&childContext;
        child.mCurrentPortal=scenario=="nested" ? &portal : &linked;
        Pf020ViewDiagnostics::SceneBegin(&child,1);
        Pf020ViewDiagnostics::SpriteVertices(&child,&sprite,vertices);
        Pf020ViewDiagnostics::SceneEnd(&child);
        Pf020ViewDiagnostics::Restored(&root);
        assert(Observer.Stack.size()==1 && Observer.Stack.back().Owner==&root);
    } else if (scenario=="owner-mismatch") {
        HWDrawInfo wrong=root;
        Pf020ViewDiagnostics::SceneEnd(&wrong);
        assert(!Observer.Error.empty() && Observer.Stack.size()==1);
    } else if (scenario=="nonfinite") {
        vertices[2].u=std::numeric_limits<float>::quiet_NaN();
        Pf020ViewDiagnostics::SpriteVertices(&root,&sprite,vertices);
        assert(!Observer.Error.empty());
    } else if (scenario=="null-vertices") {
        Pf020ViewDiagnostics::SpriteVertices(&root,&sprite,nullptr);
        assert(!Observer.Error.empty());
    } else if (scenario=="huge-record") {
        texture.Name.Value=std::string(17000,'x');
        Pf020ViewDiagnostics::SpriteVertices(&root,&sprite,vertices);
        assert(!Observer.Error.empty() && Observer.Records.size()==1);
    } else if (scenario=="limit-stack") {
        for (int i=1;i<34 && Observer.Error.empty();++i) Pf020ViewDiagnostics::SceneBegin(&root,0);
        assert(!Observer.Error.empty() && Observer.Stack.size()==32);
        while (!Observer.Stack.empty()) Pf020ViewDiagnostics::SceneEnd(&root);
    } else if (scenario=="invalid-scene") {
        Pf020ViewDiagnostics::SceneBegin(nullptr,0);
        assert(!Observer.Error.empty());
    } else if (scenario=="bad-restore") {
        HWDrawInfo wrong=root;
        Pf020ViewDiagnostics::Restored(&wrong);
        assert(!Observer.Error.empty());
    } else if (scenario=="reset-phase") {
        Pf020ViewDiagnostics::SpriteVertices(&root,&sprite,vertices);
        pf020view_begin({{"pf020view_begin","illegal phase"}});
        assert(Observer.Phase=="startup");
        pf020view_begin({{"pf020view_begin","during-scene"}});
        assert(Observer.Phase=="startup");
    } else {
        Pf020ViewDiagnostics::SpriteVertices(&root,&sprite,vertices);
        Pf020ViewDiagnostics::SpriteVertices(&root,&sprite,vertices);
        assert(Observer.Sprites==2 && Observer.Records.size()==2);
    }
    Pf020ViewDiagnostics::SceneEnd(&root);
    assert(Observer.Stack.empty());
    if (scenario=="completed-later") {
        // Same semantic key remains deduplicated, while a later completed
        // producer must retain its actual invocation's changed time and view.
        gametic=456;
        root.Viewpoint.Pos.X=25;
        root.VPUniforms.mViewMatrix.Values[12]=25;
        Pf020ViewDiagnostics::SceneBegin(&root,0);
        Pf020ViewDiagnostics::SceneEnd(&root);
        assert(Observer.Records.size()==2 && Observer.Scenes==2);
    }
    if (Observer.Error.empty()) {
        const auto completed=Pf020ViewDiagnostics::CurrentSceneKeyJson();
        assert(!completed.empty() && completed.find(scenario=="completed-later" ? "\"diagnosticIdentity\":2" : "\"diagnosticIdentity\":1")!=std::string::npos);
        std::ofstream key(prefix+".completed.json"); key<<completed;
    }
    if (scenario=="reset-phase") {
        pf020view_begin({{"pf020view_begin","fixed-capture"}});
        assert(Observer.Records.size()==2 && Observer.Scenes==1 && Observer.Phase=="fixed-capture");
        Pf020ViewDiagnostics::SceneBegin(&root,0);
        Pf020ViewDiagnostics::SpriteVertices(&root,&sprite,vertices);
        Pf020ViewDiagnostics::SceneEnd(&root);
        assert(Observer.Records.size()==4 && Observer.Scenes==2 && Observer.Sprites==2);
    }
    Pf020ViewDiagnostics::PostprocessCompleted(&root);
    pf020view_dump({{"pf020view_dump"}});
    assert(Observer.Written);
    const auto size=std::filesystem::file_size(prefix+".scene.json");
    pf020view_dump({{"pf020view_dump"}});
    assert(std::filesystem::file_size(prefix+".scene.json")==size);
    assert(!Pf020ViewDiagnostics::Enabled());
    assert(!Pf020ViewDiagnostics::FixtureActive());
    assert(Pf020ViewDiagnostics::CurrentSceneKeyJson().empty());
    assert(Pf020ViewDiagnostics::ActorFraction(.375)==.375);
    return 0;
}
'''


class ProductionObserverGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch = tempfile.TemporaryDirectory(prefix="pf020-observer-cpu-")
        cls.addClassCleanup(cls.scratch.cleanup)
        cls.directory = Path(cls.scratch.name)
        cls.executables = {}
        cls.source_hash = hashlib.sha256(OBSERVER.read_bytes()).hexdigest()
        for variant in ("current", "original"):
            directory = cls.directory/variant
            directory.mkdir()
            (directory/"stub_engine.h").write_text(STUBS, encoding="utf-8", newline="\n")
            for name in HEADERS:
                target = directory/name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('#include "stub_engine.h"\n', encoding="utf-8", newline="\n")
            wrapper = directory/"observer_fixture.cpp"
            mode = "#define PF020_ORIGINAL_SEAMS 1\n" if variant == "original" else ""
            wrapper.write_text(mode+'#include "stub_engine.h"\n#include '+json.dumps(OBSERVER.as_posix())+'\n'+HARNESS,
                               encoding="utf-8", newline="\n")
            cls.executables[variant] = compile_fixture(wrapper, output_dir=directory, includes=[directory], name="observer-"+variant)
        if hashlib.sha256(OBSERVER.read_bytes()).hexdigest() != cls.source_hash:
            raise AssertionError("Production observer changed during CPU compilation")

    def observe(self, scenario, variant="current"):
        prefix = self.directory/(scenario+"-"+variant)
        result = subprocess.run([str(self.executables[variant]), scenario, str(prefix)],
                                check=True, timeout=10, capture_output=True, text=True)
        path = Path(str(prefix)+".scene.json")
        return result.stdout, json.loads(path.read_text()) if path.exists() and scenario != "existing" else None

    def test_actual_tu_current_and_original_publish_only_state(self):
        for variant in self.executables:
            with self.subTest(variant=variant):
                output, receipt = self.observe("normal", variant)
                self.assertEqual(receipt["status"], "COLLECTED_STATE_ONLY")
                self.assertFalse(receipt["freezeAccepted"])
                self.assertFalse(receipt["imagesCapturedByThisObserver"])
                self.assertIn("PF020_VIEW_DUMP_REJECTED", output)
                scene = next(r for r in receipt["records"] if r["event"] == "scene")
                sprite = next(r for r in receipt["records"] if r["event"] == "sprite-vertices")
                self.assertEqual(scene["productionContextAvailable"], variant == "current")
                self.assertEqual(sprite["productionSurfaceAvailable"], variant == "current")
                self.assertEqual(sprite["verticesXYZUV"], [[1,2,3,.125,.25],[4,5,6,.875,.25],[7,8,9,.125,.75],[10,11,12,.875,.75]])
                self.assertEqual(sprite["previousPosition"], [-32,-48,8])
                self.assertEqual(sprite["interpolatedPosition"], [-28,-44,8])
                self.assertEqual(sprite["fraction"], .5)
                self.assertEqual(sprite["previousAngles"], [0,3,4])
                self.assertEqual(sprite["actorAngles"], [22.5,1,2])
                self.assertEqual(sprite["interpolatedAngles"], [11.25,2,3])
                self.assertEqual(sprite["effectiveSpriteAngles"], [11.25,2,3])
                self.assertEqual(receipt["spriteVertexCalls"], 2)
                self.assertEqual(len([r for r in receipt["records"] if r["event"] == "sprite-vertices"]), 1)
                completed = json.loads((self.directory/("normal-"+variant+".completed.json")).read_text())
                self.assertEqual(completed["diagnosticIdentity"], scene["diagnosticIdentity"])
                self.assertEqual(completed["semanticKey"], scene["semanticKey"])
                self.assertEqual(completed["completedView"]["tic"], scene["tic"])
                self.assertEqual(completed["completedView"]["viewMatrix"], scene["viewMatrix"])
                self.assertEqual(completed["completedView"]["productionContextAvailable"], variant == "current")

    def test_completed_producer_snapshot_uses_later_actual_view_after_semantic_dedup(self):
        for variant in self.executables:
            with self.subTest(variant=variant):
                _, receipt = self.observe("completed-later", variant)
                first = next(r for r in receipt["records"] if r["event"] == "scene")
                completed = json.loads((self.directory/("completed-later-"+variant+".completed.json")).read_text())
                self.assertEqual(first["tic"], 123)
                self.assertEqual(first["position"], [1, 2, 3])
                self.assertEqual(completed["semanticKey"], first["semanticKey"])
                self.assertNotEqual(completed["diagnosticIdentity"], first["diagnosticIdentity"])
                self.assertEqual(completed["completedView"]["tic"], 456)
                self.assertEqual(completed["completedView"]["position"], [25, 2, 3])
                self.assertEqual(completed["completedView"]["viewMatrix"][12], 25)
                self.assertEqual(completed["completedView"]["depth"], 0)
                self.assertEqual(completed["completedView"]["productionContextAvailable"], variant == "current")

    def test_disabled_and_foreign_map_leave_fractions_and_records_untouched(self):
        output, receipt = self.observe("off")
        self.assertIsNone(receipt)
        self.assertIn("DUMP_REJECTED", output)
        _, receipt = self.observe("foreign")
        self.assertEqual(receipt["status"], "FAIL")
        self.assertEqual(receipt["records"], [])

    def test_fraction_requires_explicit_request_and_never_changes_probe_faces(self):
        for variant in self.executables:
            with self.subTest(variant=variant):
                _, receipt = self.observe("no-fraction", variant)
                self.assertFalse(receipt["fixedActorFractionRequested"])
                self.assertEqual(next(r for r in receipt["records"] if r["event"] == "sprite-vertices")["fraction"], .375)
                self.assertIsNone(self.observe("fraction-roots", variant)[1])

    def test_nested_parent_stack_and_restored_state_use_actual_observer(self):
        for variant in self.executables:
            with self.subTest(variant=variant):
                _, receipt = self.observe("nested", variant)
                scenes = [r for r in receipt["records"] if r["event"] == "scene"]
                self.assertEqual([s["depth"] for s in scenes], [0,1])
                self.assertEqual(scenes[1]["diagnosticParent"], scenes[0]["diagnosticIdentity"])
                self.assertEqual(receipt["restorationCalls"], 1)
                self.assertEqual(next(r for r in receipt["records"] if r["event"] == "restored")["lineMirrorFlag"], 0)
                self.assertEqual(scenes[1]["lineMirrorFlag"], 1)

    def test_owner_mismatch_and_invalid_scene_restoration_fail_closed(self):
        for scenario in ("owner-mismatch", "invalid-scene", "bad-restore"):
            with self.subTest(scenario=scenario):
                _, receipt = self.observe(scenario)
                self.assertEqual(receipt["status"], "FAIL")
                self.assertTrue(receipt["error"])

    def test_linked_portal_serializes_real_interface_endpoints_without_resolving_them(self):
        for variant in self.executables:
            with self.subTest(variant=variant):
                _, receipt = self.observe("linked", variant)
                row = next(r for r in receipt["records"] if r["event"] == "scene" and r["depth"] == 1)
                self.assertTrue(row["linePortalAvailable"])
                self.assertEqual(len(row["linePortalSpan"]), 1)
                link = row["linePortalSpan"][0]
                self.assertTrue(link["linked"])
                self.assertTrue(link["destinationLinksBack"])
                self.assertEqual((link["originLineIndex"], link["destinationLineIndex"]), (101,102))
                self.assertEqual(link["displacementXY"], [1024,0])
                self.assertEqual((link["sourceGroup"], link["destinationGroup"]), (0,1))

    def test_invalid_linked_portal_span_endpoints_and_probe_face_are_rejected(self):
        for scenario in ("missing-endpoints", "portal-limit", "bad-face"):
            with self.subTest(scenario=scenario):
                _, receipt = self.observe(scenario)
                self.assertEqual(receipt["status"], "FAIL")
                self.assertTrue(receipt["error"])

    def test_nonfinite_and_missing_vertex_data_are_rejected(self):
        for scenario in ("nonfinite", "null-vertices"):
            with self.subTest(scenario=scenario):
                _, receipt = self.observe(scenario)
                self.assertEqual(receipt["status"], "FAIL")
                self.assertTrue(receipt["error"])

    def test_stack_record_and_serialized_string_limits_fail_closed(self):
        for scenario in ("limit-stack", "limit-records", "huge-record"):
            with self.subTest(scenario=scenario):
                _, receipt = self.observe(scenario)
                self.assertEqual(receipt["status"], "FAIL")
                self.assertLessEqual(len(receipt["records"]), 2048)
                self.assertTrue(receipt["error"])

    def test_fresh_destination_single_option_and_fraction_arity_guards(self):
        for scenario in ("missing-prefix", "duplicate-prefix", "existing", "bad-fraction", "duplicate-fraction"):
            with self.subTest(scenario=scenario):
                output, receipt = self.observe(scenario)
                if receipt is not None:
                    self.assertEqual(receipt["status"], "FAIL")
                    self.assertTrue(receipt["error"])
                    self.assertEqual(receipt["records"], [])
                    self.assertIn("PF020_VIEW_STATE_WRITTEN", output)
                else:
                    self.assertIn("PF020_VIEW_DUMP_FAILED", output)
                if scenario == "existing":
                    self.assertEqual((self.directory/"existing-current.scene.json").read_text(), "sentinel")

    def test_phase_change_rejects_active_stack_and_retains_startup_rows(self):
        output, receipt = self.observe("reset-phase")
        self.assertGreaterEqual(output.count("PF020_VIEW_BEGIN_REJECTED"), 2)
        self.assertEqual(receipt["phase"], "fixed-capture")
        self.assertEqual(receipt["sceneCalls"], 2)
        self.assertEqual(receipt["spriteVertexCalls"], 2)
        self.assertEqual(len([r for r in receipt["records"] if r["event"] == "scene"]), 2)
        self.assertEqual(len([r for r in receipt["records"] if r["event"] == "sprite-vertices"]), 2)
        self.assertEqual({r["phase"] for r in receipt["records"]}, {"startup", "fixed-capture"})


class ObserverIntegrationSourceGuards(unittest.TestCase):
    def test_finite_guard_translation_units_have_explicit_precise_math_policy(self):
        cmake = (ROOT/"src/CMakeLists.txt").read_text()
        frontend = "rendering/hwrenderer/diagnostics/hw_pfviewdiagnostics.cpp"
        backend = "common/rendering/vulkan/textures/vk_pfviewdiagnostics.cpp"
        fast = re.search(r"set\s*\(\s*FASTMATH_SOURCES\b(.*?)\n\)", cmake, re.S)
        self.assertIsNotNone(fast)
        self.assertNotIn(frontend, fast.group(1))
        self.assertIn('set(PF020_DIAGNOSTIC_MATH "/fp:precise")', cmake)
        self.assertIn('set(PF020_DIAGNOSTIC_MATH "-fno-fast-math -ffp-contract=off")', cmake)
        self.assertRegex(cmake, r"set_source_files_properties\("+re.escape(frontend)+r"\s+"+re.escape(backend)+r"\s+PROPERTIES COMPILE_FLAGS \"\$\{PF020_DIAGNOSTIC_MATH\}\"\)")

    def test_actual_hooks_follow_frame_setup_and_complete_cpu_vertex_emission(self):
        entry = (ROOT/"src/rendering/hwrenderer/hw_entrypoint.cpp").read_text()
        setup = entry.index("R_SetupFrame(mainvp, r_viewwindow, camera, side)")
        begin = entry.index("Pf020ViewDiagnostics::BeginRoot(", setup)
        fraction = entry.index("Pf020ViewDiagnostics::ActorFraction(mainvp.TicFrac)", begin)
        self.assertLess(setup, begin)
        self.assertLess(begin, fraction)
        sprites = (ROOT/"src/rendering/hwrenderer/scene/hw_sprites.cpp").read_text()
        body = sprites.split("void HWSprite::CreateVertices(", 1)[1].split("\n}\n", 1)[0]
        self.assertLess(body.index("vp[3].Set("), body.index("Pf020ViewDiagnostics::SpriteVertices(di, this, vp)"))
        draws = (ROOT/"src/rendering/hwrenderer/scene/hw_drawinfo.cpp").read_text()
        scene = draws.split("void HWDrawInfo::DrawScene(", 1)[1].split("\n}\n", 1)[0]
        self.assertLess(scene.index("Pf020ViewDiagnostics::SceneBegin("), scene.index("RenderScene(state)"))
        self.assertLess(scene.index("RenderTranslucent(state)"), scene.index("Pf020ViewDiagnostics::SceneEnd("))


if __name__ == "__main__":
    unittest.main()
