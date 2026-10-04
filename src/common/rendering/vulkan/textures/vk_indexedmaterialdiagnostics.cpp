/*
 * PF-110: explicitly invoked, bounded indexed-material acceptance diagnostic.
 * This is newly authored diagnostic code; the renderer remains the producer.
 * No startup hook, fault injection, global cache flush or benchmark loop.
 */

#include "c_dispatch.h"
#include "c_cvars.h"
#include "m_argv.h"
#include "doomstat.h"
#include "gamestate.h"
#include "g_levellocals.h"
#include "cmdlib.h"
#include "printf.h"
#include "v_video.h"
#include "v_draw.h"
#include "v_2ddrawer.h"
#include "texturemanager.h"
#include "gametexture.h"
#include "r_translate.h"
#include "hw_material.h"
#include "hw_renderstate.h"
#include "vulkan/vk_renderdevice.h"
#include "vulkan/vk_renderstate.h"
#include "vulkan/buffers/vk_buffer.h"
#include "vulkan/buffers/vk_rsbuffers.h"
#include "vulkan/commands/vk_commandbuffer.h"
#include "vulkan/descriptorsets/vk_descriptorset.h"
#include "vulkan/samplers/vk_samplers.h"
#include "vulkan/textures/vk_renderbuffers.h"
#include "vulkan/textures/vk_texture.h"
#include "vk_hwtexture.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <vector>

EXTERN_CVAR(Int, gl_texture_filter)
EXTERN_CVAR(Bool, gl_async_textures)
EXTERN_CVAR(Bool, hw_2dmip)
EXTERN_CVAR(Int, vid_rendermode)
// Actual engine restart count; D_Cleanup increments it after TexMan.DeleteAll.
extern int restart;

namespace
{
constexpr int OutputWidth = 128;
constexpr int OutputHeight = 20;
constexpr std::array<uint8_t, 16> SourceRow = { 5, 5, 250, 250, 10, 10, 20, 20, 96, 96, 160, 160, 200, 200, 32, 32 };

void Require(bool value, const char* explanation)
{
	if (!value) throw std::runtime_error(explanation);
}

template<class T> uint64_t Handle(T value)
{
	if constexpr (std::is_pointer<T>::value) return static_cast<uint64_t>(reinterpret_cast<uintptr_t>(value));
	else return static_cast<uint64_t>(value);
}

std::string Quote(const std::string& text)
{
	std::ostringstream out;
	out << '"';
	for (unsigned char c : text)
	{
		if (c == '\\' || c == '"') out << '\\' << char(c);
		else if (c < 32) out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << int(c) << std::dec;
		else out << char(c);
	}
	out << '"';
	return out.str();
}

std::string Hex(const std::vector<uint8_t>& bytes)
{
	std::ostringstream out;
	out << std::hex << std::setfill('0');
	for (uint8_t byte : bytes) out << std::setw(2) << unsigned(byte);
	return out.str();
}

void WriteBytes(const std::string& path, const std::vector<uint8_t>& bytes)
{
	Require(!std::ifstream(path, std::ios::binary).good(), "Artifact already exists: use a fresh output prefix");
	std::ofstream out(path, std::ios::binary);
	Require(bool(out), "Cannot open diagnostic artifact output");
	out.write(reinterpret_cast<const char*>(bytes.data()), static_cast<std::streamsize>(bytes.size()));
	out.close();
	Require(bool(out), "Could not write complete diagnostic artifact");
}

std::vector<uint8_t> CpuIndices(FGameTexture* source, int translation)
{
	auto buffer = source->GetTexture()->CreateTexBuffer(translation, CTF_Indexed);
	Require(buffer.mWidth == 16 && buffer.mHeight == 4 && buffer.mBuffer, "PF110 source must be the exact 16x4 indexed patch");
	return { buffer.mBuffer, buffer.mBuffer + 64 };
}

std::vector<uint8_t> BasePaletteBytes()
{
	std::vector<uint8_t> result;
	result.reserve(1024);
	for (int i = 0; i < 256; i++)
	{
		const auto color = GPalette.BaseColors[i];
		result.push_back(color.b);
		result.push_back(color.g);
		result.push_back(color.r);
		result.push_back(255);
	}
	return result;
}

std::vector<uint8_t> ReadImage(VulkanRenderDevice* fb, VkTextureImage* image, unsigned texelBytes)
{
	Require(image && image->Image && image->View, "Resident image/view missing");
	Require(image->Image->mipLevels >= 1 && image->Image->layerCount == 1, "Unexpected readback image shape");
	const size_t size = size_t(image->Image->width) * size_t(image->Image->height) * texelBytes;
	Require(size > 0 && size <= 1024 * 1024, "Diagnostic readback size is outside its bounded fixture");
	auto staging = BufferBuilder().Size(size)
		.Usage(VK_BUFFER_USAGE_TRANSFER_DST_BIT, VMA_MEMORY_USAGE_GPU_TO_CPU)
		.DebugName("PF110.Readback").Create(fb->GetDevice());
	auto commands = fb->GetCommands()->GetDrawCommands();
	const auto previousLayout = image->Layout;
	VkImageTransition().AddImage(image, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, false).Execute(commands);
	VkBufferImageCopy region = {};
	region.imageSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
	region.imageSubresource.layerCount = 1;
	region.imageExtent = { unsigned(image->Image->width), unsigned(image->Image->height), 1 };
	commands->copyImageToBuffer(image->Image->image, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, staging->buffer, 1, &region);
	VkImageTransition().AddImage(image, previousLayout, false).Execute(commands);
	// Normal submission publishes bindless writes and waits the owning draw fence.
	fb->GetCommands()->WaitForCommands(false);
	auto mapped = static_cast<const uint8_t*>(staging->Map(0, size));
	Require(mapped != nullptr, "Readback mapping failed");
	std::vector<uint8_t> result(mapped, mapped + size);
	staging->Unmap();
	return result;
}

// A separate production VkRenderState keeps diagnostic material/pipeline/view
// state out of the main renderer. Never call BeginFrame on shared RS buffers.
class DiagnosticRenderState : public VkRenderState
{
public:
	explicit DiagnosticRenderState(VulkanRenderDevice* fb) : VkRenderState(fb) { }
	FMaterialState BoundMaterial() const { return mMaterial; }
	int BoundTextureIndex() const { return mSurfaceUniforms.uTextureIndex; }
	SurfaceUniforms DrawUniforms = {};
	unsigned IndexedDraws = 0;
	void DoDrawIndexed(int dt, int index, int count, bool apply) override
	{
		VkRenderState::DoDrawIndexed(dt, index, count, apply);
		// Copy the exact uniforms used by the production draw, before Draw2D
		// resets its object/add colours. This is an observer, not an override.
		DrawUniforms = mSurfaceUniforms;
		IndexedDraws++;
	}
};

struct DiagnosticTarget
{
	VulkanRenderDevice* fb;
	VkTextureImage color, depth;
	explicit DiagnosticTarget(VulkanRenderDevice* device) : fb(device)
	{
		color.Image = ImageBuilder().Format(VK_FORMAT_R8G8B8A8_UNORM).Size(OutputWidth, OutputHeight)
			.Usage(VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT)
			.DebugName("PF110.OwnColor").Create(fb->GetDevice());
		color.View = ImageViewBuilder().Image(color.Image.get(), VK_FORMAT_R8G8B8A8_UNORM)
			.DebugName("PF110.OwnColorView").Create(fb->GetDevice());
		Require(fb->DepthStencilFormat != VK_FORMAT_UNDEFINED, "Device depth/stencil format unavailable");
		depth.Image = ImageBuilder().Format(fb->DepthStencilFormat).Size(OutputWidth, OutputHeight)
			.Usage(VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT)
			.DebugName("PF110.OwnDepth").Create(fb->GetDevice());
		depth.AspectMask = VK_IMAGE_ASPECT_DEPTH_BIT | VK_IMAGE_ASPECT_STENCIL_BIT;
		depth.View = ImageViewBuilder().Image(depth.Image.get(), fb->DepthStencilFormat, depth.AspectMask)
			.DebugName("PF110.OwnDepthView").Create(fb->GetDevice());
		VkImageTransition().AddImage(&color, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL, true)
			.AddImage(&depth, VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL, true)
			.Execute(fb->GetCommands()->GetDrawCommands());
	}
	~DiagnosticTarget()
	{
		// Including exception paths: defer native resource destruction to the
		// regular draw retirement list. The caller ends its render pass first.
		color.Reset(fb);
		depth.Reset(fb);
	}
};

struct RestoreMainBoundary
{
	VulkanRenderDevice* fb;
	bool savedMip;
	explicit RestoreMainBoundary(VulkanRenderDevice* device) : fb(device), savedMip(hw_2dmip)
	{
		fb->GetRenderState()->EndRenderPass();
		fb->GetCommands()->WaitForCommands(false);
	}
	~RestoreMainBoundary()
	{
		hw_2dmip = savedMip;
		auto buffers = fb->GetBuffers();
		fb->GetRenderState()->SetRenderTarget(&buffers->SceneColor, buffers->SceneDepthStencil.View.get(),
			buffers->GetWidth(), buffers->GetHeight(), VK_FORMAT_R16G16B16A16_SFLOAT, buffers->GetSceneSamples());
		fb->GetRenderState()->EndRenderPass(); // force all cached binds to be reapplied.
	}
};

struct RestoreTranslation
{
	FTranslationID id;
	FRemapTable* original;
	explicit RestoreTranslation(FTranslationID translation) : id(translation), original(GPalette.TranslationToTable(id)) { }
	~RestoreTranslation() { GPalette.UpdateTranslation(id, original); }
};

struct CaseIdentity
{
	FRendererResourceIdentity token;
	uint64_t image = 0, view = 0, paletteImage = 0, paletteView = 0;
	intptr_t remap = 0;
	int clamp = -1;
};

bool SameToken(const CaseIdentity& a, const CaseIdentity& b)
{
	return a.token.Index == b.token.Index && a.token.Generation == b.token.Generation && a.token.Epoch == b.token.Epoch;
}
}

