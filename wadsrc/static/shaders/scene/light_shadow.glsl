
// Check if light is in shadow

float ActorOccluderRayVisibility(vec3 lightPos, vec3 receiver, int casterIndex)
{
	// Light-to-receiver ray intersects the actual light-facing sprite plane.
	// Its binary coverage comes from the selected source frame alpha, not an
	// opaque collision cylinder or any composited world-space decal.
	vec3 center = actorShadowCasters[casterIndex].center;
	float bottom = actorShadowCasters[casterIndex].bottom;
	float top = actorShadowCasters[casterIndex].top;
	float left = actorShadowCasters[casterIndex].left;
	float right = actorShadowCasters[casterIndex].right;
	if (actorShadowCasters[casterIndex].radius <= 0.0 || bottom >= top || right <= left)
		return 1.0;
	vec3 ray = receiver - lightPos;
	vec2 n = vec2(actorShadowCasters[casterIndex].planeNx, actorShadowCasters[casterIndex].planeNz);
	float denom = dot(ray.xz, n);
	if (abs(denom) < 0.00001)
		return 1.0;
	float t = dot(center.xz - lightPos.xz, n) / denom;
	// World-space endpoint tolerance does not grow into a large peter-panning
	// gap for distant receivers. Sprite self-shadowing is excluded by identity.
	float endpointBias = min(0.01, 0.05 / max(length(ray), 0.0001));
	if (t <= endpointBias || t >= 1.0 - endpointBias)
		return 1.0; // caster must be strictly between light and receiver
	vec3 hit = lightPos + ray * t;
	vec2 tangent = vec2(-n.y, n.x);
	float horizontal = dot(hit.xz - center.xz, tangent);
	// HWSprite's leftfac vertex uses source U=1 for an unmirrored frame.
	// The rectangle and alpha are both unexpanded source-image coordinates.
	float u = (right - horizontal) / (right - left);
	float v = (hit.y - bottom) / (top - bottom);
	if (u < 0.0 || u >= 1.0 || v < 0.0 || v >= 1.0)
		return 1.0;
	if (actorShadowCasters[casterIndex].mirrorX > 0.5)
		u = 1.0 - u;
	if (actorShadowCasters[casterIndex].mirrorY > 0.5)
		v = 1.0 - v;
	const int width = 64;
	const int height = 128;
	int px = clamp(int(floor(u * float(width))), 0, width - 1);
	int py = clamp(int(floor((1.0 - v) * float(height))), 0, height - 1);
	int bit = py * width + px;
	return (actorShadowCasters[casterIndex].alphaWords[bit / 32] &
		(1u << uint(bit & 31))) != 0u ? 0.0 : 1.0;
}

float ActorLightShadowVisibility(DynLightInfo light)
{
	if (light.actorShadowCount <= 0 || light.actorShadowMask == 0 ||
		(light.flags & LIGHTINFO_SUN) != 0)
		return 1.0;
	int count = min(light.actorShadowCount, 4);
	// Validate the complete range before any SSBO access. Exhaustion simply
	// leaves this emitter on its existing world-shadow path.
	if (light.actorShadowIndex < 0 || light.actorShadowIndex >
		min(actorShadowCasters.length(), 4096) - count)
		return 1.0;
	for (int i = 0; i < count; ++i)
	{
		if ((light.actorShadowMask & (1 << i)) != 0 &&
			ActorOccluderRayVisibility(light.pos.xyz, SDVK_LIGHTING_POSITION,
				light.actorShadowIndex + i) < 0.5)
			return 0.0;
	}
	return 1.0;
}


#include <shaders/scene/light_trace.glsl> // needed always to do per-pixel tracing of lightmap lights for sprites


#define shadowAttenuationRaytrace(lightpos, shadowIndex, softShadowRadius, flags) traceShadow(lightpos, softShadowRadius)


float shadowDirToU(vec2 dir)
{
	if (abs(dir.y) > abs(dir.x))
	{
		float x = dir.x / dir.y * 0.125;
		if (dir.y >= 0.0)
			return 0.125 + x;
		else
			return (0.50 + 0.125) + x;
	}
	else
	{
		float y = dir.y / dir.x * 0.125;
		if (dir.x >= 0.0)
			return (0.25 + 0.125) - y;
		else
			return (0.75 + 0.125) - y;
	}
}

