#include <atomic>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>
enum { Button_Forward, Button_Right, Button_Attack };
struct Buttons { bool pressed[3]={}; bool ButtonDown(int i) const { return pressed[i]; } } buttonMap;
bool cl_capfps=true, vid_vsync=false, singletics=false, r_NoInterpolate=false;
bool netgame=false, multiplayer=false, demoplayback=false, demorecording=false, sdvk_gameplay_pending=false;
int vid_maxfps=0;
enum { ga_nothing, ga_newgame }; int gameaction=ga_nothing;
enum { GS_LEVEL, GS_CONSOLE }; int gamestate=GS_LEVEL;
struct Mesh { uint64_t owner=100; uint64_t GetResourceOwner() const { return owner; } } mesh;
struct MapNameValue { const char* name="SDVGPA"; int Compare(const char* other) const { return std::strcmp(name,other); } };
struct Level { MapNameValue MapName; Mesh* levelMesh=&mesh; } level;
struct Observer { bool GameplayInput=true; const char* GameplayPendingMap=nullptr; uint64_t GameplayPreviousOwner=0; std::atomic<uint64_t> Frame{8}; };
bool failed=false;
namespace SdvkDiagnostics { void Fail(const char*) { failed=true; } }
constexpr int PRINT_HIGH=1, PRINT_NONOTIFY=2;
void Printf(int,const char*,...) {}
std::vector<std::string> commands;
void AddCommandString(const char* text) { commands.emplace_back(text); }
#include "gameplay_input.inc"
int main()
{
    Observer observer;
    observer.GameplayInput=false; DriveGameplayInput(observer); assert(commands.empty());
    observer.GameplayInput=true; DriveGameplayInput(observer);
    assert(commands.size()==1 && commands.back()=="+forward; wait 6; -forward; sdvk_gameplay_pending false");
    assert(sdvk_gameplay_pending);
    observer.Frame=24; DriveGameplayInput(observer); assert(failed && commands.size()==1);
    failed=false; sdvk_gameplay_pending=false; buttonMap.pressed[Button_Forward]=true;
    DriveGameplayInput(observer); assert(failed && commands.size()==1);
    failed=false; buttonMap.pressed[Button_Forward]=false; DriveGameplayInput(observer);
    assert(!failed && commands.size()==2 && sdvk_gameplay_pending);
    sdvk_gameplay_pending=false; observer.Frame=56; DriveGameplayInput(observer);
    assert(commands.back()=="map SDVGPB" && observer.GameplayPendingMap);
    observer.Frame=80; gameaction=ga_newgame; DriveGameplayInput(observer); assert(failed);
    failed=false; gameaction=ga_nothing; level.MapName.name="SDVGPB";
    DriveGameplayInput(observer); assert(failed); // same mesh is not a completed transition
    failed=false; mesh.owner=101; DriveGameplayInput(observer);
    assert(!failed && !observer.GameplayPendingMap && sdvk_gameplay_pending);
    assert(commands.back()=="+attack; wait 8; -attack; sdvk_gameplay_pending false");
    failed=false; sdvk_gameplay_pending=false; observer.Frame=96; singletics=true;
    const auto before=commands.size(); DriveGameplayInput(observer); assert(failed && commands.size()==before);
}
