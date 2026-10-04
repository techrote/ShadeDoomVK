/* PF020: bounded opt-in observations of actual Vulkan producers and caches. */
#include "vk_pfviewdiagnostics.h"
#include "c_dispatch.h"
#include "m_argv.h"
#include "printf.h"
#include "cmdlib.h"
#include "i_specialpaths.h"
#include "v_video.h"
#include "diagnostics/hw_pfviewdiagnostics.h"
#include "texturemanager.h"
#include "gametexture.h"
#include "textures.h"
#include "vulkan/vk_renderdevice.h"
#include "vulkan/vk_renderstate.h"
#include "vulkan/commands/vk_commandbuffer.h"
#include "vulkan/textures/vk_renderbuffers.h"
#include "vulkan/textures/vk_imagetransition.h"
#include "vulkan/descriptorsets/vk_descriptorset.h"
#include "vulkan/pipelines/vk_renderpass.h"
#include "vulkan/shaders/vk_shader.h"
#include "vulkan/shaders/sha1.h"
#include <zvulkan/vulkanbuilders.h>
#include <array>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <map>
#include <mutex>
#include <set>
#include <sstream>
#include <stdexcept>
#include <thread>
#include <vector>

namespace
{
constexpr size_t MaxKeys = 8192;
constexpr size_t MaxKeyBytes = 4096;
constexpr size_t MaxImageBytes = 8 * 1024 * 1024;
struct Observation
{
	std::mutex Mutex;
	bool Initialized = false, Enabled = false, Written = false;
	std::thread::id OwnerThread;
	std::string Prefix, CacheRoot, Error;
	std::map<std::string, uint64_t> Keys;
	std::vector<std::string> Images, CacheEvents;
	std::array<std::string, 6> FaceKeys;
	std::array<VulkanImageView::CreationArguments, 6> FaceViews;
	std::array<uint64_t, 6> FaceHandles = {};
	std::set<std::string> Captured;
	uint64_t Sequence = 0;
	uint64_t QueuedWorkers = 0, ActiveWorkers = 0, PendingMain = 0, FailedWorkers = 0;
	uint64_t ScheduledPrecache = 0, ScheduledPriority = 0, CompletedWorkers = 0, CompletedMain = 0;
};
Observation& State() { static Observation state; return state; }
std::string Quote(const std::string& value)
{
	std::ostringstream out;
	out << '"';
	for (unsigned char c : value)
	{
		if (c == '"' || c == '\\') out << '\\' << char(c);
		else if (c < 32) out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << unsigned(c) << std::dec;
		else out << char(c);
	}
	out << '"';
	return out.str();
}
void Require(bool condition, const char* message) { if (!condition) throw std::runtime_error(message); }
void Fail(const std::string& error)
{
	auto& state = State();
	std::lock_guard<std::mutex> lock(state.Mutex);
	if (state.Error.empty()) state.Error = error;
	Printf("PF020 Vulkan observation failed: %s\n", error.c_str());
}
void WriteFresh(const std::string& path, const void* data, size_t bytes)
{
	Require(!std::filesystem::exists(std::filesystem::u8path(path)), "PF020 evidence path already exists");
	std::ofstream output(std::filesystem::u8path(path), std::ios::binary);
	Require(bool(output), "PF020 evidence file could not be opened");
	output.write(static_cast<const char*>(data), static_cast<std::streamsize>(bytes));
	output.close();
	Require(bool(output), "PF020 evidence file write/close failed");
}
void WriteFresh(const std::string& path, const std::string& value) { WriteFresh(path, value.data(), value.size()); }
bool Under(const std::filesystem::path& root, const std::filesystem::path& child)
{
	auto relative = child.lexically_relative(root);
	if (relative.empty() || relative == "." || relative.is_absolute()) return false;
	for (const auto& part : relative) if (part == "..") return false;
	return true;
}
bool Enabled()
{
	auto& state = State();
	// First call is the main-thread cache constructor, before its workers exist.
	if (state.Initialized) return state.Enabled;
	state.Initialized = true;
	state.OwnerThread = std::this_thread::get_id();
	state.Enabled = Pf020ViewDiagnostics::Enabled();
	if (!state.Enabled) return false;
	try
	{
		const char* prefix = Pf020ViewDiagnostics::OutputPrefix();
		Require(prefix && *prefix, "PF020 frontend output prefix unavailable");
		state.Prefix = prefix;
		Require(!std::filesystem::exists(std::filesystem::u8path(state.Prefix + ".vulkan.json")) &&
			!std::filesystem::exists(std::filesystem::u8path(state.Prefix + ".cache-events.jsonl")), "PF020 Vulkan output prefix is not fresh");
		int index = Args->CheckParm("-pf020viewcache");
		Require(index > 0 && index + 1 < Args->NumArgs() && Args->GetArg(index + 1)[0] != '-', "Explicit project-local -pf020viewcache is required");
		unsigned occurrences = 0;
		for (int i = 1; i < Args->NumArgs(); ++i) if (!stricmp(Args->GetArg(i), "-pf020viewcache")) ++occurrences;
		Require(occurrences == 1, "Duplicate PF020 cache root arguments");
		auto root = std::filesystem::weakly_canonical(std::filesystem::current_path() / "build");
		auto requestedCache = std::filesystem::absolute(std::filesystem::u8path(Args->GetArg(index + 1))).lexically_normal();
		auto cache = std::filesystem::weakly_canonical(requestedCache);
		Require(cache == requestedCache, "PF020 cache root cannot resolve through a symbolic link/reparse alias");
		Require(Under(root, cache), "PF020 cache root must lie strictly under current project build directory");
		// Existing warm cache roots are allowed, but never arbitrary source or shared caches.
		auto check = cache;
		while (check != root && !check.empty())
		{
			Require(!std::filesystem::is_symlink(std::filesystem::symlink_status(check)), "PF020 cache path cannot use a symbolic link");
			check = check.parent_path();
		}
		std::filesystem::create_directories(cache);
		for (const auto& entry : std::filesystem::directory_iterator(cache))
			Require(entry.is_regular_file() && !entry.is_symlink() &&
				(entry.path().filename() == "shadercache.zdsc" || entry.path().filename() == "pipelinecache.zdpc"), "PF020 cache root contains unexpected content");
		state.CacheRoot = cache.u8string();
	}
	catch (const std::exception& error)
	{
		Fail(error.what());
		// Never fall back to the shared cache after an invalid explicit request.
		I_Error("PF020 Vulkan observation initialization failed: %s", error.what());
	}
	return true;
}
std::string SceneKey()
{
	if (std::this_thread::get_id() != State().OwnerThread) return "null";
	auto key = Pf020ViewDiagnostics::CurrentSceneKeyJson();
	return key.empty() ? "null" : key;
}
std::string ActiveSceneKey()
{
	if (std::this_thread::get_id() != State().OwnerThread) return "null";
	auto key = Pf020ViewDiagnostics::ActiveSemanticKeyJson();
	return key.empty() ? "null" : key;
}
std::string ShaderFields(const VkShaderKey& key)
{
	std::ostringstream out;
	out << '{';
#define PF_FIELD(name) out << "\"" #name "\":" << uint64_t(key.name) << ','
	PF_FIELD(Simple2D); PF_FIELD(TextureMode); PF_FIELD(ClampY); PF_FIELD(Brightmap); PF_FIELD(Detailmap); PF_FIELD(Glowmap);
	PF_FIELD(UseShadowmap); PF_FIELD(UseRaytrace); PF_FIELD(ShadowmapFilter); PF_FIELD(FogBeforeLights); PF_FIELD(FogAfterLights);
	PF_FIELD(FogRadial); PF_FIELD(SWLightRadial); PF_FIELD(SWLightBanded); PF_FIELD(LightMode); PF_FIELD(LightBlendMode);
	PF_FIELD(LightAttenuationMode); PF_FIELD(PaletteMode); PF_FIELD(FogBalls); PF_FIELD(NoFragmentShader);
	PF_FIELD(DepthFadeThreshold); PF_FIELD(AlphaTestOnly); PF_FIELD(LightNoNormals); PF_FIELD(UseSpriteCenter);
#undef PF_FIELD
	out << "\"SpecialEffect\":" << key.SpecialEffect << ",\"EffectState\":" << key.EffectState << ",\"VertexFormat\":" << key.VertexFormat << ",\"layout\":{";
#define PF_LAYOUT(name) out << "\"" #name "\":" << uint64_t(key.Layout.name) << ','
	PF_LAYOUT(AlphaTest); PF_LAYOUT(Simple); PF_LAYOUT(Simple3D); PF_LAYOUT(GBufferPass); PF_LAYOUT(UseLevelMesh); PF_LAYOUT(ShadeVertex);
#undef PF_LAYOUT
	out << "\"UseRaytracePrecise\":" << uint64_t(key.Layout.UseRaytracePrecise) << "}}";
	return out.str();
}
std::string PipelineFields(const VkPipelineKey& key)
{
	std::ostringstream out;
	out << '{';
#define PF_FIELD(name) out << "\"" #name "\":" << uint64_t(key.name) << ','
	PF_FIELD(DrawType); PF_FIELD(CullMode); PF_FIELD(ColorMask); PF_FIELD(DepthWrite); PF_FIELD(DepthTest); PF_FIELD(DepthClamp);
	PF_FIELD(DepthBias); PF_FIELD(DepthFunc); PF_FIELD(StencilTest); PF_FIELD(StencilPassOp); PF_FIELD(DrawLine); PF_FIELD(IsGeneralized);
#undef PF_FIELD
	out << "\"shader\":" << ShaderFields(key.ShaderKey) << ",\"style\":{\"BlendOp\":" << unsigned(key.RenderStyle.BlendOp)
		<< ",\"SrcAlpha\":" << unsigned(key.RenderStyle.SrcAlpha) << ",\"DestAlpha\":" << unsigned(key.RenderStyle.DestAlpha)
		<< ",\"Flags\":" << unsigned(key.RenderStyle.Flags) << "}}";
	return out.str();
}
void Key(const std::string& json)
{
	auto& state = State();
	std::lock_guard<std::mutex> lock(state.Mutex);
	if (!state.Error.empty() || state.Written) return;
	if (json.size() > MaxKeyBytes) { state.Error = "PF020 key record byte cap reached"; return; }
	auto it = state.Keys.find(json);
	if (it == state.Keys.end())
	{
		if (state.Keys.size() >= MaxKeys) { state.Error = "PF020 key record cap reached"; return; }
		state.Keys.emplace(json, 1);
	}
	else ++it->second;
}
std::string FileState(const std::string& path)
{
	if (!std::filesystem::exists(std::filesystem::u8path(path))) return "{\"exists\":false,\"bytes\":0,\"sha1\":null}";
	Require(std::filesystem::is_regular_file(std::filesystem::u8path(path)), "Cache artifact is not a regular file");
	Require(std::filesystem::file_size(std::filesystem::u8path(path)) <= 64 * 1024 * 1024, "Cache artifact exceeds bounded diagnostic hashing size");
	std::ifstream input(std::filesystem::u8path(path), std::ios::binary);
	Require(bool(input), "Cache artifact cannot be read");
	SHA1 hash;
	hash.update(input);
	Require(!input.bad(), "Cache artifact hashing failed");
	std::ostringstream out;
	out << "{\"exists\":true,\"bytes\":" << std::filesystem::file_size(std::filesystem::u8path(path)) << ",\"sha1\":" << Quote(hash.final()) << '}';
	return out.str();
}
struct SamplingCapture
{
	VulkanRenderDevice* Fb;
	VkTextureImage Target;
	std::unique_ptr<VulkanImageView> SourceView;
	std::unique_ptr<VulkanSampler> Sampler;
	std::unique_ptr<VulkanDescriptorSetLayout> SetLayout;
	std::unique_ptr<VulkanDescriptorPool> Pool;
	std::unique_ptr<VulkanDescriptorSet> Set;
	std::unique_ptr<VulkanPipelineLayout> Layout;
	std::unique_ptr<VulkanRenderPass> Pass;
	std::unique_ptr<VulkanPipeline> Pipeline;
	std::unique_ptr<VulkanBuffer> Staging;
	bool PassOpen = false, Recorded = false, Waited = false;
	explicit SamplingCapture(VulkanRenderDevice* fb) : Fb(fb) { }
	~SamplingCapture()
	{
		try
		{
			if (PassOpen) { Fb->GetCommands()->GetDrawCommands()->endRenderPass(); PassOpen = false; }
			if (Recorded && !Waited) Fb->GetCommands()->WaitForCommands(false);
			auto list = Fb->GetCommands()->DrawDeleteList.get();
			list->Add(std::move(Set)); list->Add(std::move(Pool)); list->Add(std::move(SourceView));
			list->Add(std::move(Sampler)); list->Add(std::move(Staging)); Target.Reset(Fb);
			Fb->GetCommands()->WaitForCommands(false);
			// Pipeline/pass/layout are private and destroyed only after their fence.
			Pipeline.reset(); Pass.reset(); Layout.reset(); SetLayout.reset();
			Fb->GetRenderState()->EndRenderPass();
		}
		catch (...)
		{
			// A failed fence is never permission to destroy in-flight objects.
			Set.release(); Pool.release(); SourceView.release(); Sampler.release(); Staging.release();
			Target.PPFramebuffer.release(); Target.View.release(); Target.Image.release();
			Pipeline.release(); Pass.release(); Layout.release(); SetLayout.release();
			Fail("PF020 private sampling cleanup fence failed; evidence remains invalid");
		}
	}
	std::string Run(VulkanImage* source, VulkanImageView* producerView, VkImageLayout sourceLayout,
		int layer, const std::string& semantic, const std::string& scene, const std::string& producer)
	{
		Require(source && producerView, "Completed producer image/view unavailable");
		const auto creation = producerView->GetCreationArguments();
		Require(creation.Captured && creation.Image == source->image && creation.Range.baseMipLevel == 0 &&
			creation.Range.levelCount == 1 && creation.Range.aspectMask == VK_IMAGE_ASPECT_COLOR_BIT,
			"Producer view creation arguments do not identify the exact color mip");
		Require(creation.Format == VK_FORMAT_R8G8B8A8_UNORM || creation.Format == VK_FORMAT_R16G16B16A16_SFLOAT,
			"Producer format has no exact PF020 same-format sampling contract");
		Require(creation.Range.baseArrayLayer == 0 && creation.Range.layerCount == uint32_t(source->layerCount) &&
			creation.ViewType == (source->layerCount == 6 ? VK_IMAGE_VIEW_TYPE_CUBE : VK_IMAGE_VIEW_TYPE_2D), "Unexpected producer view/layer representation");
		Require(sourceLayout == VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL && source->width > 0 && source->height > 0 && source->width <= 1024 && source->height <= 1024 &&
			layer >= 0 && layer < source->layerCount && source->mipLevels >= 1, "Completed producer layout/extent/layer invalid");
		const size_t bytes = size_t(source->width) * size_t(source->height) * (creation.Format == VK_FORMAT_R8G8B8A8_UNORM ? 4 : 8);
		Require(bytes <= MaxImageBytes, "Producer readback exceeds bounded fixture image size");
		Fb->GetRenderState()->EndRenderPass();
		Fb->GetCommands()->WaitForCommands(false);
		SourceView = ImageViewBuilder().Type(VK_IMAGE_VIEW_TYPE_2D).Image(source, creation.Format,
			VK_IMAGE_ASPECT_COLOR_BIT, 0, layer, 1, 1).DebugName("PF020.ActualProducerLayerView").Create(Fb->GetDevice());
		Sampler = SamplerBuilder().MinFilter(VK_FILTER_NEAREST).MagFilter(VK_FILTER_NEAREST).MaxLod(0).Create(Fb->GetDevice());
		const auto samplerArgs = Sampler->GetCreationArguments();
		Require(samplerArgs.Captured && samplerArgs.MinFilter == VK_FILTER_NEAREST && samplerArgs.MagFilter == VK_FILTER_NEAREST &&
			samplerArgs.MaxLod == 0 && !samplerArgs.AnisotropyEnable, "Private texel-fetch sampler creation contract mismatch");
		Target.Image = ImageBuilder().Size(source->width, source->height).Format(creation.Format)
			.Usage(VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT).DebugName("PF020.SameFormatReadbackTarget").Create(Fb->GetDevice());
		Target.View = ImageViewBuilder().Image(Target.Image.get(), creation.Format).Create(Fb->GetDevice());
		SetLayout = DescriptorSetLayoutBuilder().AddBinding(0, VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, 1, VK_SHADER_STAGE_FRAGMENT_BIT).Create(Fb->GetDevice());
		Pool = DescriptorPoolBuilder().AddPoolSize(VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, 1).MaxSets(1).Create(Fb->GetDevice());
		Set = Pool->allocate(SetLayout.get());
		WriteDescriptors().AddCombinedImageSampler(Set.get(), 0, SourceView.get(), Sampler.get(), sourceLayout).Execute(Fb->GetDevice());
		Layout = PipelineLayoutBuilder().AddSetLayout(SetLayout.get()).Create(Fb->GetDevice());
		Pass = RenderPassBuilder().AddAttachment(creation.Format, VK_SAMPLE_COUNT_1_BIT, VK_ATTACHMENT_LOAD_OP_DONT_CARE,
			VK_ATTACHMENT_STORE_OP_STORE, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL)
			.AddSubpass().AddSubpassColorAttachmentRef(0, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL).Create(Fb->GetDevice());
		Target.PPFramebuffer = FramebufferBuilder().RenderPass(Pass.get()).AddAttachment(Target.View.get()).Size(source->width, source->height).Create(Fb->GetDevice());
		const std::string vertex = "#version 460\nvoid main(){vec2 p=vec2((gl_VertexIndex<<1)&2,gl_VertexIndex&2);gl_Position=vec4(p*2.-1.,0,1);}\n";
		const std::string fragment = "#version 460\nlayout(set=0,binding=0) uniform sampler2D Source;layout(location=0) out vec4 Result;void main(){Result=texelFetch(Source,ivec2(gl_FragCoord.xy),0);}\n";
		auto vert = GLSLCompiler().Type(ShaderType::Vertex).AddSource("PF020.SampleVertex", vertex).Compile(Fb->GetDevice());
		auto frag = GLSLCompiler().Type(ShaderType::Fragment).AddSource("PF020.SampleExactTexel", fragment).Compile(Fb->GetDevice());
		Require(vert.size() >= 5 && frag.size() >= 5 && vert[0] == 0x07230203u && frag[0] == 0x07230203u,
			"Private same-format sampling SPIR-V unavailable");
		const auto stem = State().Prefix + "-" + semantic;
		WriteFresh(stem + ".vert.spv", vert.data(), vert.size() * sizeof(uint32_t));
		WriteFresh(stem + ".frag.spv", frag.data(), frag.size() * sizeof(uint32_t));
		WriteFresh(stem + ".vert.glsl", vertex);
		WriteFresh(stem + ".frag.glsl", fragment);
		Pipeline = GraphicsPipelineBuilder().Layout(Layout.get()).RenderPass(Pass.get())
			.Topology(VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST).Viewport(0, 0, source->width, source->height).Scissor(0, 0, source->width, source->height)
			.Cull(VK_CULL_MODE_NONE, VK_FRONT_FACE_COUNTER_CLOCKWISE).DepthStencilEnable(false, false, false)
			.AddColorBlendAttachment(ColorBlendAttachmentBuilder().Create()).AddVertexShader(vert).AddFragmentShader(frag).Create(Fb->GetDevice());
		auto commands = Fb->GetCommands()->GetDrawCommands();
		Recorded = true; // First following command references private resources.
		PipelineBarrier().AddImage(source, sourceLayout, sourceLayout,
			VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT | VK_ACCESS_SHADER_READ_BIT, VK_ACCESS_SHADER_READ_BIT,
			VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, layer, 1).Execute(commands,
			VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT | VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT);
		VkImageTransition().AddImage(&Target, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL, true).Execute(commands);
		RenderPassBegin().RenderPass(Pass.get()).Framebuffer(Target.PPFramebuffer.get()).RenderArea(0, 0, source->width, source->height).Execute(commands);
		PassOpen = true;
		commands->bindPipeline(VK_PIPELINE_BIND_POINT_GRAPHICS, Pipeline.get());
		commands->bindDescriptorSet(VK_PIPELINE_BIND_POINT_GRAPHICS, Layout.get(), 0, Set.get());
		commands->draw(3, 1, 0, 0);
		commands->endRenderPass(); PassOpen = false;
		VkImageTransition().AddImage(&Target, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, false).Execute(commands);
		Staging = BufferBuilder().Size(bytes).Usage(VK_BUFFER_USAGE_TRANSFER_DST_BIT, VMA_MEMORY_USAGE_GPU_TO_CPU).Create(Fb->GetDevice());
		VkBufferImageCopy copy = {};
		copy.imageSubresource = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1 };
		copy.imageExtent = { uint32_t(source->width), uint32_t(source->height), 1 };
		// Only the private TRANSFER_SRC target is copied; producer usage is unchanged.
		commands->copyImageToBuffer(Target.Image->image, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, Staging->buffer, 1, &copy);
		Fb->GetCommands()->WaitForCommands(false); Waited = true;
		const void* mapped = Staging->Map(0, bytes);
		Require(mapped != nullptr, "PF020 private readback mapping failed");
		try
		{
			Fb->GetDevice()->CheckVulkanError(vmaInvalidateAllocation(Fb->GetDevice()->allocator, Staging->allocation, 0, bytes), "PF020 readback cache invalidation failed");
			WriteFresh(stem + (creation.Format == VK_FORMAT_R8G8B8A8_UNORM ? ".rgba8" : ".rgba16f"), mapped, bytes);
		}
		catch (...) { Staging->Unmap(); throw; }
		Staging->Unmap();
		const auto sampled = SourceView->GetCreationArguments();
		Require(sampled.Captured && sampled.Image == source->image && sampled.ViewType == VK_IMAGE_VIEW_TYPE_2D && sampled.Format == creation.Format &&
			sampled.Range.baseMipLevel == 0 && sampled.Range.levelCount == 1 && sampled.Range.baseArrayLayer == uint32_t(layer) &&
			sampled.Range.layerCount == 1 && sampled.Range.aspectMask == VK_IMAGE_ASPECT_COLOR_BIT, "Actual sampled layer view creation mismatch");
		std::ostringstream result;
		result << "{\"semantic\":" << Quote(semantic) << ",\"scene\":" << scene << ",\"sourceImage\":" << uint64_t(source->image)
			<< ",\"producerView\":" << uint64_t(producerView->view) << ",\"sourceViewType\":" << creation.ViewType
			<< ",\"sampledViewType\":" << sampled.ViewType << ",\"sampledBaseLayer\":" << sampled.Range.baseArrayLayer
			<< ",\"sampledLayerCount\":" << sampled.Range.layerCount << ",\"mip\":0,\"format\":" << creation.Format
			<< ",\"producerMipCount\":" << source->mipLevels << ",\"producerLayerCount\":" << source->layerCount
			<< ",\"producerViewBaseLayer\":" << creation.Range.baseArrayLayer << ",\"producerViewLayers\":" << creation.Range.layerCount
			<< ",\"width\":" << source->width << ",\"height\":" << source->height << ",\"bytes\":" << bytes
			<< ",\"sourceLayoutBefore\":" << sourceLayout << ",\"sourceLayoutAfter\":" << sourceLayout
			<< ",\"file\":" << Quote(stem + (creation.Format == VK_FORMAT_R8G8B8A8_UNORM ? ".rgba8" : ".rgba16f"))
			<< ",\"vertexGLSL\":" << Quote(stem + ".vert.glsl") << ",\"fragmentGLSL\":" << Quote(stem + ".frag.glsl")
			<< ",\"vertexSPIRV\":" << Quote(stem + ".vert.spv") << ",\"fragmentSPIRV\":" << Quote(stem + ".frag.spv")
			<< ",\"rowBytes\":" << bytes / size_t(source->height) << ",\"channels\":4,\"sourceUsageBasis\":\"pinned-production-ImageBuilder-code\""
			<< ",\"creationMetadataBasis\":\"captured-successful-application-vkCreateImageView-and-vkCreateSampler-arguments\""
			<< ",\"sampler\":{\"minFilter\":" << samplerArgs.MinFilter << ",\"magFilter\":" << samplerArgs.MagFilter
			<< ",\"maxLod\":" << samplerArgs.MaxLod << ",\"anisotropyEnable\":" << (samplerArgs.AnisotropyEnable ? "true" : "false") << '}'
			<< ",\"producerState\":" << producer
			<< ",\"producerRerendered\":false,\"sourceCopied\":false,\"sameFormatTexelFetch\":true,\"normalFenceWaited\":true,\"allocationInvalidated\":true}";
		return result.str();
	}
};
void Capture(VulkanRenderDevice* fb, VulkanImage* image, VulkanImageView* view, int layer, const std::string& semantic,
	const std::string& scene, const std::string& producer = "null")
{
	auto& state = State();
	if (!Enabled() || !Pf020ViewDiagnostics::FixtureActive()) return;
	{
		std::lock_guard<std::mutex> lock(state.Mutex);
		if (!state.Error.empty() || state.Written || state.Captured.count(semantic)) return;
		// Mark before execution: failures are retained rather than hidden by retrying.
		state.Captured.insert(semantic);
	}
	try
	{
		Require(!scene.empty() && scene != "null", "Completed image has no actual completed scene key");
		std::string result;
		{
			SamplingCapture capture(fb);
			result = capture.Run(image, view, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL, layer, semantic, scene, producer);
		}
		std::lock_guard<std::mutex> lock(state.Mutex);
		state.Images.push_back(std::move(result));
	}
	catch (const std::exception& error) { Fail(error.what()); }
}
}

