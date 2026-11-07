#include "hw_viewmodel_policy.h"
#include "hw_sprite_tangent.h"
#include <cassert>
#include <cmath>

int main()
{
    using namespace HWViewmodel;
    assert(Resolve(0, true, false, false, false).mode == Legacy);
    assert(Resolve(1, true, false, false, false).mode == Sector);
    assert(Resolve(2, true, false, false, false).mode == Enhanced);
    assert(Resolve(2, false, false, false, false).fallback == PerPixelDisabled);
    assert(Resolve(2, true, true, false, false).fallback == PortalAmbiguous);
    assert(Resolve(2, true, false, true, false).mode == Enhanced);
    assert(Resolve(2, true, false, true, false).fallback == None);
    assert(Resolve(2, true, false, false, true).mode == Legacy);
    assert(Resolve(3, true, false, false, false).fallback == InvalidMode);
    assert(Resolve(-1, true, false, false, false).mode == Legacy);
    // Camera-facing HUD card at yaw=0, pitch=0 in shader-world coordinates.
    const float p[4][3] = {{0,1,0},{0,1,1},{0,0,0},{0,0,1}};
    const auto normal = ResolveHWSpriteTangentBasis(p,0,1,0,1);
    const auto mirror = ResolveHWSpriteTangentBasis(p,1,0,0,1);
    assert(normal.valid && mirror.valid);
    assert(normal.normal.X == -1 && mirror.normal.X == -1);
    assert(normal.tangent.Z == 1 && mirror.tangent.Z == -1);
    assert(normal.handedness == -mirror.handedness);
	const float partial[4][3] = {{0,1,0},{0,1,0},{0,0,0},{0,0,1}};
	assert(!ResolveHWSpriteTangentBasis(partial,0,1,0,1).valid);
    return 0;
}