// Only the integrator adds this explicit friend seam to the two renderer
// classes. The diagnostic never substitutes a descriptor producer or shader.
struct FIndexedMaterialDiagnosticAccess
{
	struct Inspection
	{
		VkHardwareTexture* owner = nullptr;
		VkTextureImage* indices = nullptr;
		VkTextureImage* palette = nullptr;
		CaseIdentity identity;
	};

	static Inspection Inspect(VulkanRenderDevice* fb, VkMaterial* material, const FMaterialState& state)
	{
		auto& entry = material->GetDescriptorEntry(state);
		MaterialLayerInfo* layer = nullptr;
		auto owner = static_cast<VkHardwareTexture*>(material->GetLayer(0, state.mTranslation, &layer));
		Require(owner && layer, "Actual material albedo owner missing");
		Inspection result;
		result.owner = owner;
		result.palette = entry.IndexedPalette.get();
		if (material->GetScaleFlags() & CTF_Indexed)
		{
			if (entry.remap)
			{
				auto& variants = entry.redIsAlpha ? owner->IndexedAlphaImages : owner->IndexedPaletteImages;
				auto found = variants.find(reinterpret_cast<const FRemapTable*>(entry.remap));
				Require(found != variants.end(), "Descriptor key has no existing resident indexed variant");
				result.indices = found->second.get();
			}
			else result.indices = entry.redIsAlpha ? &owner->mAlphaImage : &owner->mPaletteImage;
		}
		else result.indices = state.mPaletteMode ? (entry.redIsAlpha ? &owner->mAlphaImage : &owner->mPaletteImage) : &owner->mImage;
		Require(result.indices && result.indices->Image && result.indices->View, "Actual descriptor source image missing");
		result.identity.token = fb->GetDescriptorSetManager()->GetBindlessIdentity(entry.bindlessIndex);
		result.identity.image = Handle(result.indices->Image->image);
		result.identity.view = Handle(result.indices->View->view);
		result.identity.remap = entry.remap;
		result.identity.clamp = entry.clampmode;
		if (result.palette)
		{
			Require(result.palette->Image && result.palette->View, "Actual palette image missing");
			result.identity.paletteImage = Handle(result.palette->Image->image);
			result.identity.paletteView = Handle(result.palette->View->view);
		}
		return result;
	}

	static void ResetIndexedAsset(FGameTexture* source)
	{
		auto material = static_cast<VkMaterial*>(FMaterial::ValidateTexture(source, CTF_Indexed));
		Require(material != nullptr, "Valid diagnostic indexed material missing");
		material->DeleteDescriptors();
		auto owner = static_cast<VkHardwareTexture*>(material->GetLayer(0, 0));
		Require(owner != nullptr, "Valid diagnostic indexed owner missing");
		owner->Reset();
		Require(owner->IndexedPaletteImages.empty() && owner->IndexedAlphaImages.empty() && !owner->mPaletteImage.Image,
			"Indexed reset did not clear its scoped images");
	}

	static size_t DescriptorCount(VkMaterial* material) { return material->mDescriptorSets.size(); }

	struct RegistrySnapshot
	{
		size_t materialCount = 0, descriptorCount = 0;
		int hardwareTextureCount = 0, gameTextureCount = 0;
		std::vector<uint64_t> entries;
		bool operator==(const RegistrySnapshot& other) const
		{
			return materialCount == other.materialCount && descriptorCount == other.descriptorCount &&
				hardwareTextureCount == other.hardwareTextureCount && gameTextureCount == other.gameTextureCount && entries == other.entries;
		}
	};

	static RegistrySnapshot SnapshotExisting(VulkanRenderDevice* fb)
	{
		RegistrySnapshot result;
		const auto& materials = fb->GetDescriptorSetManager()->Materials;
		Require(materials.size() <= 65536, "Existing material registry exceeds bounded observer limit");
		result.materialCount = materials.size();
		result.hardwareTextureCount = fb->GetTextureManager()->GetHWTextureCount();
		result.gameTextureCount = TexMan.NumTextures();
		for (auto material : materials)
		{
			Require(material && material->mDescriptorSets.size() <= 256, "Existing descriptor cache exceeds bounded observer limit");
			result.entries.push_back(Handle(material));
			result.entries.push_back(material->mDescriptorSets.size());
			result.descriptorCount += material->mDescriptorSets.size();
			Require(result.descriptorCount <= 65536, "Existing descriptor registry exceeds bounded observer limit");
			for (const auto& entry : material->mDescriptorSets)
			{
				result.entries.push_back(static_cast<uint64_t>(entry.bindlessIndex));
				result.entries.push_back(static_cast<uint64_t>(entry.remap));
				result.entries.push_back(Handle(entry.IndexedPalette.get()));
			}
		}
		return result;
	}

	struct SoftwareCanvasObservation
	{
		VkMaterial* material = nullptr;
		VkHardwareTexture* owner = nullptr;
		VkTextureImage* palette = nullptr;
		uint64_t image = 0, view = 0, paletteImage = 0, paletteView = 0;
		uint64_t offset = 0, nativePitch = 0, producerPitch = 0;
		int width = 0, height = 0;
		std::vector<uint8_t> mappedBytes;
		std::vector<FRendererResourceIdentity> tokens;
	};

	static std::vector<SoftwareCanvasObservation> ObserveExistingSoftwareCanvases(VulkanRenderDevice* fb)
	{
		// The caller has ended the main pass and waited the normal draw fence.
		// Never validate a material, acquire a descriptor, call GetLayer, map an
		// image or manufacture an SWSceneDrawer producer inside this observer.
		std::vector<SoftwareCanvasObservation> result;
		for (auto material : fb->GetDescriptorSetManager()->Materials)
		{
			auto source = material->Source();
			if (!source || source->GetUseType() != ETextureType::SWCanvas) continue;
			Require(result.size() < 2, "More than two real rotating software canvases were found");
			Require(source->GetName().IsEmpty() && source->GetTexture() &&
				static_cast<FWrapperTexture*>(source->GetTexture())->GetColorFormat() == 0,
				"Existing SWCanvas must be the unnamed palette-format wrapper");
			Require(material->GetScaleFlags() == 0 && material->NumLayers() == 2 && material->GetShaderIndex() == SHADER_Paletted,
				"Existing software canvas must retain its actual two-layer material");
			MaterialLayerDiagnostic base, row;
			Require(material->GetLayerDiagnostic(0, base) && material->GetLayerDiagnostic(1, row) &&
				base.sourceTexture == source->GetTexture() && row.sourceTexture && base.scaleFlags == 0 && row.scaleFlags == 0,
				"Existing SWCanvas layer diagnostics must describe the wrapper and palette row");
			// Translation zero and scale zero select the existing default slots in
			// the public container; they cannot reserve a translated cache entry.
			auto owner = static_cast<VkHardwareTexture*>(base.sourceTexture->SystemTextures.GetHardwareTexture(0, base.scaleFlags));
			auto paletteOwner = static_cast<VkHardwareTexture*>(row.sourceTexture->SystemTextures.GetHardwareTexture(0, row.scaleFlags));
			Require(owner && paletteOwner && owner->mImage.Image && owner->mImage.View && owner->mappedSWFB && owner->mTexelsize == 1,
				"Existing software canvas must already own its mapped R8 image and view");
			Require(paletteOwner->mImage.Image && paletteOwner->mImage.View && owner->mImage.Layout == VK_IMAGE_LAYOUT_GENERAL &&
				paletteOwner->mImage.Layout == VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL,
				"Existing software base is GENERAL and its ordinary palette row is shader-readable");
			Require(owner->IndexedPaletteImages.empty() && owner->IndexedAlphaImages.empty() &&
				!owner->mPaletteImage.Image && !owner->mAlphaImage.Image,
				"Existing SWCanvas has no public-indexed auxiliary image or remap cache");
			Require(source->GetTexelWidth() == fb->GetWidth() && source->GetTexelHeight() == fb->GetHeight() &&
				owner->mImage.Image->width == fb->GetWidth() && owner->mImage.Image->height == fb->GetHeight() &&
				paletteOwner->mImage.Image->width == 256 && paletteOwner->mImage.Image->height == 1,
				"Existing software producer and palette have the actual screen and row dimensions");
			Require(!material->mDescriptorSets.empty(), "Real software canvas was never consumed by the renderer");
			SoftwareCanvasObservation observed;
			observed.material = material;
			observed.owner = owner;
			observed.palette = &paletteOwner->mImage;
			observed.width = owner->mImage.Image->width;
			observed.height = owner->mImage.Image->height;
			Require(observed.width > 0 && observed.height > 0 && size_t(observed.width) * size_t(observed.height) <= 1024 * 1024,
				"Existing software canvas is outside the bounded observer extent");
			for (const auto& entry : material->mDescriptorSets)
			{
				Require(!entry.IndexedPalette, "Real software descriptor must not own a public-indexed palette row");
				auto token = fb->GetDescriptorSetManager()->GetBindlessIdentity(entry.bindlessIndex);
				Require(token.IsSet() && token.Span == 2 && fb->GetDescriptorSetManager()->ValidateBindlessIdentity(token),
					"Existing software two-resource descriptor identity must be live");
				observed.tokens.push_back(token);
			}
			VkImageSubresource resource = {};
			resource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
			VkSubresourceLayout layout = {};
			vkGetImageSubresourceLayout(fb->GetDevice()->device, owner->mImage.Image->image, &resource, &layout);
			observed.offset = layout.offset;
			observed.nativePitch = layout.rowPitch;
			observed.producerPitch = owner->GetBufferPitch();
			Require(layout.offset == 0 && layout.rowPitch == observed.producerPitch && layout.rowPitch >= uint64_t(observed.width),
				"Actual mapped SWCanvas pitch and offset must match the existing producer");
			// The production allocation is HOST_VISIBLE|HOST_COHERENT. Read only
			// its already mapped bytes after the fence, without host writes, map,
			// invalidation, transition or transfer copy of the sampled-only image.
			for (int y = 0; y < observed.height; y++)
			{
				const auto begin = owner->mappedSWFB + size_t(y) * size_t(layout.rowPitch);
				observed.mappedBytes.insert(observed.mappedBytes.end(), begin, begin + observed.width);
			}
			observed.image = Handle(owner->mImage.Image->image);
			observed.view = Handle(owner->mImage.View->view);
			observed.paletteImage = Handle(observed.palette->Image->image);
			observed.paletteView = Handle(observed.palette->View->view);
			result.push_back(std::move(observed));
		}
		return result;
	}

