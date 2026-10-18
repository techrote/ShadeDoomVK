// SPDX-License-Identifier: GPL-3.0-or-later
// Production RectPacker + real TArray; independent requested-size/occupancy oracle.
#include <algorithm>
#include <cassert>
#include <climits>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#include "tarray.h"
#include "engineerrors.h"

void* M_Malloc(size_t n) { auto p=std::malloc(n); if(!p) throw std::bad_alloc(); return p; }
void* M_Realloc(void* p,size_t n) { auto q=std::realloc(p,n); if(!q) throw std::bad_alloc(); return q; }
void M_Free(void* p) { std::free(p); }
void* M_Calloc(size_t n,size_t m) { auto p=std::calloc(n,m); if(!p) throw std::bad_alloc(); return p; }
[[noreturn]] void I_FatalError(const char* format,...) {
    char message[512]; va_list args; va_start(args,format);
    std::vsnprintf(message,sizeof(message),format,args); va_end(args);
    throw std::runtime_error(message);
}
[[noreturn]] void I_Error(const char* format,...) { throw std::runtime_error(format); }

// Only access visibility changes. Ownership, allocation and list operations
// execute the exact header/implementation; counters never steer the packer.
#define private public
#define VALIDATE_RECTPACKER
#include "hw_rectpacker.h"
#undef private
#include "sdvk014_rectpacker_under_test.cpp"