namespace Pf020VulkanDiagnostics
{
FString CacheFilename(const char* leaf)
{
	if (!Enabled()) { FString path = M_GetCachePath(true); CreatePath(path.GetChars()); return path + "/" + leaf; }
	Require(!State().CacheRoot.empty(), "PF020 cache initialization did not establish an isolated root");
	Require(std::string(leaf) == "pipelinecache.zdpc" || std::string(leaf) == "shadercache.zdsc", "Unknown PF020 cache leaf");
	return (std::filesystem::u8path(State().CacheRoot) / leaf).u8string().c_str();
}
void CacheFile(const char* kind, const char* stage, const FString& filename, bool completed, size_t entries)
{
	if (!Enabled()) return;
	try
	{
		auto& state = State();
		std::lock_guard<std::mutex> lock(state.Mutex);
		std::ostringstream event;
		event << "{\"sequence\":" << ++state.Sequence << ",\"cache\":" << Quote(kind) << ",\"stage\":" << Quote(stage)
			<< ",\"operationCompleted\":" << (completed ? "true" : "false") << ",\"count\":" << entries
			<< ",\"countMeaning\":" << Quote(std::string(kind) == "shader" ? "in-memory-compiled-shader-entries" : "driver-initial-data-bytes")
			<< ",\"path\":" << Quote(filename.GetChars())
			<< ",\"file\":" << FileState(filename.GetChars()) << '}';
		std::ofstream output(std::filesystem::u8path(state.Prefix + ".cache-events.jsonl"), std::ios::binary | std::ios::app);
		Require(bool(output), "PF020 cache event output unavailable");
		output << event.str() << '\n'; output.close();
		Require(bool(output), "PF020 cache event write/close failed");
		state.CacheEvents.push_back(event.str());
	}
	catch (const std::exception& error) { Fail(error.what()); }
}
void ShaderLookup(const VkShaderKey& key, bool generalized, bool hit, const char* route)
{
	if (!Enabled()) return;
	std::ostringstream record;
	record << "{\"kind\":\"shader\",\"route\":" << Quote(route) << ",\"generalized\":" << (generalized ? "true" : "false")
		<< ",\"hit\":" << (hit ? "true" : "false") << ",\"actualGeneralizedKey\":";
	if (generalized) record << key.GeneralizedShaderKey(); else record << "null";
	record << ",\"shader\":" << ShaderFields(key) << ",\"workerThread\":" << (std::this_thread::get_id() == State().OwnerThread ? "false" : "true")
		<< ",\"scene\":" << ActiveSceneKey() << '}';
	Key(record.str());
}
void ShaderBinaryLookup(const char* checksum, bool hit)
{
	if (!Enabled()) return;
	std::ostringstream record;
	record << "{\"kind\":\"shader-binary-cache\",\"actualSourceChecksum\":" << Quote(checksum ? checksum : "")
		<< ",\"hit\":" << (hit ? "true" : "false") << ",\"workerThread\":" << (std::this_thread::get_id() == State().OwnerThread ? "false" : "true")
		<< ",\"scene\":" << ActiveSceneKey() << '}';
	Key(record.str());
}
void PipelineLookup(const VkPipelineKey& key, const VkRenderPassKey& pass, const char* route, bool hit, bool ready)
{
	if (!Enabled()) return;
	std::ostringstream record;
	record << "{\"kind\":\"pipeline\",\"route\":" << Quote(route) << ",\"hit\":" << (hit ? "true" : "false")
		<< ",\"ready\":" << (ready ? "true" : "false") << ",\"pipeline\":" << PipelineFields(key)
		<< ",\"pass\":{\"DepthStencil\":" << pass.DepthStencil << ",\"Samples\":" << pass.Samples << ",\"DrawBuffers\":" << pass.DrawBuffers
		<< ",\"DrawBufferFormat\":" << pass.DrawBufferFormat << "},\"workerThread\":" << (std::this_thread::get_id() == State().OwnerThread ? "false" : "true")
		<< ",\"scene\":" << ActiveSceneKey() << '}';
	Key(record.str());
}
void WorkerScheduled(bool precache)
{
	if (!Enabled()) return;
	auto& state = State(); std::lock_guard<std::mutex> lock(state.Mutex);
	++state.QueuedWorkers;
	if (precache) ++state.ScheduledPrecache; else ++state.ScheduledPriority;
}
void WorkerStarted()
{
	if (!Enabled()) return;
	auto& state = State(); std::lock_guard<std::mutex> lock(state.Mutex);
	if (!state.QueuedWorkers) { state.Error = "Worker started without an observed scheduled task"; return; }
	--state.QueuedWorkers; ++state.ActiveWorkers;
}
void WorkerFinished(bool failed)
{
	if (!Enabled()) return;
	auto& state = State(); std::lock_guard<std::mutex> lock(state.Mutex);
	if (!state.ActiveWorkers) { state.Error = "Worker completed without an observed active task"; return; }
	--state.ActiveWorkers; ++state.CompletedWorkers;
	if (failed) ++state.FailedWorkers;
}
void MainTaskScheduled()
{
	if (!Enabled()) return;
	auto& state = State(); std::lock_guard<std::mutex> lock(state.Mutex); ++state.PendingMain;
}
void MainTaskCompleted()
{
	if (!Enabled()) return;
	auto& state = State(); std::lock_guard<std::mutex> lock(state.Mutex);
	if (!state.PendingMain) { state.Error = "Main publication task completed without an observed queued task"; return; }
	--state.PendingMain; ++state.CompletedMain;
}
void ProbeFaceCompleted(int side, VulkanImageView* attachment)
{
	if (!Enabled() || !Pf020ViewDiagnostics::FixtureActive()) return;
	if (side < 0 || side >= 6) { Fail("Probe face outside six-face producer"); return; }
	if (!State().Captured.count("probe-face-" + std::to_string(side)))
	{
		if (!attachment) { Fail("Probe face has no actual render attachment view"); return; }
		State().FaceKeys[side] = SceneKey();
		State().FaceViews[side] = attachment->GetCreationArguments();
		State().FaceHandles[side] = uint64_t(attachment->view);
	}
}
void ProbeCompleted(VulkanRenderDevice* fb, VulkanImage* image, VulkanImageView* view)
{
	if (!Enabled() || !Pf020ViewDiagnostics::FixtureActive()) return;
	for (int side = 0; side < 6; ++side)
	{
		const auto& attachment = State().FaceViews[side];
		if (!image || !attachment.Captured || attachment.Image != image->image || attachment.ViewType != VK_IMAGE_VIEW_TYPE_2D ||
			attachment.Format != VK_FORMAT_R16G16B16A16_SFLOAT || attachment.Range.baseMipLevel != 0 || attachment.Range.levelCount != 1 ||
			attachment.Range.baseArrayLayer != uint32_t(side) || attachment.Range.layerCount != 1 || attachment.Range.aspectMask != VK_IMAGE_ASPECT_COLOR_BIT)
		{ Fail("Completed probe face attachment identity/layer does not match sampled producer cube"); return; }
		std::ostringstream producer;
		producer << "{\"actualRenderAttachmentView\":" << State().FaceHandles[side] << ",\"actualRenderAttachmentLayer\":" << attachment.Range.baseArrayLayer
			<< ",\"actualRenderAttachmentFormat\":" << attachment.Format << '}';
		Capture(fb, image, view, side, "probe-face-" + std::to_string(side), State().FaceKeys[side], producer.str());
	}
}
void CameraCompleted(VulkanRenderDevice* fb, VkTextureImage* image, FCanvasTexture* texture)
{
	if (!Enabled() || !Pf020ViewDiagnostics::FixtureActive() || !texture) return;
	auto owner = TexMan.FindGameTexture("PFVCAM", ETextureType::MiscPatch, FTextureManager::TEXMAN_TryAny | FTextureManager::TEXMAN_DontCreate);
	if (!owner || owner->GetTexture() != texture) return;
	if (!image || image->Layout != VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL) { Fail("Camera producer did not complete its sampled layout"); return; }
	const bool first = texture->bFirstUpdate;
	const bool requested = texture->CheckNeedsUpdate();
	if (!first && !requested) { Fail("Demanded camera producer has no actual update request"); return; }
	Capture(fb, image->Image.get(), image->View.get(), 0, first ? "camera-PFVCAM-startup" : "camera-PFVCAM-demanded", SceneKey(),
		std::string("{\"firstUpdate\":") + (first ? "true" : "false") + ",\"requestedUpdate\":" + (requested ? "true" : "false") + "}");
}
}