	static std::string MappedLayoutPreflight(VulkanRenderDevice* fb)
	{
		// Query a diagnostic allocation through the actual allocation method.
		// This is not an observed SWSceneDrawer producer or software scene.
		// No host pixels are written, sampled or transfer-copied here.
		std::ostringstream out;
		out << '[';
		for (int texelBytes : { 1, 4 })
		{
			VkHardwareTexture owner(fb, texelBytes);
			owner.AllocateBuffer(640, 480, texelBytes);
			fb->GetCommands()->WaitForCommands(false);
			auto& image = owner.mImage;
			VkImageSubresource resource = {};
			resource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
			VkSubresourceLayout layout = {};
			vkGetImageSubresourceLayout(fb->GetDevice()->device, image.Image->image, &resource, &layout);
			const bool mapped = owner.MapBuffer() != nullptr;
			const auto producerPitch = uint64_t(owner.GetBufferPitch()) * texelBytes;
			const bool coherent = mapped && image.Layout == VK_IMAGE_LAYOUT_GENERAL &&
				layout.offset == 0 && layout.rowPitch == producerPitch;
			if (texelBytes != 1) out << ',';
			out << "{\"width\":640,\"height\":480,\"texelBytes\":" << texelBytes
				<< ",\"trackedImageLayout\":" << int(image.Layout) << ",\"mapped\":" << (mapped ? "true" : "false")
				<< ",\"observationalAllocationOnly\":true,\"hostPixelsWritten\":false,\"actualSoftwareProducer\":false"
				<< ",\"nativeOffsetBytes\":" << layout.offset << ",\"nativeRowPitchBytes\":" << layout.rowPitch
				<< ",\"producerPitchBytes\":" << producerPitch << ",\"coherent\":" << (coherent ? "true" : "false") << '}';
			owner.Reset();
			fb->GetCommands()->WaitForCommands(false);
		}
		out << ']';
		return out.str();
	}
};

namespace
{
enum class DrawControl { Standard, PublicAlphaHalf, PublicColour, ShaderObjectAdd };

struct DiagnosticRun
{
	VulkanRenderDevice* fb;
	std::string prefix;
	std::vector<std::string> cases;
	std::vector<std::string> checks;
	unsigned assertions = 0;
	std::string mappedLayoutPreflight = "[]";
	std::string softwareCanvas = "{\"required\":false,\"observed\":false}";
	std::array<FRendererResourceIdentity, 2> pairedRestartTokens = {};

	void Check(bool value, const char* explanation)
	{
		std::ostringstream out;
		out << "{\"name\":" << Quote(explanation) << ",\"pass\":" << (value ? "true" : "false") << '}';
		checks.push_back(out.str());
		assertions++;
		Require(value, explanation);
	}

