// Generated disposable CPU adapter. No current shader repair is supplied.
#pragma once
// SOURCE: vulkanbuilders.cpp; extraction view-default
ImageViewBuilder::ImageViewBuilder()
{
	viewInfo.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO;
	viewInfo.viewType = VK_IMAGE_VIEW_TYPE_2D;
	viewInfo.subresourceRange.baseMipLevel = 0;
	viewInfo.subresourceRange.baseArrayLayer = 0;
	viewInfo.subresourceRange.layerCount = 1;
	viewInfo.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
}

// SOURCE: vk_texture.cpp; extraction fixed-null-creation
void VkTextureManager::CreateNullTexture()
{
NullTexture = ImageBuilder()
		.Format(VK_FORMAT_R8G8B8A8_UNORM)
		.Size(1, 1)
		.Usage(VK_IMAGE_USAGE_SAMPLED_BIT)
		.DebugName("VkDescriptorSetManager.NullTexture")
		.Create(fb->GetDevice());
NullTextureView = ImageViewBuilder()
		.Image(NullTexture.get(), VK_FORMAT_R8G8B8A8_UNORM)
		.DebugName("VkDescriptorSetManager.NullTextureView")
		.Create(fb->GetDevice());
}

// SOURCE: vk_texture.cpp; extraction fixed-brdf-creation
void VkTextureManager::CreateBrdfLutTexture()
{
BrdfLutTexture = ImageBuilder()
		.Format(VK_FORMAT_R16G16_SFLOAT)
		.Size(512, 512)
		.Usage(VK_IMAGE_USAGE_SAMPLED_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT)
		.DebugName("VkDescriptorSetManager.BrdfLutTexture")
		.Create(fb->GetDevice());
BrdfLutTextureView = ImageViewBuilder()
		.Image(BrdfLutTexture.get(), VK_FORMAT_R16G16_SFLOAT)
		.DebugName("VkDescriptorSetManager.BrdfLutTextureView")
		.Create(fb->GetDevice());
}

// SOURCE: vk_texture.cpp; extraction initial-resource-call-order
void VkTextureManager::CreateFixtureInitial()
{
CreateNullTexture();
CreateBrdfLutTexture();
CreateGamePalette();
CreateShadowmap();
CreateLightmap();
CreateIrradiancemap();
CreatePrefiltermap();
}

// SOURCE: vk_texture.cpp; extraction check-irradiance
void VkTextureManager::CheckIrradiancemapSize(int cubeCount)
{
	int createStart = static_cast<int>(Irradiancemaps.size());
	if (Irradiancemaps.size() <= (size_t)cubeCount)
		Irradiancemaps.resize(cubeCount);

	for (int i = createStart; i < cubeCount; i++)
	{
		Irradiancemaps[i].Image = ImageBuilder()
			.Size(IrradiancemapSize, IrradiancemapSize, 1, 6)
			.Format(VK_FORMAT_R16G16B16A16_SFLOAT)
			.Usage(VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT)
			.Flags(VK_IMAGE_CREATE_CUBE_COMPATIBLE_BIT)
			.DebugName("VkTextureManager.Irradiancemap")
			.Create(fb->GetDevice());

		Irradiancemaps[i].View = ImageViewBuilder()
			.Type(VK_IMAGE_VIEW_TYPE_CUBE)
			.Image(Irradiancemaps[i].Image.get(), VK_FORMAT_R16G16B16A16_SFLOAT)
			.DebugName("VkTextureManager.IrradiancemapView")
			.Create(fb->GetDevice());
	}
}

