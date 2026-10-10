
#ifndef SIMPLE3D
	#include "shaders/scene/material_gettexel.glsl"
	#include "shaders/scene/material_normalmap.glsl"
	#include "shaders/scene/material_relief.glsl"
#endif

struct Material
{
	vec4 Base;
	vec4 Bright;
	vec4 Glow;
	vec3 Normal;
	vec3 Specular;
	float Glossiness;
	float SpecularLevel;
	float Metallic;
	float Roughness;
	float AO;
};

vec4 Process(vec4 color);
void SetupMaterial(inout Material mat);
vec3 ProcessMaterialLight(Material material, vec3 color, float sunlightAttenuation);
vec3 ProcessSWLight(Material material, float sunlightAttenuation);
vec2 GetTexCoord();

// Optional SDVK-005 authoring seam. Height is linear scalar data and is not
// consumed by the default material path; later relief/custom shaders opt in.
bool HasMaterialHeightMap()
{
	return uHeightTextureIndex >= 0;
}

float SampleMaterialHeight(vec2 texCoord)
{
	return HasMaterialHeightMap() ? texture(uHeightTextureIndex, texCoord).r : 0.0;
}

Material CreateMaterial()
{
	Material material;
	material.Base = vec4(0.0);
	material.Bright = vec4(0.0);
	material.Glow = vec4(0.0);
	material.Normal = vec3(0.0);
	material.Specular = vec3(0.0);
	material.Glossiness = 0.0;
	material.SpecularLevel = 0.0;
	material.Metallic = 0.0;
	material.Roughness = 0.0;
	material.AO = 0.0;
	SetupMaterial(material);
	return material;
}

#ifndef SIMPLE3D
	void SetMaterialProps(inout Material material, vec2 texCoord)
	{
		#ifdef NPOT_EMULATION
			if (uNpotEmulation.y != 0.0)
			{
				float period = floor(texCoord.t / uNpotEmulation.y);
				texCoord.s += uNpotEmulation.x * floor(mod(texCoord.t, uNpotEmulation.y));
				texCoord.t = period + mod(texCoord.t, uNpotEmulation.y);
			}
		#endif	
			// Opt-in SDVK-008 sprite relief samples only existing material layers.
			// Original alpha remains authoritative for the rasterized silhouette.
			bool reliefApplied = false;
			vec2 relieved = SDVKResolveSpriteReliefUV(texCoord.st, reliefApplied);
			if (reliefApplied)
			{
				vec4 baseTexel = getTexel(texCoord.st);
				vec4 reliefTexel = getTexel(relieved);
				if (reliefTexel.a > uAlphaThreshold)
				{
					material.Base = vec4(reliefTexel.rgb, baseTexel.a);
					texCoord = relieved;
				}
				else material.Base = baseTexel;
			}
			else material.Base = getTexel(texCoord.st);
			material.Normal = ApplyNormalMap(texCoord.st);
			
		// OpenGL doesn't care, but Vulkan pukes all over the place if these texture samplings are included in no-texture shaders, even though never called.
		#ifndef NO_LAYERS
			if (TEXF_Brightmap)
			{
				material.Bright = desaturate(texture(brighttexture, texCoord.st));
			}
			
			if (TEXF_Detailmap)
			{
				vec4 Detail = texture(detailtexture, texCoord.st * uDetailParms.xy) * uDetailParms.z;
				material.Base.rgb *= Detail.rgb;
			}
			
			if (TEXF_Glowmap)
			{
				material.Glow = desaturate(texture(glowtexture, texCoord.st));
			}
			
			#ifdef PBR
				material.Metallic = texture(metallictexture, texCoord.st).r;
				material.Roughness = texture(roughnesstexture, texCoord.st).r;
				material.AO = texture(aotexture, texCoord.st).r;
			#endif
			
			#ifdef SPECULAR
				material.Specular = texture(speculartexture, texCoord.st).rgb;
				material.Glossiness = uSpecularMaterial.x;
				material.SpecularLevel = uSpecularMaterial.y;
			#endif
		#endif
	}
#endif