	CaseIdentity Draw(const char* name, FGameTexture* source, int translation, bool inverse = false,
		bool offGrid = false, bool indexed = true, bool retireBeforeWait = false, DrawControl control = DrawControl::Standard)
	{
		const std::vector<uint8_t> input = CpuIndices(source, 0);
		const std::vector<uint8_t> expectedIndices = CpuIndices(source, translation);
		const auto expectedPalette = BasePaletteBytes();
		const auto queuedBefore = fb->GetTextureManager()->GetAsyncUploadStats().JobsQueued;
		DiagnosticTarget target(fb);
		DiagnosticRenderState state(fb);
		struct EndPass { DiagnosticRenderState& state; ~EndPass() { state.EndRenderPass(); } } endPass{ state };
		state.EnableDrawBuffers(1, true);
		state.SetRenderTarget(&target.color, target.depth.View.get(), OutputWidth, OutputHeight,
			VK_FORMAT_R8G8B8A8_UNORM, VK_SAMPLE_COUNT_1_BIT);
		state.Clear(CT_Color | CT_Depth | CT_Stencil);
		F2DDrawer drawer;
		drawer.Begin(OutputWidth, OutputHeight);
		const double left = offGrid ? .25 : 0;
		const double width = offGrid ? 127.5 : OutputWidth;
		FRenderStyle style = DefaultRenderStyle();
		if (inverse) style.AsDWORD = 0x12030201; // Add/Src/InvSrc, Alpha1 + InvertSource.
		const double publicAlpha = control == DrawControl::PublicAlphaHalf ? .5 : 1.;
		const uint32_t publicColour = control == DrawControl::PublicColour ? 0xff80c0ffu : 0xffffffffu;
		if (control == DrawControl::PublicAlphaHalf) style = LegacyRenderStyles[STYLE_Translucent];
		if (control == DrawControl::ShaderObjectAdd)
		{
			// Actual render-state uniforms, not DTA_Color: the production
			// getTexel applies additive/object colour to R8 before palette lookup.
			state.SetAddColor(PalEntry(0, 16, 0, 0));
			state.SetObjectColor(PalEntry(255, 128, 255, 255));
		}
		DrawTexture(&drawer, source, left, 0., DTA_Indexed, int(indexed),
			DTA_TranslationIndex, translation, DTA_DestWidthF, width, DTA_DestHeightF, double(OutputHeight),
			DTA_TopOffset, 0, DTA_LeftOffset, 0, DTA_Masked, 0, DTA_RenderStyle, int(style.AsDWORD),
			DTA_Alpha, publicAlpha, DTA_Color, int(publicColour), TAG_DONE);
		Check(drawer.mData.Size() == 1, "real tag parser emits exactly one fixture draw");
		Check(bool(drawer.mData[0].mFlags & F2DDrawer::DTF_Indexed) == indexed, "real tag parser retains indexed classification");
		bool whiteVertexColour = true;
		for (const auto& vertex : drawer.mVertices) whiteVertexColour = whiteVertexColour && vertex.color0.d == 0xffffffffu;
		const int commandLightLevel = indexed ? drawer.mData[0].mLightLevel : -1;
		if (control == DrawControl::PublicAlphaHalf || control == DrawControl::PublicColour)
		{
			Check(whiteVertexColour && drawer.mVertices.Size() == 4,
				"public indexed alpha/colour tags retain the inherited white RGBA vertex result");
			Check(commandLightLevel == PalEntry(publicColour).Luminance(),
				"public indexed colour tag is represented by command luminance rather than object tint");
			if (control == DrawControl::PublicAlphaHalf) Check(!(drawer.mData[0].mRenderStyle.Flags & STYLEF_Alpha1),
				"half-alpha control uses the actual translucent style without forced Alpha1");
		}
		if (inverse) Check(drawer.mData[0].mDrawMode == TM_INVERTOPAQUE, "actual inverse style reaches getTexel inversion");
		::Draw2D(&drawer, state, 0, 0, OutputWidth, OutputHeight);
		state.EndRenderPass();
		drawer.End();
		if (control == DrawControl::ShaderObjectAdd)
		{
			const auto& uniforms = state.DrawUniforms;
			Check(state.IndexedDraws == 1 && std::abs(uniforms.uAddColor.X - 16.f / 255.f) < 1.e-7f &&
				std::abs(uniforms.uObjectColor.X - 128.f / 255.f) < 1.e-7f && uniforms.uObjectColor.W == 1.f &&
				uniforms.uObjectColor2.W == 0.f && uniforms.uDesaturationFactor == 0.f && uniforms.uTextureAddColor.W == 0.f,
				"actual submitted getTexel uniforms contain bounded additive/object colour without another manipulation");
		}
		const auto actualState = state.BoundMaterial();
		auto material = static_cast<VkMaterial*>(actualState.mMaterial);
		Check(material && material->Source() == source, "real Draw2D binds the exact diagnostic source");
		Check(material->GetShaderIndex() == (indexed ? SHADER_Paletted : SHADER_Default), "real material selects expected production shader");
		Check(actualState.mOverrideShader == -1 && actualState.globalShaderAddr.type == 3 &&
			actualState.globalShaderAddr.num == 0 && actualState.globalShaderAddr.name == 0 && !actualState.mPaletteMode,
			"fixed shader-output oracle has no global shader or software-colormap substitution");
		auto inspection = FIndexedMaterialDiagnosticAccess::Inspect(fb, material, actualState);
		const auto identity = inspection.identity;
		const auto expectedSpan = indexed ? 2u : static_cast<unsigned>(material->NumLayers());
		Check(identity.token.IsSet() && identity.token.Span == expectedSpan, "actual bindless block has the shader-required span");
		Check(identity.token.Index == state.BoundTextureIndex(), "actual shader texture index equals inspected descriptor entry");
		Check(fb->GetDescriptorSetManager()->ValidateBindlessIdentity(identity.token), "actual bindless token is live before publication");
		Check(inspection.indices->Layout == VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL, "resident source is shader-readable before any diagnostic copy");
		if (indexed)
		{
			Check(inspection.palette && inspection.palette->Layout == VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL,
				"actual second binding is a shader-readable palette row");
			Check(inspection.indices->Image->mipLevels == 1 && inspection.palette->Image->mipLevels == 1,
				"index and palette resources use one mip");
			Check(fb->GetTextureManager()->GetAsyncUploadStats().JobsQueued == queuedBefore,
				"indexed resident content does not queue a deferred numeric-ID upload");
		}
		std::vector<uint8_t> indices, palette;
		uintptr_t retireList = 0;
		if (retireBeforeWait)
		{
			// Preserve native object pointers before entry/vector destruction. Test
			// that the queued draw still owns both images until its fence is waited.
			auto oldIndexImage = inspection.indices->Image.get();
			auto oldIndexView = inspection.indices->View.get();
			auto oldPaletteImage = inspection.palette->Image.get();
			auto oldPaletteView = inspection.palette->View.get();
			auto& list = *fb->GetCommands()->DrawDeleteList;
			// CFX resource IDs are zero when tracing is disabled. The list itself
			// remains the authoritative owner; do not require a trace campaign.
			retireList = reinterpret_cast<uintptr_t>(&list);
			FIndexedMaterialDiagnosticAccess::ResetIndexedAsset(source);
			Check(!fb->GetDescriptorSetManager()->ValidateBindlessIdentity(identity.token), "retired descriptor token is rejected before reuse");
			Check(std::any_of(list.Images.begin(), list.Images.end(), [=](const auto& p) { return p.get() == oldIndexImage; }) &&
				std::any_of(list.Images.begin(), list.Images.end(), [=](const auto& p) { return p.get() == oldPaletteImage; }),
				"queued draw images are held in the owning retirement list before its fence");
			Check(std::any_of(list.ImageViews.begin(), list.ImageViews.end(), [=](const auto& p) { return p.get() == oldIndexView; }) &&
				std::any_of(list.ImageViews.begin(), list.ImageViews.end(), [=](const auto& p) { return p.get() == oldPaletteView; }),
				"queued draw views are held in the owning retirement list before its fence");
		}
		else
		{
			indices = ReadImage(fb, inspection.indices, indexed ? 1 : 4);
			if (indexed)
			{
				palette = ReadImage(fb, inspection.palette, 4);
				Check(indices == expectedIndices, "actual resident R8 bytes equal the immutable translation producer bytes");
				Check(palette == expectedPalette, "actual palette binding equals opaque current BaseColors bytes");
			}
		}
		auto pixels = ReadImage(fb, &target.color, 4);
		if (retireBeforeWait) Check(reinterpret_cast<uintptr_t>(fb->GetCommands()->DrawDeleteList.get()) != retireList &&
			fb->GetCommands()->DrawDeleteList->Images.empty() && fb->GetCommands()->DrawDeleteList->ImageViews.empty(),
			"owning draw retirement list releases only after the normal fence wait");
		unsigned mismatches = 0, changedPixels = 0, rejectedOrderingPixels = 0;
		if (indexed)
		{
			for (int y = 0; y < OutputHeight; y++) for (int x = 0; x < OutputWidth; x++)
			{
				const int sx = std::clamp(int(std::floor((x + .5 - left) * 16 / width)), 0, 15);
				uint8_t index = expectedIndices[sx];
				if (inverse) index = uint8_t(255 - index);
				if (control == DrawControl::ShaderObjectAdd)
					index = uint8_t(std::clamp(int(std::floor((int(index) + 16) * (128. / 255.) + .5)), 0, 255));
				const auto expected = GPalette.BaseColors[index];
				const auto* actual = &pixels[(y * OutputWidth + x) * 4];
				if (actual[0] != expected.r || actual[1] != expected.g || actual[2] != expected.b || actual[3] != 255) mismatches++;
				if (control == DrawControl::ShaderObjectAdd)
				{
					const auto neutral = GPalette.BaseColors[expectedIndices[sx]];
					if (actual[0] != neutral.r || actual[1] != neutral.g || actual[2] != neutral.b) changedPixels++;
					const auto beforeRemap = uint8_t(std::clamp(int(std::floor((int(input[sx]) + 16) * (128. / 255.) + .5)), 0, 255));
					const auto remap = GPalette.TranslationToTable(translation);
					const auto wrong = GPalette.BaseColors[remap && !remap->Inactive ? remap->Remap[beforeRemap] : beforeRemap];
					if (actual[0] != wrong.r || actual[1] != wrong.g || actual[2] != wrong.b) rejectedOrderingPixels++;
				}
			}
		}
		const auto stem = prefix + "-" + name;
		WriteBytes(stem + ".rgba8", pixels);
		WriteBytes(stem + ".input-r8", input);
		WriteBytes(stem + ".expected-r8", expectedIndices);
		WriteBytes(stem + ".basepalette-bgra8", expectedPalette);
		if (!indices.empty()) WriteBytes(stem + (indexed ? ".resident-r8" : ".resident-bgra8"), indices);
		if (!palette.empty()) WriteBytes(stem + ".resident-palette-bgra8", palette);
		std::ostringstream out;
		out << "{\"name\":" << Quote(name) << ",\"source\":" << Quote(source->GetName().GetChars())
			<< ",\"translation\":" << translation << ",\"indexed\":" << (indexed ? "true" : "false")
			<< ",\"inverse\":" << (inverse ? "true" : "false") << ",\"left\":" << left << ",\"destWidth\":" << width
			<< ",\"width\":128,\"height\":20,\"resultUnits\":\"raw VK_FORMAT_R8G8B8A8_UNORM bytes; no postprocess or sRGB transform\""
			<< ",\"actualTextureIndex\":" << state.BoundTextureIndex() << ",\"shaderIndex\":" << material->GetShaderIndex()
			<< ",\"actualTranslation\":" << actualState.mTranslation << ",\"overrideShader\":" << actualState.mOverrideShader
			<< ",\"token\":{\"index\":" << identity.token.Index << ",\"generation\":" << identity.token.Generation
			<< ",\"epoch\":" << identity.token.Epoch << ",\"span\":" << identity.token.Span << '}'
			<< ",\"canonicalRemapPointer\":" << Quote(std::to_string(uint64_t(identity.remap)))
			<< ",\"indexImage\":" << Quote(std::to_string(identity.image)) << ",\"indexView\":" << Quote(std::to_string(identity.view))
			<< ",\"paletteImage\":" << Quote(std::to_string(identity.paletteImage)) << ",\"paletteView\":" << Quote(std::to_string(identity.paletteView))
			<< ",\"resolvedClamp\":" << identity.clamp << ",\"queuedUploadDelta\":" << (fb->GetTextureManager()->GetAsyncUploadStats().JobsQueued - queuedBefore)
			<< ",\"retiredBeforeWait\":" << (retireBeforeWait ? "true" : "false")
			<< ",\"control\":" << Quote(control == DrawControl::PublicAlphaHalf ? "public-alpha-half-inherited-opaque" :
				control == DrawControl::PublicColour ? "public-colour-command-luminance-white-vertex" :
				control == DrawControl::ShaderObjectAdd ? "actual-getTexel-add-object-before-palette" : "standard")
			<< ",\"publicAlpha\":" << publicAlpha << ",\"publicColor\":" << uint64_t(publicColour)
			<< ",\"whiteVertexColour\":" << (whiteVertexColour ? "true" : "false") << ",\"commandLightLevel\":" << commandLightLevel
			<< ",\"addRedByte\":" << (control == DrawControl::ShaderObjectAdd ? 16 : 0)
			<< ",\"objectRedByte\":" << (control == DrawControl::ShaderObjectAdd ? 128 : 255)
			<< ",\"changedPixels\":" << changedPixels << ",\"rejectedOrderingPixels\":" << rejectedOrderingPixels
			<< ",\"pixelMismatches\":" << mismatches << ",\"pixelOracleApplied\":" << (indexed ? "true" : "false")
			<< ",\"artifactStem\":" << Quote(stem) << ",\"rgbaBytes\":" << pixels.size()
			<< ",\"cpuInputHex\":" << Quote(Hex(input)) << ",\"cpuExpectedIndicesHex\":" << Quote(Hex(expectedIndices))
			<< ",\"residentIndicesHex\":" << Quote(Hex(indices)) << ",\"residentPaletteBgraHex\":" << Quote(Hex(palette)) << '}';
		cases.push_back(out.str());
		if (indexed) Check(mismatches == 0, "actual production paletted shader output matches BaseColors after remap and style");
		if (control == DrawControl::ShaderObjectAdd) Check(changedPixels > 0 && rejectedOrderingPixels > 0,
			"actual shader colour result differs from neutral colour and rejected manipulation-before-remap order");
		return identity;
	}