// SOURCE: vk_texture.cpp; extraction check-prefilter
void VkTextureManager::CheckPrefiltermapSize(int cubeCount)
{
	int createStart = static_cast<int>(Prefiltermaps.size());
	if (Prefiltermaps.size() <= (size_t)cubeCount)
		Prefiltermaps.resize(cubeCount);

	int w = PrefiltermapSize;
	int h = PrefiltermapSize;
	[[maybe_unused]] int pixelsize = 8;
	int miplevels = MAX_REFLECTION_LOD + 1;

	for (int i = createStart; i < cubeCount; i++)
	{
		Prefiltermaps[i].Image = ImageBuilder()
			.Size(w, h, miplevels, 6)
			.Format(VK_FORMAT_R16G16B16A16_SFLOAT)
			.Usage(VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT)
			.Flags(VK_IMAGE_CREATE_CUBE_COMPATIBLE_BIT)
			.DebugName("VkTextureManager.Prefiltermap")
			.Create(fb->GetDevice());

		Prefiltermaps[i].View = ImageViewBuilder()
			.Type(VK_IMAGE_VIEW_TYPE_CUBE)
			.Image(Prefiltermaps[i].Image.get(), VK_FORMAT_R16G16B16A16_SFLOAT)
			.DebugName("VkTextureManager.PrefiltermapView")
			.Create(fb->GetDevice());
	}
}

// SOURCE: vk_texture.cpp; extraction initial-irradiance
void VkTextureManager::CreateIrradiancemap()
{
	TArray<uint16_t> data(IrradiancemapSize * IrradiancemapSize * 6 * 3, true);
	memset(data.data(), 0, data.size() * sizeof(uint16_t));
	UploadIrradiancemap(1, std::move(data));
}

// SOURCE: vk_texture.cpp; extraction initial-prefilter
void VkTextureManager::CreatePrefiltermap()
{
	int texsize = 0;
	for (int level = 0; level <= MAX_REFLECTION_LOD; level++)
	{
		int mipsize = PrefiltermapSize >> level;
		texsize += mipsize * mipsize;
	}

	TArray<uint16_t> data(texsize * 6 * 3, true);
	memset(data.data(), 0, data.size() * sizeof(uint16_t));
	UploadPrefiltermap(1, std::move(data));
}

// SOURCE: vk_texture.cpp; extraction reset-probes
void VkTextureManager::ResetLightProbes()
{
	LightProbeEpoch.Invalidate();

	// Special thanks to Khronos for making it so simple to clear an image...

	auto cmdbuffer = fb->GetCommands()->GetTransferCommands();
	int miplevels = MAX_REFLECTION_LOD + 1;

	VkImageTransition barrier0;
	for (auto& map : Prefiltermaps)
	{
		if (map.Image)
			barrier0.AddImage(&map, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, true, 0, miplevels, 0, 6);
	}
	for (auto& map : Irradiancemaps)
	{
		if (map.Image)
			barrier0.AddImage(&map, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, true, 0, 1, 0, 6);
	}
	barrier0.Execute(cmdbuffer);

	VkClearColorValue color = {};
	VkImageSubresourceRange range = {};
	range.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
	range.layerCount = 6;
	range.levelCount = miplevels;
	for (auto& map : Prefiltermaps)
	{
		if (map.Image)
			cmdbuffer->clearColorImage(map.Image->image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, &color, 1, &range);
	}

	range.levelCount = 1;
	for (auto& map : Irradiancemaps)
	{
		if (map.Image)
			cmdbuffer->clearColorImage(map.Image->image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, &color, 1, &range);
	}

	VkImageTransition barrier1;
	for (auto& map : Prefiltermaps)
	{
		if (map.Image)
			barrier1.AddImage(&map, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL, false, 0, miplevels, 0, 6);
	}
	for (auto& map : Irradiancemaps)
	{
		if (map.Image)
			barrier1.AddImage(&map, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL, false, 0, 1, 0, 6);
	}
	barrier1.Execute(cmdbuffer);
}

// SOURCE: vk_texture.cpp; extraction copy-irradiance
void VkTextureManager::CopyIrradiancemap(const std::vector<std::unique_ptr<VulkanImage>>& probes)
{
	CheckIrradiancemapSize(static_cast<int>(probes.size()));

	auto cmdbuffer = fb->GetCommands()->GetDrawCommands();

	VkImageTransition barrier0;
	for (size_t i = 0; i < probes.size(); i++)
		barrier0.AddImage(&Irradiancemaps[i], VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, true, 0, 1, 0, 6);
	barrier0.Execute(cmdbuffer);

	VkImageCopy region = {};
	region.extent.width = IrradiancemapSize;
	region.extent.height = IrradiancemapSize;
	region.extent.depth = 1;
	region.srcSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
	region.srcSubresource.layerCount = 6;
	region.dstSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
	region.dstSubresource.layerCount = 6;

	for (size_t i = 0; i < probes.size(); i++)
	{
		cmdbuffer->copyImage(probes[i]->image, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, Irradiancemaps[i].Image->image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 1, &region);
	}

	VkImageTransition barrier1;
	for (size_t i = 0; i < probes.size(); i++)
		barrier1.AddImage(&Irradiancemaps[i], VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL, false, 0, 1, 0, 6);
	barrier1.Execute(cmdbuffer);
}

