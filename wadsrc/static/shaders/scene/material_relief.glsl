// SDVK-008: bounded, opt-in sprite-only shallow parallax occlusion mapping.
// Uses the *accepted* SDVK-007 final-quad world tangent and UV handedness.
// Do not treat this as geometry, sprite shadows, or changes to fragment depth.
#ifndef SDVK_SPRITE_RELIEF_GLSL
#define SDVK_SPRITE_RELIEF_GLSL

bool SDVKFinite(float v) { return !isnan(v) && !isinf(v); }
bool SDVKFinite(vec2 v) { return all(not(isnan(v))) && all(not(isinf(v))); }
bool SDVKFinite(vec3 v) { return all(not(isnan(v))) && all(not(isinf(v))); }
bool SDVKInsideReliefRect(vec2 uv, vec2 lo, vec2 hi)
{
	return all(greaterThanEqual(uv, lo)) && all(lessThanEqual(uv, hi));
}

// Returns the original coordinate for every unsupported or invalid case.
// The inherited material sampler is still the only source for final color.
vec2 SDVKResolveSpriteReliefUV(vec2 original, out bool applied)
{
	applied = false;
#if !defined(NO_LAYERS) && (defined(SHADERTYPE_DEFAULT) || defined(SHADERTYPE_SPECULAR) || defined(SHADERTYPE_PBR))
	// Implicit derivatives must be evaluated before nonuniform shader branches.
	vec2 uvDx = dFdx(original);
	vec2 uvDy = dFdy(original);
	float scale = uSpriteReliefParams.x;
	int quality = int(uSpriteReliefParams.y + 0.5);
	if (uSpriteReliefParams.w < 0.5 || uSpriteNormal.w < 0.5 ||
		uHeightTextureIndex < 0 || quality < 1 || quality > 3 ||
		scale <= 0.0 || scale > 0.0200 || !SDVKFinite(scale) ||
		!SDVKFinite(original) || !SDVKFinite(uvDx) || !SDVKFinite(uvDy) ||
		PALETTEMODE || TM_STENCIL || TM_OPAQUE || TM_INVERSE ||
		TM_INVERTOPAQUE || TM_ALPHATEXTURE || TM_FOGLAYER || TM_CLAMPY ||
		uNpotEmulation.y != 0.0)
		return original;

	// vTexCoord already includes TextureMatrix. Permit only axis-aligned,
	// positively scaled transforms; a rotated/skewed/negative-U matrix would
	// need a different material TBN and is explicitly unsupported.
	if (!SDVKFinite(TextureMatrix[0][0]) || !SDVKFinite(TextureMatrix[1][1]) ||
		TextureMatrix[0][0] <= 0.0 || TextureMatrix[1][1] <= 0.0 ||
		abs(TextureMatrix[1][0]) > 0.000001 || abs(TextureMatrix[0][1]) > 0.000001 ||
		abs(TextureMatrix[0][3]) > 0.000001 || abs(TextureMatrix[1][3]) > 0.000001 ||
		abs(TextureMatrix[3][3] - 1.0) > 0.000001 ||
		!SDVKFinite(uSpriteReliefBounds.xy) || !SDVKFinite(uSpriteReliefBounds.zw))
		return original;

	vec2 p0 = (TextureMatrix * vec4(uSpriteReliefBounds.xy, 0.0, 1.0)).xy;
	vec2 p1 = (TextureMatrix * vec4(uSpriteReliefBounds.zw, 0.0, 1.0)).xy;
	vec2 rectLo = min(p0, p1);
	vec2 rectHi = max(p0, p1);
	if (!SDVKFinite(rectLo) || !SDVKFinite(rectHi) ||
		any(lessThan(rectLo, vec2(0.0))) || any(greaterThan(rectHi, vec2(1.0))) ||
		any(lessThanEqual(rectHi - rectLo, vec2(0.00001))))
		return original;

	ivec2 heightDimensions = textureSize(uHeightTextureIndex, 0);
	ivec2 albedoDimensions = textureSize(tex, 0);
	if (any(lessThanEqual(heightDimensions, ivec2(0))) ||
		any(lessThanEqual(albedoDimensions, ivec2(0))))
		return original;
	vec2 dims = vec2(heightDimensions);
	float rho = max(length(uvDx*dims), length(uvDy*dims));
	float lod = clamp(log2(max(rho, 0.000001)), 0.0, 4.0);
	// Include the bilinear/mipmap filtering footprint, not only the center UV.
	// Oversized footprints disable relief instead of bleeding into an atlas.
	vec2 texelMax = max(1.0/dims, 1.0/vec2(albedoDimensions));
	vec2 pad = max(texelMax * (1.0 + exp2(lod)),
		2.0 * (abs(uvDx) + abs(uvDy)));
	vec2 safeLo = rectLo + pad;
	vec2 safeHi = rectHi - pad;
	if (!SDVKInsideReliefRect(original, safeLo, safeHi))
		return original;

	vec3 direction = uCameraPos.xyz - pixelpos.xyz;
	float distanceSq = dot(direction, direction);
	if (!SDVKFinite(direction) || !SDVKFinite(distanceSq) || distanceSq <= 1e-12)
		return original;
	direction *= inversesqrt(distanceSq);
	vec3 bitangent = cross(uSpriteNormal.xyz, uSpriteTangent.xyz) * uSpriteTangent.w;
	vec3 view = vec3(dot(direction,uSpriteTangent.xyz), dot(direction,bitangent), dot(direction,uSpriteNormal.xyz));
	if (!SDVKFinite(view) || view.z <= 0.20)
		return original;
	if (length(view.xy) <= 1e-8)
		return original;

	float fade = smoothstep(0.20, 0.32, view.z);
	vec2 ray = (scale * fade / view.z) * view.xy;
	float rayLength = length(ray);
	if (!SDVKFinite(ray) || !SDVKFinite(rayLength) || rayLength <= 1e-10)
		return original;
	if (rayLength > 0.0500) ray *= 0.0500/rayLength;

	int steps = quality == 1 ? 8 : (quality == 2 ? 12 : 20);
	int refinements = quality == 1 ? 1 : 2;
	// One original sample + up to 20 fixed march + two fixed refinements.
	float fLow = textureLod(uHeightTextureIndex, original, lod).r - 1.0;
	if (!SDVKFinite(fLow) || fLow < -1.0 || fLow > 0.0)
		return original;
	if (fLow >= 0.0) return original; // height 1 touches the front plane
	float dLow = 0.0;
	float dHigh = 1.0;
	float fHigh = 0.0;
	bool bracketed = false;
	for (int i = 1; i <= 20; ++i)
	{
		if (i > steps) break;
		float depth = float(i) / float(steps);
		vec2 uv = original - depth*ray;
		if (!SDVKInsideReliefRect(uv, safeLo, safeHi)) return original;
		float heightValue = textureLod(uHeightTextureIndex, uv, lod).r;
		if (!SDVKFinite(heightValue) || heightValue < 0.0 || heightValue > 1.0) return original;
		float f = depth + heightValue - 1.0;
		if (f >= 0.0)
		{
			dHigh = depth;
			fHigh = f;
			bracketed = true;
			break;
		}
		dLow = depth;
		fLow = f;
	}
	if (!bracketed) return original;
	for (int j = 0; j < 2; ++j)
	{
		if (j >= refinements) break;
		float mid = 0.5 * (dLow + dHigh);
		vec2 uv = original - mid*ray;
		if (!SDVKInsideReliefRect(uv, safeLo, safeHi)) return original;
		float h = textureLod(uHeightTextureIndex, uv, lod).r;
		if (!SDVKFinite(h) || h < 0.0 || h > 1.0) return original;
		float f = mid + h - 1.0;
		if (f >= 0.0) { dHigh = mid; fHigh = f; }
		else { dLow = mid; fLow = f; }
	}
	float denom = fHigh - fLow;
	float lerp = denom > 1e-12 ? clamp(-fLow / denom, 0.0, 1.0) : 0.5;
	float depth = mix(dLow, dHigh, lerp);
	vec2 resolved = original - depth*ray;
	if (!SDVKFinite(resolved) || !SDVKInsideReliefRect(resolved, safeLo, safeHi))
		return original;
	applied = true;
	return resolved;
#else
	return original;
#endif
}
#endif