	void ObserveSoftwareCanvas()
	{
		if (int(vid_rendermode) != 0)
		{
			softwareCanvas = "{\"required\":false,\"observed\":false,\"actualMode\":" + std::to_string(int(vid_rendermode)) +
				",\"reason\":\"actual renderer mode is not software palette mode\"}";
			return;
		}
		// RestoreMainBoundary has already ended the main pass and waited its
		// ordinary fence. Observe the producer that rendered preceding frames.
		const auto before = FIndexedMaterialDiagnosticAccess::SnapshotExisting(fb);
		const auto observed = FIndexedMaterialDiagnosticAccess::ObserveExistingSoftwareCanvases(fb);
		Check(observed.size() == 2, "actual software mode requires both existing rotating SWCanvas producers");
		Check(FIndexedMaterialDiagnosticAccess::SnapshotExisting(fb) == before,
			"software observation creates no material, texture or descriptor cache entry");
		std::vector<std::string> records;
		for (size_t i = 0; i < observed.size(); i++)
		{
			const auto& canvas = observed[i];
			// The SW base has sampled-only usage: never transition or transfer
			// read it. The existing ordinary palette upload supports readback.
			const auto palette = ReadImage(fb, canvas.palette, 4);
			Check(palette == BasePaletteBytes(), "real SWCanvas palette row retains complete opaque BaseColors bytes");
			Check(canvas.palette->Layout == VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL,
				"software palette readback restores its tracked shader-readable layout");
			const auto stem = prefix + "-software-existing-swcanvas-" + std::to_string(i);
			WriteBytes(stem + ".mapped-r8", canvas.mappedBytes);
			WriteBytes(stem + ".resident-palette-bgra8", palette);
			std::ostringstream row;
			row << "{\"ownerPointer\":" << Quote(std::to_string(Handle(canvas.owner)))
				<< ",\"materialPointer\":" << Quote(std::to_string(Handle(canvas.material)))
				<< ",\"sourceName\":\"\",\"sourceScaleFlags\":0,\"wrapperColorFormat\":0,\"layerCount\":2"
				<< ",\"width\":" << canvas.width << ",\"height\":" << canvas.height
				<< ",\"indexImage\":" << Quote(std::to_string(canvas.image)) << ",\"indexView\":" << Quote(std::to_string(canvas.view))
				<< ",\"paletteImage\":" << Quote(std::to_string(canvas.paletteImage)) << ",\"paletteView\":" << Quote(std::to_string(canvas.paletteView))
				<< ",\"trackedBaseLayout\":" << int(VK_IMAGE_LAYOUT_GENERAL)
				<< ",\"trackedPaletteLayout\":" << int(canvas.palette->Layout)
				<< ",\"nativeOffsetBytes\":" << canvas.offset << ",\"nativeRowPitchBytes\":" << canvas.nativePitch
				<< ",\"producerPitchBytes\":" << canvas.producerPitch << ",\"pitchMatchesProducer\":true"
				<< ",\"mappedReadAfterNormalFence\":true,\"mappedImageTransferred\":false,\"indexedAuxiliaryImagesAbsent\":true"
				<< ",\"indexedPaletteDescriptorAbsent\":true,\"artifactStem\":" << Quote(stem)
				<< ",\"mappedBytes\":" << canvas.mappedBytes.size() << ",\"paletteBytes\":" << palette.size()
				<< ",\"tokens\":[";
			for (size_t j = 0; j < canvas.tokens.size(); j++)
			{
				if (j) row << ',';
				const auto& token = canvas.tokens[j];
				row << "{\"index\":" << token.Index << ",\"generation\":" << token.Generation
					<< ",\"epoch\":" << token.Epoch << ",\"span\":" << token.Span << ",\"live\":true}";
			}
			row << "]}";
			records.push_back(row.str());
		}
		const auto after = FIndexedMaterialDiagnosticAccess::SnapshotExisting(fb);
		Check(after == before, "software readback leaves existing material, texture and descriptor cache state unchanged");
		auto counts = [](const FIndexedMaterialDiagnosticAccess::RegistrySnapshot& snapshot)
		{
			std::ostringstream out;
			out << "{\"materials\":" << snapshot.materialCount << ",\"hardwareTextures\":" << snapshot.hardwareTextureCount
				<< ",\"gameTextures\":" << snapshot.gameTextureCount << ",\"descriptorEntries\":" << snapshot.descriptorCount << '}';
			return out.str();
		};
		std::ostringstream out;
		out << "{\"required\":true,\"observed\":true,\"actualMode\":0,\"ownerCount\":" << observed.size()
			<< ",\"registryUnchanged\":true,\"hostPixelsWritten\":false,\"producerCreationPerformed\":false"
			<< ",\"softwareDrawPerformedByDiagnostic\":false,\"before\":" << counts(before) << ",\"after\":" << counts(after)
			<< ",\"mappedMemoryContract\":\"existing production HOST_VISIBLE|HOST_COHERENT allocation; allocation flags not independently queried\""
			<< ",\"records\":[";
		for (size_t i = 0; i < records.size(); i++) { if (i) out << ','; out << records[i]; }
		out << "]}";
		softwareCanvas = out.str();
		cases.push_back("{\"name\":\"software-existing-swcanvas\",\"descriptorOnly\":true,\"shaderResultClaimed\":false,\"observerOnly\":true," + softwareCanvas.substr(1));
	}

	void Execute(bool retainForRestart = false)
	{
		Check(fb->GetBuffers()->GetWidth() > 0 && fb->GetBuffers()->GetHeight() > 0, "renderer frame resources are initialized");
		auto rs = fb->GetBufferManager()->GetRSBuffers();
		Check(rs && rs->Viewpoint.Data && rs->Viewpoint.Count - rs->Viewpoint.UploadIndex >= 64,
			"bounded diagnostic has initialized viewpoint capacity without resetting shared frame buffers");
		FGameTexture* source = TexMan.GetGameTextureByName("PF110SRC");
		FGameTexture* sourceA = TexMan.GetGameTextureByName("PF110SA");
		FGameTexture* sourceB = TexMan.GetGameTextureByName("PF110SB");
		Check(source && sourceA && sourceB && source->isValid() && sourceA->isValid() && sourceB->isValid(), "exact PF110 source assets are loaded");
		Check(source->GetTexture() != sourceA->GetTexture() && sourceA->GetTexture() != sourceB->GetTexture() &&
			source->GetTexture() != sourceB->GetTexture(), "first-use aliases are independent real source owners");
		std::vector<uint8_t> expectedSource;
		for (int y = 0; y < 4; y++) expectedSource.insert(expectedSource.end(), SourceRow.begin(), SourceRow.end());
		Check(CpuIndices(source, 0) == expectedSource && CpuIndices(sourceA, 0) == expectedSource && CpuIndices(sourceB, 0) == expectedSource,
			"all independent fixture aliases retain exact known source index bytes");
		const auto idA = R_FindCustomTranslation(FName("PF110_A"));
		const auto idB = R_FindCustomTranslation(FName("PF110_B"));
		Check(idA.isvalid() && idA.index() > 0 && idB.isvalid() && idB.index() > 0 && idA != idB, "actual named translations are registered");
		auto remapA = GPalette.TranslationToTable(idA);
		auto remapB = GPalette.TranslationToTable(idB);
		Check(remapA && remapB && remapA != remapB && !remapA->Inactive && !remapB->Inactive, "named translations have distinct active canonical owners");
		Check(remapA->Remap[5] == 10 && remapA->Remap[250] == 20 && remapB->Remap[5] == 96 && remapB->Remap[250] == 160,
			"actual fixture translations distinguish both original and inverse witnesses");
		const std::array<uint8_t, 16> rowA = { 10, 10, 20, 20, 32, 32, 200, 200, 160, 160, 96, 96, 200, 200, 32, 32 };
		const std::array<uint8_t, 16> rowB = { 96, 96, 160, 160, 200, 200, 32, 32, 20, 20, 10, 10, 5, 5, 250, 250 };
		std::vector<uint8_t> bytesA, bytesB;
		for (int y = 0; y < 4; y++)
		{
			bytesA.insert(bytesA.end(), rowA.begin(), rowA.end());
			bytesB.insert(bytesB.end(), rowB.begin(), rowB.end());
		}
		Check(CpuIndices(source, idA.index()) == bytesA && CpuIndices(source, idB.index()) == bytesB,
			"complete authored A/B translation rows equal the actual indexed producer");
		RestoreMainBoundary boundary(fb);
		ObserveSoftwareCanvas();
		mappedLayoutPreflight = FIndexedMaterialDiagnosticAccess::MappedLayoutPreflight(fb);
		RestoreTranslation restoreA(idA);
		for (auto asset : { source, sourceA, sourceB }) FIndexedMaterialDiagnosticAccess::ResetIndexedAsset(asset);
		hw_2dmip = true;
		Draw("default", source, 0);
		const auto a0 = Draw("a-first", sourceA, idA.index());
		const auto b0 = Draw("b-after-a", sourceA, idB.index());
		const auto a1 = Draw("a-return", sourceA, idA.index());
		const auto b1 = Draw("b-return", sourceA, idB.index());
		const auto a2 = Draw("a-return-again", sourceA, idA.index());
		Check(a0.image != b0.image && !SameToken(a0, b0), "A and B retain distinct image and descriptor identities on one forced indexed owner");
		Check(a0.image == a1.image && a0.image == a2.image && SameToken(a0, a1) && SameToken(a0, a2) &&
			b0.image == b1.image && SameToken(b0, b1), "A/B/A/B/A reuses exact canonical image and descriptor state");
		const auto bb0 = Draw("b-first", sourceB, idB.index());
		const auto aa0 = Draw("a-after-b", sourceB, idA.index());
		const auto bb1 = Draw("b-first-return", sourceB, idB.index());
		Check(bb0.image != aa0.image && bb0.image == bb1.image && SameToken(bb0, bb1), "B/A/B first-use order retains equivalent cache semantics");
		// Values only: both blocks already have actual R8/row/result readbacks.
		pairedRestartTokens = { bb0.token, aa0.token };
		Draw("inverse-a", source, idA.index(), true);
		Draw("inverse-b", source, idB.index(), true);
		Draw("off-grid", source, idA.index(), false, true);
		hw_2dmip = false;
		const auto noMip = Draw("xy-nomip", source, idA.index(), false, true);
		Check(noMip.clamp == CLAMP_NOFILTER_XY, "public XY_NOMIP indexed route normalizes to nearest clamped sampler");
		hw_2dmip = true;
		GPalette.UpdateTranslation(idA, remapB);
		const auto replacement = Draw("same-id-replaced-b", sourceA, idA.index());
		Check(replacement.image == b0.image && SameToken(replacement, b0), "same numeric ID replacement selects its current canonical B content");
		GPalette.UpdateTranslation(idA, remapA);
		const auto restored = Draw("same-id-restored-a", sourceA, idA.index());
		Check(restored.image == a0.image && SameToken(restored, a0), "restoring numeric ID recovers canonical A content");
		Draw("nonpositive", source, -1);
		Draw("invalid-translation", source, 0x00ff1234);
		Draw("luminosity-unremapped", source, MakeLuminosityTranslation(1, 0, 255).index());
		FRemapTable inactive = *remapA;
		inactive.Inactive = true;
		GPalette.UpdateTranslation(idA, &inactive);
		Draw("inactive-unremapped", source, idA.index());
		GPalette.UpdateTranslation(idA, remapA);
		const auto retired = Draw("retire-queued-draw", sourceA, idA.index(), false, false, true, true);
		const auto recreated = Draw("recreated-after-retirement", sourceA, idA.index());
		Check(!SameToken(retired, recreated), "recreated material block never reuses the retired PF token");
		Draw("ordinary-control", source, 0, false, false, false);
		Draw("indexed-alpha-half-opaque", source, idA.index(), false, false, true, false, DrawControl::PublicAlphaHalf);
		Draw("indexed-colour-tag", source, idA.index(), false, false, true, false, DrawControl::PublicColour);
		Draw("indexed-object-add-colour", source, idA.index(), false, false, true, false, DrawControl::ShaderObjectAdd);
		// Distinct inherited state-driven palette/RedIsAlpha paths: retain their
		// real resident producer bytes and descriptor state, without presenting
		// these descriptor-only controls as a software-colormap shader draw.
		auto ordinaryMaterial = static_cast<VkMaterial*>(FMaterial::ValidateTexture(source, 0));
		FMaterialState paletteState;
		paletteState.mMaterial = ordinaryMaterial;
		paletteState.mClampMode = CLAMP_XY_NOMIP;
		paletteState.mPaletteMode = true;
		const auto paletteIndex = FIndexedMaterialDiagnosticAccess::Inspect(fb, ordinaryMaterial, paletteState);
		const auto indexBytes = ReadImage(fb, paletteIndex.indices, 1);
		Check(!paletteIndex.palette && paletteIndex.identity.token.Span == static_cast<unsigned>(ordinaryMaterial->NumLayers()) && indexBytes == expectedSource,
			"ordinary state-driven palette descriptor retains its separate R8 index contract");
		paletteState.mRedIsAlpha = true;
		const auto paletteAlpha = FIndexedMaterialDiagnosticAccess::Inspect(fb, ordinaryMaterial, paletteState);
		const auto alphaBytes = ReadImage(fb, paletteAlpha.indices, 1);
		auto cpuAlpha = source->GetTexture()->CreateTexBuffer(0, CTF_IndexedRedIsAlpha);
		Check(cpuAlpha.mWidth == 16 && cpuAlpha.mHeight == 4 && cpuAlpha.mBuffer,
			"ordinary RedIsAlpha control has exact producer dimensions");
		const std::vector<uint8_t> expectedAlpha(cpuAlpha.mBuffer, cpuAlpha.mBuffer + 64);
		Check(!paletteAlpha.palette && paletteAlpha.identity.token.Span == static_cast<unsigned>(ordinaryMaterial->NumLayers()) && alphaBytes == expectedAlpha &&
			paletteAlpha.identity.image != paletteIndex.identity.image && !SameToken(paletteAlpha.identity, paletteIndex.identity),
			"ordinary palette-index and RedIsAlpha interpretations retain separate images and descriptors");
		WriteBytes(prefix + "-ordinary-palette.resident-r8", indexBytes);
		WriteBytes(prefix + "-ordinary-alpha.resident-r8", alphaBytes);
		WriteBytes(prefix + "-ordinary-alpha.expected-r8", expectedAlpha);
		std::ostringstream paletteControls;
		paletteControls << "{\"name\":\"ordinary-palette-and-alpha-controls\",\"descriptorOnly\":true,\"shaderResultClaimed\":false,"
			<< "\"indexImage\":" << Quote(std::to_string(paletteIndex.identity.image))
			<< ",\"alphaImage\":" << Quote(std::to_string(paletteAlpha.identity.image))
			<< ",\"indexToken\":" << paletteIndex.identity.token.Index << ",\"alphaToken\":" << paletteAlpha.identity.token.Index
			<< ",\"indexClamp\":" << paletteIndex.identity.clamp << ",\"alphaClamp\":" << paletteAlpha.identity.clamp
			<< ",\"residentIndexHex\":" << Quote(Hex(indexBytes)) << ",\"residentAlphaHex\":" << Quote(Hex(alphaBytes)) << '}';
		cases.push_back(paletteControls.str());
		F2DDrawer missing;
		missing.Begin(OutputWidth, OutputHeight);
		DrawTexture(&missing, static_cast<FGameTexture*>(nullptr), 0., 0., DTA_Indexed, 1, TAG_DONE);
		Check(missing.mData.Size() == 0 && FMaterial::ValidateTexture(nullptr, CTF_Indexed) == nullptr,
			"public missing-input path emits no material or draw");
		missing.End();
		for (auto asset : { source, sourceA, sourceB })
			if (!retainForRestart || asset != sourceB) FIndexedMaterialDiagnosticAccess::ResetIndexedAsset(asset);
		fb->GetCommands()->WaitForCommands(false);
	}

