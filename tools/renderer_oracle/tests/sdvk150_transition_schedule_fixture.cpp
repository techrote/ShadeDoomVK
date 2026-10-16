// SPDX-License-Identifier: GPL-3.0-or-later
// CPU services for actual generated fixture-driver bodies and exact production
// Step/Full. No renderer, Vulkan, network socket, or ZScript VM is instantiated.
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <functional>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#include "tarray.h"
#include "hw_lightprobe.h"
void* M_Malloc(size_t n) { auto p=std::malloc(n); if(!p)throw std::bad_alloc(); return p; }
void* M_Realloc(void* p,size_t n) { auto q=std::realloc(p,n); if(!q)throw std::bad_alloc(); return q; }
void M_Free(void* p) { std::free(p); }
void* M_Calloc(size_t n,size_t m) { auto p=std::calloc(n,m); if(!p)throw std::bad_alloc(); return p; }
static void require(bool ok,const char* message) { if(!ok)throw std::logic_error(message); }
struct RenderEvent {};
struct ConsoleEvent {
    std::string Name;
    bool IsManual = false;
    int Player = 0;
    int Args[3] = {};
};
constexpr int consoleplayer = 0;
constexpr int CHANGELEVEL_NOINTERMISSION = 16;
constexpr int CHANGELEVEL_NOAUTOSAVE = 128;
static int MainViewsA = 0, QueueAt = 0, AppliedAt = 0, QueueCount = 0, ApplyCount = 0;
static int Counter = 0;
struct CVar {
    static CVar GetCVar(const std::string& name) {
        require(name=="sdvk150_owner_frames","driver-counter-name"); return {};
    }
    int GetInt() { return Counter; }
    void SetInt(int value) { Counter=value; }
};
struct Console {
    static void Printf(const char*,int) {} // passive log sink
};
struct LevelService {
    std::string MapName = "SDV15A";
    bool PendingB = false;
    void ChangeLevel(const std::string& next, int position, int flags) {
        require(next=="SDV15B" && position==0 &&
                flags==(CHANGELEVEL_NOINTERMISSION|CHANGELEVEL_NOAUTOSAVE),"driver-changelevel-route");
        PendingB=true;
        ++ApplyCount;
        AppliedAt=MainViewsA;
    }
} Level;
static std::vector<ConsoleEvent> Queue;
class EventHandler {
public:
    static void SendNetworkEvent(const std::string& name,int frames) {
        ++QueueCount;
        QueueAt=MainViewsA;
        Queue.push_back({name,false,consoleplayer,{frames,0,0}});
    }
};
#include "sdvk150_generated_driver.hpp"
struct Screen {
    int resets[2] = {}, passes[2] = {};
    void ResetLightProbes(){ ++resets[Level.MapName=="SDV15A" ? 0 : 1]; }
    void EndLightProbePass(){ ++passes[Level.MapName=="SDV15A" ? 0 : 1]; }
} ScreenObject;
static Screen* screen=&ScreenObject;
// Exact inherited TArray producer compares bounded int progress with size_t.
#ifdef _MSC_VER
#pragma warning(push)
#pragma warning(disable: 4018)
#else
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wsign-compare"
#endif
#include "sdvk150_probe_methods.cpp"
#ifdef _MSC_VER
#pragma warning(pop)
#else
#pragma GCC diagnostic pop
#endif

static TArray<LightProbe> authored(int owner) {
    TArray<LightProbe> result;
    for(int i=0;i<2;++i) result.Push({FVector3(float(owner*1000+i),0,0),i});
    return result;
}

static void simulate(const std::string& mode,int ticsPerView) {
    require(ticsPerView>0,"invalid-tic-cadence");
    SDVKProbeOwnerTransition driver{};
    if(mode=="forged-events") {
        // No UI-to-play mutation: malformed/manual/wrong-player events must not apply.
        for (auto event : std::vector<ConsoleEvent>{
            {"other",false,0,{32,0,0}}, {"SDVK150_Advance",true,0,{32,0,0}},
            {"SDVK150_Advance",false,1,{32,0,0}}, {"SDVK150_Advance",false,0,{31,0,0}}})
            driver.NetworkProcess(event);
        require(ApplyCount==0,"driver-accepted-invalid-event");
        driver.NetworkProcess({"SDVK150_Advance",false,0,{32,0,0}});
        driver.NetworkProcess({"SDVK150_Advance",false,0,{32,0,0}});
        require(ApplyCount==1,"driver-duplicate-apply");
        Level.MapName="SDV15B";
        driver.RenderOverlay({});
        driver.NetworkProcess({"SDVK150_Advance",false,0,{32,0,0}});
        require(ApplyCount==1 && QueueCount==0,"driver-wrong-map-dispatch");
        return;
    }
    const bool oldWait=mode=="old-tic-wait";
    LightProbeIncrementalBuilder builder;
    TArray<LightProbe> probes=authored(1);
    uint64_t revision=11;
    int waitLeft=21, captures[2]={};
    bool actorAvailable=false;
    for(int frame=0;frame<100;++frame) {
        // The inherited adaptive play loop may consume several tics before
        // the next D_Display. Use the same Step ordering for both schedules.
        const int ticks=oldWait && frame<2 ? 1 : ticsPerView;
        for(int tick=0;tick<ticks;++tick) {
            if(oldWait && --waitLeft==0) Level.PendingB=true;
            for(const auto& event:Queue) driver.NetworkProcess(event);
            Queue.clear();
            if(Level.PendingB) {
                Level.MapName="SDV15B";
                Level.PendingB=false;
                probes=authored(2);
                revision=19;
                actorAvailable=false;
            }
        }
        // One real RenderView entry per view, with the actual first-frame
        // actor-spawn delay. Cube-face rendering does not call RenderOverlay.
        if(actorAvailable) {
            auto render=[&](int index,const LightProbe& probe) {
                const int owner=Level.MapName=="SDV15A"?0:1;
                require(index==probe.index && int(probe.position.X)==(owner+1)*1000+index,
                        "mixed-probe-capture-owner");
                ++captures[owner];
            };
#ifdef SDVK150_RETAINED
            (void)revision;
            builder.Step(probes,render);
#else
            builder.Step(probes,revision,render);
#endif
        } else actorAvailable=true;
        if(Level.MapName=="SDV15A") ++MainViewsA;
        if(!oldWait) driver.RenderOverlay({});
    }
    std::cout << "A_views=" << MainViewsA << " A_passes=" << screen->passes[0]
              << " B_passes=" << screen->passes[1] << " queue_count=" << QueueCount
              << " apply_count=" << ApplyCount << " queue_at=" << QueueAt
              << " apply_at=" << AppliedAt << '\n';
    require(screen->passes[0]==5 && captures[0]==10,"A-incomplete-before-transition");
    require(screen->passes[1]==5 && captures[1]==10,"B-incomplete-after-transition");
    if(!oldWait) {
        require(QueueCount==1 && ApplyCount==1,"transition-not-once");
        require(QueueAt==32 && AppliedAt==32 && MainViewsA==32,"transition-not-after-32-main-views");
        require(Counter==32,"unbounded-driver-counter");
    }
}
int main(int argc,char** argv) {
    if(argc!=3)return 2;
    try { simulate(argv[1],std::stoi(argv[2])); std::cout<<"PASS "<<argv[1]<<'\n'; return 0; }
    catch(const std::exception& e) { std::cerr<<"REJECT "<<e.what()<<'\n'; return 11; }
}
