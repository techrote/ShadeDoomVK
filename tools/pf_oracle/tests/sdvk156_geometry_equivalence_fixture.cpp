// SPDX-License-Identifier: GPL-3.0-or-later
// Identical valid request/free/Clear trace against retained and current allocators.
#include <algorithm>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#ifdef __clang__
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wunused-parameter"
#endif
#include "tarray.h"
#ifdef __clang__
#pragma clang diagnostic pop
#endif
#include "engineerrors.h"
#define VALIDATE_RECTPACKER
#include "sdvk156_geometry_mode.h"
#include "hw_rectpacker.h"
#include "hw_lightmaptile.h"
void* M_Malloc(size_t n) { auto p=std::malloc(n); if(!p)throw std::bad_alloc(); return p; }
void* M_Realloc(void* p,size_t n) { auto q=std::realloc(p,n); if(!q)throw std::bad_alloc(); return q; }
void M_Free(void* p) { std::free(p); }
[[noreturn]] void I_FatalError(const char* fmt, ...) {
    char message[512];va_list args;va_start(args,fmt);std::vsnprintf(message,sizeof(message),fmt,args);va_end(args);
    throw std::runtime_error(message);
}
#include "sdvk156_geometry_allocator.cpp"
#if SDVK156_CURRENT
using Receipt=RectPackerAllocation;
#else
using Receipt=RectPackerItem*;
#endif
int main(int argc,char** argv) {
    if(argc==2&&std::string(argv[1])=="sizes") {
        std::cout<<"{\"receipt\":"<<sizeof(Receipt)<<",\"item\":"<<sizeof(RectPackerItem)
                 <<",\"packer\":"<<sizeof(RectPacker)<<",\"tile\":"<<sizeof(LightmapTile)<<"}\n";
        return 0;
    }
    try {
        RectPacker p(64,48,2);uint32_t random=156;int count=0;
        auto next=[&] {random=random*1664525u+1013904223u;return random;};
        auto allocate=[&] {
            const int w=1+int(next()%20),h=1+int(next()%12);
            auto receipt=p.Alloc(w,h);
#if SDVK156_CURRENT
            const auto r=p.GetRegion(receipt);
#else
            const auto& r=*receipt;
#endif
            std::cout<<count++<<':'<<r.PageIndex<<','<<r.X<<','<<r.Y<<','<<r.Width<<','<<r.Height<<'\n';
            return receipt;
        };
        for(int cycle=0;cycle<32;++cycle) {
            std::vector<Receipt> active;
            for(int i=0;i<64;++i)active.push_back(allocate());
            for(int i=0;i<64;i+=2){p.Free(active[i]);active[i]={};}
            for(int i=0;i<16;++i)active.push_back(allocate());
            for(auto receipt:active)if(receipt)p.Free(receipt);
            std::cout<<"pages="<<p.GetNumPages()<<'\n';p.Clear();
        }
        return 0;
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
