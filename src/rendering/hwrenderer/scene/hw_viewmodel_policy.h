#pragma once
// SDVK-011: render-only policy. HUD cards are not world geometry.
namespace HWViewmodel
{
enum Mode { Legacy = 0, Sector = 1, Enhanced = 2 };
enum Fallback { None = 0, InvalidMode, PerPixelDisabled, PortalAmbiguous, HudModel, SpecialStyle, InvalidBasis };
struct Policy { int mode = Legacy; int fallback = None; };
inline Policy Resolve(int requested, bool perPixel, bool portalAmbiguous, bool model, bool specialStyle)
{
    if (requested < Legacy || requested > Enhanced) return {Legacy, InvalidMode};
    if (requested != Enhanced) return {requested, None};
    if (specialStyle) return {Legacy, SpecialStyle};
    if (!perPixel) return {Legacy, PerPixelDisabled};
    if (portalAmbiguous) return {Legacy, PortalAmbiguous};
    if (model) return {Sector, HudModel};
    return {Enhanced, None};
}
}
