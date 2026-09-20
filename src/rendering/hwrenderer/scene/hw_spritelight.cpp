// 
//---------------------------------------------------------------------------
//
// Copyright(C) 2002-2016 Christoph Oelckers
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
** gl_light.cpp
** Light level / fog management / dynamic lights
**
*/

#include "c_dispatch.h"
#include "a_dynlight.h" 
#include "p_local.h"
#include "p_effect.h"
#include "g_level.h"
#include "g_levellocals.h"
#include "actorinlines.h"
#include "hw_drawcontext.h"
#include "hw_dynlightdata.h"
#include "hw_shadowmap.h"
#include "hw_visibilitycache.h"
#include "hwrenderer/scene/hw_drawinfo.h"
#include "hwrenderer/scene/hw_drawstructs.h"
#include "models.h"
#include "stats.h"
#include <atomic>
#include <chrono>
#include <cmath>	// needed for std::floor on mac
#include <vector>
#include "hw_cvars.h"

namespace
{
std::atomic<uint64_t> TraceCacheHits { 0 };
std::atomic<uint64_t> TraceCacheMisses { 0 };
std::atomic<uint64_t> TraceCacheActorInvalidations { 0 };
std::atomic<uint64_t> TraceCacheWorldInvalidations { 0 };
std::atomic<uint64_t> TraceCachePortalInvalidations { 0 };
std::atomic<uint64_t> TraceCacheLightInvalidations { 0 };
std::atomic<uint64_t> SunTraceCacheHits { 0 };
std::atomic<uint64_t> SunTraceCacheMisses { 0 };
std::atomic<uint64_t> LightQueryBaselineQueries { 0 };
std::atomic<uint64_t> LightQueryLocalQueries { 0 };
std::atomic<uint64_t> LightQueryQualificationPasses { 0 };
std::atomic<uint64_t> LightQueryQualificationFallbacks { 0 };
std::atomic<uint64_t> LightQueryVisitedSections { 0 };
std::atomic<uint64_t> LightQueryCandidates { 0 };
std::atomic<uint64_t> LightQueryDuplicates { 0 };
std::atomic<uint64_t> LightQueryFiltered { 0 };
std::atomic<uint64_t> LightQueryTraces { 0 };
std::atomic<uint64_t> LightQueryBaselineNanos { 0 };
std::atomic<uint64_t> LightQueryLocalNanos { 0 };
std::atomic<uint64_t> LightQueryQualificationNanos { 0 };

uint64_t CurrentWorldQueryEpoch()
{
	return level.levelMesh ? level.levelMesh->GetMutationEpochs().Query : 0;
}

struct LightQuerySelection
{
	FDynamicLight* Light = nullptr;
	int Group = 0;
	int Class = LIGHTARRAY_NORMAL;

	bool operator==(const LightQuerySelection& other) const
	{
		return Light == other.Light && Group == other.Group && Class == other.Class;
	}
};

int LightQueryClass(FDynamicLight* light)
{
	if (light->IsSubtractive()) return LIGHTARRAY_SUBTRACTIVE;
	if (light->IsAdditive()) return LIGHTARRAY_ADDITIVE;
	return LIGHTARRAY_NORMAL;
}
}

template<class T>
T smoothstep(const T edge0, const T edge1, const T x)
{
	auto t = clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0);
	return t * t * (3.0 - 2.0 * t);
}

