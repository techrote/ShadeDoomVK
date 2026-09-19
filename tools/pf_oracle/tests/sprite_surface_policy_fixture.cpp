#include "hw_sprite_surface.h"

#include <cassert>

static HWSpriteOrientationPolicy resolve(HWSpriteOrientationPolicyInput input)
{
	return ResolveHWSpriteOrientationPolicy(input);
}

int main()
{
	HWSpriteOrientationPolicyInput input{};
	input.isActor = true;

	// Default face sprites remain inherited Y-axis billboards.
	auto policy = resolve(input);
	assert(policy.presentation == HWSpritePresentation::FaceYAxis);
	assert(!policy.xyBillboard);
	assert(!policy.facesCamera);

	// Global XY mode affects ordinary actors.
	input.globalXYBillboard = true;
	policy = resolve(input);
	assert(policy.presentation == HWSpritePresentation::FaceXY);
	assert(policy.xyBillboard);

	// Actor FORCEY still suppresses the global XY preference.
	input.actorForceYBillboard = true;
	policy = resolve(input);
	assert(policy.presentation == HWSpritePresentation::FaceYAxis);
	assert(!policy.xyBillboard);

	// Actor FORCEXY is effective when FORCEY is absent.
	input.globalXYBillboard = false;
	input.actorForceYBillboard = false;
	input.actorForceXYBillboard = true;
	policy = resolve(input);
	assert(policy.presentation == HWSpritePresentation::FaceXY);
	assert(policy.xyBillboard);

	// Face-camera may coexist with XY; the descriptive presentation records the
	// camera-facing specialization while the XY bit remains available to the
	// inherited pitch/roll transform.
	input.globalXYBillboard = true;
	input.globalFacesCamera = true;
	policy = resolve(input);
	assert(policy.presentation == HWSpritePresentation::FaceCamera);
	assert(policy.xyBillboard);
	assert(policy.facesCamera);

	// hw_force_cambbpref preserves its inherited meaning: actor preference bits
	// are ignored and the global camera-facing preference alone decides.
	input.globalXYBillboard = false;
	input.globalFacesCamera = false;
	input.forceCameraPreference = true;
	input.actorFacesCamera = true;
	policy = resolve(input);
	assert(!policy.facesCamera);
	assert(policy.presentation == HWSpritePresentation::FaceXY);

	// Without forced camera preference, actor opt-in is honored unless vetoed.
	input.actorForceXYBillboard = false;
	input.forceCameraPreference = false;
	policy = resolve(input);
	assert(policy.facesCamera);
	assert(policy.presentation == HWSpritePresentation::FaceCamera);
	input.actorNoFaceCamera = true;
	policy = resolve(input);
	assert(!policy.facesCamera);
	assert(policy.presentation == HWSpritePresentation::FaceYAxis);

	// Wall and flat cards retain their semantic presentation even when global
	// billboard preferences are enabled. The boolean policy remains available
	// because the inherited wall path still observes the shared transform code.
	input = {};
	input.isActor = true;
	input.isWall = true;
	input.globalXYBillboard = true;
	input.globalFacesCamera = true;
	policy = resolve(input);
	assert(policy.presentation == HWSpritePresentation::Wall);
	assert(policy.xyBillboard);
	assert(policy.facesCamera);

	input.isWall = false;
	input.isFlat = true;
	policy = resolve(input);
	assert(policy.presentation == HWSpritePresentation::Flat);

	// Textured particles retain the two independent inherited routes into XY
	// and face-camera mode, including the NO_XY and NOFACECAMERA boundaries.
	input = {};
	input.isParticle = true;
	input.particleXYBillboard = true;
	policy = resolve(input);
	assert(policy.presentation == HWSpritePresentation::FaceXY);
	assert(policy.xyBillboard);
	input.particleNoXYBillboard = true;
	policy = resolve(input);
	assert(!policy.xyBillboard);
	assert(policy.presentation == HWSpritePresentation::FaceYAxis);

	input.particleHasTexture = true;
	input.particleFacesCamera = true;
	policy = resolve(input);
	assert(policy.facesCamera);
	assert(policy.presentation == HWSpritePresentation::FaceCamera);
	input.particleNoFaceCamera = true;
	policy = resolve(input);
	assert(!policy.facesCamera);

	// The inherited global XY preference still applies to particles even if the
	// particle-specific XY preference is disabled/vetoed.
	input.globalXYBillboard = true;
	policy = resolve(input);
	assert(policy.xyBillboard);

	// Models are explicitly classified and are not accidentally presented as
	// sprite cards by downstream PF consumers.
	input = {};
	input.isActor = true;
	input.isModel = true;
	input.globalXYBillboard = true;
	input.globalFacesCamera = true;
	policy = resolve(input);
	assert(policy.presentation == HWSpritePresentation::Model);

	return 0;
}
