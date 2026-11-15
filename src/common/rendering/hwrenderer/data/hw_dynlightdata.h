// 
//---------------------------------------------------------------------------
//
// Copyright(C) 2005-2016 Christoph Oelckers
// All rights reserved.
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Lesser General Public License as published by
// the Free Software Foundation, either version 2 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Lesser General Public License for more details.
//
// You should have received a copy of the GNU Lesser General Public License
// along with this program.  If not, see http://www.gnu.org/licenses/
//
//--------------------------------------------------------------------------
//

#ifndef __GLC_DYNLIGHT_H
#define __GLC_DYNLIGHT_H

#include "tarray.h"
#include "vectors.h"
#include <cstdint>
#include <cstddef>

enum FDynLightInfoFlags
{
	LIGHTINFO_ATTENUATED = 1,
	LIGHTINFO_SHADOWMAPPED = 2,
	LIGHTINFO_SPOT = 4,
	LIGHTINFO_TRACE = 8,
	LIGHTINFO_SUN = 16,
};

// Light-facing source-alpha silhouette, sampled into a 64x128 binary mask.
// Actor x/y/z positions use renderer space (x, height, map-y). The visible
// sprite image stays unchanged: only its independently projected shadow alpha
// is sampled. Masks live in a bounded frame-owned side buffer, never repeated
// in every surface's dynamic-light record. Each uint32 packs 32 source samples.
constexpr int MaxActorShadowCastersPerLight = 4;
constexpr int ActorShadowMaskWidth = 64;
constexpr int ActorShadowMaskHeight = 128;
constexpr int ActorShadowMaskWords = ActorShadowMaskWidth * ActorShadowMaskHeight / 32;
constexpr int MaxActorShadowCastersPerFrame = 4096;
struct FActorShadowCaster
{
	float x, y, z, radius;   // sprite anchor; radius used only for selection
	float bottom, top, planeNx, planeNz;
	float left, right, mirrorX, mirrorY;
	uint32_t alphaWords[ActorShadowMaskWords];
};

struct FDynLightInfo
{
	float x;
	float y;
	float z;
	int actorShadowIndex; // side-buffer range; valid only when count/mask != 0
	float r;
	float g;
	float b;
	int actorShadowCount; // 8
	float spotDirX;
	float spotDirY;
	float spotDirZ;
	int actorShadowMask; // receiver-specific enabled bits; excludes self
	float radius;
	float linearity;
	float softShadowRadius;
	float strength; // 16
	float spotInnerAngle;
	float spotOuterAngle;
	int shadowIndex;
	int flags; // 20
};
static_assert(sizeof(FActorShadowCaster) == 1072, "Actor shadow buffer ABI changed");
static_assert(offsetof(FActorShadowCaster, alphaWords) == 48, "Actor mask offset changed");
// Reuse the three existing padding words: OFF retains the original light stride.
static_assert(sizeof(FDynLightInfo) == 80, "Dynamic-light buffer ABI changed");
static_assert(offsetof(FDynLightInfo, actorShadowIndex) == 12, "Actor range offset changed");
static_assert(offsetof(FDynLightInfo, actorShadowCount) == 28, "Actor count offset changed");
static_assert(offsetof(FDynLightInfo, actorShadowMask) == 44, "Actor mask bits offset changed");

enum FDynLightDataArrays
{
	LIGHTARRAY_NORMAL,
	LIGHTARRAY_SUBTRACTIVE,
	LIGHTARRAY_ADDITIVE,
};

#define MAX_LIGHT_DATA 80000

struct FDynLightData
{
	TArray<FDynLightInfo> arrays[3];

	void Clear()
	{
		arrays[LIGHTARRAY_NORMAL].Clear();
		arrays[LIGHTARRAY_SUBTRACTIVE].Clear();
		arrays[LIGHTARRAY_ADDITIVE].Clear();
	}

};

struct sun_trace_cache_t
{
	DVector3 Pos = DVector3(-12345678.0, -12345678.0, -12345678.0);
	bool SunResult = false;
	uint64_t QueryEpoch = 0;
	int PortalGroup = 0;

	// PF-016 actor/model candidate-source qualification. This is deliberately
	// separate from PF-015 visibility validity: it records only the geometric
	// fact that the actor's current render-radius circle touches one section in
	// one portal group. Once proven, that exact actor state may source candidates
	// directly from the section light list. Movement/radius/section/group changes
	// force the baseline BSP qualification path again.
	DVector3 LocalQueryPos = DVector3(-12345678.0, -12345678.0, -12345678.0);
	const void* LocalQuerySection = nullptr;
	double LocalQueryRadius = -1.0;
	int LocalQueryPortalGroup = 0;
	bool LocalQueryKnown = false;
	bool LocalQueryExact = false;
};

enum FShadowCastingTypes
{
	SHADOWCASTING_None = 0,
	SHADOWCASTING_Static,
	// Not yet implemented.
	//SHADOWCASTING_Dynamic
};

extern thread_local FDynLightData lightdata;


#endif