class ActorTraceStaticLight
{
public:
	ActorTraceStaticLight(AActor* actor, int portalGroup) : Actor(actor), CachePortalGroup(portalGroup)
	{
		if (!Actor)
			return;

		const bool positionChanged = Actor->Pos() != Actor->StaticLightsTraceCache.Pos ||
			(Actor->Sector && (Actor->Sector->Flags & SECF_LM_DYNAMIC) && lm_dynamic);
		const uint64_t queryEpoch = CurrentWorldQueryEpoch();
		BaseValidity = HWCheckVisibilityCacheValidity(positionChanged,
			Actor->StaticLightsTraceCache.QueryEpoch, queryEpoch,
			Actor->StaticLightsTraceCache.PortalGroup, CachePortalGroup, false);

		if (!BaseValidity.CanReuse())
		{
			Actor->StaticLightsTraceCache.Pos = Actor->Pos();
			Actor->StaticLightsTraceCache.SunResult = false;
			Actor->StaticLightsTraceCache.QueryEpoch = queryEpoch;
			Actor->StaticLightsTraceCache.PortalGroup = CachePortalGroup;
			ActorMoved = true;
		}
	}

	bool TraceLightVisbility(FLightNode* node, const FVector3& L, float dist, bool ignoreCache)
	{
		FDynamicLight* light = node->lightsource;
		if (!light->TraceActors() || !level.levelMesh || !Actor)
			return true;

		unsigned index = light->ActorList.SortedFind(Actor, false);
		auto validity = BaseValidity;
		validity.LightStateChanged = ignoreCache;
		const bool hasEntry = index < light->ActorList.Size() && light->ActorList[index] == Actor;

		if (validity.CanReuse() && hasEntry)
		{
			TraceCacheHits.fetch_add(1, std::memory_order_relaxed);
			return light->ActorResult[index];
		}

		TraceCacheMisses.fetch_add(1, std::memory_order_relaxed);
		if (validity.ActorPositionChanged) TraceCacheActorInvalidations.fetch_add(1, std::memory_order_relaxed);
		if (validity.WorldQueryChanged) TraceCacheWorldInvalidations.fetch_add(1, std::memory_order_relaxed);
		if (validity.PortalContextChanged) TraceCachePortalInvalidations.fetch_add(1, std::memory_order_relaxed);
		if (validity.LightStateChanged) TraceCacheLightInvalidations.fetch_add(1, std::memory_order_relaxed);

		bool traceResult = !level.levelMesh->Trace(FVector3((float)light->Pos.X, (float)light->Pos.Y, (float)light->Pos.Z), FVector3(-L.X, -L.Y, -L.Z), dist);
		if (!hasEntry)
		{
			light->ActorList.Insert(index, Actor);
			light->ActorResult.Insert(index, traceResult);
		}
		else
		{
			light->ActorResult[index] = traceResult;
		}
		return traceResult;
	}

	static bool TraceSunVisibility(float x, float y, float z, sun_trace_cache_t *cache, bool moved)
	{
		if (!level.lightmaps || !cache)
			return false;

		const uint64_t queryEpoch = CurrentWorldQueryEpoch();
		const bool worldQueryChanged = cache->QueryEpoch != queryEpoch;
		if (!moved && !worldQueryChanged)
		{
			SunTraceCacheHits.fetch_add(1, std::memory_order_relaxed);
			return cache->SunResult;
		}

		SunTraceCacheMisses.fetch_add(1, std::memory_order_relaxed);
		bool traceResult = level.levelMesh->TraceSky(FVector3(x, y, z), level.SunDirection, 65536.0f);
		cache->SunResult = traceResult;
		cache->QueryEpoch = queryEpoch;
		return traceResult;
	}

	AActor* Actor;
	int CachePortalGroup = 0;
	bool ActorMoved = false;
	HWVisibilityCacheValidity BaseValidity;
};

//==========================================================================
//
// Sets a single light value from all dynamic lights affecting the specified location
//
//==========================================================================

static float mix(float a, float b, float t)
{
	return a * (1.0f - t) + t * b;
}

float inverseSquareAttenuation(float dist, float radius, float strength, float linearity)
{
	float a = dist / radius;
	float b = clamp(1.0f - a * a * a * a, 0.0f, 1.0f);
	return mix(((b * b) / (dist * dist + 1.0f) * strength), clamp((radius - dist) / radius, 0.0f, 1.0f), linearity);
}