	std::string Json(bool pass, const std::string& error) const
	{
		std::ostringstream out;
		out << "{\"schema\":\"shadedoomvk-pf110-native-indexed/v1\",\"status\":" << Quote(pass ? "PASS" : "FAIL")
			<< ",\"error\":" << Quote(error) << ",\"device\":" << Quote(fb->DeviceName())
			<< ",\"globalTextureFilter\":" << int(gl_texture_filter) << ",\"asyncTextures\":" << (gl_async_textures ? "true" : "false")
			<< ",\"rendererMode\":" << int(vid_rendermode)
			<< ",\"depthStencilFormat\":" << int(fb->DepthStencilFormat) << ",\"assertions\":" << assertions
			<< ",\"mappedLayoutPreflight\":" << mappedLayoutPreflight
			<< ",\"softwareCanvas\":" << softwareCanvas
			<< ",\"scope\":\"explicit command, actual production DrawTexture/Draw2D/material/shader and native resident/result readbacks\""
			<< ",\"limitations\":[\"not a performance measurement\",\"external runner must verify exact executable/source/config, layer activation and process exit\","
			<< "\"ordinary result retained as a control, not compared to the indexed palette equation\","
			<< "\"palette-arena restart remains a separate production-linked fixture/runner control\","
			<< "\"SWCanvas mode0 observes pre-existing producer state and mapped bytes; no diagnostic software draw or image-result equivalence claimed\","
			<< "\"public indexed DTA_Alpha and DTA_Color retain inherited white vertices and opaque palette results; neither tag is an object-uniform tint claim\"]"
			<< ",\"cases\":[";
		for (size_t i = 0; i < cases.size(); i++) { if (i) out << ','; out << cases[i]; }
		out << "],\"checks\":[";
		for (size_t i = 0; i < checks.size(); i++) { if (i) out << ','; out << checks[i]; }
		out << "]}\n";
		return out.str();
	}
};
}

CCMD(pf_indexedmaterial_validate)
{
	if (argv.argc() != 2 || !argv[1][0])
	{
		Printf("Usage: pf_indexedmaterial_validate <fresh-existing-directory/output-prefix>\n");
		return;
	}
	if (!screen || !screen->IsVulkan())
	{
		Printf("PF110 FAIL: an initialized Vulkan backend is required; no GPU work performed.\n");
		return;
	}
	const std::string prefix = argv[1];
	if (std::ifstream(prefix + ".json", std::ios::binary).good())
	{
		Printf("PF110 FAIL: output already exists; use a fresh immutable prefix.\n");
		return;
	}
	std::ofstream receipt(prefix + ".json", std::ios::binary);
	if (!receipt) { Printf("PF110 FAIL: cannot create output receipt; no GPU work performed.\n"); return; }
	DiagnosticRun run{ static_cast<VulkanRenderDevice*>(screen), prefix, {}, {}, 0, "[]", "{\"required\":false,\"observed\":false}" };
	bool pass = false;
	std::string error;
	try { run.Execute(); pass = true; }
	catch (const std::exception& e) { error = e.what(); }
	const auto json = run.Json(pass, error);
	receipt.write(json.data(), static_cast<std::streamsize>(json.size()));
	receipt.close();
	if (!receipt) { pass = false; error = "receipt write failed"; }
	Printf("PF110 %s: %u assertions, %u retained cases; %s%s%s\n", pass ? "PASS" : "FAIL", run.assertions,
		unsigned(run.cases.size()), (prefix + ".json").c_str(), error.empty() ? "" : "; ", error.c_str());
}

