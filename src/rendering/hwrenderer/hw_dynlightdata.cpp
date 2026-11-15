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
#include "hw_actor_shadowmask.h"
#include "hw_lightcompat.h"
#include"hw_cvars.h"
#include "v_video.h"
#include "hwrenderer/scene/hw_drawstructs.h"
#include "hwrenderer/doom_levelmesh.h"
#include "hw_renderstate.h"
#include "g_levellocals.h"
#include "d_player.h"
#include "r_utility.h"
#include "models.h"
#include "sprites.h"
#include "texturemanager.h"
#include "textures.h"
#include "image.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <iterator>
#include <limits>

// If we want to share the array to avoid constant allocations it needs to be thread local unless it'd be littered with expensive synchronization.
thread_local FDynLightData lightdata;

//==========================================================================
//
// Light related CVARs
//
//==========================================================================

// These shouldn't be called 'gl...' anymore...
CVAR (Bool, gl_light_sprites, true, CVAR_ARCHIVE | CVAR_GLOBALCONFIG);
CVAR (Bool, gl_light_particles, true, CVAR_ARCHIVE | CVAR_GLOBALCONFIG);

CVAR (Bool, gl_light_shadow_nearest_dither, true, CVAR_ARCHIVE | CVAR_GLOBALCONFIG);
// Opt-in during qualification; the owner-facing visual profile enables this.
CVAR (Bool, gl_actor_light_shadows, false, CVAR_ARCHIVE | CVAR_GLOBALCONFIG);



// Shadow sampling uses an independently filtered source *alpha* mask.
// It never changes the original sprite's texture/albedo or creates a decal.
// The light-facing sprite rotation and mirrored frame follow GetSpriteFrame.
extern TArray<spritedef_t> sprites;
extern uint32_t r_renderercaps;