void HWDrawInfo::GetDynSpriteLight(AActor *self, sun_trace_cache_t * traceCache, double x, double y, double z, FLightNode *node, int portalgroup, float *out, bool fullbright)
{
	if (fullbright || get_gl_spritelight() > 0)
		return;

	FDynamicLight *light;
	float frac, lr, lg, lb;
	float radius;
	
	out[0] = out[1] = out[2] = 0.f;

	ActorTraceStaticLight staticLight(self, portalgroup);

	if (ActorTraceStaticLight::TraceSunVisibility(x, y, z, traceCache, (self ? staticLight.ActorMoved : traceCache ? traceCache->Pos != DVector3(x, y, z) : false)))
	{
		if(!self && traceCache)
		{
			traceCache->Pos = DVector3(x, y, z);
		}

		out[0] = Level->SunColor.X * Level->SunIntensity;
		out[1] = Level->SunColor.Y * Level->SunIntensity;
		out[2] = Level->SunColor.Z * Level->SunIntensity;
	}

	// Go through both light lists
	while (node)
	{
		light=node->lightsource;
		if (light->ShouldLightActor(self))
		{
			float dist;
			FVector3 L;

			// This is a performance critical section of code where we cannot afford to let the compiler decide whether to inline the function or not.
			// This will do the calculations explicitly rather than calling one of AActor's utility functions.
			if (Level->Displacements.size > 0)
			{
				int fromgroup = light->Sector->PortalGroup;
				int togroup = portalgroup;
				if (fromgroup == togroup || fromgroup == 0 || togroup == 0) goto direct;

				DVector2 offset = Level->Displacements.getOffset(fromgroup, togroup);
				L = FVector3(x - (float)(light->X() + offset.X), y - (float)(light->Y() + offset.Y), z - (float)light->Z());
			}
			else
			{
			direct:
				L = FVector3(x - (float)light->X(), y - (float)light->Y(), z - (float)light->Z());
			}

			dist = (float)L.LengthSquared();
			radius = light->GetRadius();

			if (radius > 0 && dist < radius * radius)
			{
				dist = sqrtf(dist);	// only calculate the square root if we really need it.

				if (light->IsSpot() || light->TraceActors())
					L *= -1.0f / dist;

				if (staticLight.TraceLightVisbility(node, L, dist, light->updated))
				{
					if(level.info->lightattenuationmode == ELightAttenuationMode::INVERSE_SQUARE)
					{
						frac = (inverseSquareAttenuation(std::max(dist, sqrt(radius) * 2), radius, light->GetStrength(), light->GetLinearity()));
					}
					else
					{
						frac = 1.0f - (dist / radius);
					}

					if (light->IsSpot())
					{
						DAngle negPitch = -*light->pPitch;
						DAngle Angle = light->target->Angles.Yaw;
						double xyLen = negPitch.Cos();
						double spotDirX = -Angle.Cos() * xyLen;
						double spotDirY = -Angle.Sin() * xyLen;
						double spotDirZ = -negPitch.Sin();
						double cosDir = L.X * spotDirX + L.Y * spotDirY + L.Z * spotDirZ;
						frac *= (float)smoothstep(light->pSpotOuterAngle->Cos(), light->pSpotInnerAngle->Cos(), cosDir);
					}

					if (frac > 0 && (!light->shadowmapped || (self && light->TraceActors()) || screen->mShadowMap->ShadowTest(light->Pos, { x, y, z })))
					{
						lr = light->GetRed() / 255.0f;
						lg = light->GetGreen() / 255.0f;
						lb = light->GetBlue() / 255.0f;

						if (light->target && (light->target->renderflags2 & RF2_LIGHTMULTALPHA))
						{
							float alpha = (float)light->target->Alpha;
							lr *= alpha;
							lg *= alpha;
							lb *= alpha;
						}

						// Get GLDEFS intensity
						lr *= light->GetLightDefIntensity();
						lg *= light->GetLightDefIntensity();
						lb *= light->GetLightDefIntensity();

						if (light->IsSubtractive())
						{
							float bright = (float)FVector3(lr, lg, lb).Length();
							FVector3 lightColor(lr, lg, lb);
							lr = (bright - lr) * -1;
							lg = (bright - lg) * -1;
							lb = (bright - lb) * -1;
						}

						out[0] += lr * frac;
						out[1] += lg * frac;
						out[2] += lb * frac;
					}
				}
			}
		}
		node = node->nextLight;
	}
}

