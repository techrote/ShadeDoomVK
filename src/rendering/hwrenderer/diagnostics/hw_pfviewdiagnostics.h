#pragma once
#include <string>

struct HWDrawInfo;
struct FFlatVertex;
class HWSprite;

// PF020-only scene observations. The separately requested fixture actor fraction
// changes visual interpolation only. No production context is constructed here;
// a derived original-seams build reports that metadata as unavailable.
namespace Pf020ViewDiagnostics
{
bool Enabled();
// Called once after the real map load, before the first play-loop tic. This
// opt-in fixture scheduler preserves game tics; it is not a timing benchmark.
bool BeginFixtureClock(const char* map, bool ordinarySinglePlayer);
bool FixtureActive();
const char* OutputPrefix();
std::string CurrentSceneKeyJson();
std::string ActiveSceneKeyJson();
std::string ActiveSemanticKeyJson();
void BeginRoot(bool mainview, bool toscreen, int side, const char* map);
// Apply the explicit fixture fraction before viewpoint interpolation. This
// does not depend on a previous root and preserves the inherited probe value.
double SetupFraction(double inherited, int side, const char* map);
double ActorFraction(double inherited);
void BeginEye(int eye);
void SceneBegin(const HWDrawInfo* di, int drawmode);
void SceneEnd(const HWDrawInfo* di);
void Restored(const HWDrawInfo* di);
void PostprocessCompleted(const HWDrawInfo* di);
void SpriteVertices(const HWDrawInfo* di, const HWSprite* sprite, const FFlatVertex* vertices);
}
