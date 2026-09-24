// 
//---------------------------------------------------------------------------
//
// Copyright(C) 2002-2018 Christoph Oelckers
// All rights reserved.
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Lesser General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
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
/*
** gl_dynlight1.cpp
** dynamic light application
**
**/

#include "actorinlines.h"
#include "a_dynlight.h"
#include "hw_dynlightdata.h"
#include "hw_lightcompat.h"
#include"hw_cvars.h"
#include "v_video.h"
#include "hwrenderer/scene/hw_drawstructs.h"
#include "g_levellocals.h"

#include <atomic>
#include <limits>
#include <type_traits>

// If we want to share the array to avoid constant allocations it needs to be thread local unless it'd be littered with expensive synchronization.
thread_local FDynLightData lightdata;

namespace
{
static_assert(sizeof(FDynLightInfo) == 80, "PF-017 packing snapshots require the accepted 80-byte FDynLightInfo layout");
static_assert(std::is_trivially_copyable<FDynLightInfo>::value, "PF-017 snapshots require trivially copyable packed light records");

thread_local HWLightPackingContextState DynLightPackingContext;

class HWAtomicLightPackingRevisionClock
{
public:
	uint64_t Allocate()
	{
		if (mDisabled.load(std::memory_order_relaxed))
			return 0;

		uint64_t current = mNextRevision.load(std::memory_order_relaxed);
		for (;;)
		{
			if (current == 0 || current == std::numeric_limits<uint64_t>::max())
			{
				mDisabled.store(true, std::memory_order_release);
				return 0;
			}

			if (mNextRevision.compare_exchange_weak(
				current, current + 1,
				std::memory_order_relaxed,
				std::memory_order_relaxed))
			{
				return current;
			}

			if (mDisabled.load(std::memory_order_acquire))
				return 0;
		}
	}

private:
	std::atomic<uint64_t> mNextRevision{ 1 };
	std::atomic<bool> mDisabled{ false };
};

HWAtomicLightPackingRevisionClock DynLightPackingRevisionClock;

int PackLightInfo(FDynLightInfo& info, int group, FDynamicLight* light, bool forceAttenuate, bool doTrace)
{
	info = {};

	int lightClass = LIGHTARRAY_NORMAL;
	DVector3 pos = light->PosRelative(group);

	info.radius = light->GetRadius();

	float cs;
	if (light->IsAdditive())
	{
		cs = HWLightCompat::AdditiveGpuColorScale;
		lightClass = LIGHTARRAY_ADDITIVE;
	}
	else
	{
		cs = 1.0f;
	}

	if (light->target && (light->target->renderflags2 & RF2_LIGHTMULTALPHA))
		cs *= (float)light->target->Alpha;

	// Multiply intensity from GLDEFS
	cs *= (float)light->GetLightDefIntensity();

	info.r = HWLightCompat::NormalizeColorChannel(light->GetRed()) * cs;
	info.g = HWLightCompat::NormalizeColorChannel(light->GetGreen()) * cs;
	info.b = HWLightCompat::NormalizeColorChannel(light->GetBlue()) * cs;

	if (light->IsSubtractive())
	{
		DVector3 v(info.r, info.g, info.b);
		float length = (float)v.Length();

		info.r = length - info.r;
		info.g = length - info.g;
		info.b = length - info.b;
		lightClass = LIGHTARRAY_SUBTRACTIVE;
	}

	if (light->shadowmapped && screen->mShadowMap->Enabled())
	{
		info.flags |= LIGHTINFO_SHADOWMAPPED;
		info.shadowIndex = light->mShadowmapIndex;
	}
	else
	{
		info.shadowIndex = 1024;
	}

	if (light->IsAttenuated() || forceAttenuate)
		info.flags |= LIGHTINFO_ATTENUATED;

	if (light->IsSpot())
	{
		info.flags |= LIGHTINFO_SPOT;

		info.spotInnerAngle = (float)light->pSpotInnerAngle->Cos();
		info.spotOuterAngle = (float)light->pSpotOuterAngle->Cos();

		DAngle negPitch = -*light->pPitch;
		DAngle Angle = light->target->Angles.Yaw;
		double xzLen = negPitch.Cos();
		info.spotDirX = float(-Angle.Cos() * xzLen);
		info.spotDirY = float(-negPitch.Sin());
		info.spotDirZ = float(-Angle.Sin() * xzLen);
	}

	if (light->Trace() && doTrace)
		info.flags |= (LIGHTINFO_TRACE | LIGHTINFO_SHADOWMAPPED);

	info.x = float(pos.X);
	info.z = float(pos.Y);
	info.y = float(pos.Z);

	info.softShadowRadius = (gl_light_shadow_filter == 0 && !gl_light_shadow_nearest_dither) ? 0 : light->GetSoftShadowRadius();
	info.linearity = HWLightCompat::ClampLinearity(light->GetLinearity());
	info.strength = light->GetStrength();

	return lightClass;
}

bool QualifiesForPackingReuse(int group, FDynamicLight* light, uint64_t contextEpoch)
{
	if (contextEpoch == 0 || light->IsSpot())
		return false;

	if (light->target && (light->target->renderflags2 & RF2_LIGHTMULTALPHA))
		return false;

	// Foreign portal groups alter packed position. Keep those on the accepted
	// path rather than trying to make a source-owned snapshot multi-space.
	if (!light->Sector || group != light->Sector->PortalGroup)
		return false;

	return true;
}
}

