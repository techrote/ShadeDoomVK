#include <cassert>
#include <initializer_list>
#include "src/rendering/hwrenderer/scene/hw_viewmodel_policy.h"
struct FVector3 { float X=0, Y=0, Z=0; };
struct HUDSprite { int viewmodelMode=2, viewmodelRequested=2, viewmodelProbe=3; FVector3 viewmodelSample{1,2,3}; };
struct FGameTexture { int shader; };
struct AActor { void* GetClass(){return nullptr;} };
using FTranslationID = int;
constexpr int UF_Skin=0, CLAMP_NOFILTER=1, CLAMP_NONE=0, FIRST_USER_SHADER=100;
bool TrueColor=true;
bool V_IsTrueColor(){return TrueColor;}
struct UserShader { void BindActorFields(AActor*){} } usershaders[1];
namespace HWViewmodel { void RecordMode(int, int) {} }
struct FRenderState
{
    int shader=0, mode=-1, fallback=-1, probe=10, light=10;
    bool vertex=true, noNormals=true, center=false, model=false;
    FVector3 sample{}, actor{};
    void SetMaterial(FGameTexture* skin,int,int,int,FTranslationID,int,void*){shader=skin->shader;}
    int getShaderIndex(){return shader;}
    void SetViewmodelLighting(FVector3 p,int,int m,int f,bool mdl){sample=p;mode=m;fallback=f;model=mdl;}
    void SetLightProbeIndex(int p){probe=p;}
    void SetShadeVertex(bool p){vertex=p;}
    void SetLightNoNormals(bool p){noNormals=p;}
    void SetUseSpriteCenter(bool p){center=p;}
    void SetActorCenter(float x,float y,float z){actor={x,y,z};}
    void SetLightIndex(int p){light=p;}
};
struct FHWModelRenderer
{
    FRenderState& state;
    int modellightindex=7;
    const HUDSprite* viewmodel=nullptr;
    bool worldNormalValid=true;
    AActor* lastAct=nullptr;
    int lastShader=0;
    explicit FHWModelRenderer(FRenderState& s):state(s){}
    void SetMaterial(FGameTexture*,bool,FTranslationID,void*);
};
#include "model_skin_method.inc"

int main()
{
    FRenderState state;
    FHWModelRenderer renderer(state);
    FGameTexture pbr{4}, normal{3}, warp{2}, custom{100};
    HUDSprite hud;
    renderer.viewmodel=&hud;
    for (FGameTexture* skin : {&pbr, &warp, &normal, &custom, &pbr})
    {
        renderer.SetMaterial(skin,false,0,nullptr);
        const bool supported=skin->shader==3 || skin->shader==4;
        assert(state.mode==(supported?2:1));
        assert(state.fallback==(supported?0:4));
        assert(state.probe==(supported?3:-1));
        assert(state.light==(supported?7:-1));
        assert(state.center==supported && !state.vertex && !state.noNormals && state.model);
        assert(state.sample.X==(supported?1.f:0.f));
        if(supported)assert(state.actor.X==1 && state.actor.Y==2 && state.actor.Z==3);
    }
    renderer.worldNormalValid=false;
    renderer.SetMaterial(&pbr,false,0,nullptr);
    assert(state.mode==1 && state.fallback==4 && state.probe==-1 && state.light==-1);
    renderer.worldNormalValid=true;TrueColor=false;
    renderer.SetMaterial(&pbr,false,0,nullptr);
    assert(state.mode==1 && state.fallback==4 && !state.center);
    TrueColor=true;
    // Legacy HUD and world models retain the inherited material/light binding.
    hud.viewmodelMode=0;state.mode=88;state.probe=89;state.center=false;
    renderer.SetMaterial(&pbr,false,0,nullptr);
    assert(state.mode==88 && state.probe==89 && state.light==7 && !state.center);
    renderer.viewmodel=nullptr;
    renderer.SetMaterial(&normal,false,0,nullptr);
    assert(state.mode==88 && state.probe==89 && state.light==7 && !state.center);
}