namespace
{
struct ActorShadowCacheEntry
{
	const FDynamicLight* light = nullptr;
	uint64_t owner = 0;
	uint32_t generation = 0;
	int group = 0;
	uint64_t bufferEpoch = 0;
	double ticFrac = 0;
	int count = 0;
	int index = -1;
	const AActor* actors[MaxActorShadowCastersPerLight] = {};
};

struct ActorMaskCacheEntry
{
	// Source identity is scoped by the renderer's monotonic resource owner and
	// generation. No GPU texture or actor lifetime is extended by this cache.
	const FTexture* texture = nullptr;
	const FImageSource* image = nullptr;
	int imageId = -1;
	uint64_t owner = 0;
	uint32_t generation = 0;
	int width = 0, height = 0;
	unsigned alphaCutoff = 0;
	bool valid = false;
	uint32_t words[ActorShadowMaskWords] = {};
};

thread_local std::array<ActorShadowCacheEntry, 256> actorShadowCache;
thread_local size_t actorShadowCacheNext = 0;
thread_local std::array<ActorMaskCacheEntry, 64> actorMaskCache;
thread_local size_t actorMaskCacheNext = 0;

bool SourceAlphaMask(const FLevelLocals* level, FGameTexture* texture,
	uint32_t (&words)[ActorShadowMaskWords])
{
	FTexture* sourceTexture = texture ? texture->GetTexture() : nullptr;
	const FImageSource* image = sourceTexture ? sourceTexture->GetImage() : nullptr;
	// Canvas/procedural textures have no immutable image identity. Their
	// current GPU pixels cannot safely be represented by this CPU alpha cache.
	if (!sourceTexture || !image || sourceTexture->isCanvas() ||
		texture->isWarped() || texture->GetShaderIndex() >= FIRST_USER_SHADER)
		return false;
	const int width = sourceTexture->GetWidth(), height = sourceTexture->GetHeight();
	if (width <= 0 || width > 2048 || height <= 0 || height > 2048)
		return false;
	const uint64_t owner = level && level->levelMesh ? level->levelMesh->GetResourceOwner() : 0;
	const uint32_t generation = level && level->levelMesh ? level->levelMesh->GetResourceEpoch().Generation : 0;
	const float threshold = float(gl_mask_sprite_threshold);
	if (!std::isfinite(threshold)) return false;
	// Opaque sprite drawing uses Alpha_GEqual (threshold - .001). Source alpha
	// zero always remains clear, including when the draw threshold is zero.
	const unsigned alphaCutoff = unsigned(std::clamp(int(std::floor(
		std::clamp(threshold, 0.0f, 1.0f) * 255.0f - 0.255f)) + 1, 1, 255));
	if (owner != 0)
	{
		for (const auto& cached : actorMaskCache)
		{
			if (cached.texture == sourceTexture && cached.image == image &&
				cached.imageId == image->GetId() && cached.owner == owner &&
				cached.generation == generation && cached.width == width &&
				cached.height == height && cached.alphaCutoff == alphaCutoff)
			{
				if (cached.valid) std::copy(std::begin(cached.words), std::end(cached.words), words);
				return cached.valid;
			}
		}
	}

	ActorMaskCacheEntry entry;
	entry.texture = sourceTexture;
	entry.image = image;
	entry.imageId = image->GetId();
	entry.owner = owner;
	entry.generation = generation;
	entry.width = width;
	entry.height = height;
	entry.alphaCutoff = alphaCutoff;
	// Unexpanded source pixels pair with GetSpritePositioning(false) below.
	// Trimmed/expanded sprite UVs must not be stretched over this full image.
	auto source = sourceTexture->CreateTexBuffer(0);
	if (source.mWidth == width && source.mHeight == height)
		entry.valid = HWActorShadow::BuildAlphaMask(source.mBuffer, width, height,
			ActorShadowMaskWidth, ActorShadowMaskHeight, alphaCutoff,
			entry.words, ActorShadowMaskWords);
	if (owner != 0) actorMaskCache[actorMaskCacheNext++ % actorMaskCache.size()] = entry;
	if (entry.valid) std::copy(std::begin(entry.words), std::end(entry.words), words);
	return entry.valid;
}

bool ActorSilhouetteEligible(AActor* actor, double ticFrac)
{
	// Unsupported appearance types explicitly omit this new caster. The
	// existing material, legacy contact shadow and world shadow paths remain.
	if ((actor->renderflags & RF_SPRITETYPEMASK) != RF_FACESPRITE ||
		(actor->renderflags & (RF_INVISIBLE | RF_ROLLSPRITE | RF_MASKROTATION |
			RF_FORCEXYBILLBOARD | RF_NOSPRITESHADOW)) ||
		(actor->renderflags2 & (RF2_ISOMETRICSPRITES | RF2_ONLYVISIBLEINMIRRORS |
			RF2_INVISIBLEINMIRRORS)) ||
		actor->picnum.isValid() || !actor->IsVisibleToPlayer() ||
		(actor->RenderRequired & ~r_renderercaps) || (actor->RenderHidden & r_renderercaps))
		return false;
	const double alpha = actor->InterpolatedAlpha(ticFrac);
	if (!std::isfinite(alpha) || alpha < 1.0 || !actor->RenderStyle.IsVisible(alpha))
		return false;
	// Fuzz, additive and special blend modes do not have an opaque cutout
	// contract. Ordinary fully-opaque translucent actors are equivalent here.
	if (actor->RenderStyle != LegacyRenderStyles[STYLE_Normal] &&
		actor->RenderStyle != LegacyRenderStyles[STYLE_Translucent])
		return false;
	return true;
}

bool BuildActorSilhouette(FActorShadowCaster& caster, AActor* actor,
	const DVector3& origin, const DVector3& pos, const FLevelLocals* level,
	double ticFrac)
{
	int sprite = actor->sprite;
	DVector2 scale = actor->InterpolatedScale(ticFrac);
	if (actor->player) P_CheckPlayerSprite(actor, sprite, scale);
	if (sprite <= 0 || sprite >= int(sprites.Size()) ||
		FindModelFrame(actor, sprite, actor->frame, !!(actor->flags & MF_DROPPED)))
		return false;

	const DVector3 anchor = pos + actor->WorldOffset;
	const DVector2 toActor(anchor.X - origin.X, anchor.Y - origin.Y);
	const double distance = toActor.Length();
	if (distance < 1.0 || !std::isfinite(distance)) return false;
	bool mirror = false;
	const DAngle lightFacing = actor->GetSpriteAngle(toActor.Angle(), ticFrac);
	const FTextureID pic = sprites[sprite].GetSpriteFrame(actor->frame, -1,
		lightFacing, &mirror, !!(actor->renderflags & RF_SPRITEFLIP));
	if (!pic.isValid()) return false;
	FGameTexture* texture = TexMan.GetGameTexture(pic, false);
	if (!texture || !texture->isValid() || !texture->GetTexture()) return false;

	uint32_t alpha[ActorShadowMaskWords] = {};
	if (!SourceAlphaMask(level, texture, alpha)) return false;

	// Equivalent to GetSpritePositioning(false), without lazily allocating
	// sprite-positioning data from parallel light-list workers. This rectangle
	// describes the unexpanded full alpha; the visible trimmed quad encloses
	// precisely the same nontransparent source texels.
	const float texScaleX = texture->GetScaleX(), texScaleY = texture->GetScaleY();
	if (!std::isfinite(texScaleX) || !std::isfinite(texScaleY) ||
		texScaleX <= 0.0f || texScaleY <= 0.0f) return false;
	FloatRect rect = {
		-float(texture->GetTexelLeftOffset(r_spriteadjustHW)) / texScaleX,
		-float(texture->GetTexelTopOffset(r_spriteadjustHW)) / texScaleY,
		float(texture->GetTexelWidth()) / texScaleX,
		float(texture->GetTexelHeight()) / texScaleY
	};
	const float sx = float(scale.X), sy = float(scale.Y);
	if (!std::isfinite(sx) || !std::isfinite(sy) || sx <= 0.0f || sy <= 0.0f ||
		sx > 8.0f || sy > 8.0f)
		return false;
	const bool flipX = mirror ^ bool(actor->renderflags & RF_XFLIP) ^
		bool(actor->renderflags & RF_SPRITEFLIP);
	const bool flipY = !!(actor->renderflags & RF_YFLIP);
	if (flipX) rect.left = -rect.width - rect.left;
	rect.Scale(sx, sy);
	if ((actor->renderflags2 & RF2_SQUAREPIXELS) && !(actor->renderflags2 & RF2_STRETCHPIXELS))
	{
		const double pixelstretch = level->pixelstretch;
		if (!std::isfinite(pixelstretch) || pixelstretch <= 0) return false;
		const double mult = 1.0 / std::sqrt(pixelstretch);
		rect.Scale(mult * pixelstretch, mult);
	}
	const float offsetX = actor->GetSpriteOffset(false);
	const float offsetY = actor->GetSpriteOffset(true);
	const float spriteZ = float(anchor.Z - actor->Floorclip + actor->GetBobOffset(ticFrac));
	const float top = spriteZ - rect.top + offsetY;
	const float bottom = top - rect.height;
	const float left = -rect.left - rect.width + offsetX;
	const float right = -rect.left + offsetX;
	if (!std::isfinite(top) || !std::isfinite(bottom) || bottom >= top ||
		!std::isfinite(left) || !std::isfinite(right) || left >= right ||
		!std::isfinite(anchor.X) || !std::isfinite(anchor.Y))
		return false;

	caster.x = float(anchor.X);
	caster.y = spriteZ;
	caster.z = float(anchor.Y);
	caster.radius = float(actor->radius);
	caster.bottom = bottom;
	caster.top = top;
	caster.planeNx = float(toActor.X / distance);
	caster.planeNz = float(toActor.Y / distance);
	caster.left = left;
	caster.right = right;
	caster.mirrorX = flipX ? 1.0f : 0.0f;
	caster.mirrorY = flipY ? 1.0f : 0.0f;
	std::copy(std::begin(alpha), std::end(alpha), caster.alphaWords);
	return true;
}

void ApplyActorShadowCache(FDynLightInfo& info, const ActorShadowCacheEntry& entry,
	const AActor* receiver)
{
	if (entry.index < 0 || entry.count <= 0) return;
	info.actorShadowIndex = entry.index;
	info.actorShadowCount = entry.count;
	info.actorShadowMask = (1 << entry.count) - 1;
	for (int i = 0; receiver && i < entry.count; ++i)
	{
		// Identity exclusion prevents a camera-facing receiver sprite from
		// intersecting its own independently light-facing caster plane.
		if (entry.actors[i] == receiver) info.actorShadowMask &= ~(1 << i);
	}
}

void CollectActorShadowCasters(FDynLightInfo& info, FDynamicLight* light, int group,
	const AActor* receiver)
{
	if (!gl_actor_light_shadows || !light || !light->Level || !light->Sector ||
		light->Sector->PortalGroup != group || light->GetRadius() <= 0 ||
		light->GetRadius() >= HWLightCompat::SunProxyRadius)
		return;
	FRenderState* renderState = screen ? screen->RenderState() : nullptr;
	const uint64_t bufferEpoch = renderState ? renderState->GetActorShadowEpoch() : 0;
	if (!bufferEpoch || !light->Level->levelMesh) return;
	const uint64_t owner = light->Level->levelMesh->GetResourceOwner();
	const uint32_t generation = light->Level->levelMesh->GetResourceEpoch().Generation;
	// Use the authoritative main-root display fraction for every light/caster.
	// No camera position, orientation or portal-view billboard participates.
	const double ticFrac = std::clamp(r_viewpoint.TicFrac, 0.0, 1.0);
	for (const auto& cached : actorShadowCache)
	{
		if (cached.light == light && cached.owner == owner && cached.generation == generation &&
			cached.group == group && cached.bufferEpoch == bufferEpoch && cached.ticFrac == ticFrac)
		{
			ApplyActorShadowCache(info, cached, receiver);
			return;
		}
	}

	ActorShadowCacheEntry fresh;
	fresh.light = light;
	fresh.owner = owner;
	fresh.generation = generation;
	fresh.group = group;
	fresh.bufferEpoch = bufferEpoch;
	fresh.ticFrac = ticFrac;
	FActorShadowCaster casters[MaxActorShadowCastersPerLight] = {};
	float ranks[MaxActorShadowCastersPerLight];
	for (float& rank : ranks) rank = std::numeric_limits<float>::infinity();
	const DVector3 origin = light->PosRelative(group);
	const float reach = float(light->GetRadius());
	auto iter = light->Level->GetThinkerIterator<AActor>();
	for (AActor* candidate = iter.Next(); candidate != nullptr; candidate = iter.Next())
	{
		if (candidate == light->target || !candidate->Sector ||
			candidate->Sector->PortalGroup != group || !(candidate->flags & MF_SHOOTABLE) ||
			!ActorSilhouetteEligible(candidate, ticFrac))
			continue;
		const float radius = float(candidate->radius);
		const float height = float(candidate->Height);
		if (!std::isfinite(radius) || !std::isfinite(height) || radius <= 0.0f ||
			height <= 0.0f || radius > 128.0f || height > 512.0f)
			continue;
		// Only same-group actors are eligible, so no portal displacement is
		// needed. Interpolation and the image pose share the same time sample.
		const DVector3 pos = candidate->InterpolatedPosition(ticFrac);
		const DVector3 center = pos + candidate->WorldOffset + DVector3(0, 0, height * 0.5);
		const float dist2 = float((origin - center).LengthSquared());
		const float range = reach + radius;
		if (!(dist2 < range * range) || dist2 >= ranks[MaxActorShadowCastersPerLight - 1])
			continue;

		FActorShadowCaster caster = {};
		if (!BuildActorSilhouette(caster, candidate, origin, pos, light->Level, ticFrac)) continue;
		for (int i = 0; i < MaxActorShadowCastersPerLight; ++i)
		{
			if (dist2 < ranks[i])
			{
				for (int j = MaxActorShadowCastersPerLight - 1; j > i; --j)
				{
					ranks[j] = ranks[j - 1];
					casters[j] = casters[j - 1];
					fresh.actors[j] = fresh.actors[j - 1];
				}
				ranks[i] = dist2;
				casters[i] = caster;
				fresh.actors[i] = candidate;
				if (fresh.count < MaxActorShadowCastersPerLight) ++fresh.count;
				break;
			}
		}
	}
	if (fresh.count > 0) fresh.index = renderState->UploadActorShadowCasters(casters, fresh.count);
	actorShadowCache[actorShadowCacheNext++ % actorShadowCache.size()] = fresh;
	ApplyActorShadowCache(info, fresh, receiver);
}
} // namespace

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
void AddLightToList(FDynLightData &dld, int group, FDynamicLight * light, bool forceAttenuate, bool doTrace, AActor* receiver)
{
	FDynLightInfo info = {};

	int i = LIGHTARRAY_NORMAL;

	DVector3 pos = light->PosRelative(group);
	
	info.radius = light->GetRadius();

	float cs;
	if (light->IsAdditive()) 
	{
		cs = HWLightCompat::AdditiveGpuColorScale;
		i = LIGHTARRAY_ADDITIVE;
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
		i = LIGHTARRAY_SUBTRACTIVE;
	}

	if(light->shadowmapped && screen->mShadowMap->Enabled())
	{
		info.flags |= LIGHTINFO_SHADOWMAPPED;
		info.shadowIndex = light->mShadowmapIndex;
	}
	else
	{
		info.shadowIndex = 1024;
	}

	// Store attenuate flag in the sign bit of the float.
	if (light->IsAttenuated() || forceAttenuate)
	{
		info.flags |= LIGHTINFO_ATTENUATED;
	}

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

	if(light->Trace() && doTrace)
	{
		info.flags |= (LIGHTINFO_TRACE | LIGHTINFO_SHADOWMAPPED);
	}

	info.x = float(pos.X);
	info.z = float(pos.Y);
	info.y = float(pos.Z);

	info.softShadowRadius = (gl_light_shadow_filter == 0 && !gl_light_shadow_nearest_dither)? 0 : light->GetSoftShadowRadius();

	info.linearity = HWLightCompat::ClampLinearity(light->GetLinearity());

	info.strength = light->GetStrength();

	CollectActorShadowCasters(info, light, group, receiver);
	dld.arrays[i].Push(info);
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
}