uint64_t HWBeginDynLightPackingContext(uint64_t epoch)
{
	return DynLightPackingContext.Begin(epoch);
}

void HWEndDynLightPackingContext(uint64_t epoch)
{
	DynLightPackingContext.End(epoch);
}

uint64_t HWActiveDynLightPackingContext()
{
	return DynLightPackingContext.ActiveEpoch();
}

//==========================================================================
//
// Light related CVARs
//
//==========================================================================

// These shouldn't be called 'gl...' anymore...
CVAR (Bool, gl_light_sprites, true, CVAR_ARCHIVE | CVAR_GLOBALCONFIG);
CVAR (Bool, gl_light_particles, true, CVAR_ARCHIVE | CVAR_GLOBALCONFIG);

CVAR (Bool, gl_light_shadow_nearest_dither, true, CVAR_ARCHIVE | CVAR_GLOBALCONFIG);


//==========================================================================
//
// Sets up the parameters to render one dynamic light onto one plane
//
//==========================================================================
bool GetLight(FDynLightData& dld, int group, Plane & p, FDynamicLight * light, bool checkside)
{
	DVector3 pos = light->PosRelative(group);
	float radius = (light->GetRadius());

	auto dist = fabs(p.DistToPoint((float)pos.X, (float)pos.Z, (float)pos.Y));

	if (radius <= 0.f) return false;
	if (dist > radius) return false;
	if (checkside && p.PointOnSide((float)pos.X, (float)pos.Z, (float)pos.Y))
	{
		return false;
	}

	AddLightToList(dld, group, light, false, false);
	return true;
}

//==========================================================================
//
// Add one dynamic light to the light data list
//
//==========================================================================
void AddLightToList(FDynLightData &dld, int group, FDynamicLight * light, bool forceAttenuate, bool doTrace)
{
	FDynLightInfo info = {};
	int lightClass = LIGHTARRAY_NORMAL;
	uint64_t revision = 0;

	const uint64_t contextEpoch = HWActiveDynLightPackingContext();
	const bool qualified = QualifiesForPackingReuse(group, light, contextEpoch);
	const unsigned snapshotIndex = (forceAttenuate ? 1u : 0u) | (doTrace ? 2u : 0u);

	if (qualified && HWTryReuseLightPackingSnapshot(
		light->packingSnapshots[snapshotIndex],
		contextEpoch,
		group,
		info,
		lightClass,
		revision))
	{
		dld.arrays[lightClass].Push(info);
		dld.revisions[lightClass].Push(revision);
		return;
	}

	lightClass = PackLightInfo(info, group, light, forceAttenuate, doTrace);

	if (qualified)
	{
		revision = HWCommitLightPackingSnapshot(
			light->packingSnapshots[snapshotIndex],
			info,
			lightClass,
			group,
			contextEpoch,
			DynLightPackingRevisionClock);
	}

	dld.arrays[lightClass].Push(info);
	dld.revisions[lightClass].Push(revision);
}

void AddSunLightToList(FDynLightData& dld, float x, float y, float z, const FVector3& sundir, const FVector3& suncolor, bool doTrace)
{
	FDynLightInfo info = {};

	// Cheap way of faking a directional light. These are compatibility proxy
	// values rather than photometric units; PF-011 owns their documented meaning.
	float dist = HWLightCompat::SunProxyDistance;
	info.radius = HWLightCompat::SunProxyRadius;
	info.x = x + sundir.X * dist;
	info.z = y + sundir.Y * dist;
	info.y = z + sundir.Z * dist;
	info.r = suncolor.X;
	info.g = suncolor.Y;
	info.b = suncolor.Z;
	info.flags = LIGHTINFO_ATTENUATED | (doTrace ? (LIGHTINFO_TRACE | LIGHTINFO_SUN) : 0);
	info.strength = HWLightCompat::SunProxyStrength;

	dld.arrays[LIGHTARRAY_NORMAL].Push(info);
	dld.revisions[LIGHTARRAY_NORMAL].Push(0);
}
