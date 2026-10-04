"""#110 real constructor/descriptor repro, with bounded CPU interface services.

Generated definitions come from current production source. The complete original
constructor/GetLayer/descriptor definitions below preserve the pre-fix failure.
The inherited unused sampler local and UploadTexture's unused format parameter
receive [[maybe_unused]] AFTER original source hashing; these harness annotations
change no producer or descriptor logic. Create/upload/reset/palette and image
selection bodies also come from production; original no-mipmap methods preserve
the missing final sampled-layout transition as an independent negative witness.
Checked TArray reports invalid element access instead of executing C++ UB.
Vulkan services record copies and retirement. Canonical palette pointers are
supplied coherently; AddRemap dedup is not modelled. Async callbacks replay on one
CPU thread, not concurrent renderer/worker execution. The scalar shader adapter
proves operation ordering only. None of this is native GPU/image acceptance.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle.fixture_runner import compile_fixture

BASELINE = "4df7dea1338f063c6417e024f967bfa4aa23edd4"
# Preserve the original trailing tab/space in the evaluated pinned body while
# keeping this Python source free of trailing-whitespace diagnostics.
LEGACY_CONSTRUCTOR = r'''
FMaterial::FMaterial(FGameTexture * tx, int scaleflags)
{
	mShaderIndex = SHADER_Default;
	sourcetex = tx;
	auto imgtex = tx->GetTexture();
	mTextureLayers.Push({ imgtex, scaleflags, -1, MaterialLayerSampling::Default, MaterialLayerSemantic::Albedo, -1 });

	if (tx->GetUseType() == ETextureType::SWCanvas && static_cast<FWrapperTexture*>(imgtex)->GetColorFormat() == 0)
	{
		mShaderIndex = SHADER_Paletted;
	}
	else if (scaleflags & CTF_Indexed)
	{
		mTextureLayers[0].scaleFlags |= CTF_Indexed;
		mShaderIndex = SHADER_Paletted;
	}
	else if (tx->isHardwareCanvas())
	{
		if (tx->GetShaderIndex() >= FIRST_USER_SHADER)
		{
			mShaderIndex = tx->GetShaderIndex();
		}
		mTextureLayers.Last().clampflags = CLAMP_CAMTEX;
		// no additional layers for cameratexture
	}
	else
	{
		if (tx->isWarped())
		{
			mShaderIndex = tx->isWarped(); // This picks SHADER_Warp1 or SHADER_Warp2
		}
		// Note that the material takes no ownership of the texture!
		else if (tx->Layers && tx->Layers->Normal.get() && tx->Layers->Specular.get())
		{
			mTextureLayers.Push({ tx->Layers->Normal.get(), 0, -1, MaterialLayerSampling::Default, MaterialLayerSemantic::Normal, -1 });
			mTextureLayers.Push({ tx->Layers->Specular.get(), 0, -1, MaterialLayerSampling::Default, MaterialLayerSemantic::LegacySpecular, -1 });
			mShaderIndex = SHADER_Specular;
		}
		else if (tx->Layers && tx->Layers->Normal.get() && tx->Layers->Metallic.get() && tx->Layers->Roughness.get() && tx->Layers->AmbientOcclusion.get())
		{
			mTextureLayers.Push({ tx->Layers->Normal.get(), 0, -1, MaterialLayerSampling::Default, MaterialLayerSemantic::Normal, -1 });
			mTextureLayers.Push({ tx->Layers->Metallic.get(), 0, -1, MaterialLayerSampling::Default, MaterialLayerSemantic::Metallic, -1 });
			mTextureLayers.Push({ tx->Layers->Roughness.get(), 0, -1, MaterialLayerSampling::Default, MaterialLayerSemantic::Roughness, -1 });
			mTextureLayers.Push({ tx->Layers->AmbientOcclusion.get(), 0, -1, MaterialLayerSampling::Default, MaterialLayerSemantic::AmbientOcclusion, -1 });
			mShaderIndex = SHADER_PBR;
		}

		// Note that these layers must present a valid texture even if not used, because empty TMUs in the shader are an undefined condition.
		tx->CreateDefaultBrightmap();
		auto placeholder = TexMan.GameByIndex(1);
		if (tx->Brightmap.get())
		{
			mTextureLayers.Push({ tx->Brightmap.get(), scaleflags, -1, MaterialLayerSampling::Default, MaterialLayerSemantic::Brightmap, -1 });
			mLayerFlags |= TEXF_Brightmap;
		}
		else__PF_ORIGINAL_TAB__
		{__PF_ORIGINAL_SPACE__
			mTextureLayers.Push({ placeholder->GetTexture(), 0, -1, MaterialLayerSampling::Default, MaterialLayerSemantic::Brightmap, -1 });
		}
		if (tx->Layers && tx->Layers->Detailmap.get())
		{
			mTextureLayers.Push({ tx->Layers->Detailmap.get(), 0, CLAMP_NONE, MaterialLayerSampling::Default, MaterialLayerSemantic::Detail, -1 });
			mLayerFlags |= TEXF_Detailmap;
		}
		else
		{
			mTextureLayers.Push({ placeholder->GetTexture(), 0, -1, MaterialLayerSampling::Default, MaterialLayerSemantic::Detail, -1 });
		}
		if (tx->Layers && tx->Layers->Glowmap.get())
		{
			mTextureLayers.Push({ tx->Layers->Glowmap.get(), scaleflags, -1, MaterialLayerSampling::Default, MaterialLayerSemantic::Glow, -1 });
			mLayerFlags |= TEXF_Glowmap;
		}
		else
		{
			mTextureLayers.Push({ placeholder->GetTexture(), 0, -1, MaterialLayerSampling::Default, MaterialLayerSemantic::Glow, -1 });
		}

		mNumNonMaterialLayers = mTextureLayers.Size();

		auto index = tx->GetShaderIndex();

		const auto globalshader = mShaderIndex < FIRST_USER_SHADER ? &globalshaders[mShaderIndex] : &nullglobalshader;

		if (gl_customshader)
		{
			if (index >= FIRST_USER_SHADER || globalshader->shaderindex >= FIRST_USER_SHADER)
			{

				if (index >= FIRST_USER_SHADER && usershaders[index - FIRST_USER_SHADER].shaderType == mShaderIndex) // Only apply user shader if it matches the expected material
				{
					if (tx->Layers)
					{
						size_t i = 0;
						for (auto& texture : tx->Layers->CustomShaderTextures)
						{
							if (texture != nullptr)
							{
								mTextureLayers.Push({ texture.get(), 0, -1, tx->Layers->CustomShaderTextureSampling[i], MaterialLayerSemantic::Custom, static_cast<int>(i) });	// scalability should be user-definable.
							}
							i++;
						}
					}
					mShaderIndex = index;
				}
				else if(mShaderIndex < FIRST_USER_SHADER && globalshader->shaderindex >= FIRST_USER_SHADER)
				{
					size_t i = 0;
					for (auto& texture : globalshader->CustomShaderTextures)
					{
						if (texture != nullptr)
						{
							mTextureLayers.Push({ texture.get(), 0, -1, globalshader->CustomShaderTextureSampling[i], MaterialLayerSemantic::Custom, static_cast<int>(i) });	// scalability should be user-definable.
						}
						i++;
					}

					mShaderIndex = globalshader->shaderindex;
				}
			}
		}
	}
	mScaleFlags = scaleflags;

	mTextureLayers.ShrinkToFit();
	tx->Material[scaleflags] = this;
}
'''.replace('__PF_ORIGINAL_TAB__', '\t').replace('__PF_ORIGINAL_SPACE__', ' ').strip()

LEGACY_GET_LAYER = r'''
IHardwareTexture* FMaterial::GetLayer(int i, int translation, MaterialLayerInfo** pLayer) const
{
	auto& layer = mTextureLayers[i];
	if (pLayer) *pLayer = &layer;
	if (mScaleFlags & CTF_Indexed) translation = -1;
	if (layer.layerTexture) return layer.layerTexture->GetHardwareTexture(translation, layer.scaleFlags);
	return nullptr;
}
'''.strip()

LEGACY_DESCRIPTOR = r'''
VkMaterial::DescriptorEntry& VkMaterial::GetDescriptorEntry(const FMaterialState& state)
{
	auto base = Source();
	int clampmode = state.mClampMode;
	int translation = state.mTranslation;
	GlobalShaderAddr globalShaderAddr = state.globalShaderAddr;
	auto translationp = IsLuminosityTranslation(translation)? translation : intptr_t(GPalette.GetTranslation(GetTranslationType(translation), GetTranslationIndex(translation)));

	clampmode = base->GetClampMode(clampmode);

	int paletteFlags = 0;
	const bool indexedRedIsAlpha = state.mPaletteMode && state.mRedIsAlpha;
	if (state.mPaletteMode)
	{
		paletteFlags |= indexedRedIsAlpha ? CTF_IndexedRedIsAlpha : CTF_Indexed;

		// We can't do linear filtering for indexed textures
		if (clampmode < CLAMP_NOFILTER)
			clampmode += CLAMP_NOFILTER;
	}

	for (auto& set : mDescriptorSets)
	{
		if (set.clampmode == clampmode && set.remap == translationp && set.globalShaderAddr == globalShaderAddr && set.indexed == state.mPaletteMode && set.redIsAlpha == indexedRedIsAlpha) return set;
	}

	const GlobalShaderDesc& globalshader = *GetGlobalShader(globalShaderAddr);
	int numLayersMat = globalshader ? NumNonMaterialLayers() : NumLayers();
	auto descriptors = fb->GetDescriptorSetManager();
	auto* sampler = fb->GetSamplerManager()->Get(clampmode);

	MaterialLayerInfo *layer = nullptr;
	auto systex = static_cast<VkHardwareTexture*>(GetLayer(0, state.mTranslation, &layer));

	// How many textures do we need?
	int textureCount;
	if (!(layer->scaleFlags & CTF_Indexed))
	{
		textureCount = numLayersMat;
		if (globalshader)
		{
			for (auto& texture : globalshader.CustomShaderTextures)
			{
				if (texture != nullptr)
					textureCount++;
			}
		}
	}
	else
	{
		textureCount = 3;
	}

	int bindlessIndex = descriptors->AllocBindlessSlot(textureCount);
	int texIndex = bindlessIndex;

	auto systeximage = systex->GetImage(layer->layerTexture, state.mTranslation, layer->scaleFlags | paletteFlags);
	descriptors->SetBindlessTexture(texIndex++, systeximage->View.get(), fb->GetSamplerManager()->Get(GetLayerFilter(0), clampmode));

	if (!(layer->scaleFlags & CTF_Indexed))
	{
		for (int i = 1; i < numLayersMat; i++)
		{
			auto syslayer = static_cast<VkHardwareTexture*>(GetLayer(i, 0, &layer));
			auto syslayerimage = syslayer->GetImage(layer->layerTexture, 0, layer->scaleFlags | paletteFlags);
			descriptors->SetBindlessTexture(texIndex++, syslayerimage->View.get(), fb->GetSamplerManager()->Get(GetLayerFilter(i), clampmode));
		}

		if(globalshader)
		{
			size_t i = 0;
			for (auto& texture : globalshader.CustomShaderTextures)
			{
				if (texture != nullptr)
				{
					VkHardwareTexture *tex = static_cast<VkHardwareTexture*>(texture.get()->GetHardwareTexture(0, 0));
					VkTextureImage *img = tex->GetImage(texture.get(), 0, paletteFlags);
					descriptors->SetBindlessTexture(texIndex++, img->View.get(), fb->GetSamplerManager()->Get(globalshader.CustomShaderTextureSampling[i], clampmode));
				}
				i++;
			}
		}
	}
	else
	{
		for (int i = 1; i < 3; i++)
		{
			auto syslayer = static_cast<VkHardwareTexture*>(GetLayer(i, translation, &layer));
			auto syslayerimage = syslayer->GetImage(layer->layerTexture, 0, layer->scaleFlags | paletteFlags);
			descriptors->SetBindlessTexture(texIndex++, syslayerimage->View.get(), fb->GetSamplerManager()->Get(GetLayerFilter(i), clampmode));
		}
	}

	if (texIndex != bindlessIndex + textureCount)
		I_FatalError("VkMaterial.GetDescriptorEntry: texIndex != bindlessIndex + textureCount");

	mDescriptorSets.emplace_back(clampmode, translationp, bindlessIndex, globalShaderAddr, state.mPaletteMode, indexedRedIsAlpha);
	return mDescriptorSets.back();
}
'''.strip()

LEGACY_CREATE_TEXTURE = r'''
void VkHardwareTexture::CreateTexture(VkTextureImage* image, int w, int h, int pixelsize, VkFormat format, const void *pixels, bool mipmap)
{
	if (w <= 0 || h <= 0)
		throw CVulkanError("Trying to create zero size texture");

	int totalSize = w * h * pixelsize;
	if (totalSize <= 0)
		throw CVulkanError("Texture staging size overflow");

	auto staging = fb->GetTextureManager()->StageTextureUpload(pixels, static_cast<std::size_t>(totalSize));

	image->Image = ImageBuilder()
		.Format(format)
		.Size(w, h, !mipmap ? 1 : GetMipLevels(w, h))
		.Usage(VK_IMAGE_USAGE_TRANSFER_SRC_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_SAMPLED_BIT)
		.DebugName("VkHardwareTexture.mImage")
		.Create(fb->GetDevice());

	image->View = ImageViewBuilder()
		.Image(image->Image.get(), format)
		.DebugName("VkHardwareTexture.mImageView")
		.Create(fb->GetDevice());

	auto cmdbuffer = fb->GetCommands()->GetTransferCommands();

	VkImageTransition()
		.AddImage(image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, true)
		.Execute(cmdbuffer);

	VkBufferImageCopy region = {};
	region.bufferOffset = staging.Offset;
	region.imageSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
	region.imageSubresource.layerCount = 1;
	region.imageExtent.depth = 1;
	region.imageExtent.width = w;
	region.imageExtent.height = h;
	cmdbuffer->copyBufferToImage(staging.Buffer->buffer, image->Image->image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 1, &region);

	if (mipmap) image->GenerateMipmaps(cmdbuffer);
	fb->GetTextureManager()->FinishTextureUpload(staging);
}
'''.strip()

LEGACY_UPLOAD_TEXTURE = r'''
void VkHardwareTexture::UploadTexture(VkTextureImage* image, int w, int h, int pixelsize, VkFormat format, const void* pixels, bool mipmap)
{
	if (w <= 0 || h <= 0)
		throw CVulkanError("Trying to create zero size texture");

	int totalSize = w * h * pixelsize;
	if (totalSize <= 0)
		throw CVulkanError("Texture staging size overflow");

	auto staging = fb->GetTextureManager()->StageTextureUpload(pixels, static_cast<std::size_t>(totalSize));

	auto cmdbuffer = fb->GetCommands()->GetTransferCommands();

	VkImageTransition()
		.AddImage(image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, true)
		.Execute(cmdbuffer);

	VkBufferImageCopy region = {};
	region.bufferOffset = staging.Offset;
	region.imageSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
	region.imageSubresource.layerCount = 1;
	region.imageExtent.depth = 1;
	region.imageExtent.width = w;
	region.imageExtent.height = h;
	cmdbuffer->copyBufferToImage(staging.Buffer->buffer, image->Image->image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 1, &region);

	if (mipmap) image->GenerateMipmaps(cmdbuffer);
	fb->GetTextureManager()->FinishTextureUpload(staging);
}
'''.strip()

LEGACY_LAYOUT_HASHES = {'create': '4ac4b2dbb96c75f6597ded25e4f71ce99d8526fb762401449ac4072511e00491', 'upload': '01120a55c3e0fd8a378b10c41453cc61d752beca3158011f5e9d187078536f1a'}

LEGACY_HASHES = {'constructor': '6ae35dff28d2a29c06962d0d53c2fcbf9c640d9a4141676445e618926f6b4fcf', 'get_layer': 'a376b5e74f2a8d34c04f285f2daacb0676d05286f77d62ea1392679c043d8724', 'descriptor': '83f78df77f25a6d5d73e71663dfeda837c3a7b2e662d14f9626969a6bdec4d67'}


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def definition(text: str, signature: str) -> str:
    """Extract one complete definition; ignore braces inside strings/comments."""
    start = text.index(signature)
    brace = text.index("{", start)
    depth, index, state = 1, brace + 1, "code"
    while depth:
        char, pair = text[index], text[index:index + 2]
        if state == "code":
            if pair == "//": state = "line"; index += 1
            elif pair == "/*": state = "block"; index += 1
            elif char == '"': state = "string"
            elif char == "'": state = "char"
            elif char == "{": depth += 1
            elif char == "}": depth -= 1
        elif state == "line" and char == "\n": state = "code"
        elif state == "block" and pair == "*/": state = "code"; index += 1
        elif state in ("string", "char"):
            if char == "\\": index += 1
            elif char == ('"' if state == "string" else "'"): state = "code"
        index += 1
    return text[start:index]


def generated_header(*, legacy: bool) -> str:
    material = source("src/common/textures/hw_material.cpp")
    backend = source("src/common/rendering/vulkan/textures/vk_hwtexture.cpp")
    textures = source("src/common/textures/texture.cpp")
    descriptors = source("src/common/rendering/vulkan/descriptorsets/vk_descriptorset.cpp")
    parts = [
        definition(backend, "static const FRemapTable* ResolveIndexedTranslation("),
        LEGACY_CONSTRUCTOR if legacy else definition(material, "FMaterial::FMaterial("),
        LEGACY_GET_LAYER if legacy else definition(material, "IHardwareTexture* FMaterial::GetLayer("),
        definition(material, "FMaterial * FMaterial::ValidateTexture("),
        definition(backend, "VkMaterial::VkMaterial("),
        definition(backend, "VkMaterial::~VkMaterial("),
        definition(backend, "void VkMaterial::DeleteDescriptors("),
        definition(backend, "int VkMaterial::GetBindlessIndex("),
        LEGACY_DESCRIPTOR if legacy else definition(backend, "VkMaterial::DescriptorEntry& VkMaterial::GetDescriptorEntry("),
        definition(backend, "VkTextureImage *VkHardwareTexture::GetImage("),
        definition(backend, "VkTextureImage *VkHardwareTexture::GetIndexedMaterialImage("),
        definition(backend, "void VkHardwareTexture::CreateImage("),
        LEGACY_CREATE_TEXTURE if legacy else definition(backend, "void VkHardwareTexture::CreateTexture(VkTextureImage*"),
        (LEGACY_UPLOAD_TEXTURE if legacy else definition(backend, "void VkHardwareTexture::UploadTexture(")).replace(
            "VkFormat format,", "[[maybe_unused]] VkFormat format,", 1),
        definition(backend, "int VkHardwareTexture::GetMipLevels("),
        definition(backend, "void VkHardwareTexture::Reset("),
        definition(backend, "std::unique_ptr<VkTextureImage> VkMaterial::CreateIndexedPalette("),
        definition(textures, "IHardwareTexture* FTexture::GetHardwareTexture("),
        definition(descriptors, "void VkDescriptorSetManager::AddMaterial("),
        definition(descriptors, "void VkDescriptorSetManager::RemoveMaterial("),
    ]
    # Extract only the actual indexed producer branch. Truecolor processing,
    # locks and non-8x1 orientation are explicitly outside this bounded fixture.
    producer = definition(textures, "FTextureBuffer FTexture::CreateTexBuffer(")
    indexed_branch = definition(producer, "if (flags & (CTF_Indexed | CTF_IndexedRedIsAlpha))")
    parts.append("FTextureBuffer FTexture::CreateTexBuffer(int translation, int flags)\n{\n"
                 "// Instrumentation records producer input; it does not change indexed bytes.\n"
                 "LastProducedTexture = this; LastProducedTranslation = translation; LastProducedFlags = flags;\n"
                 "FTextureBuffer result;\n" + indexed_branch + "\n"
                 "// Truecolour services are placeholders, outside this indexed-byte fixture.\n"
                 "if (!(flags & (CTF_Indexed | CTF_IndexedRedIsAlpha))) { result.mWidth = 8; result.mHeight = 1; result.mBuffer = new uint8_t[32]{}; }\n"
                 "return result;\n}")
    reset = definition(source("src/common/rendering/vulkan/textures/vk_imagetransition.h"), "void Reset(VulkanRenderDevice* fb)")
    parts.append(reset.replace("void Reset(", "void VkTextureImage::Reset(", 1))

    # A scalar red-channel order oracle, not a complete GLSL implementation.
    # The inverse branch is compiled verbatim with bounded vec4 support. The
    # additive/object-colour statements are projected onto red explicitly;
    # absent blend/desaturation/gradient controls are fixed neutral here.
    texel = source("wadsrc/static/shaders/scene/material_gettexel.glsl")
    inverse = definition(texel, "else if (TM_INVERSE)").replace("else if (TM_INVERSE)", "if (inverse)", 1)
    add = "texel.rgb += uAddColor.rgb;"
    multiply = "if (uObjectColor2.a == 0.0) texel *= uObjectColor;"
    coordinate = "index = ((index * 255.0) + 0.5) / 256.0;"
    if add not in texel or multiply not in texel or coordinate not in source("wadsrc/static/shaders/scene/material_paletted.glsl"):
        raise AssertionError("Actual indexed shader style/coordinate statements changed; reconcile order oracle")
    parts.append("uint8_t SourceShaderOrderIndex(uint8_t byte, bool inverse, double add, double multiply) {\n"
                 "vec4 texel(static_cast<double>(byte) / 255.0, 0.0, 0.0, 1.0);\n" + inverse + "\n"
                 "vec4 uAddColor(add, 0.0, 0.0, 0.0), uObjectColor(multiply, 1.0, 1.0, 1.0);\n"
                 "// Red-only projection of exact source: " + add + "\n"
                 "texel.r += uAddColor.r;\n"
                 "// Neutral second-object colour alpha; red-only projection of: " + multiply + "\n"
                 "texel.r *= uObjectColor.r;\n"
                 "double index = texel.r;\n" + coordinate + "\n"
                 "const int sampled = static_cast<int>(std::floor(index * 256.0));\n"
                 "return static_cast<uint8_t>(sampled < 0 ? 0 : sampled > 255 ? 255 : sampled);\n}")
    append = "mat->AddTextureLayer(PaletteTexture, false, MaterialLayerSampling::Default);"
    if append not in source("src/rendering/swrenderer/r_swscene.cpp"):
        raise AssertionError("Production software palette append changed; reconcile its real route")
    parts.append("void SourceAppendSWPalette(FMaterial* mat, FTexture* PaletteTexture) { " + append + " }")
    joined = "\n\n".join(parts)
    original_sampler = "auto* sampler = fb->GetSamplerManager()->Get(clampmode);"
    joined = joined.replace(original_sampler, "[[maybe_unused]] " + original_sampler)
    return "// Source-extracted production definitions; GPU services are recorded stubs.\n" + joined + "\n"


class IndexedMaterialContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="pf-indexed-material-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.directory = Path(cls.temp.name)
        cls.executables = {}
        for legacy in (False, True):
            directory = cls.directory / ("original" if legacy else "current")
            directory.mkdir()
            (directory / "production_indexed_material.h").write_text(generated_header(legacy=legacy), encoding="utf-8")
            cls.executables[legacy] = compile_fixture(
                "tools/pf_oracle/tests/indexed_material_fixture.cpp", output_dir=directory,
                includes=(directory,), root=ROOT,
            )

    def fixture(self, mode, *, legacy=False):
        result = subprocess.run([str(self.executables[legacy]), mode], cwd=ROOT,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(mode + " passed", result.stdout)
        return result

    def test_original_production_constructor_consumer_missing_layer_is_preserved(self):
        result = self.fixture("legacy", legacy=True)
        self.assertIn("layers=1 allocation=3 writes=1 missing=1", result.stdout)

    def test_current_public_indexed_material_has_actual_palette_descriptor(self):
        self.fixture("indexed")

    def test_ordinary_palette_mode_and_red_is_alpha_state_are_separate(self):
        self.fixture("ordinary")

    def test_software_canvas_owns_its_separate_real_palette_layer(self):
        self.fixture("swcanvas")

    def test_missing_invalid_and_uncreated_textures_are_rejected(self):
        self.fixture("missing")

    def test_descriptor_cleanup_and_recreation_free_each_range_once(self):
        self.fixture("cleanup")

    def test_existing_image_owner_first_translation_counterexample(self):
        result = self.fixture("owner")
        self.assertIn("forced=-1 first=1 requested-second=2 upload-count=1", result.stdout)

    def test_actual_base_palette_row_upload_shape_bytes_and_offset(self):
        self.fixture("palette")

    def test_canonical_translation_variants_reuse_and_numerical_id_replacement(self):
        self.fixture("variants")

    def test_default_inactive_invalid_and_luminosity_share_untranslated_policy(self):
        self.fixture("policy")

    def test_material_palette_and_red_is_alpha_variants_remain_separate(self):
        self.fixture("alpha-variants")

    def test_actual_index_sampler_mapping_preserves_wrap_axes(self):
        self.fixture("sampling")

    def test_noncommuting_inverse_and_tint_follow_real_producer_order(self):
        self.fixture("style")

    def test_all_variant_maps_and_palette_rows_retire_and_recreate(self):
        self.fixture("retirement")

    def test_public_indexed_upload_is_synchronous_and_old_async_reset_is_rejected(self):
        self.fixture("async")

    def test_actual_no_mipmap_creation_and_update_end_in_sampled_layout(self):
        self.fixture("layout")

    def test_original_no_mipmap_creation_and_update_leave_transfer_layout(self):
        self.fixture("legacy-layout", legacy=True)

    def test_current_material_publication_matches_actual_uploaded_read_layouts(self):
        self.fixture("descriptor-layout")


class IndexedMaterialSourceContract(unittest.TestCase):
    def test_frozen_negative_has_exact_original_source_hashes(self):
        for name, text in (("constructor", LEGACY_CONSTRUCTOR), ("get_layer", LEGACY_GET_LAYER), ("descriptor", LEGACY_DESCRIPTOR)):
            self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), LEGACY_HASHES[name])
        self.assertIn("mTextureLayers.Push", LEGACY_CONSTRUCTOR)
        self.assertIn("textureCount = 3;", LEGACY_DESCRIPTOR)
        self.assertIn("GetLayer(i, translation, &layer)", LEGACY_DESCRIPTOR)
        for name, text in (("create", LEGACY_CREATE_TEXTURE), ("upload", LEGACY_UPLOAD_TEXTURE)):
            self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), LEGACY_LAYOUT_HASHES[name])
            self.assertNotIn("else VkImageTransition().AddImage(image, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL", text)

    def test_public_draw_tag_routes_to_the_real_indexed_material_flag(self):
        self.assertIn("DTA_Indexed", source("wadsrc/static/zscript/engine/base.zs"))
        self.assertIn("DTF_Indexed ? CTF_Indexed : 0", source("src/common/rendering/hwrenderer/hw_draw2d.cpp"))
        self.assertIn("if (scaleflags & CTF_Indexed) scaleflags = CTF_Indexed;", source("src/common/textures/hw_material.cpp"))

    def test_shader_consumes_binding_one_real_palette_and_opaque_alpha(self):
        shader = source("wadsrc/static/shaders/scene/material_paletted.glsl")
        bindings = source("wadsrc/static/shaders/scene/binding_textures.glsl")
        self.assertIn("texture(texture2, vec2(index, 0.5))", shader)
        self.assertIn("tex.a = 1.0;", shader)
        self.assertIn("const int texture2 = 1;", bindings)
        self.assertNotIn("texture3", shader)

    def test_indexed_remap_is_the_index_mapping_not_ideal_truecolor_palette(self):
        producer = definition(source("src/common/textures/texture.cpp"), "FTextureBuffer FTexture::CreateTexBuffer(")
        branch = definition(producer, "if (flags & (CTF_Indexed | CTF_IndexedRedIsAlpha))")
        self.assertIn("remap->Remap[result.mBuffer[i]]", branch)
        self.assertIn("if (remap && remap->Inactive) remap = nullptr;", branch)
        self.assertIn("IsLuminosityTranslation(translation)", branch)
        self.assertNotIn("remap->Palette", branch)

    def test_extractor_ignores_comment_and_string_braces(self):
        text = 'void owner() { const char* name = "}"; /* } */ if (true) { } // }\n}\nvoid next() {}'
        self.assertEqual(definition(text, "void owner()"), text[:text.index("\nvoid next()")])

    def test_material_only_upload_disables_async_without_changing_generic_route(self):
        backend = source("src/common/rendering/vulkan/textures/vk_hwtexture.cpp")
        material_image = definition(backend, "VkTextureImage *VkHardwareTexture::GetIndexedMaterialImage(")
        self.assertIn("CreateImage(image, tex, translation, flags, false);", material_image)
        generic = definition(backend, "VkTextureImage *VkHardwareTexture::GetImage(")
        self.assertNotIn("GetIndexedMaterialImage", generic)
        self.assertNotIn("false", generic)
        creator = definition(backend, "void VkHardwareTexture::CreateImage(")
        self.assertIn("allowAsync && gl_async_textures && tex->GetImage()", creator)

    def test_order_oracle_extracts_shader_operations_before_palette_lookup(self):
        header = generated_header(legacy=False)
        self.assertIn("texel = vec4(1.0-texel.r, 1.0-texel.b, 1.0-texel.g, texel.a);", header)
        self.assertIn("Red-only projection of exact source: texel.rgb += uAddColor.rgb;", header)
        self.assertIn("index = ((index * 255.0) + 0.5) / 256.0;", header)
        shader = source("wadsrc/static/shaders/scene/material_paletted.glsl")
        self.assertLess(shader.index("getTexel("), shader.index("texture(texture2"))


if __name__ == "__main__":
    unittest.main()
