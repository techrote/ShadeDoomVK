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
#include "hw_lightreuse.h"
#include <cstdint>

enum FDynLightInfoFlags
{
	LIGHTINFO_ATTENUATED = 1,
	LIGHTINFO_SHADOWMAPPED = 2,
	LIGHTINFO_SPOT = 4,
	LIGHTINFO_TRACE = 8,
	LIGHTINFO_SUN = 16,
};

struct FDynLightInfo
{
	float x;
	float y;
	float z;
	float padding0; // 4
	float r;
	float g;
	float b;
	float padding1; // 8
	float spotDirX;
	float spotDirY;
	float spotDirZ;
	float padding2; // 12
	float radius;
	float linearity;
	float softShadowRadius;
	float strength; // 16
	float spotInnerAngle;
	float spotOuterAngle;
	int shadowIndex;
	int flags; // 20
};

using FDynLightPackingSnapshot = HWLightPackingSnapshot<FDynLightInfo>;

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
	TArray<uint64_t> revisions[3];

	void Clear()
	{
		for (int i = 0; i < 3; ++i)
		{
			arrays[i].Clear();
			revisions[i].Clear();
		}
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

// PF-017: only top-level PF-010 render epochs may qualify source-owned packing
// reuse. Epoch rollback/wrap disables reuse fail-closed for the process.
uint64_t HWBeginDynLightPackingContext(uint64_t epoch);
void HWEndDynLightPackingContext(uint64_t epoch);
uint64_t HWActiveDynLightPackingContext();

class HWDynLightPackingContextScope
{
public:
	explicit HWDynLightPackingContextScope(uint64_t epoch)
		: mEpoch(HWBeginDynLightPackingContext(epoch))
	{
	}

	~HWDynLightPackingContextScope()
	{
		if (mEpoch != 0)
			HWEndDynLightPackingContext(mEpoch);
	}

	HWDynLightPackingContextScope(const HWDynLightPackingContextScope&) = delete;
	HWDynLightPackingContextScope& operator=(const HWDynLightPackingContextScope&) = delete;

	bool Qualified() const { return mEpoch != 0; }

private:
	uint64_t mEpoch = 0;
};

#endif