void HWDrawInfo::GetDynSpriteLight(AActor *thing, particle_t *particle, sun_trace_cache_t * traceCache, float *out)
{
	if (thing)
	{
		GetDynSpriteLight(thing, &thing->StaticLightsTraceCache, thing->X(), thing->Y(), thing->Center(), thing->section->lighthead, thing->Sector->PortalGroup, out, (thing->flags5 & MF5_BRIGHT));
	}
	else if (particle)
	{
		GetDynSpriteLight(nullptr, traceCache, particle->Pos.X, particle->Pos.Y, particle->Pos.Z, particle->subsector->section->lighthead, particle->subsector->sector->PortalGroup, out, (particle->flags & SPF_FULLBRIGHT));
	}
}


void HWDrawInfo::GetDynSpriteLightList(AActor *self, double x, double y, double z, sun_trace_cache_t * traceCache, FDynLightData &modellightdata, bool isModel)
{
	modellightdata.Clear();

	if (self && (self->flags5 & MF5_BRIGHT))
		return;

	float actorradius = self ? (float)self->RenderRadius() : 1;
	float radiusSquared = actorradius * actorradius;
	dl_validcount++;

	const int actorPortalGroup = self && self->Sector ? self->Sector->PortalGroup : 0;
	ActorTraceStaticLight staticLight(self, actorPortalGroup);

	int gl_spritelight = get_gl_spritelight();

	if(isModel && gl_fakemodellight)
	{
		//fake light for contrast
		AddSunLightToList(modellightdata, x, y, z, FVector3(Level->SunDirection.X + 180, 45, 0), Level->SunColor * Level->SunIntensity * gl_fakemodellightintensity, false);
	}

	if ((level.lightmaps && gl_spritelight > 0) || ActorTraceStaticLight::TraceSunVisibility(x, y, z, traceCache, (self ? staticLight.ActorMoved : traceCache ? traceCache->Pos != DVector3(x, y, z) : false)))
	{
		AddSunLightToList(modellightdata, x, y, z, Level->SunDirection, Level->SunColor * Level->SunIntensity, gl_spritelight > 0);
	}

	// PF-016: both candidate sources feed exactly the same filter/portal/trace
	// pipeline. The generation set preserves first-encounter order without the
	// old SortedFind + insertion maintenance cost.
	drawctx->lightQuerySeen.BeginQuery();
	uint64_t visitedSections = 0;
	uint64_t candidates = 0;
	uint64_t duplicates = 0;
	uint64_t filtered = 0;
	uint64_t traces = 0;

	auto processLightList = [&](FLightNode *node, int group, HWGenerationSet<FDynamicLight*>& seen,
		FDynLightData* output, std::vector<LightQuerySelection>* selections, bool countDiagnostics)
	{
		if (countDiagnostics) ++visitedSections;
		while (node)
		{
			FDynamicLight *light = node->lightsource;
			if (countDiagnostics) ++candidates;
			if (!light->ShouldLightActor(self))
			{
				if (countDiagnostics) ++filtered;
				node = node->nextLight;
				continue;
			}

			DVector3 pos = light->PosRelative(group);
			float radius = (float)(light->GetRadius() + actorradius);
			double dx = pos.X - x;
			double dy = pos.Y - y;
			double dz = pos.Z - z;
			double distSquared = dx * dx + dy * dy + dz * dz;
			if (distSquared >= radius * radius)
			{
				if (countDiagnostics) ++filtered;
				node = node->nextLight;
				continue;
			}

			if (!seen.MarkFirst(light))
			{
				if (countDiagnostics) ++duplicates;
				node = node->nextLight;
				continue;
			}

			FVector3 L(dx, dy, dz);
			float dist = sqrtf((float)distSquared);
			const bool needsTrace = gl_spritelight == 0 && light->TraceActors();
			if (needsTrace)
			{
				L *= 1.0f / dist;
				if (countDiagnostics) ++traces;
			}

			if (gl_spritelight > 0 || staticLight.TraceLightVisbility(node, L, dist, light->updated))
			{
				if (selections)
					selections->push_back({ light, group, LightQueryClass(light) });
				if (output)
					AddLightToList(*output, group, light, true, gl_spritelight > 0);
			}
			else if (countDiagnostics)
			{
				++filtered;
			}

			node = node->nextLight;
		}
	};

	const DVector3 queryPos(x, y, z);
	const bool qualificationMatches = self && traceCache && self->section &&
		traceCache->LocalQueryKnown && traceCache->LocalQueryPos == queryPos &&
		traceCache->LocalQuerySection == self->section &&
		traceCache->LocalQueryRadius == actorradius &&
		traceCache->LocalQueryPortalGroup == actorPortalGroup;
	const bool useLocalSection = qualificationMatches && traceCache->LocalQueryExact;
	const auto queryStart = std::chrono::steady_clock::now();

	if (useLocalSection)
	{
		LightQueryLocalQueries.fetch_add(1, std::memory_order_relaxed);
		processLightList(self->section->lighthead, actorPortalGroup, drawctx->lightQuerySeen, &modellightdata, nullptr, true);
		const uint64_t elapsed = (uint64_t)std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now() - queryStart).count();
		LightQueryLocalNanos.fetch_add(elapsed, std::memory_order_relaxed);
	}
	else
	{
		LightQueryBaselineQueries.fetch_add(1, std::memory_order_relaxed);
		bool localGeometryExact = self && traceCache && self->section;
		bool sawSubsector = false;
		std::vector<LightQuerySelection> baselineSelections;

		BSPWalkCircle(Level, x, y, radiusSquared, [&](subsector_t *subsector)
		{
			sawSubsector = true;
			auto section = subsector->section;
			const int group = subsector->sector->PortalGroup;
			if (localGeometryExact && (section != self->section || group != actorPortalGroup))
				localGeometryExact = false;

			// The legacy validcount guard is intentionally retained. Candidate
			// identity de-duplication is independently generation-stamped below.
			if (section->validcount == dl_validcount) return;
			processLightList(section->lighthead, group, drawctx->lightQuerySeen, &modellightdata,
				self && traceCache && self->section ? &baselineSelections : nullptr, true);
		});

		const uint64_t baselineElapsed = (uint64_t)std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now() - queryStart).count();
		LightQueryBaselineNanos.fetch_add(baselineElapsed, std::memory_order_relaxed);

		if (self && traceCache && self->section)
		{
			bool localSelectionExact = false;
			if (localGeometryExact && sawSubsector)
			{
				const auto qualificationStart = std::chrono::steady_clock::now();
				HWGenerationSet<FDynamicLight*> comparisonSeen;
				comparisonSeen.BeginQuery();
				std::vector<LightQuerySelection> localSelections;
				processLightList(self->section->lighthead, actorPortalGroup, comparisonSeen, nullptr, &localSelections, false);
				localSelectionExact = baselineSelections == localSelections;
				const uint64_t qualificationElapsed = (uint64_t)std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now() - qualificationStart).count();
				LightQueryQualificationNanos.fetch_add(qualificationElapsed, std::memory_order_relaxed);
			}

			if (localSelectionExact)
				LightQueryQualificationPasses.fetch_add(1, std::memory_order_relaxed);
			else
				LightQueryQualificationFallbacks.fetch_add(1, std::memory_order_relaxed);

			traceCache->LocalQueryPos = queryPos;
			traceCache->LocalQuerySection = self->section;
			traceCache->LocalQueryRadius = actorradius;
			traceCache->LocalQueryPortalGroup = actorPortalGroup;
			traceCache->LocalQueryKnown = true;
			traceCache->LocalQueryExact = localSelectionExact;
		}
	}

	LightQueryVisitedSections.fetch_add(visitedSections, std::memory_order_relaxed);
	LightQueryCandidates.fetch_add(candidates, std::memory_order_relaxed);
	LightQueryDuplicates.fetch_add(duplicates, std::memory_order_relaxed);
	LightQueryFiltered.fetch_add(filtered, std::memory_order_relaxed);
	LightQueryTraces.fetch_add(traces, std::memory_order_relaxed);
}