namespace
{
constexpr unsigned RestartSchemaVersion = 1;
constexpr const char* RestartSchema = "shadedoomvk-pf110-indexed-restart/v1";
enum class RestartPhase { Empty, Armed, Consumed, Complete, Failed };

// Survives D_Cleanup, but never owns or dereferences a former arena/resource.
// A Span2 token identifies the actual index+palette descriptor block; no
// independent palette-slot token or address-inequality test is invented.
struct RestartCheckpoint
{
	RestartPhase phase = RestartPhase::Empty;
	unsigned schemaVersion = RestartSchemaVersion;
	std::string beforePrefix, afterPrefix, iwad, mod, afterExec;
	int counter = -1, rendererMode = -1, globalFilter = -1;
	uint64_t managerIdentity = 0, deviceIdentity = 0, framebufferIdentity = 0;
	std::array<FRendererResourceIdentity, 2> tokens = {};
	FRendererLifetimeStats lifetime = {};
};
static RestartCheckpoint RestartState;

std::string TrimRestartText(std::string text)
{
	const auto first = text.find_first_not_of(" \t\r\n");
	if (first == std::string::npos) return {};
	const auto last = text.find_last_not_of(" \t\r\n");
	return text.substr(first, last - first + 1);
}

std::string RestartPath(const std::string& path)
{
	Require(!path.empty() && path.size() <= 1024 && path[0] != '+' && path[0] != '-', "restart path must be a bounded filename, not an option");
	Require(std::all_of(path.begin(), path.end(), [](unsigned char c) { return c >= 32 && c < 127 && c != '"' && c != ';'; }),
		"restart paths must be printable ASCII without console separators or quotes");
	std::string normalized = path;
	std::replace(normalized.begin(), normalized.end(), '\\', '/');
	Require(normalized[0] == '/' || (normalized.size() > 2 && normalized[1] == ':' && normalized[2] == '/'), "restart paths must be absolute");
	return normalized;
}

std::string RestartQuoted(const std::string& path) { return "\"" + RestartPath(path) + "\""; }

void FreshRestartPrefix(const std::string& prefix)
{
	const auto normalized = RestartPath(prefix);
	const auto slash = normalized.find_last_of('/');
	Require(slash != std::string::npos && slash + 1 < normalized.size() && normalized.find("/../") == std::string::npos && normalized.find("/./") == std::string::npos,
		"restart prefix must name an absolute bounded artifact, not a directory or traversal");
	Require(DirExists(normalized.substr(0, slash + 1).c_str()), "restart receipt parent must already exist");
	for (const char* suffix : { ".json", ".restart-before.json", ".restart-after.json" })
		Require(!FileExists((normalized + suffix).c_str()), "native/restart receipt prefix must be fresh and immutable");
}

std::string ReadRestartScript(const std::string& path)
{
	std::ifstream in(RestartPath(path), std::ios::binary);
	Require(bool(in), "restart exec input must already exist");
	std::array<char, 16385> bytes = {};
	in.read(bytes.data(), std::streamsize(bytes.size()));
	const auto count = in.gcount();
	Require(count > 0 && count <= 16384, "restart exec input exceeds the bounded script size");
	std::string text(bytes.data(), size_t(count));
	while (!text.empty() && (text.back() == '\n' || text.back() == '\r')) text.pop_back();
	Require(text.find_first_of("\r\n\0", 0, 3) == std::string::npos, "restart exec input must be one physical command chain");
	return TrimRestartText(text);
}

std::vector<std::string> RestartCommands(const std::string& text)
{
	std::vector<std::string> commands;
	size_t offset = 0;
	while (offset <= text.size())
	{
		const auto end = text.find(';', offset);
		commands.push_back(TrimRestartText(text.substr(offset, end == std::string::npos ? end : end - offset)));
		Require(!commands.back().empty() && commands.size() <= 16, "restart exec chain has an empty or excess command");
		if (end == std::string::npos) break;
		offset = end + 1;
	}
	return commands;
}

bool RestartWait(const std::string& text, int minimum = 1)
{
	if (text.compare(0, 5, "wait ") != 0) return false;
	const auto value = text.substr(5);
	if (value.empty() || value.size() > 3 || !std::all_of(value.begin(), value.end(), [](unsigned char c) { return c >= '0' && c <= '9'; })) return false;
	const int ticks = std::stoi(value);
	return ticks >= minimum && ticks <= 140;
}

struct RestartArguments
{
	std::string iwad, mod, config, exec, map;
};

RestartArguments ReadRestartArguments()
{
	Require(Args && Args->NumArgs() >= 2 && Args->NumArgs() <= 32, "restart requires the bounded dedicated fixture command line");
	RestartArguments result;
	std::vector<std::string> seen;
	for (int i = 1; i < Args->NumArgs(); i++)
	{
		const std::string flag = Args->GetArg(i);
		Require(std::find(seen.begin(), seen.end(), flag) == seen.end(), "duplicate restart fixture option");
		seen.push_back(flag);
		if (flag == "-stdout" || flag == "-noautoload" || flag == "-noautoexec" || flag == "-nosound" || flag == "-nojoy") continue;
		Require(flag == "-iwad" || flag == "-file" || flag == "-config" || flag == "-width" || flag == "-height" || flag == "+exec" || flag == "+map",
			"unknown or unpinned restart fixture option");
		Require(i + 1 < Args->NumArgs(), "restart fixture option has no value");
		const std::string value = Args->GetArg(++i);
		Require(!value.empty() && value[0] != '+' && value[0] != '-', "restart fixture option has invalid arity");
		if (flag == "-width" || flag == "-height") Require(value == (flag == "-width" ? "640" : "480"), "restart fixture command extent must be 640x480");
		else if (flag == "+map") { Require(value == "PF110", "restart fixture must name only PF110"); result.map = value; }
		else
		{
			const auto path = RestartPath(value);
			Require(std::ifstream(path, std::ios::binary).good(), "pinned restart input does not exist");
			if (flag == "-iwad") result.iwad = path;
			else if (flag == "-file") result.mod = path;
			else if (flag == "-config") result.config = path;
			else result.exec = path;
		}
	}
	for (const char* flag : { "-stdout", "-noautoload", "-noautoexec", "-nosound", "-nojoy", "-iwad", "-file", "-config", "-width", "-height", "+exec" })
		Require(std::find(seen.begin(), seen.end(), flag) != seen.end(), "required isolated restart fixture option missing");
	return result;
}

void GuardRestartScripts(const RestartArguments& arguments, const std::string& beforePrefix, const std::string& afterPrefix, const std::string& afterExec)
{
	Require(arguments.exec != afterExec, "BEFORE and AFTER exec inputs must be independent");
	const auto before = RestartCommands(ReadRestartScript(arguments.exec));
	const auto terminal = "pf_indexedmaterial_restart_before " + RestartQuoted(beforePrefix) + " " + RestartQuoted(afterPrefix) + " " + RestartQuoted(afterExec);
	Require(before.size() >= 2 && before.back() == terminal, "BEFORE must end at the exact guarded command without restart/quit continuation");
	for (size_t i = 0; i + 1 < before.size(); i++)
		Require(RestartWait(before[i]) || before[i] == "vid_setsize 640 480", "BEFORE contains an extra exec, restart or uncontrolled command");
	const auto after = RestartCommands(ReadRestartScript(afterExec));
	Require(after.size() >= 7 && RestartWait(after[0], 35) && after[1] == "map PF110" && RestartWait(after[2], 105) &&
		after[3] == "vid_setsize 640 480" && RestartWait(after[4], 35) &&
		after[5] == "pf_indexedmaterial_restart_after " + RestartQuoted(afterPrefix) && after.back() == "quit",
		"AFTER must explicitly load/warm PF110, use the same prefix, and terminate");
	for (size_t i = 6; i + 1 < after.size(); i++)
	{
		if (RestartWait(after[i]) || after[i] == "pf110_overlay true") continue;
		FCommandLine command(after[i].c_str());
		Require(command.argc() == 2 && std::strcmp(command[0], "screenshot") == 0, "AFTER contains an extra exec, restart or uncontrolled command");
		RestartPath(command[1]);
	}
}

VulkanRenderDevice* RestartFramebuffer()
{
	Require(!UnsafeExecutionContext && !netgame && !multiplayer, "restart fixture requires safe local single-player command execution");
	Require(screen && screen->IsVulkan(), "restart fixture requires the initialized Vulkan backend");
	Require(gamestate == GS_LEVEL && primaryLevel && std::strcmp(primaryLevel->MapName.GetChars(), "PF110") == 0,
		"restart phase requires the actual explicitly loaded PF110 map");
	Require(screen->GetWidth() == 640 && screen->GetHeight() == 480, "restart phase requires actual native 640x480 extent");
	auto fb = static_cast<VulkanRenderDevice*>(screen);
	Require(fb->GetDevice() && fb->GetDescriptorSetManager(), "restart phase requires initialized device and descriptor manager");
	return fb;
}

std::string RestartTokenJson(const FRendererResourceIdentity& token)
{
	std::ostringstream out;
	out << "{\"index\":" << token.Index << ",\"generation\":" << token.Generation << ",\"epoch\":" << token.Epoch << ",\"span\":" << token.Span << '}';
	return out.str();
}

std::string RestartLifetimeJson(const FRendererLifetimeStats& stats)
{
	std::ostringstream out;
	out << "{\"activations\":" << stats.Activations << ",\"retirements\":" << stats.Retirements << ",\"resets\":" << stats.Resets
		<< ",\"staleRejects\":" << stats.StaleRejects << ",\"invalidRetires\":" << stats.InvalidRetires << ",\"duplicateActivations\":" << stats.DuplicateActivations << '}';
	return out.str();
}

void WriteNativeRestartReceipt(const DiagnosticRun& run, bool pass, const std::string& error)
{
	const auto text = run.Json(pass, error);
	WriteBytes(run.prefix + ".json", { text.begin(), text.end() });
}

void WriteRestartReceipt(const std::string& prefix, const char* stage, bool pass, const std::string& error,
	const std::array<bool, 2>& live, const std::string& nativeReceipt)
{
	std::ostringstream out;
	auto fb = screen && screen->IsVulkan() ? static_cast<VulkanRenderDevice*>(screen) : nullptr;
	auto descriptors = fb ? fb->GetDescriptorSetManager() : nullptr;
	auto device = fb ? fb->GetDevice() : nullptr;
	out << "{\"schema\":" << Quote(RestartSchema) << ",\"stage\":" << Quote(stage) << ",\"status\":" << Quote(pass ? "PASS" : "FAIL")
		<< ",\"schemaVersion\":" << RestartState.schemaVersion
		<< ",\"error\":" << Quote(error) << ",\"prefix\":" << Quote(prefix) << ",\"nativeReceipt\":" << Quote(nativeReceipt)
		<< ",\"beforeNativePrefix\":" << Quote(RestartState.beforePrefix) << ",\"afterNativePrefix\":" << Quote(RestartState.afterPrefix)
		<< ",\"beforeCounter\":" << RestartState.counter << ",\"actualCounter\":" << restart
		<< ",\"managerIdentity\":" << Quote(std::to_string(RestartState.managerIdentity))
		<< ",\"deviceIdentity\":" << Quote(std::to_string(RestartState.deviceIdentity))
		<< ",\"framebufferIdentity\":" << Quote(std::to_string(RestartState.framebufferIdentity))
		<< ",\"actualManagerIdentity\":" << Quote(std::to_string(Handle(descriptors)))
		<< ",\"actualDeviceIdentity\":" << Quote(std::to_string(device ? Handle(device->device) : 0))
		<< ",\"actualFramebufferIdentity\":" << Quote(std::to_string(fb ? Handle(fb) : 0))
		<< ",\"beforeLifetime\":" << RestartLifetimeJson(RestartState.lifetime)
		<< ",\"actualLifetime\":" << RestartLifetimeJson(descriptors ? descriptors->GetBindlessLifetimeStats() : FRendererLifetimeStats{})
		<< ",\"iwad\":" << Quote(RestartState.iwad) << ",\"mod\":" << Quote(RestartState.mod) << ",\"afterExec\":" << Quote(RestartState.afterExec)
		<< ",\"rendererMode\":" << RestartState.rendererMode << ",\"globalTextureFilter\":" << RestartState.globalFilter
		<< ",\"tokens\":[" << RestartTokenJson(RestartState.tokens[0]) << ',' << RestartTokenJson(RestartState.tokens[1]) << ']'
		<< ",\"oldTokensLive\":[" << (live[0] ? "true" : "false") << ',' << (live[1] ? "true" : "false") << ']'
		<< ",\"oldTokensCheckedBeforeProducer\":" << (pass && std::strcmp(stage, "after") == 0 ? "true" : "false")
		<< ",\"valueOnlyCheckpoint\":true,\"oldResourcePointersDereferenced\":false,\"paletteAddressInequalityRequired\":false"
		<< ",\"scope\":\"actual debug_restart; old-token guard before fresh production DrawTexture/Draw2D/resident oracle\""
		<< ",\"externalProofRequired\":[\"one process and exact executable/input hashes\",\"two actual startup/archive blocks\",\"strict Vulkan layer and exit evidence\"]}\n";
	const auto text = out.str();
	WriteBytes(prefix + ".restart-" + stage + ".json", { text.begin(), text.end() });
}
}

