// PF-011: inherited renderer calibration. These are compatibility scalars,
// not photometric units; see PF-011-LIGHTING-COMPATIBILITY-CONTRACT.md.
const float LIGHT_COMPAT_SUN_ATTENUATION_RADIUS = 1000000.0;
const float LIGHT_COMPAT_PBR_BRIGHTNESS_SCALE = 2.5;
const float LIGHT_COMPAT_PBR_AMBIENT_SCALE = 2.25;
const float LIGHT_COMPAT_PBR_METAL_SPECULAR_SCALE = 0.40;

float distanceAttenuation(float dist, float radius, float strength, float linearity)
{
	if (LIGHT_ATTENUATION_INVERSE_SQUARE)
	{
		// The far-away sunlight proxy bypasses local-light falloff.
		if (radius >= LIGHT_COMPAT_SUN_ATTENUATION_RADIUS) return 1.0;
		float a = dist / radius;
		float b = clamp(1.0 - a * a * a * a, 0.0, 1.0);
		return mix((b * b) / (dist * dist + 1.0) * strength, clamp((radius - dist) / radius, 0.0, 1.0), linearity);
	}
	else
	{
		return clamp((radius - dist) / radius, 0.0, 1.0);
	}
}

