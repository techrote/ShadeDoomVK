// Actual fixed driver, ordinary G_Ticker action loop and G_DoNewGame completion.
// Map installation/console services are CPU doubles; no renderer/device exists.
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>
struct Name {
 std::string Text="SDV161A"; const char* GetChars()const{return Text.c_str();}
 int Compare(const char* other)const{return Text.compare(other);}
 Name& operator=(const char* other){Text=other;return *this;}
};
struct Mesh {uint64_t Owner=3;uint64_t GetResourceOwner()const{return Owner;}} Current;
struct {Mesh* levelMesh=&Current;Name MapName;} level;
struct Observer {bool SpecialSurfaceInput=false;unsigned Seen=0,Collected=0;};
static Observer ObserverValue;
Observer& Get(){return ObserverValue;}
static bool EnabledValue=true;
static bool cl_capfps=true,vid_vsync=false;
static int vid_maxfps=0;
static std::string Failure;
static bool InstallMesh=true,AdvanceOwner=true;
static const char* OverrideMap=nullptr;
constexpr int PRINT_HIGH=1,PRINT_NONOTIFY=2;
template<class... Args>void Printf(int,const char* format,Args... args){std::printf(format,args...);}
void Require(bool value,const char* reason){if(!value)throw std::runtime_error(reason);}
namespace SdvkDiagnostics {
bool Enabled(){return EnabledValue;}
void Fail(const char* reason){Failure=reason;}
void SpecialSurfaceMapTransitionCompleted();
}
#include "map_transition_actions.inc"
static Name d_mapname;
static int d_skill=-1,gameskill=0,consoleplayer=0,playeringame[1]={},gamestate=0;
static Name newdemoname,newdemomap,savegamefile,savedescription,shotfile;
constexpr int GS_CUTSCENE=1,GS_INTRO=2;
void CheckWarpTransMap(Name&,bool){}
void G_NewInit(){}
void G_InitNew(const char* map,bool){
 level.MapName=OverrideMap?OverrideMap:map;
 if(AdvanceOwner)++Current.Owner;
 level.levelMesh=InstallMesh?&Current:nullptr;
}
#include "map_transition_defer.inc"
#include "map_transition_newgame.inc"
void AddCommandString(const char* command){
 std::cout<<"COMMAND "<<command<<'\n';
 if(!std::strncmp(command,"map ",4))G_DeferedInitNew(command+4,-1);
}
#include "map_transition_input.inc"
namespace SdvkDiagnostics {
#include "map_transition_pending.inc"
#include "map_transition_complete.inc"
}
// Unvisited ordinary gameaction services; actual map completion above is kept.
#define SERVICE(name) template<class...T>void name(T...){gameaction=ga_nothing;}
SERVICE(G_CheckDemoStatus) SERVICE(G_RecordDemo) SERVICE(G_BeginRecording)
SERVICE(G_DoLoadGame) SERVICE(G_DoSaveGame) SERVICE(G_DoAutoSave)
SERVICE(G_DoPlayDemo) SERVICE(G_DoCompleted) SERVICE(G_DoWorldDone)
SERVICE(M_ScreenShot) SERVICE(G_FullConsole) SERVICE(AM_ToggleMap)
SERVICE(P_ResumeConversation) SERVICE(D_StartTitle) SERVICE(C_HideConsole)
void C_AdjustBottom(){}
void OrdinaryTicker(){
#include "map_transition_ticker.inc"
}
static bool M_IsAnimated(){return false;}
static bool ActualTicWait(bool vid_dontdowait,bool cl_capfps=true,bool r_NoInterpolate=true){
 bool pauseext=false,vid_vsync=false,AppActive=true,vid_lowerinbackground=false;
 int vid_maxfps=0;
#include "map_transition_wait.inc"
 return doWait;
}
static void Check(bool value,const char* reason){if(!value)throw std::runtime_error(reason);}
static void Clear(){Failure.clear();PendingSpecialSurfaceMapInput()={};gameaction=ga_nothing;level.levelMesh=&Current;level.MapName="SDV161A";InstallMesh=AdvanceOwner=true;OverrideMap=nullptr;cl_capfps=true;vid_maxfps=0;vid_vsync=false;}
static void Queue(unsigned ordinal=56){ObserverValue.SpecialSurfaceInput=true;ObserverValue.Seen=ordinal;ObserverValue.Collected=ordinal-32;DriveSpecialSurfaceInput(ObserverValue);}
int main(int argc,char** argv){try{
 std::string mode=argc>1?argv[1]:"schedule";
 if(mode=="schedule"){
  for(ObserverValue.Seen=0;ObserverValue.Seen<=128;++ObserverValue.Seen)DriveSpecialSurfaceInput(ObserverValue);
  std::cout<<"ENABLED\n";ObserverValue.SpecialSurfaceInput=true;
  for(ObserverValue.Seen=0;ObserverValue.Seen<=128;++ObserverValue.Seen){
   ObserverValue.Collected=ObserverValue.Seen>32?ObserverValue.Seen-32:0;
   DriveSpecialSurfaceInput(ObserverValue);
   if(PendingSpecialSurfaceMapInput().Phase){
    const auto before=Current.Owner;const auto views=ObserverValue.Seen;
    OrdinaryTicker();Check(gameaction==ga_newgame && Current.Owner==before,"first ordinary tic did not defer old owner");
    // Without the display barrier this exact old owner would be retained.
    Check(SdvkDiagnostics::SpecialSurfaceMapTransitionPending(),"old-owner display was not blocked");
    Check(ObserverValue.Seen==views,"barrier changed presented ordinal");
    OrdinaryTicker();Check(gameaction==ga_nothing && Current.Owner!=before,"ordinary completion did not install new owner");
    Check(!SdvkDiagnostics::SpecialSurfaceMapTransitionPending() && Failure.empty(),"completed transition remained pending");
    SdvkDiagnostics::SpecialSurfaceMapTransitionCompleted(); // no duplicate receipt
   }
  }
 }else if(mode=="multi-tic"){
  Queue();OrdinaryTicker();OrdinaryTicker();
  Check(!SdvkDiagnostics::SpecialSurfaceMapTransitionPending() && Failure.empty(),"same-loop two-tic completion failed");
 }else if(mode=="failures"){
  Clear();Queue();gameaction=ga_nothing;Check(!SdvkDiagnostics::SpecialSurfaceMapTransitionPending()&&!Failure.empty(),"cancelled request admitted");
  Clear();Queue();gameaction=ga_screenshot;Check(!SdvkDiagnostics::SpecialSurfaceMapTransitionPending()&&!Failure.empty(),"other action admitted");
  Clear();Queue();Check(SdvkDiagnostics::SpecialSurfaceMapTransitionPending(),"first bounded wait");Check(SdvkDiagnostics::SpecialSurfaceMapTransitionPending(),"second bounded wait");Check(!SdvkDiagnostics::SpecialSurfaceMapTransitionPending()&&!Failure.empty(),"unbounded pending action");
  for(int variant=0;variant<3;++variant){Clear();Queue();if(variant==0)InstallMesh=false;if(variant==1)AdvanceOwner=false;if(variant==2)OverrideMap="WRONG";OrdinaryTicker();OrdinaryTicker();Check(!Failure.empty()&&!PendingSpecialSurfaceMapInput().Phase,"invalid completion admitted");}
  Clear();Queue();DriveSpecialSurfaceInput(ObserverValue);Check(!Failure.empty(),"duplicate request admitted");
  for(int variant=0;variant<3;++variant){
   Clear();Queue();if(variant==0)cl_capfps=false;if(variant==1)vid_maxfps=60;if(variant==2)vid_vsync=true;
   Check(!SdvkDiagnostics::SpecialSurfaceMapTransitionPending()&&!Failure.empty(),"changed waiting settings admitted");
   Clear();if(variant==0)cl_capfps=false;if(variant==1)vid_maxfps=60;if(variant==2)vid_vsync=true;Queue();Check(!Failure.empty()&&!PendingSpecialSurfaceMapInput().Phase,"nonwaiting request admitted");
  }
  Clear();Queue();++ObserverValue.Seen;OrdinaryTicker();Check(!SdvkDiagnostics::SpecialSurfaceMapTransitionPending()&&!Failure.empty(),"advanced view admitted while pending");
  Clear();Queue();++ObserverValue.Seen;OrdinaryTicker();OrdinaryTicker();Check(!Failure.empty(),"late completion admitted after old-owner view");
  std::cout<<"PASS cancellation/other-action/missing-callback/bounded-wait/missing-owner/same-owner/wrong-map/duplicate\n";
 }else if(mode=="inert"){
  Check(ActualTicWait(false)&&ActualTicWait(true),"pinned ordinary timing can skip tic wait");
  Check(!ActualTicWait(true,false,false),"uncapped zero-tic path negative no longer distinct");
  ObserverValue.SpecialSurfaceInput=false;gameaction=ga_newgame2;Check(!SdvkDiagnostics::SpecialSurfaceMapTransitionPending(),"ordinary map blocked");SdvkDiagnostics::SpecialSurfaceMapTransitionCompleted();
  ObserverValue.SpecialSurfaceInput=true;EnabledValue=false;Check(!SdvkDiagnostics::SpecialSurfaceMapTransitionPending(),"disabled map blocked");SdvkDiagnostics::SpecialSurfaceMapTransitionCompleted();Check(Failure.empty(),"inert completion failed");
  std::cout<<"PASS ordinary/disabled behavior unchanged\n";
 }else throw std::runtime_error("unknown fixture mode");
 return 0;
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}}