// SOURCE: vk_texture.cpp; extraction copy-prefilter
void VkTextureManager::CopyPrefiltermap(const std::vector<std::unique_ptr<VulkanImage>>& probes)
{
	CheckPrefiltermapSize(static_cast<int>(probes.size()));

	auto cmdbuffer = fb->GetCommands()->GetDrawCommands();
	int miplevels = MAX_REFLECTION_LOD + 1;

	VkImageTransition barrier0;
	for (size_t i = 0; i < probes.size(); i++)
		barrier0.AddImage(&Prefiltermaps[i], VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, true, 0, miplevels, 0, 6);
	barrier0.Execute(cmdbuffer);

	std::vector<VkImageCopy> regions;
	for (int level = 0; level < miplevels; level++)
	{
		VkImageCopy region = {};
		region.extent.width = PrefiltermapSize >> level;
		region.extent.height = PrefiltermapSize >> level;
		region.extent.depth = 1;
		region.srcSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
		region.srcSubresource.layerCount = 6;
		region.srcSubresource.mipLevel = level;
		region.dstSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
		region.dstSubresource.layerCount = 6;
		region.dstSubresource.mipLevel = level;
		regions.push_back(region);
	}

	for (size_t i = 0; i < probes.size(); i++)
	{
		cmdbuffer->copyImage(probes[i]->image, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, Prefiltermaps[i].Image->image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, (uint32_t)regions.size(), regions.data());
	}

	VkImageTransition barrier1;
	for (size_t i = 0; i < probes.size(); i++)
		barrier1.AddImage(&Prefiltermaps[i], VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL, false, 0, miplevels, 0, 6);
	barrier1.Execute(cmdbuffer);
}

// SOURCE: vk_descriptorset.cpp; extraction lookup
int VkDescriptorSetManager::GetLightProbeTextureIndex(int probeIndex)
{
	if ((size_t)probeIndex >= LightProbes.size())
		LightProbes.resize(probeIndex + 1, -1);

	if (LightProbes[probeIndex] == -1)
	{
		auto textures = fb->GetTextureManager();

		// Seems we might be rendering a probe before we have data for it
		if (textures->Irradiancemaps.size() > (size_t)probeIndex && textures->Irradiancemaps[probeIndex].View &&
			textures->Prefiltermaps.size() > (size_t)probeIndex && textures->Prefiltermaps[probeIndex].View)
		{
			int bindIndex = AllocBindlessSlot(2);
			LightProbes[probeIndex] = bindIndex;
			SetBindlessTexture(bindIndex, textures->Irradiancemaps[probeIndex].View.get(), fb->GetSamplerManager()->IrradiancemapSampler.get());
			SetBindlessTexture(bindIndex + 1, textures->Prefiltermaps[probeIndex].View.get(), fb->GetSamplerManager()->PrefiltermapSampler.get());
		}
		else
		{
			return 0;
		}
	}

	return LightProbes[probeIndex];
}

// SOURCE: vk_descriptorset.cpp; extraction fixed-descriptor-publication
void VkDescriptorSetManager::SetFixtureFixed()
{
SetBindlessTexture(0, fb->GetTextureManager()->GetNullTextureView(), fb->GetSamplerManager()->Get(CLAMP_XY_NOMIP));
SetBindlessTexture(1, fb->GetTextureManager()->GetBrdfLutTextureView(), fb->GetSamplerManager()->Get(CLAMP_XY_NOMIP));
}

