#pragma once

#include <cstdint>

// Renderer-side semantic description of how a sprite card is presented.
// This is deliberately independent of actor/gameplay state and shader/TBN policy.
enum class HWSpriteSurfaceSource : uint8_t
{
	Actor,
	Particle,
	VisualThinker,
};

enum class HWSpritePresentation : uint8_t
{
	FaceYAxis,
	FaceXY,
	FaceCamera,
	Wall,
	Flat,
	Model,
};

struct HWSpriteOrientationPolicyInput
{
	bool isActor = false;
	bool isParticle = false;
	bool isWall = false;
	bool isFlat = false;
	bool isModel = false;

	bool globalXYBillboard = false;
	bool particleXYBillboard = false;
	bool particleNoXYBillboard = false;
	bool actorForceYBillboard = false;
	bool actorForceXYBillboard = false;

	bool globalFacesCamera = false;
	bool forceCameraPreference = false;
	bool actorFacesCamera = false;
	bool actorNoFaceCamera = false;
	bool particleHasTexture = false;
	bool particleFacesCamera = false;
	bool particleNoFaceCamera = false;
};

struct HWSpriteOrientationPolicy
{
	HWSpritePresentation presentation = HWSpritePresentation::FaceYAxis;
	bool xyBillboard = false;
	bool facesCamera = false;
};

// Keep this resolver behavior-identical to the inherited checks in
// HWSprite::CalculateVertices.  PF-009 centralizes those checks; it does not
// redefine billboard preference semantics.
constexpr HWSpriteOrientationPolicy ResolveHWSpriteOrientationPolicy(const HWSpriteOrientationPolicyInput& input)
{
	HWSpriteOrientationPolicy result;

	result.xyBillboard =
		(input.isParticle && input.particleXYBillboard && !input.particleNoXYBillboard) ||
		(!(input.isActor && input.actorForceYBillboard) &&
			(input.globalXYBillboard || (input.isActor && input.actorForceXYBillboard)));

	result.facesCamera = input.forceCameraPreference
		? input.globalFacesCamera
		: input.globalFacesCamera ||
			(input.isActor && !input.actorNoFaceCamera && input.actorFacesCamera) ||
			(input.isParticle && input.particleHasTexture && !input.particleNoFaceCamera && input.particleFacesCamera);

	if (input.isModel)
		result.presentation = HWSpritePresentation::Model;
	else if (input.isFlat)
		result.presentation = HWSpritePresentation::Flat;
	else if (input.isWall)
		result.presentation = HWSpritePresentation::Wall;
	else if (result.facesCamera)
		result.presentation = HWSpritePresentation::FaceCamera;
	else if (result.xyBillboard)
		result.presentation = HWSpritePresentation::FaceXY;
	else
		result.presentation = HWSpritePresentation::FaceYAxis;

	return result;
}