CCMD(pf_indexedmaterial_restart_before)
{
	std::string prefix, nativeReceipt;
	std::array<bool, 2> live = {};
	try
	{
		Require(argv.argc() == 4, "Usage: pf_indexedmaterial_restart_before <before-native-prefix> <after-native-prefix> <absolute-after-exec>");
		prefix = RestartPath(argv[1]);
		const auto afterPrefix = RestartPath(argv[2]);
		const auto afterExec = RestartPath(argv[3]);
		Require(RestartState.phase == RestartPhase::Empty, "restart BEFORE is one-shot and cannot be repeated");
		Require(restart >= 0 && restart < std::numeric_limits<int>::max(), "actual engine restart counter is invalid");
		auto fb = RestartFramebuffer();
		const auto arguments = ReadRestartArguments();
		Require(prefix != afterPrefix, "BEFORE and AFTER native receipts must be independent");
		FreshRestartPrefix(prefix);
		FreshRestartPrefix(afterPrefix);
		GuardRestartScripts(arguments, prefix, afterPrefix, afterExec);
		// Preflight the exact public pair-removal semantics without mutating Args.
		FArgs remaining(*Args);
		Require(RestartPath(remaining.TakeValue("+exec").GetChars()) == arguments.exec, "original +exec pair did not remove exactly");
		Require(std::string(remaining.TakeValue("+map").GetChars()) == arguments.map, "original +map pair did not remove exactly");
		for (int i = 1; i < remaining.NumArgs(); i++) Require(remaining.GetArg(i)[0] != '+', "unexpected command remains across restart");
		// Preflight the inherited debug_restart removal exactly. Its terminal
		// RemoveArgs bug must fail BEFORE, never strand an orphan after restart.
		FArgs dispatched(remaining), desired(remaining);
		dispatched.RemoveArgs("-iwad"); dispatched.RemoveArgs("-file");
		Require(RestartPath(desired.TakeValue("-iwad").GetChars()) == arguments.iwad && RestartPath(desired.TakeValue("-file").GetChars()) == arguments.mod,
			"pinned package pairs did not remove exactly in restart preflight");
		Require(dispatched.NumArgs() == desired.NumArgs(), "inherited debug_restart would retain a terminal orphan package argument");
		for (int i = 0; i < desired.NumArgs(); i++) Require(std::strcmp(dispatched.GetArg(i), desired.GetArg(i)) == 0, "inherited debug_restart removal differs from the exact desired argv");
		DiagnosticRun run{ fb, prefix, {}, {}, 0, "[]", "{\"required\":false,\"observed\":false}" };
		nativeReceipt = run.prefix + ".json";
		bool nativePass = false;
		std::string nativeError;
		try
		{
			run.Execute(true); // RestoreTranslation and RestoreMainBoundary end here.
			const auto tokens = run.pairedRestartTokens;
			run.Check(tokens[0].IsSet() && tokens[1].IsSet() && tokens[0].Span == 2 && tokens[1].Span == 2 && tokens[0].Index != tokens[1].Index,
				"restart retains two actual independent index+palette blocks");
			for (size_t i = 0; i < tokens.size(); i++) live[i] = fb->GetDescriptorSetManager()->ValidateBindlessIdentity(tokens[i]);
			run.Check(live[0] && live[1], "both retained blocks remain live after native oracle RAII return and normal fence");
			RestartState.beforePrefix = prefix; RestartState.afterPrefix = afterPrefix;
			RestartState.iwad = arguments.iwad; RestartState.mod = arguments.mod; RestartState.afterExec = afterExec;
			RestartState.counter = restart; RestartState.rendererMode = int(vid_rendermode); RestartState.globalFilter = int(gl_texture_filter);
			RestartState.managerIdentity = Handle(fb->GetDescriptorSetManager()); RestartState.deviceIdentity = Handle(fb->GetDevice()->device);
			RestartState.framebufferIdentity = Handle(fb); RestartState.tokens = tokens;
			run.Check(RestartState.managerIdentity != 0 && RestartState.deviceIdentity != 0 && RestartState.framebufferIdentity != 0,
				"restart checkpoint has actual nonzero manager, device and framebuffer value identities");
			RestartState.lifetime = fb->GetDescriptorSetManager()->GetBindlessLifetimeStats();
			nativePass = true;
		}
		catch (const std::exception& e) { nativeError = e.what(); }
		WriteNativeRestartReceipt(run, nativePass, nativeError);
		Require(nativePass, nativeError.c_str());
		WriteRestartReceipt(prefix, "before", true, {}, live, nativeReceipt);
		RestartState.phase = RestartPhase::Armed;
		// Only this PASS path can invoke the real engine cleanup/reinitialization.
		Args->TakeValue("+exec");
		Args->TakeValue("+map");
		const auto command = "debug_restart -iwad " + RestartQuoted(arguments.iwad) + " -file " + RestartQuoted(arguments.mod) + " +exec " + RestartQuoted(afterExec);
		Printf("PF110_RESTART_BEFORE PASS counter=%d blocks=2; %s\n", restart, (prefix + ".restart-before.json").c_str());
		AddCommandString(command.c_str());
		return;
	}
	catch (const std::exception& e)
	{
		RestartState.phase = RestartPhase::Failed;
		if (!prefix.empty()) try { WriteRestartReceipt(prefix, "before", false, e.what(), live, nativeReceipt); } catch (const std::exception&) { }
		Printf("PF110_RESTART_BEFORE FAIL: %s\n", e.what());
	}
	// A failed guarded phase must not return to an uncontrolled continuation.
	// Clearing the delayed queue here would delete its currently ticking command.
	AddCommandString("quit");
}

CCMD(pf_indexedmaterial_restart_after)
{
	std::string prefix, nativeReceipt;
	std::array<bool, 2> live = {};
	try
	{
		Require(argv.argc() == 2, "Usage: pf_indexedmaterial_restart_after <same-absolute-prefix>");
		prefix = RestartPath(argv[1]);
		Require(RestartState.phase == RestartPhase::Armed && RestartState.schemaVersion == RestartSchemaVersion && prefix == RestartState.afterPrefix,
			"restart AFTER requires the same armed one-shot prefix/schema");
		RestartState.phase = RestartPhase::Consumed;
		auto fb = RestartFramebuffer();
		Require(restart == RestartState.counter + 1, "AFTER requires exactly one genuine engine D_Cleanup restart");
		Require(Handle(fb) == RestartState.framebufferIdentity && Handle(fb->GetDescriptorSetManager()) == RestartState.managerIdentity &&
			Handle(fb->GetDevice()->device) == RestartState.deviceIdentity, "restart must preserve the actual framebuffer/descriptor manager/device");
		Require(int(vid_rendermode) == RestartState.rendererMode && int(gl_texture_filter) == RestartState.globalFilter, "restart changed the selected protected route/filter");
		const auto arguments = ReadRestartArguments();
		Require(arguments.iwad == RestartState.iwad && arguments.mod == RestartState.mod && arguments.exec == RestartState.afterExec && arguments.map.empty(),
			"AFTER must reuse the pinned packages and sole new exec without stale +map");
		// Must precede Execute, ResetIndexedAsset, ValidateTexture or any new
		// diagnostic producer. No old remap/resource address is ever dereferenced.
		for (size_t i = 0; i < RestartState.tokens.size(); i++) live[i] = fb->GetDescriptorSetManager()->ValidateBindlessIdentity(RestartState.tokens[i]);
		Require(!live[0] && !live[1], "normal engine cleanup must retire both formerly live descriptor blocks");
		const auto lifetime = fb->GetDescriptorSetManager()->GetBindlessLifetimeStats();
		Require(lifetime.Retirements >= RestartState.lifetime.Retirements + 2 && lifetime.Resets == RestartState.lifetime.Resets &&
			lifetime.InvalidRetires == RestartState.lifetime.InvalidRetires, "restart retirement must use the normal owner path without allocator reset or invalid frees");
		FreshRestartPrefix(prefix);
		DiagnosticRun run{ fb, prefix, {}, {}, 0, "[]", "{\"required\":false,\"observed\":false}" };
		nativeReceipt = run.prefix + ".json";
		bool nativePass = false;
		std::string nativeError;
		try { run.Execute(); nativePass = true; }
		catch (const std::exception& e) { nativeError = e.what(); }
		WriteNativeRestartReceipt(run, nativePass, nativeError);
		Require(nativePass, nativeError.c_str());
		WriteRestartReceipt(prefix, "after", true, {}, live, nativeReceipt);
		RestartState.phase = RestartPhase::Complete;
		Printf("PF110_RESTART_AFTER PASS counter=%d old_blocks_stale=2; %s\n", restart, (prefix + ".restart-after.json").c_str());
		return;
	}
	catch (const std::exception& e)
	{
		RestartState.phase = RestartPhase::Failed;
		if (!prefix.empty()) try { WriteRestartReceipt(prefix, "after", false, e.what(), live, nativeReceipt); } catch (const std::exception&) { }
		Printf("PF110_RESTART_AFTER FAIL: %s\n", e.what());
	}
	AddCommandString("quit");
}