vec2 shadowUToDir(float u)
{
	u *= 4.0;
	vec2 raydir;
	switch (int(u))
	{
	case 0: raydir = vec2(u * 2.0 - 1.0, 1.0); break;
	case 1: raydir = vec2(1.0, 1.0 - (u - 1.0) * 2.0); break;
	case 2: raydir = vec2(1.0 - (u - 2.0) * 2.0, -1.0); break;
	case 3: raydir = vec2(-1.0, (u - 3.0) * 2.0 - 1.0); break;
	}
	return raydir;
}

float sampleShadowmap(vec3 planePoint, float v)
{
	float bias = 1.0;
	float negD = dot(vWorldNormal.xyz, planePoint);

	vec3 ray = planePoint;

	vec2 isize = textureSize(ShadowMap, 0);
	float scale = float(isize.x) * 0.25;

	// Snap to shadow map texel grid
	if (abs(ray.z) > abs(ray.x))
	{
		ray.y = ray.y / abs(ray.z);
		ray.x = ray.x / abs(ray.z);
		ray.x = (floor((ray.x + 1.0) * 0.5 * scale) + 0.5) / scale * 2.0 - 1.0;
		ray.z = sign(ray.z);
	}
	else
	{
		ray.y = ray.y / abs(ray.x);
		ray.z = ray.z / abs(ray.x);
		ray.z = (floor((ray.z + 1.0) * 0.5 * scale) + 0.5) / scale * 2.0 - 1.0;
		ray.x = sign(ray.x);
	}

	float t = negD / dot(vWorldNormal.xyz, ray) - bias;
	vec2 dir = ray.xz * t;

	float u = shadowDirToU(dir);
	float dist2 = dot(dir, dir);
	return step(dist2, texture(ShadowMap, vec2(u, v)).x);
}

float sampleShadowmapPCF(vec3 planePoint, float v)
{
	float bias = 1.0;
	float negD = dot(vWorldNormal.xyz, planePoint);

	vec3 ray = planePoint;

	if (abs(ray.z) > abs(ray.x))
		ray.y = ray.y / abs(ray.z);
	else
		ray.y = ray.y / abs(ray.x);

	vec2 isize = textureSize(ShadowMap, 0);
	float scale = float(isize.x);
	float texelPos = floor(shadowDirToU(ray.xz) * scale);

	float sum = 0.0;
	float step_count = SHADOWMAP_FILTER;

	texelPos -= step_count + 0.5;
	for (float x = -step_count; x <= step_count; x++)
	{
		float u = fract(texelPos / scale);
		vec2 dir = shadowUToDir(u);

		ray.x = dir.x;
		ray.z = dir.y;
		float t = negD / dot(vWorldNormal.xyz, ray) - bias;
		dir = ray.xz * t;

		float dist2 = dot(dir, dir);
		sum += step(dist2, texture(ShadowMap, vec2(u, v)).x);
		texelPos++;
	}
	return sum / (SHADOWMAP_FILTER * 2.0 + 1.0);
}

float shadowmapAttenuation(vec3 lightpos, float shadowIndex)
{
	vec3 planePoint = SDVK_LIGHTING_POSITION - lightpos.xyz;
	planePoint += 0.01; // nudge light position slightly as Doom maps tend to have their lights perfectly aligned with planes

	if (dot(planePoint.xz, planePoint.xz) < 1.0)
		return 1.0; // Light is too close

	float v = (shadowIndex + 0.5) / 1024.0;
	
	if (SHADOWMAP_FILTER == 0)
		return sampleShadowmap(planePoint, v);
	else
		return sampleShadowmapPCF(planePoint, v);
}

float shadowAttenuationShadowMap(vec3 lightpos, int shadowIndex, float softShadowRadius, int flags)
{
	if (shadowIndex >= 1024)
		return 1.0; // No shadowmap available for this light
	return shadowmapAttenuation(lightpos, float(shadowIndex));
}

float shadowAttenuation(vec3 lightpos, int shadowIndex, float softShadowRadius, int flags)
{
	if(USE_RAYTRACE || (flags & LIGHTINFO_TRACE) > 0)
	{
		return shadowAttenuationRaytrace(lightpos, shadowIndex, softShadowRadius, flags);
	}
	else if(USE_SHADOWMAP)
	{
		return shadowAttenuationShadowMap(lightpos, shadowIndex, softShadowRadius, flags);
	}
	else
	{
		return 1.0;
	}
}
