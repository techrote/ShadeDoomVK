#pragma once
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>
namespace PF17Acceptance {
struct Identity { uint64_t incarnation; int tid, sourceGroup, renderGroup, policy; };
static_assert(sizeof(Identity)==24, "diagnostic identity layout");
struct State {
 std::mutex mutex;
 std::unordered_map<const void*,uint64_t> births;
 uint64_t next=1, frame=0;
 int tick=-1;
 unsigned long long calls=0, records[3]={}, bytes=0, writes=0, reused=0, zeroClasses=0;
 unsigned long long packs=0,hits=0,fallbacks=0,noContext=0,packingMismatch=0,bufferMismatch=0;
 FILE* identities=nullptr; bool headerWritten=false;
};
inline State& S(){static State* s=new State; return *s;}
inline const char* Directory(){static const char* p=std::getenv("PF17_ACCEPTANCE_DIR"); return p;}
inline bool Checkpoint(int tic){return tic==45 || tic==105 || tic==165;}
inline void Born(const void* p){if(Directory()){auto& s=S();std::lock_guard<std::mutex> lock(s.mutex);s.births[p]=s.next++;}}
inline Identity Source(const void* p,int tid,int sourceGroup,int renderGroup,int policy){auto& s=S();std::lock_guard<std::mutex> lock(s.mutex);auto it=s.births.find(p);return {it==s.births.end()?0:it->second,tid,sourceGroup,renderGroup,policy};}
inline void Pack(bool hit,bool fallback,bool noContext,bool mismatch){if(Directory()){auto& s=S();std::lock_guard<std::mutex> lock(s.mutex);++s.packs;s.hits+=hit;s.fallbacks+=fallback;s.noContext+=noContext;s.packingMismatch+=mismatch;}}
inline void Write(size_t bytes){if(Directory()&&bytes){S().bytes+=bytes;++S().writes;}}
inline void Class(bool reused,const uint64_t* revisions,size_t count){if(!Directory())return;S().reused+=reused;bool zero=!revisions;for(size_t i=0;revisions&&i<count;++i)zero|=revisions[i]==0;S().zeroClasses+=zero;}
template<class Buffer> void Frame(Buffer& buffer,int tic){
 if(!Directory())return;
 auto& s=S(); std::lock_guard<std::mutex> lock(s.mutex);
 if(s.identities){std::fclose(s.identities);s.identities=nullptr;}
 if(s.calls){
  auto path=std::string(Directory())+"/counters.csv";FILE* f=std::fopen(path.c_str(),"a");
  if(f){if(!s.headerWritten){std::fprintf(f,"frame,tic,calls,normal,subtractive,additive,mapped_bytes,mapped_writes,reused_classes,zero_revision_classes,packing_calls,packing_hits,packing_fallbacks,no_context_fallbacks,packing_mismatches,buffer_mismatches\n");s.headerWritten=true;}
   std::fprintf(f,"%llu,%d,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu\n",s.frame,s.tick,s.calls,s.records[0],s.records[1],s.records[2],s.bytes,s.writes,s.reused,s.zeroClasses,s.packs,s.hits,s.fallbacks,s.noContext,s.packingMismatch,s.bufferMismatch);std::fclose(f);}
 }
 if(Checkpoint(s.tick)&&s.calls){
  char name[1024];std::snprintf(name,sizeof(name),"%s/buffer-tic-%03d.bin",Directory(),s.tick);FILE* f=std::fopen(name,"wb");
  if(f){int counts[2]={buffer.UploadIndex,buffer.DataIndex};std::fwrite(counts,4,2,f);std::fwrite(buffer.Data,16,counts[0],f);std::fwrite((char*)buffer.Data+buffer.Count*16,80,counts[1],f);std::fclose(f);}
 }
 ++s.frame;s.tick=tic;s.calls=s.bytes=s.writes=s.reused=s.zeroClasses=0;for(auto& n:s.records)n=0;s.packs=s.hits=s.fallbacks=s.noContext=s.packingMismatch=s.bufferMismatch=0;
 if(Checkpoint(tic)){char name[1024];std::snprintf(name,sizeof(name),"%s/identities-tic-%03d.bin",Directory(),tic);s.identities=std::fopen(name,"wb");}
}
template<class Data,class Buffer> void Consumer(const Data& data,Buffer& buffer,int index,int offset){
 if(!Directory())return;
 auto& s=S(); ++s.calls;int counts[5]={index,offset,(int)data.arrays[0].Size(),(int)data.arrays[1].Size(),(int)data.arrays[2].Size()};
 if(s.identities)std::fwrite(counts,4,5,s.identities);
 int ranges[4]={offset,offset+counts[2],offset+counts[2]+counts[3],offset+counts[2]+counts[3]+counts[4]};
 if(std::memcmp((int*)buffer.Data+index*4,ranges,16))++s.bufferMismatch;
 const char* mapped=(const char*)buffer.Data+buffer.Count*16+offset*80;
 for(int c=0;c<3;++c){size_t count=data.arrays[c].Size();s.records[c]+=count;
  if(data.identities[c].size()!=count){++s.bufferMismatch;continue;}
  if(count&&std::memcmp(mapped,data.arrays[c].Data(),count*80))++s.bufferMismatch;
  if(s.identities)for(size_t i=0;i<count;++i){std::fwrite(&data.identities[c][i],24,1,s.identities);std::fwrite(&data.arrays[c][i],80,1,s.identities);}
  mapped+=count*80;
 }
}
}
