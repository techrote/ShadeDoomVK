
layout(set = 0, binding = 0) uniform sampler2D Tex;

layout(push_constant) uniform PushConstants
{
	int SrcTexSize;
	int DestTexSize;
	int ProbeCount;
	int Padding;
};

struct ProbeSelectionEntry
{
	vec3 position;
	uint textureIndex;
};

layout(std430, set = 0, binding = 2) buffer readonly ProbeSelectionBuffer
{
	ProbeSelectionEntry probes[];
};

layout(location = 0) in vec2 TexCoord;
layout(location = 1) in vec3 WorldPos;

layout(location = 0) out vec4 FragColor;
layout(location = 1) out uvec4 FragProbe;

uint findClosestProbe(vec3 pos, float radius)
{
	const uint fallbackIndex = 0u;
	const uint maxProbeMapIndex = 0xffffu;
	float radiusSquared = radius * radius;
	float closestDistanceSquared = radiusSquared;
	uint closestTextureIndex = fallbackIndex;
	bool found = false;

	for (int i = 0; i < ProbeCount; ++i)
	{
		ProbeSelectionEntry candidate = probes[i];
		if (candidate.textureIndex == fallbackIndex || candidate.textureIndex > maxProbeMapIndex)
			continue;

		vec3 delta = candidate.position - pos;
		float distanceSquared = dot(delta, delta);
		if (distanceSquared <= radiusSquared && (!found || distanceSquared < closestDistanceSquared))
		{
			closestDistanceSquared = distanceSquared;
			closestTextureIndex = candidate.textureIndex;
			found = true;
		}
	}

	return closestTextureIndex;
}

void main()
{
	uint probeIndex = findClosestProbe(WorldPos, 512.0);

	FragColor = texture(Tex, TexCoord);
	FragProbe = uvec4(probeIndex, 0u, 0u, 0u);
}