void HWDrawInfo::GetDynSpriteLightList(AActor *thing, particle_t *particle, sun_trace_cache_t * traceCache, FDynLightData &modellightdata, bool isModel)
{
	if (thing)
	{
		GetDynSpriteLightList(thing, thing->X(), thing->Y(), thing->Center(), &thing->StaticLightsTraceCache, modellightdata, isModel);
	}
	else if (particle)
	{
		if(particle->flags & SPF_FULLBRIGHT) return;
		GetDynSpriteLightList(nullptr, particle->Pos.X, particle->Pos.Y, particle->Pos.Z, traceCache, modellightdata, isModel);
	}
}

ADD_STAT(actorlightcache)
{
	FString out;
	out.Format("hits=%llu misses=%llu actor=%llu world=%llu portal=%llu light=%llu sunhits=%llu sunmisses=%llu",
		(unsigned long long)TraceCacheHits.load(std::memory_order_relaxed),
		(unsigned long long)TraceCacheMisses.load(std::memory_order_relaxed),
		(unsigned long long)TraceCacheActorInvalidations.load(std::memory_order_relaxed),
		(unsigned long long)TraceCacheWorldInvalidations.load(std::memory_order_relaxed),
		(unsigned long long)TraceCachePortalInvalidations.load(std::memory_order_relaxed),
		(unsigned long long)TraceCacheLightInvalidations.load(std::memory_order_relaxed),
		(unsigned long long)SunTraceCacheHits.load(std::memory_order_relaxed),
		(unsigned long long)SunTraceCacheMisses.load(std::memory_order_relaxed));
	return out;
}