struct Region { int x,y,w,h,page,requestedW,requestedH; RectPackerAllocation item; };
static Region receipt(RectPacker& owner,RectPackerAllocation item,int w,int h) { const auto p=owner.GetRegion(item); return {p.X,p.Y,p.Width,p.Height,p.PageIndex,w,h,item}; }
static std::string validate(const std::vector<Region>& regions,int size,int padding,int pages) {
    std::vector<int> occupied(static_cast<size_t>(size)*size*pages,-1);
    for(size_t i=0;i<regions.size();++i) {
        const auto& r=regions[i];
        if(r.w!=r.requestedW || r.h!=r.requestedH) return "size-mismatch";
        if(r.page<0 || r.page>=pages || r.x<padding || r.y<padding || r.w<=0 || r.h<=0 ||
           r.w>size-2*padding || r.h>size-2*padding || r.x>size-padding-r.w || r.y>size-padding-r.h)
            return "outside-page";
        for(int y=r.y-padding;y<r.y+r.h+padding;++y) for(int x=r.x-padding;x<r.x+r.w+padding;++x) {
            auto at=static_cast<size_t>(r.page)*size*size+static_cast<size_t>(y)*size+x;
            if(occupied[at]!=-1) return "overlap";
            occupied[at]=static_cast<int>(i);
        }
    }
    return "valid";
}
static void require(bool condition,const char* message) { if(!condition) throw std::logic_error(message); }
static void run(const std::string& mode) {
    if(mode=="full-height" || mode=="padded-full-page") {
        const int pad=mode=="full-height"?0:3;
        RectPacker p(16,16,pad);
        const int w=mode=="full-height"?8:10, h=16-pad*2;
        auto a=receipt(p,p.Alloc(w,h),w,h);
        require(a.page==0 && a.x==pad && a.y==pad,"exact-fill-identity");
        require(validate({a},16,pad,1)=="valid","exact-fill-region");
        p.Free(a.item);
        auto b=receipt(p,p.Alloc(w,h),w,h);
        require(b.page==0 && p.GetNumPages()==1,"freed-full-height-reuse");
    } else if(mode=="clear-rebuild") {
        RectPacker p(16,16,0);
        p.Alloc(8,8);
        p.Clear();
        require(p.GetNumPages()==0,"clear-page-count");
        auto b=receipt(p,p.Alloc(8,8),8,8);
        require(validate({b},16,0,1)=="valid","clear-rebuild-region");
    } else if(mode=="invalid-atomic") {
        RectPacker p(16,16,2);
        bool rejected=false;
        try { p.Alloc(0,5); } catch(const std::runtime_error&) { rejected=true; }
        require(rejected,"zero-width-not-rejected");
        require(p.GetNumPages()==0 && p.Items.size()==0,"invalid-allocation-mutated-owner");
    } else if(mode=="invalid-boundaries") {
        for(const auto& dims:std::vector<std::pair<int,int>>{{0,4},{4,0},{-1,4},{4,-1},{13,4},{4,13},{INT_MAX,1},{1,INT_MAX}}) {
            RectPacker p(16,16,2); bool rejected=false;
            try { p.Alloc(dims.first,dims.second); } catch(const std::runtime_error&) { rejected=true; }
            require(rejected && p.GetNumPages()==0 && p.Items.size()==0,"invalid-dimension-atomicity");
        }
        for(const auto& dims:std::vector<std::pair<int,int>>{{0,16},{16,0},{-1,16},{16,-1}}) {
            bool rejected=false;
            try { RectPacker p(dims.first,dims.second,0); } catch(const std::runtime_error&) { rejected=true; }
            require(rejected,"invalid-page-accepted");
        }
        for(int pad: {-1,8,INT_MAX}) {
            bool rejected=false;
            try { RectPacker p(16,16,pad); } catch(const std::runtime_error&) { rejected=true; }
            require(rejected,"invalid-padding-accepted");
        }
        RectPacker tiny(1,1,0); tiny.Alloc(1,1);
    } else if(mode=="oracle-negatives") {
        RectPacker p(16,16,0);
        std::vector<Region> good{receipt(p,p.Alloc(16,16),16,16),receipt(p,p.Alloc(16,16),16,16)};
        require(validate(good,16,0,2)=="valid","two-page-baseline");
        auto bad=good; bad[1].page=0;
        require(validate(bad,16,0,2)=="overlap","swapped-page-not-detected");
        bad=good; bad[0].x=1;
        require(validate(bad,16,0,2)=="outside-page","stale-region-not-detected");
        bad=good; bad[0].w=15;
        require(validate(bad,16,0,2)=="size-mismatch","changed-region-size-not-detected");
        bad=good; bad[0].page=2;
        require(validate(bad,16,0,2)=="outside-page","unknown-page-not-detected");
    } else if(mode=="bounded-stress") {
        RectPacker p(32,32,1); size_t warmItems=0; int warmPages=0;
        for(int cycle=0;cycle<128;++cycle) {
            p.Clear(); std::vector<Region> live;
            for(int i=0;i<64;++i) {
                const int w=1+(i*5)%11, h=1+(i*7)%9;
                live.push_back(receipt(p,p.Alloc(w,h),w,h));
                require(validate(live,32,1,p.GetNumPages())=="valid","stress-allocation-overlap");
            }
            for(int i=63;i>=0;i-=2) {
                p.Free(live[static_cast<size_t>(i)].item);
                live.erase(live.begin()+i);
                require(validate(live,32,1,p.GetNumPages())=="valid","stress-free-corrupted-neighbour");
            }
            for(int i=0;i<32;++i) {
                const int w=1+(i*5)%11, h=1+(i*7)%9;
                live.push_back(receipt(p,p.Alloc(w,h),w,h));
                require(validate(live,32,1,p.GetNumPages())=="valid","stress-reuse-overlap");
            }
            if(cycle==0) { warmItems=p.Items.size(); warmPages=p.GetNumPages(); }
            require(p.Items.size()==warmItems && p.GetNumPages()==warmPages,"monotonic-resource-growth");
            for(const auto& r:live) p.Free(r.item);
            require(p.ItemFreeList.size()<=p.Items.size(),"free-list-overflow");
        }
        p.Clear();
        require(p.GetNumPages()==0 && p.ItemFreeList.size()==p.Items.size(),"stress-clear-ownership");
        std::cout<<"cycles=128 allocations=12288 pages_high_water="<<warmPages<<" item_objects_high_water="<<warmItems<<" final_pages=0\n";
    } else throw std::logic_error("unknown-case");
}
int main(int argc,char** argv) {
    if(argc!=2) return 2;
    try { run(argv[1]); std::cout<<"PASS "<<argv[1]<<'\n'; return 0; }
    catch(const std::logic_error& e) { std::cerr<<"ORACLE_REJECT "<<e.what()<<'\n'; return 11; }
    catch(const std::runtime_error& e) { std::cerr<<"PRODUCTION_REJECT "<<e.what()<<'\n'; return 10; }
}
