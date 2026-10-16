// SPDX-License-Identifier: GPL-3.0-or-later
// Exact Step/Full definitions with CPU callback sinks. No Vulkan is instantiated.
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
static std::vector<int> repeated(int count,int owner,int passes=5) {
    std::vector<int> out;
    for(int p=0;p<passes;++p) for(int i=0;i<count;++i) out.push_back(owner*1000+i);
    return out;
}

struct Route {
    bool gl_lightprobe=true;
    struct {
        TArray<LightProbe> lightProbes;
        uint64_t revision=1;
    } level;
    LightProbeIncrementalBuilder lightProbeBuilder;
    std::vector<int> captures;

    void markChanged() {
        ++level.revision;
        if(level.revision==0) level.revision=1;
    }
    void replaceOwner(int count,int owner) {
        level.lightProbes=authored(count,owner);
        markChanged();
    }
    void clearOwner() {
        level.lightProbes.Clear();
        markChanged();
    }
    void captureStep() {
#ifdef SDVK150_RETAINED
        lightProbeBuilder.Step(level.lightProbes,[&](int,const LightProbe& p){captures.push_back(int(p.position.X));});
#else
        lightProbeBuilder.Step(level.lightProbes,level.revision,[&](int,const LightProbe& p){captures.push_back(int(p.position.X));});
#endif
    }
    void emptyStep() {
#ifdef SDVK150_RETAINED
        lightProbeBuilder.Step(level.lightProbes,[](int,const LightProbe&){});
#else
        lightProbeBuilder.Step(level.lightProbes,level.revision,{});
#endif
    }
    void fullOnce() {
#ifdef SDVK150_RETAINED
        lightProbeBuilder.Full(level.lightProbes,[&](int,const LightProbe& p){captures.push_back(int(p.position.X));});
#else
        lightProbeBuilder.Full(level.lightProbes,level.revision,[&](int,const LightProbe& p){captures.push_back(int(p.position.X));});
#endif
    }
    void frame() {
#ifdef SDVK150_RETAINED
        if (gl_lightprobe && level.lightProbes.size() > 0)
            captureStep();
#else
        if (gl_lightprobe) {
            if (level.lightProbes.size() == 0) emptyStep();
            else captureStep();
        }
#endif
    }
    void frames(){for(int i=0;i<32;++i)frame();}
};

static void requireInitial(Route& r) {
    r.level.lightProbes=authored(2,1);
    r.frames();
    require(r.captures==repeated(2,1),"initial-pass-identity");
    require(screen->resets==1 && screen->passes==5,"initial-publication-count");
}

static void run(const std::string& mode) {
    if(mode=="partial-owner") {
        Route r;
        r.level.lightProbes=authored(2,1);
        r.frame(); // initial owner/count reset
        r.frame(); // collect A probe 0 only
        require(r.captures==std::vector<int>({1000}),"partial-owner-setup");
        require(screen->resets==1 && screen->passes==0,"partial-owner-setup-publication");
        r.captures.clear();
        const int resetBefore=screen->resets,passBefore=screen->passes;
        r.replaceOwner(2,2);
        r.frames();
        std::cout<<"COUNTERS partial_new_captures="<<r.captures.size()
                 <<" reset_delta="<<screen->resets-resetBefore
                 <<" pass_delta="<<screen->passes-passBefore<<'\n';
        require(r.captures==repeated(2,2),"partial-owner-mixed-pass");
        require(screen->resets==resetBefore+1 && screen->passes==passBefore+5,
                "partial-owner-publication");
        return;
    }

    if(mode=="full-same-count") {
        Route r;
        r.level.lightProbes=authored(2,1);
        for(int i=0;i<5;++i) r.fullOnce();
        require(r.captures==repeated(2,1),"full-initial-pass-identity");
        require(screen->resets==1 && screen->passes==5,"full-initial-publication");
        r.captures.clear();
        const int resetBefore=screen->resets,passBefore=screen->passes;
        r.replaceOwner(2,2);
        for(int i=0;i<5;++i) r.fullOnce();
        require(r.captures==repeated(2,2),"full-new-owner-not-rebuilt");
        require(screen->resets==resetBefore+1 && screen->passes==passBefore+5,
                "full-new-owner-publication");
        return;
    }

    Route r;
    requireInitial(r);
    r.captures.clear();
    const int resetBefore=screen->resets,passBefore=screen->passes;

    if(mode=="same-owner-terminal") {
        r.frames();
        require(r.captures.empty() && screen->resets==resetBefore,"terminal-spin");
    } else if(mode=="count-change") {
        r.replaceOwner(3,2);
        r.frames();
        require(r.captures==repeated(3,2),"changed-count-not-rebuilt");
        require(screen->resets==resetBefore+1 && screen->passes==passBefore+5,
                "changed-count-publication");
    } else if(mode=="direct-empty-step") {
        r.clearOwner();
        r.emptyStep();
        r.replaceOwner(2,2);
        r.frames();
        require(r.captures==repeated(2,2),"direct-empty-reset-failed");
        require(screen->resets==resetBefore+2 && screen->passes==passBefore+5,
                "direct-empty-publication");
    } else if(mode=="fresh-owner-control") {
        Route newOwner;
        newOwner.level.lightProbes=authored(2,2);
        newOwner.frames();
        require(newOwner.captures==repeated(2,2),"fresh-owner-not-built");
    } else if(mode=="same-count") {
        r.replaceOwner(2,2);
        r.frames();
        std::cout<<"COUNTERS old_owner_captures=10 new_owner_captures="<<r.captures.size()
                 <<" reset_delta="<<screen->resets-resetBefore
                 <<" pass_delta="<<screen->passes-passBefore<<'\n';
        require(r.captures==repeated(2,2),"new-owner-not-rebuilt");
        require(screen->resets==resetBefore+1 && screen->passes==passBefore+5,
                "new-owner-publication");
    } else if(mode=="same-count-via-empty") {
        r.clearOwner();
        r.frames();
        r.replaceOwner(2,2);
        r.frames();
        std::cout<<"COUNTERS old_owner_captures=10 new_owner_captures="<<r.captures.size()
                 <<" reset_delta="<<screen->resets-resetBefore
                 <<" pass_delta="<<screen->passes-passBefore<<'\n';
        require(r.captures==repeated(2,2),"new-owner-not-rebuilt");
        require(screen->resets==resetBefore+2 && screen->passes==passBefore+5,
                "empty-owner-publication");
    } else throw std::logic_error("unknown-case");
}

int main(int argc,char** argv) {
    if(argc!=2)return 2;
    try{run(argv[1]);std::cout<<"PASS "<<argv[1]<<'\n';return 0;}
    catch(const std::logic_error& e){std::cerr<<"BLOCKED "<<e.what()<<'\n';return 11;}
}
