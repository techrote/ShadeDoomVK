#pragma once

#ifdef LoadImage
#undef LoadImage
#endif

#define SHADED_TEXTURE -1
#define DIRECT_PALETTE -2

#include "tarray.h"
#include "hw_ihwtexture.h"
#include <zvulkan/vulkanobjects.h>
#include "vk_imagetransition.h"
#include "hw_material.h"
#include "hwrenderer/data/hw_resourcegeneration.h"
#include <list>
#include <unordered_map>

struct FMaterialState;
class VulkanDescriptorSet;
class VulkanImage;
class VulkanImageView;
class VulkanBuffer;
class VulkanRenderDevice;
class FGameTexture;

class VkHardwareTexture : public IHardwareTexture
{
	friend class VkMaterial;
	friend struct FIndexedMaterialDiagnosticAccess;
public:
	VkHardwareTexture(VulkanRenderDevice* fb, int numchannels);
	~VkHardwareTexture();

	void Reset();

	// Software renderer stuff
	void AllocateBuffer(int w, int h, int texelsize) override;
	uint8_t *MapBuffer() override;
	unsigned int CreateTexture(unsigned char * buffer, int w, int h, int texunit, bool mipmap, const char *name) override;

	// Wipe screen
	void CreateWipeTexture(int w, int h, const char *name);

	VkTextureImage *GetImage(FTexture *tex, int translation, int flags);
	VkTextureImage *GetIndexedMaterialImage(FTexture *tex, int translation, int flags);
	VkTextureImage *GetDepthStencil(FTexture *tex);

	VulkanRenderDevice* fb = nullptr;
	std::list<VkHardwareTexture*>::iterator it;

private:
	void CreateImage(VkTextureImage* image, FTexture *tex, int translation, int flags, bool allowAsync = true);

	void CreateTexture(VkTextureImage* image, int w, int h, int pixelsize, VkFormat format, const void *pixels, bool mipmap);
	void UploadTexture(VkTextureImage* image, int w, int h, int pixelsize, VkFormat format, const void* pixels, bool mipmap);
	static int GetMipLevels(int w, int h);

	VkTextureImage mImage, mPaletteImage, mAlphaImage;
	// Public indexed materials share a hardware owner, but translated bytes do
	// not share an image. Canonical remaps are immutable until texture teardown.
	std::unordered_map<const FRemapTable*, std::unique_ptr<VkTextureImage>> IndexedPaletteImages, IndexedAlphaImages;
	int mTexelsize = 4;

	VkTextureImage mDepthStencil;
	FRendererEpoch mUploadEpoch;

	uint8_t* mappedSWFB = nullptr;
};

class VkMaterial : public FMaterial
{
	friend struct FIndexedMaterialDiagnosticAccess;
	friend struct FSdvkDiagnosticAccess;
public:
	VkMaterial(VulkanRenderDevice* fb, FGameTexture* tex, int scaleflags);
	~VkMaterial();

	void DeleteDescriptors() override;

	VulkanRenderDevice* fb = nullptr;
	std::list<VkMaterial*>::iterator it;

	int GetBindlessIndex(const FMaterialState& state);

private:
	struct DescriptorEntry
	{
		int clampmode;
		intptr_t remap;
		int bindlessIndex;
		GlobalShaderAddr globalShaderAddr;
		bool indexed;
		bool redIsAlpha;
		std::unique_ptr<VkTextureImage> IndexedPalette;

		DescriptorEntry(int cm, intptr_t f, int index, GlobalShaderAddr addr, bool paletteMode, bool indexedRedIsAlpha)
		{
			clampmode = cm;
			remap = f;
			bindlessIndex = index;
			globalShaderAddr = addr;
			indexed = paletteMode;
			redIsAlpha = indexedRedIsAlpha;
		}
	};

	DescriptorEntry& GetDescriptorEntry(const FMaterialState& state);
	std::unique_ptr<VkTextureImage> CreateIndexedPalette();

	std::vector<DescriptorEntry> mDescriptorSets;
};
