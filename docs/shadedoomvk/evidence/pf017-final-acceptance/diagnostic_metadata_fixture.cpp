#include "hw_pf17acceptance.h"
#include <cassert>
#include <algorithm>
#include <iostream>
struct Packed { unsigned char bytes[80]{}; };
struct Array { std::vector<Packed> v; size_t Size()const{return v.size();} const Packed* Data()const{return v.data();}const Packed& operator[](size_t i)const{return v[i];} };
struct Data { Array arrays[3];std::vector<PF17Acceptance::Identity> identities[3];void AcceptedClear(){for(auto& a:arrays)a.v.clear();} };
struct Buffer { int Count=8,UploadIndex=1,DataIndex=3;std::vector<unsigned char> storage=std::vector<unsigned char>(8*16+8*80);void* Data=storage.data(); };
int main(int argc,char** argv){
 assert(argc==2);_putenv_s("PF17_ACCEPTANCE_DIR",argv[1]);
 Data data;Buffer buffer;
 data.arrays[0].v.resize(2);data.arrays[1].v.resize(1);
 data.identities[0].resize(2);data.identities[1].resize(1);
 // The diagnostic transformer misses baseline's three named Clear calls.
 data.AcceptedClear();assert(data.identities[0].size()==2);
 data.arrays[0].v.resize(2);data.arrays[1].v.resize(1);
 data.identities[0].resize(4);data.identities[1].resize(2);
 int range[4]={0,2,3,3};std::memcpy(buffer.Data,range,16);
 std::memcpy(buffer.storage.data()+128,data.arrays[0].Data(),160);
 std::memcpy(buffer.storage.data()+288,data.arrays[1].Data(),80);
 assert(std::memcmp(buffer.storage.data()+128,data.arrays[0].Data(),160)==0);
 assert(std::memcmp(buffer.storage.data()+288,data.arrays[1].Data(),80)==0);
 auto immutable=buffer.storage;
 PF17Acceptance::Consumer(data,buffer,0,0);
 assert(PF17Acceptance::S().bufferMismatch==2);
 data.identities[0].resize(2);data.identities[1].resize(1);
 PF17Acceptance::S().bufferMismatch=0;
 PF17Acceptance::Consumer(data,buffer,0,0);
 assert(PF17Acceptance::S().bufferMismatch==0);
 assert(buffer.storage==immutable);
 std::cout<<"PASS: stale diagnostic identities produce 2 mislabeled buffer failures; aligned metadata produces 0 with identical mapped bytes\n";
}
