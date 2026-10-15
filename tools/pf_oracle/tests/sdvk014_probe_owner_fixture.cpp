// SPDX-License-Identifier: GPL-3.0-or-later
// Actual Step/Full definitions with CPU callback sinks. No Vulkan is instantiated.
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
void* M_Malloc(size_t n) {auto p=std::malloc(n);if(!p)throw std::bad_alloc();return p;}
void* M_Realloc(void* p,size_t n) {auto q=std::realloc(p,n);if(!q)throw std::bad_alloc();return q;}
void M_Free(void* p) {std::free(p);}
void* M_Calloc(size_t n,size_t m) {auto p=std::calloc(n,m);if(!p)throw std::bad_alloc();return p;}
struct Screen {int resets=0,passes=0;void ResetLightProbes(){++resets;}void EndLightProbePass(){++passes;}} screenObject;
Screen* screen=&screenObject;
// The unchanged producer compares bounded int progress to TArray size_t.
// Keep the exact source; isolate only that inherited warning in this fixture.
#ifdef _MSC_VER
#pragma warning(push)
#pragma warning(disable: 4018)
#else
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wsign-compare"
#endif
#include "sdvk014_probe_methods.cpp"
#ifdef _MSC_VER
#pragma warning(pop)
#else
#pragma GCC diagnostic pop
#endif
static void require(bool ok,const char* why){if(!ok)throw std::logic_error(why);}
static TArray<LightProbe> authored(int count,int owner) {
    TArray<LightProbe> p;
    for(int i=0;i<count;++i) p.Push(LightProbe{FVector3(float(owner*1000+i),0,0),i});
    return p;
}
struct Route {
    // Entry condition is copied from the actual RenderView boundary at build time.
    bool gl_lightprobe=true;
    struct {TArray<LightProbe> lightProbes;} level;
    LightProbeIncrementalBuilder lightProbeBuilder;
    std::vector<int> captures;
    void frame() {
        @ENTRY_GUARD@ {
            // Assume the required LightProbe actor already exists; actor creation
            // can add a frame delay, but cannot reset the global builder.
            lightProbeBuilder.Step(level.lightProbes,[&](int,const LightProbe& p){captures.push_back(int(p.position.X));});
        }
    }
    void frames(){for(int i=0;i<32;++i)frame();}
};
static void run(const std::string& mode) {
    Route r;r.level.lightProbes=authored(2,1);r.frames();
    require(r.captures==std::vector<int>({1000,1001,1000,1001,1000,1001,1000,1001,1000,1001}),"initial-pass-identity");
    require(screen->resets==1 && screen->passes==5,"initial-publication-count");
    r.captures.clear();int resetBefore=screen->resets,passBefore=screen->passes;
    if(mode=="same-owner-terminal") {
        r.frames();require(r.captures.empty() && screen->resets==resetBefore,"terminal-spin");
    } else if(mode=="count-change") {
        r.level.lightProbes=authored(3,2);r.frames();
        require(r.captures.size()==15 && r.captures.front()==2000 && r.captures.back()==2002,"changed-count-not-rebuilt");
        require(screen->resets==resetBefore+1 && screen->passes==passBefore+5,"changed-count-publication");
    } else if(mode=="direct-empty-step") {
        TArray<LightProbe> empty;r.lightProbeBuilder.Step(empty,[](int,const LightProbe&){});
        r.level.lightProbes=authored(2,2);r.frames();
        require(r.captures.size()==10 && screen->resets==resetBefore+2,"direct-empty-reset-failed");
    } else if(mode=="fresh-owner-control") {
        Route newOwner;newOwner.level.lightProbes=authored(2,2);newOwner.frames();
        require(newOwner.captures.size()==10 && newOwner.captures.front()==2000,"fresh-owner-not-built");
    } else if(mode=="same-count" || mode=="same-count-via-empty") {
        if(mode=="same-count-via-empty") {r.level.lightProbes.Clear();r.frames();}
        r.level.lightProbes=authored(2,2);r.frames();
        std::cout<<"COUNTERS old_owner_captures=10 new_owner_captures="<<r.captures.size()
                 <<" reset_delta="<<screen->resets-resetBefore<<" pass_delta="<<screen->passes-passBefore<<'\n';
        require(r.captures.size()==10 && r.captures.front()==2000 && screen->resets==resetBefore+1,
                "new-owner-not-rebuilt");
    } else throw std::logic_error("unknown-case");
}
int main(int argc,char** argv) {
    if(argc!=2)return 2;
    try{run(argv[1]);std::cout<<"PASS "<<argv[1]<<'\n';return 0;}
    catch(const std::logic_error& e){std::cerr<<"BLOCKED "<<e.what()<<'\n';return 11;}
}