CCMD(pf020vk_dump)
{
	if (!Enabled()) { Printf("PF020 Vulkan observation is not enabled.\n"); return; }
	auto& state = State();
	try
	{
		Require(argv.argc() == 2 && std::string(argv[1]) == state.Prefix, "PF020 Vulkan dump prefix must match the explicit launch prefix");
		std::lock_guard<std::mutex> lock(state.Mutex);
		Require(!state.Written, "PF020 Vulkan observation already written");
		std::ostringstream out;
		out << "{\"schema\":\"shadedoomvk-pf020-vulkan-observation/v1\",\"status\":" << Quote(state.Error.empty() ? "COLLECTED_PENDING_VALIDATION" : "FAIL")
			<< ",\"error\":" << Quote(state.Error) << ",\"freezeAccepted\":false,\"performanceMeasured\":false,\"sourceBranch\":";
#ifdef PF020_ORIGINAL_SEAMS
		out << "\"source-derived-original-seams\",\"productionNamedKeysAvailable\":false";
#else
		out << "\"current-named-seams\",\"productionNamedKeysAvailable\":true";
#endif
		out << ",\"shaderClassification\":{\"firstUserShader\":" << FIRST_USER_SHADER << ",\"builtinShaderCount\":" << NUM_BUILTIN_SHADERS
			<< ",\"basis\":\"actual textures.h enum and emitted EffectState\"},\"workerState\":{\"queued\":" << state.QueuedWorkers << ",\"active\":" << state.ActiveWorkers
			<< ",\"pendingMainPublications\":" << state.PendingMain << ",\"failed\":" << state.FailedWorkers
			<< ",\"scheduledPrecache\":" << state.ScheduledPrecache << ",\"scheduledPriority\":" << state.ScheduledPriority
			<< ",\"completedWorkers\":" << state.CompletedWorkers << ",\"completedMainPublications\":" << state.CompletedMain
			<< ",\"allObservedTasksCompleted\":" << (!state.QueuedWorkers && !state.ActiveWorkers && !state.PendingMain && !state.FailedWorkers ? "true" : "false")
			<< "},\"images\":[";
		for (size_t i = 0; i < state.Images.size(); ++i) { if (i) out << ','; out << state.Images[i]; }
		out << "],\"keyLookups\":[";
		bool first = true;
		for (const auto& item : state.Keys) { if (!first) out << ','; first = false; out << "{\"count\":" << item.second << ",\"observation\":" << item.first << '}'; }
		out << "],\"cacheEventsAtDump\":[";
		for (size_t i = 0; i < state.CacheEvents.size(); ++i) { if (i) out << ','; out << state.CacheEvents[i]; }
		out << "],\"cacheShutdownEvents\":" << Quote(state.Prefix + ".cache-events.jsonl")
			<< ",\"limits\":[\"scene images are separate root observer/presentation evidence\",\"cache shutdown saves require completed process-exit receipt\",\"cold/warm applies to two application files, not driver-global caches\",\"same-format readback and key parity require independent validation\"]}\n";
		WriteFresh(state.Prefix + ".vulkan.json", out.str());
		state.Written = true;
		Printf("PF020 Vulkan observations retained; native evidence remains pending validation.\n");
	}
	catch (const std::exception& error) { Fail(error.what()); }
}
