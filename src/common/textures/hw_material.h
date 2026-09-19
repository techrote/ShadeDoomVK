
#ifndef __GL_MATERIAL_H
#define __GL_MATERIAL_H

#include "m_fixed.h"
#include "textures.h"
#include "material_layer_semantics.h"

struct FRemapTable;
class IHardwareTexture;

struct MaterialLayerInfo
{
	FTexture* layerTexture;
	int scaleFlags;
	int clampflags;
	MaterialLayerSampling layerFiltering;
	MaterialLayerSemantic semantic = MaterialLayerSemantic::Custom;
	int customIndex = -1;
};

struct MaterialLayerDiagnostic
{
	int binding = -1;
	MaterialLayerSemantic semantic = MaterialLayerSemantic::Custom;
	int customIndex = -1;
	FTexture* sourceTexture = nullptr;
	int scaleFlags = 0;
	int clampflags = -1;
	MaterialLayerSampling sampling = MaterialLayerSampling::Default;
};

//===========================================================================
// 
// this is the material class for OpenGL. 
//
//===========================================================================

class FMaterial
{
	private:
	TArray<MaterialLayerInfo> mTextureLayers; // the only layers allowed to scale are the brightmap and the glowmap.
	int mShaderIndex;
	int mLayerFlags = 0;
	int mScaleFlags;

	int mNumNonMaterialLayers = 0;

public:

	FGameTexture *sourcetex;	// the owning texture. 

	FMaterial(FGameTexture *tex, int scaleflags);
	virtual ~FMaterial();
	int GetLayerFlags() const { return mLayerFlags; }
	int GetShaderIndex() const { return mShaderIndex; }
	int GetScaleFlags() const { return mScaleFlags; }
	virtual void DeleteDescriptors() { }
	FVector2 GetDetailScale() const
	{
		return sourcetex->GetDetailScale();
	}

	FGameTexture* Source() const
	{
		return sourcetex;
	}

	void ClearLayers()
	{
		mTextureLayers.Resize(1);
	}

	void AddTextureLayer(FTexture *tex, bool allowscale, MaterialLayerSampling filter)
	{
		AddTextureLayer(tex, allowscale, filter, MaterialLayerSemantic::Custom, -1);
	}

	void AddTextureLayer(FTexture *tex, bool allowscale, MaterialLayerSampling filter, MaterialLayerSemantic semantic, int customIndex = -1)
	{
		mTextureLayers.Push({ tex, allowscale, -1, filter, semantic, customIndex });
	}

	int NumLayers() const
	{
		return mTextureLayers.Size();
	}

	int NumNonMaterialLayers() const
	{
		return mNumNonMaterialLayers;
	}

	IHardwareTexture *GetLayer(int i, int translation, MaterialLayerInfo **pLayer = nullptr) const;
	
	MaterialLayerSampling GetLayerFilter(int index) const
	{
		return mTextureLayers[index].layerFiltering;
	}

	MaterialLayerSemantic GetLayerSemantic(int index) const
	{
		return mTextureLayers[index].semantic;
	}

	int GetLayerCustomIndex(int index) const
	{
		return mTextureLayers[index].customIndex;
	}

	int FindLayer(MaterialLayerSemantic semantic, int customIndex = -1) const
	{
		MaterialLayerSemanticKey key{ semantic, customIndex };
		for (unsigned int i = 0; i < mTextureLayers.Size(); i++)
		{
			auto& layer = mTextureLayers[i];
			if (key.Matches(layer.semantic, layer.customIndex))
				return static_cast<int>(i);
		}
		return -1;
	}

	bool GetLayerDiagnostic(int binding, MaterialLayerDiagnostic& result) const
	{
		if (binding < 0 || binding >= static_cast<int>(mTextureLayers.Size()))
			return false;

		auto& layer = mTextureLayers[binding];
		result.binding = binding;
		result.semantic = layer.semantic;
		result.customIndex = layer.customIndex;
		result.sourceTexture = layer.layerTexture;
		result.scaleFlags = layer.scaleFlags;
		result.clampflags = layer.clampflags;
		result.sampling = layer.layerFiltering;
		return true;
	}

	static FMaterial *ValidateTexture(FGameTexture * tex, int scaleflags, bool create = true);
	const TArray<MaterialLayerInfo> &GetLayerArray() const
	{
		return mTextureLayers;
	}
};

#endif


