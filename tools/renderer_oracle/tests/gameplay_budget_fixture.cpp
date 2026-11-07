// Replay actual captured payloads through the unchanged production RecordStore
// and exact gameplay selection/Emit definitions. No renderer/device is used.
#include "hw_sdvkdiagnosticcore.h"
#include <atomic>
#include <cassert>
#include <cstring>
#include <fstream>
#include <iostream>
using namespace SdvkObservation;
struct Observer
{
    bool GameplayInput=false, GameplayDetail=false, GameplayFireA=false, GameplayFireB=false;
    int GameplayMuzzle=0;
    std::atomic<uint64_t> Frame{0};
    RecordStore Records;
};
Observer* currentObserver=nullptr;
Observer& Get() { return *currentObserver; }
bool Enabled() { return true; }
struct PlayerState { int extralight=0; } player;
struct AActor { PlayerState* player=nullptr; } cpuActor{&player};
struct PlayerSlot { AActor* camera=nullptr; } players[1]{{&cpuActor}};
int consoleplayer=0;
struct MapNameValue { const char* value="SDVGPA"; int Compare(const char* other) const { return std::strcmp(value,other); } };
struct Level { MapNameValue MapName; } level;
#include "gameplay_budget.inc"
int main(int argc,char** argv)
{
    if (argc!=3) return 2;
    std::ifstream input(argv[1],std::ios::binary);
    std::vector<std::pair<std::string,std::string>> rows;
    std::string line;
    while (std::getline(input,line))
    {
        const auto tab=line.find('\t'); assert(tab!=std::string::npos);
        rows.emplace_back(line.substr(0,tab),line.substr(tab+1));
    }
    assert(rows.size()==223);
    RecordStore original;
    unsigned rejectedFrame=0;
    for (unsigned frame=1;frame<=128 && !rejectedFrame;++frame)
        for (const auto& row: rows)
            if (!original.Add(row.first.c_str(),frame,row.second,false)) { rejectedFrame=frame; break; }
    assert(rejectedFrame>0 && rejectedFrame<40);
    assert(original.Failure()=="SDVK observation record/byte limit reached");

    Observer sampled;
    sampled.GameplayInput=true; currentObserver=&sampled;
    std::vector<unsigned> details;
    // The real legacy payload has no gameplay/checkpoint rows. Reserve maximum
    // legal payloads every frame and at all nine checkpoints, respectively.
    const std::string maxGameplay="{"+std::string(RecordStore::MaxRecordBytes-2,' ')+"}";
    for (unsigned frame=1;frame<=128;++frame)
    {
        sampled.Frame=frame;
        level.MapName.value=frame<=56 || frame>96 ? "SDVGPA" : "SDVGPB";
        player.extralight=(frame>=44 && frame<=48) || (frame>=84 && frame<=88) ? 1 : 0;
        SelectGameplayDetail(sampled);
        if (sampled.GameplayDetail) details.push_back(frame);
        for (const auto& row: rows)
        {
            Emit(row.first.c_str(),row.second,false);
        }
        Emit("gameplay",maxGameplay,false);
        if (sampled.GameplayDetail) Emit("gameplay-checkpoint",maxGameplay,false);
        // Acknowledge the selected completed muzzle view, as FramePresented
        // does only after its screenshot succeeds. It cannot select again.
        if (sampled.GameplayMuzzle==1) sampled.GameplayFireA=true;
        if (sampled.GameplayMuzzle==2) sampled.GameplayFireB=true;
    }
    assert((details==std::vector<unsigned>{8,24,40,44,56,80,84,96,120}));
    assert(sampled.Records.Failure().empty() && sampled.Records.DroppedCount()==0);
    assert(sampled.Records.ByteCount()<RecordStore::DefaultMaxBytes);
    std::ofstream retained(argv[2],std::ios::binary);
    retained<<sampled.Records.CloseJson(); retained.close(); assert(retained);
    // The selector resets its latch and never filters ordinary static captures.
    sampled.GameplayInput=false; SelectGameplayDetail(sampled);
    assert(!sampled.GameplayDetail && sampled.GameplayMuzzle==0);
    for (const auto& row: rows) assert(GameplayRecordSelected(sampled,row.first.c_str()));
    std::cout<<Object().Int("real_rows",rows.size()).Int("old_rejected_frame",rejectedFrame)
        .Int("limit_bytes",RecordStore::DefaultMaxBytes).Int("selected_bytes",sampled.Records.ByteCount())
        .Int("selected_rows",sampled.Records.Size()).Int("detail_frames",details.size())
        .Int("max_gameplay_reserve_per_frame",maxGameplay.size()).Json()<<'\n';
}