ADD_STAT(actorlightquery)
{
	FString out;
	out.Format("baseline=%llu local=%llu qualify_ok=%llu qualify_fallback=%llu sections=%llu candidates=%llu dup=%llu filtered=%llu traces=%llu baseline_ns=%llu local_ns=%llu qualify_ns=%llu",
		(unsigned long long)LightQueryBaselineQueries.load(std::memory_order_relaxed),
		(unsigned long long)LightQueryLocalQueries.load(std::memory_order_relaxed),
		(unsigned long long)LightQueryQualificationPasses.load(std::memory_order_relaxed),
		(unsigned long long)LightQueryQualificationFallbacks.load(std::memory_order_relaxed),
		(unsigned long long)LightQueryVisitedSections.load(std::memory_order_relaxed),
		(unsigned long long)LightQueryCandidates.load(std::memory_order_relaxed),
		(unsigned long long)LightQueryDuplicates.load(std::memory_order_relaxed),
		(unsigned long long)LightQueryFiltered.load(std::memory_order_relaxed),
		(unsigned long long)LightQueryTraces.load(std::memory_order_relaxed),
		(unsigned long long)LightQueryBaselineNanos.load(std::memory_order_relaxed),
		(unsigned long long)LightQueryLocalNanos.load(std::memory_order_relaxed),
		(unsigned long long)LightQueryQualificationNanos.load(std::memory_order_relaxed));
	return out;
}