// SOURCE: hw_lightprobe.cpp; extraction builder-step
void LightProbeIncrementalBuilder::Step(const TArray<LightProbe>& probes, std::function<void(int probeIndex, const LightProbe& probe)> renderScene)
{
	if (probes.size() == 0)
	{
		if (cubemapsAllocated != 0)
			screen->ResetLightProbes();
		lastIndex = 0;
		collected = 0;
		cubemapsAllocated = 0;
		iterations = 0;
		return;
	}

	if (cubemapsAllocated != probes.size())
	{
		cubemapsAllocated = probes.size();
		lastIndex = 0;
		collected = 0;
		iterations = 0;
		screen->ResetLightProbes();
		return;
	}

	if (iterations >= 5)
		return; // We are done baking

	if (lastIndex >= probes.size())
		lastIndex = 0;

	renderScene(lastIndex, probes[lastIndex]);
	lastIndex++;
	collected++;

	if (lastIndex >= probes.size())
	{
		if (collected == probes.size())
			screen->EndLightProbePass();
		collected = 0;
		iterations++;
	}
}

// SOURCE: vk_lightprober.cpp; extraction completed-publication
void VkLightprober::EndLightProbePass()
{
	fb->GetTextureManager()->CopyIrradiancemap(irradianceMap.probes);
	fb->GetTextureManager()->CopyPrefiltermap(prefilterMap.probes);
}

// SOURCE: lightmodel_pbr.glsl; extraction original-pbr-sampling
SampleResult OriginalSampling(int vLightmapIndex, int uLightProbeIndex, ShaderLightmap vLightmap, vec3 N, vec3 R, float roughness)
{
const float MAX_REFLECTION_LOD = 4.0f;
ResetSampleObserver();
	vec3 irradiance, prefilteredColor;

	if (vLightmapIndex != -1 && uLightProbeIndex == 0)
	{
		uvec4 probeIndexes = textureGather(uintTextures[nonuniformEXT(vLightmapIndex + 1)], vLightmap.xy);

		vec2 t = fract(vLightmap.xy);
		vec2 invt = 1.0 - t;
		float t00 = invt.x * invt.y;
		float t10 = t.x * invt.y;
		float t01 = invt.x * t.y;
		float t11 = t.x * t.y;
		ObserveWeights(t00, t10, t01, t11);

		vec3 irradiance0 = texture(cubeTextures[probeIndexes.x], N).rgb;
		vec3 irradiance1 = texture(cubeTextures[probeIndexes.y], N).rgb;
		vec3 irradiance2 = texture(cubeTextures[probeIndexes.z], N).rgb;
		vec3 irradiance3 = texture(cubeTextures[probeIndexes.w], N).rgb;
		
		vec3 prefilteredColor0 = textureLod(cubeTextures[probeIndexes.x + 1], R, roughness * MAX_REFLECTION_LOD).rgb;
		vec3 prefilteredColor1 = textureLod(cubeTextures[probeIndexes.y + 1], R, roughness * MAX_REFLECTION_LOD).rgb;
		vec3 prefilteredColor2 = textureLod(cubeTextures[probeIndexes.z + 1], R, roughness * MAX_REFLECTION_LOD).rgb;
		vec3 prefilteredColor3 = textureLod(cubeTextures[probeIndexes.w + 1], R, roughness * MAX_REFLECTION_LOD).rgb;

		irradiance = irradiance0 * t00 + irradiance1 * t10 + irradiance2 * t01 + irradiance3 * t11;
		prefilteredColor = prefilteredColor0 * t00 + prefilteredColor1 * t10 + prefilteredColor2 * t01 + prefilteredColor3 * t11;
	}
	else
	{
		irradiance = texture(cubeTextures[uLightProbeIndex], N).rgb;
		prefilteredColor = textureLod(cubeTextures[uLightProbeIndex + 1], R, roughness * MAX_REFLECTION_LOD).rgb;
	}

return { irradiance, prefilteredColor, ObservedWeights };
}

namespace ShaderSelection
{
struct ProbeSelectionEntry { vec3 position; uint textureIndex; };
static std::vector<ProbeSelectionEntry> probes;
static int ProbeCount = 0;
// SOURCE: frag_copy.glsl; extraction selector
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
} // namespace ShaderSelection
