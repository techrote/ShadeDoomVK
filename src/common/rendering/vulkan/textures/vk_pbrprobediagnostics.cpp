/*
 * PF-113: explicit, bounded native probe acceptance diagnostics.
 * Newly authored diagnostics. Normal scene/probe production remains authoritative.
 * The known original fixed-2D-as-cube path is never submitted to Vulkan.
 */
#include "vk_pbrprobediagnostics.h"
#include "c_dispatch.h"
#include "c_cvars.h"
#include "m_argv.h"
#include "g_levellocals.h"
#include "cmdlib.h"
#include "printf.h"
#include "v_video.h"
#include "filesystem.h"
#include "gametexture.h"
#include "hw_material.h"
#include "vulkan/vk_renderdevice.h"
#include "vulkan/vk_renderstate.h"
#include "vulkan/commands/vk_commandbuffer.h"
#include "vulkan/descriptorsets/vk_descriptorset.h"
#include "vulkan/samplers/vk_samplers.h"
#include "vulkan/textures/vk_texture.h"
#include "vulkan/textures/vk_renderbuffers.h"
#include <zvulkan/vulkanbuilders.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <cstddef>
#include <fstream>
#include <iomanip>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <vector>

EXTERN_CVAR(Bool, gl_ubershaders)
EXTERN_CVAR(Bool, gl_levelmesh)
EXTERN_CVAR(Bool, gl_lightprobe)
EXTERN_CVAR(Int, gl_light_shadows)
EXTERN_CVAR(Int, gl_texture_filter)
EXTERN_CVAR(Int, vid_rendermode)

namespace
{
constexpr int ControlWidth = 32, ControlHeight = 10;
constexpr float Tolerance = 0.0003f;

void Require(bool condition, const std::string& message)
{
	if (!condition) throw std::runtime_error(message);
}
template<class T> uint64_t Handle(T value)
{
	if constexpr (std::is_pointer<T>::value) return uint64_t(reinterpret_cast<uintptr_t>(value));
	else return uint64_t(value);
}
std::string Quote(const std::string& value)
{
	std::ostringstream out;
	out << '"';
	for (unsigned char c : value)
	{
		if (c == '"' || c == '\\') out << '\\' << char(c);
		else if (c < 32) out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << int(c) << std::dec;
		else out << char(c);
	}
	out << '"';
	return out.str();
}
void FreshPrefix(const std::string& prefix)
{
	Require(!prefix.empty() && prefix.size() < 1000, "A bounded fresh output prefix is required");
	const auto parent = ExtractFilePath(prefix.c_str());
	Require(parent.Len() > 0 && DirExists(parent.GetChars()), "Output parent must already exist");
	Require(!FileExists((prefix + ".json").c_str()), "Output receipt already exists; use a fresh prefix");
}
void Write(const std::string& path, const void* bytes, size_t count)
{
	Require(!FileExists(path.c_str()), "Artifact already exists: " + path);
	std::ofstream out(path, std::ios::binary);
	Require(bool(out), "Cannot create artifact: " + path);
	out.write(static_cast<const char*>(bytes), std::streamsize(count));
	out.close();
	Require(bool(out), "Incomplete artifact write: " + path);
}
void Write(const std::string& path, const std::string& bytes) { Write(path, bytes.data(), bytes.size()); }
std::string Load(const char* name)
{
	const int lump = fileSystem.CheckNumForFullName(name, 0);
	Require(lump >= 0, std::string("Required packaged renderer lump missing: ") + name);
	return GetStringFromLump(lump).GetChars();
}
std::string Function(const std::string& source, const std::string& signature)
{
	const size_t start = source.find(signature);
	Require(start != std::string::npos && source.find(signature, start + signature.size()) == std::string::npos,
		"Packaged shader signature missing/ambiguous: " + signature);
	const size_t open = source.find('{', start);
	Require(open != std::string::npos, "Shader function has no body");
	unsigned depth = 0;
	for (size_t i = open; i < source.size(); ++i)
	{
		if (source[i] == '{') ++depth;
		if (source[i] == '}' && --depth == 0) return source.substr(start, i + 1 - start);
	}
	throw std::runtime_error("Packaged shader body is incomplete");
}
void ReplaceOnce(std::string& source, const std::string& before, const std::string& after)
{
	const auto at = source.find(before);
	Require(at != std::string::npos && source.find(before, at + before.size()) == std::string::npos,
		"Diagnostic shader extraction boundary changed");
	source.replace(at, before.size(), after);
}
std::string ViewJson(VulkanImageView* view)
{
	Require(view && view->GetCreationArguments().Captured, "Actual image-view creation arguments are unavailable");
	const auto& c = view->GetCreationArguments();
	std::ostringstream out;
	out << "{\"handle\":" << Handle(view->view) << ",\"image\":" << Handle(c.Image)
		<< ",\"type\":" << int(c.ViewType) << ",\"format\":" << int(c.Format)
		<< ",\"baseMip\":" << c.Range.baseMipLevel << ",\"mips\":" << c.Range.levelCount
		<< ",\"baseLayer\":" << c.Range.baseArrayLayer << ",\"layers\":" << c.Range.layerCount
		<< ",\"aspect\":" << c.Range.aspectMask << ",\"basis\":\"captured-successful-vkCreateImageView-arguments\"}";
	return out.str();
}
std::string SamplerJson(VulkanSampler* sampler)
{
	Require(sampler && sampler->GetCreationArguments().Captured, "Actual sampler creation arguments unavailable");
	const auto& c = sampler->GetCreationArguments();
	std::ostringstream out;
	out << "{\"handle\":" << Handle(sampler->sampler) << ",\"minFilter\":" << int(c.MinFilter)
		<< ",\"magFilter\":" << int(c.MagFilter) << ",\"mipmapMode\":" << int(c.MipmapMode)
		<< ",\"bias\":" << c.MipLodBias << ",\"minLod\":" << c.MinLod << ",\"maxLod\":" << c.MaxLod
		<< ",\"anisotropy\":" << (c.AnisotropyEnable ? "true" : "false") << ",\"maxAnisotropy\":" << c.MaxAnisotropy
		<< ",\"address\":[" << int(c.AddressU) << ',' << int(c.AddressV) << ',' << int(c.AddressW)
		<< "],\"basis\":\"captured-successful-vkCreateSampler-arguments\"}";
	return out.str();
}
void CubeContract(VkTextureImage& map, VulkanSampler* sampler, bool irradiance)
{
	Require(map.Image && map.View && map.Image->layerCount == 6, "Actual published cube owner missing");
	const auto& v = map.View->GetCreationArguments();
	Require(v.Captured && v.ViewType == VK_IMAGE_VIEW_TYPE_CUBE && v.Image == map.Image->image &&
		v.Range.baseMipLevel == 0 && v.Range.baseArrayLayer == 0 && v.Range.layerCount == 6,
		"Published owner/view cube identity differs");
	Require(v.Range.levelCount == unsigned(irradiance ? 1 : 5) &&
		map.Image->mipLevels == (irradiance ? 1 : 5), "Published probe mip contract changed");
	const auto& s = sampler->GetCreationArguments();
	Require(s.Captured && s.MinFilter == VK_FILTER_LINEAR && s.MagFilter == VK_FILTER_LINEAR &&
		s.MipLodBias == 0.0f && s.AnisotropyEnable == VK_FALSE, "Dedicated probe sampling contract changed");
}
std::string FixedJson(VulkanRenderDevice* fb)
{
	auto textures = fb->GetTextureManager();
	auto nullView = textures->GetNullTextureView(), brdfView = textures->GetBrdfLutTextureView();
	Require(nullView && brdfView && nullView->GetCreationArguments().ViewType == VK_IMAGE_VIEW_TYPE_2D &&
		brdfView->GetCreationArguments().ViewType == VK_IMAGE_VIEW_TYPE_2D, "Fixed slots are not the actual 2D null/BRDF owners");
	return "{\"nullSlot\":0,\"brdfSlot\":1,\"null\":" + ViewJson(nullView) + ",\"brdf\":" + ViewJson(brdfView) + "}";
}
struct SceneDraw
{
	std::string kind, source, metadata;
	std::vector<uint32_t> vert, frag;
	SurfaceUniforms uniforms = {};
};
struct StartupObserver
{
	bool Checked = false, Enabled = false;
	std::string Prefix, Error;
	VulkanRenderDevice* Device = nullptr;
	VkRenderState* BoundState = nullptr;
	uint64_t BoundPipeline = 0;
	unsigned CompletedPublications = 0;
	std::vector<std::string> PublicationEvents;
	std::vector<SceneDraw> Draws;
} Observer;

bool HasDraw(const char* kind)
{
	for (const auto& draw : Observer.Draws) if (draw.kind == kind) return true;
	return false;
}
void SaveObserver(VulkanRenderDevice* fb)
{
	Require(Observer.Enabled && Observer.Device == fb, "No matching explicit startup observer");
	Require(Observer.Error.empty(), "Startup observer failed: " + Observer.Error);
	Require(HasDraw("initial-missing-probe1") && HasDraw("initial-live-authored0") && HasDraw("published-live-probe1") &&
		Observer.PublicationEvents.size() == 2, "Actual initial missing/publication/live draw sequence was not observed");
	FreshPrefix(Observer.Prefix);
	std::ostringstream json;
	json << "{\"schema\":\"shadedoomvk-pf113-startup-observer/v1\",\"status\":\"PASS\","
		<< "\"scope\":\"actual immediate PBR command emission and unmodified completed-pass publication; later normal fence waited\","
		<< "\"fixed\":" << FixedJson(fb) << ",\"events\":[";
	bool comma = false;
	for (const auto& event : Observer.PublicationEvents) { if (comma) json << ','; json << event; comma = true; }
	json << "],\"draws\":[";
	comma = false;
	for (const auto& draw : Observer.Draws)
	{
		if (comma) json << ',';
		const std::string stem = Observer.Prefix + "-" + draw.kind;
		Write(stem + ".vert.spv", draw.vert.data(), draw.vert.size() * 4);
		Write(stem + ".frag.spv", draw.frag.data(), draw.frag.size() * 4);
		Write(stem + ".uniforms.bin", &draw.uniforms, sizeof(draw.uniforms));
		json << "{\"kind\":" << Quote(draw.kind) << ",\"material\":" << Quote(draw.source)
			<< ",\"state\":" << draw.metadata << ",\"vertexSpirv\":" << Quote(stem + ".vert.spv")
			<< ",\"fragmentSpirv\":" << Quote(stem + ".frag.spv") << ",\"uniformBytes\":" << Quote(stem + ".uniforms.bin") << '}';
		comma = true;
	}
	json << "],\"completedPublicationsAtFinalCommand\":" << Observer.CompletedPublications << '}';
	Write(Observer.Prefix + "-packaged-pbr.glsl", Load("shaders/scene/lightmodel_pbr.glsl"));
	Write(Observer.Prefix + ".json", json.str());
}
} // namespace

// Access is confined to this opt-in observer; no production state is modified.
struct FPbrProbeDiagnosticAccess
{
	static void Observe(VkRenderState* state, int count, bool indexed)
	{
		auto fb = state->fb;
		auto material = state->mMaterial.mMaterial;
		if (!material || !material->Source() || state->mPipelineKey.ShaderKey.EffectState != SHADER_PBR ||
			state->mPipelineKey.ShaderKey.SpecialEffect != EFF_NONE) return;
		const std::string name = material->Source()->GetName().GetChars();
		if (name != "PF113W" && name != "PF113FL") return;
		Require(!gl_ubershaders && !gl_levelmesh, "Startup fixture must explicitly use immediate specialized scene shaders");
		Require(!level.MapName.CompareNoCase("PF113") && level.lightProbes.Size() == 2, "Observer requires the exact fresh two-probe PF113 fixture");
		const int authored = state->mLightProbeIndex;
		const unsigned token = state->mSurfaceUniforms.uLightProbeIndex;
		const char* kind = nullptr;
		if (authored == 1 && token == 0 && Observer.CompletedPublications == 0) kind = "initial-missing-probe1";
		if (authored == 0 && token != 0 && Observer.CompletedPublications == 0) kind = "initial-live-authored0";
		if (authored == 1 && token != 0 && Observer.CompletedPublications >= 1) kind = "published-live-probe1";
		if (!kind || HasDraw(kind)) return;
		Require(Observer.BoundState == state && Observer.BoundPipeline != 0 && count > 0 && state->mCommandBuffer,
			"Actual bound scene pipeline/command buffer unavailable");
		auto textures = fb->GetTextureManager();
		if (Observer.CompletedPublications == 0)
			Require(textures->Irradiancemaps.size() == 1 && textures->Prefiltermaps.size() == 1, "Missing state was not initial one-pair publication");
		else Require(textures->Irradiancemaps.size() == 2 && textures->Prefiltermaps.size() == 2, "Completed two-pair publication missing");
		auto manager = fb->GetDescriptorSetManager();
		CubeContract(textures->Irradiancemaps[0], fb->GetSamplerManager()->IrradiancemapSampler.get(), true);
		CubeContract(textures->Prefiltermaps[0], fb->GetSamplerManager()->PrefiltermapSampler.get(), false);
		if (token)
		{
			CubeContract(textures->Irradiancemaps[authored], fb->GetSamplerManager()->IrradiancemapSampler.get(), true);
			CubeContract(textures->Prefiltermaps[authored], fb->GetSamplerManager()->PrefiltermapSampler.get(), false);
		}
		if (token)
			Require(manager->GetBindlessIdentity(int(token)).Span == 2 &&
				manager->ValidateBindlessIdentity(manager->GetBindlessIdentity(int(token))), "Published runtime probe pair lacks live PF identity");
		auto program = fb->GetShaderManager()->GetProgram(state->mPipelineKey.ShaderKey, false);
		Require(program && !program->vert.empty() && !program->frag.empty(), "Bound specialized scene shader bytecode missing");
		SceneDraw draw;
		draw.kind = kind; draw.source = name; draw.vert = program->vert; draw.frag = program->frag;
		draw.uniforms = state->mSurfaceUniforms;
		std::ostringstream out;
		out << "{\"authoredProbe\":" << authored << ",\"runtimeProbe\":" << token
			<< ",\"publishedPairs\":" << textures->Irradiancemaps.size() << ",\"publicationCount\":" << Observer.CompletedPublications
			<< ",\"commandBuffer\":" << Handle(state->mCommandBuffer->buffer) << ",\"pipeline\":" << Observer.BoundPipeline
			<< ",\"shaderIndex\":" << material->GetShaderIndex() << ",\"effectState\":" << state->mPipelineKey.ShaderKey.EffectState
			<< ",\"shaderKey\":" << state->mPipelineKey.ShaderKey.AsQWORD << ",\"shaderLayout\":" << state->mPipelineKey.ShaderKey.Layout.AsDWORD
			<< ",\"pipelineKey\":" << state->mPipelineKey.AsQWORD << ",\"uniformProbe\":" << draw.uniforms.uLightProbeIndex
			<< ",\"uniformTexture\":" << draw.uniforms.uTextureIndex << ",\"surfaceDataIndex\":" << state->mPushConstants.uDataIndex
			<< ",\"uniformSize\":" << sizeof(SurfaceUniforms) << ",\"probeOffset\":" << offsetof(SurfaceUniforms, uLightProbeIndex)
			<< ",\"textureOffset\":" << offsetof(SurfaceUniforms, uTextureIndex)
			<< ",\"drawCount\":" << count << ",\"indexed\":" << (indexed ? "true" : "false")
			<< ",\"targetWidth\":" << state->mRenderTarget.Width << ",\"targetHeight\":" << state->mRenderTarget.Height
			<< ",\"targetFormat\":" << int(state->mRenderTarget.Format) << ",\"targetSamples\":" << int(state->mRenderTarget.Samples)
			<< ",\"targetView\":" << ViewJson(state->mRenderTarget.Image->View.get())
			<< ",\"viewOwnerOrdinal\":" << (token ? authored : 0) << ",\"missingTokenSamplesNoCube\":" << (token ? "false" : "true")
			<< ",\"irradianceView\":" << ViewJson(textures->Irradiancemaps[token ? authored : 0].View.get())
			<< ",\"prefilterView\":" << ViewJson(textures->Prefiltermaps[token ? authored : 0].View.get())
			<< ",\"irradianceSampler\":" << SamplerJson(fb->GetSamplerManager()->IrradiancemapSampler.get())
			<< ",\"prefilterSampler\":" << SamplerJson(fb->GetSamplerManager()->PrefiltermapSampler.get()) << '}';
		draw.metadata = out.str();
		Observer.Device = fb;
		Observer.Draws.push_back(std::move(draw));
	}
};

namespace Pf113ProbeDiagnostics
{
bool Observing()
{
	if (!Observer.Checked)
	{
		Observer.Checked = true;
		if (Args && Args->CheckParm("-pf113observe"))
		{
			Observer.Enabled = true;
			try
			{
				const char* prefix = Args->CheckValue("-pf113observe");
				Require(prefix != nullptr && Args->CheckParm("-pf113observe", Args->CheckParm("-pf113observe") + 1) == 0,
					"Exactly one -pf113observe value is required");
				Observer.Prefix = prefix;
				FreshPrefix(Observer.Prefix);
			}
			catch (const std::exception& e) { Observer.Error = e.what(); }
		}
	}
	return Observer.Enabled && Observer.Error.empty();
}
void BoundPipeline(VkRenderState* state, VulkanPipeline* pipeline)
{
	Observer.BoundState = state;
	Observer.BoundPipeline = pipeline ? Handle(pipeline->pipeline) : 0;
}
void DrawEmitted(VkRenderState* state, int count, bool indexed)
{
	try { FPbrProbeDiagnosticAccess::Observe(state, count, indexed); }
	catch (const std::exception& e) { Observer.Error = e.what(); }
}
void Publication(VulkanRenderDevice* fb, bool completed)
{
	if (level.MapName.CompareNoCase("PF113") != 0 || level.lightProbes.Size() != 2) return;
	try
	{
		if (completed) ++Observer.CompletedPublications;
		if (Observer.PublicationEvents.size() >= 2) return;
		auto textures = fb->GetTextureManager();
		std::ostringstream out;
		out << "{\"kind\":" << Quote(completed ? "completed-publication" : "before-completed-publication")
			<< ",\"sequence\":" << Observer.CompletedPublications << ",\"irradiancePairs\":" << textures->Irradiancemaps.size()
			<< ",\"prefilterPairs\":" << textures->Prefiltermaps.size() << ",\"authoredCount\":" << level.lightProbes.Size()
			<< ",\"authoredPositions\":[";
		for (unsigned i = 0; i < level.lightProbes.Size(); ++i)
		{
			if (i) out << ',';
			const auto& p = level.lightProbes[i];
			out << "{\"ordinal\":" << p.index << ",\"position\":[" << p.position.X << ',' << p.position.Y << ',' << p.position.Z << "]}";
		}
		out << "]}";
		Observer.PublicationEvents.push_back(out.str());
	}
	catch (const std::exception& e) { Observer.Error = e.what(); }
}
} // namespace Pf113ProbeDiagnostics

namespace
{
struct PrivateBoundary
{
	VulkanRenderDevice* fb;
	explicit PrivateBoundary(VulkanRenderDevice* device) : fb(device)
	{
		fb->GetRenderState()->EndRenderPass();
		fb->GetCommands()->WaitForCommands(false);
	}
	~PrivateBoundary()
	{
		// No main image was redirected or cleared. Force the inherited scene
		// target/pipeline/viewpoint/vertex/index bindings to be re-established.
		auto buffers = fb->GetBuffers();
		fb->GetRenderState()->SetRenderTarget(&buffers->SceneColor, buffers->SceneDepthStencil.View.get(),
			buffers->GetWidth(), buffers->GetHeight(), VK_FORMAT_R16G16B16A16_SFLOAT, buffers->GetSceneSamples());
		fb->GetRenderState()->EndRenderPass();
	}
};

struct NativeControls
{
	VulkanRenderDevice* fb;
	std::string prefix;
	unsigned checks = 0;
	std::vector<std::string> cases;
	std::string resourcesJson;
	std::array<int, 4> slots = { -1, -1, -1, -1 }; // pairA, unused gap, pairB, real UINT map
	std::array<FRendererResourceIdentity, 4> identities;
	VkTextureImage color, depth, map;
	std::array<VkTextureImage, 4> cubes;
	std::unique_ptr<VulkanRenderPass> pass;
	std::unique_ptr<VulkanPipelineLayout> layout;
	std::unique_ptr<VulkanPipeline> candidate, original;
	std::map<std::string, std::vector<float>> results;
	std::string fixedBefore, fixedAfter;
	float maxLiveParity = 0.0f, maxMixedError = 0.0f;
	unsigned zeroSamples = 0, positiveLiveSamples = 0, divergenceWitnesses = 0;
	bool retired = false;
	bool passOpen = false;
	bool shadersCompiled = false, retirementFenceCompleted = false;
	NativeControls(VulkanRenderDevice* device, std::string output) : fb(device), prefix(std::move(output)) { }

	void Check(bool condition, const char* message) { ++checks; Require(condition, message); }
	~NativeControls()
	{
		// Command-owned objects always use the inherited fence retirement list,
		// including exceptions after recording but before a readback wait.
		if (!retired)
		{
			try
			{
				if (passOpen) { fb->GetCommands()->GetDrawCommands()->endRenderPass(); passOpen = false; }
				fb->GetCommands()->WaitForCommands(false);
				Retire();
				fb->GetCommands()->WaitForCommands(false);
			}
			catch (...) { Printf("PF113 cleanup could not complete its normal fence boundary.\n"); }
		}
	}

	void Retire()
	{
		auto manager = fb->GetDescriptorSetManager();
		for (int& slot : slots) if (slot >= 0) { manager->FreeBindlessSlot(slot); slot = -1; }
		for (auto& cube : cubes) cube.Reset(fb);
		map.Reset(fb); color.Reset(fb); depth.Reset(fb);
		retired = true;
	}

	std::string ShaderSource(bool originalUniform) const
	{
		const std::string source = Load("shaders/scene/lightmodel_pbr.glsl");
		const std::string shared = Load("shaders/scene/lightmodel_shared.glsl");
		const auto constantsEnd = shared.find("float distanceAttenuation");
		Require(constantsEnd != std::string::npos, "Packaged PBR calibration constants missing");
		const auto helperStart = source.find("float DistributionGGX(");
		Require(helperStart != std::string::npos, "Packaged PBR constants missing");
		std::string helpers = source.substr(0, helperStart);
		for (const char* signature : { "float DistributionGGX(", "float GeometrySchlickGGX(", "float GeometrySmith(",
			"vec3 fresnelSchlick(", "vec3 fresnelSchlickRoughness(", "vec3 SampleProbeIrradiance(", "vec3 SampleProbePrefiltered(" })
			helpers += Function(source, signature) + "\n";
		std::string consumer = Function(source, "vec3 ProcessMaterialLight(");
		const std::string gather = "uvec4 probeIndexes = textureGather(uintTextures[nonuniformEXT(vLightmapIndex + 1)], vLightmap.xy);";
		ReplaceOnce(consumer, gather, gather + "\n\tdiagTaps = probeIndexes;");
		ReplaceOnce(consumer, "float t11 = t.x * t.y;", "float t11 = t.x * t.y;\n\tdiagWeights = vec4(t00,t10,t01,t11);");
		if (originalUniform)
		{
			// Only this valid uniform branch is run. The actual original two
			// expressions are retained; no zero or varying original index is used.
			ReplaceOnce(consumer, "irradiance = SampleProbeIrradiance(uint(uLightProbeIndex), N);",
				"irradiance = texture(cubeTextures[uLightProbeIndex], N).rgb;");
			ReplaceOnce(consumer, "prefilteredColor = SampleProbePrefiltered(uint(uLightProbeIndex), R, roughness * MAX_REFLECTION_LOD);",
				"prefilteredColor = textureLod(cubeTextures[uLightProbeIndex + 1], R, roughness * MAX_REFLECTION_LOD).rgb;");
		}
		ReplaceOnce(consumer, "return color;",
			"diagIrradiance=irradiance; diagPrefiltered=prefilteredColor; diagDiffuse=diffuse; diagSpecular=specular;\n"
			"diagLo=Lo; diagFinal=color; diagN=N; diagR=R;\n\treturn color;");
		std::string sourceText = R"GLSL(#version 460
#extension GL_EXT_nonuniform_qualifier : require
#define UBERSHADER
#define BrdfLUT 1
layout(set=2,binding=0) uniform sampler2D textures[];
layout(set=2,binding=0) uniform samplerCube cubeTextures[];
layout(set=2,binding=0) uniform usampler2D uintTextures[];
layout(push_constant) uniform Control { uvec4 slots; vec4 parameters; } control;
layout(location=0) out vec4 Result;
struct Material { vec4 Base; vec3 Normal; float Metallic; float Roughness; float AO; };
vec4 pixelpos, uCameraPos, uDynLightColor;
vec3 SunDir, SunColor;
float SunIntensity;
uint uLightProbeIndex;
int vLightmapIndex;
vec2 vLightmap;
vec3 diagIrradiance,diagPrefiltered,diagDiffuse,diagSpecular,diagLo,diagFinal,diagN,diagR;
uvec4 diagTaps;
vec4 diagWeights;
)GLSL";
		sourceText += shared.substr(0, constantsEnd) + helpers + consumer + "\n";
		sourceText += R"GLSL(
void main()
{
	int x=int(gl_FragCoord.x);
	int band=int(gl_FragCoord.y);
	uint mode=control.slots.w;
	uLightProbeIndex=control.slots.x;
	vLightmapIndex=-1;
	vLightmap=vec2(0.25,0.6);
	if(mode==0u) uLightProbeIndex=0u;
	if(mode==1u) { uLightProbeIndex=0u; vLightmapIndex=int(control.slots.z)-1; }
	if(mode==2u) uLightProbeIndex=(x%3==0)?0u:control.slots.x;
	if(mode==3u) uLightProbeIndex=(x%3==0)?control.slots.y:control.slots.x;
	// Adjacent directions straddle cube faces; all bands share the same
	// direction at x, enabling independent CPU comparison of exported terms.
	vec3 directions[8]=vec3[8](vec3(1,.98,.2),vec3(.98,1,.2),vec3(1,1.001,-.2),
		vec3(-1,.99,.15),vec3(.2,1,.99),vec3(.2,.99,1),vec3(.99,.1,-1),vec3(1,.1,-.99));
	Material material;
	material.Base=vec4(.35,.45,.6,1);
	material.Normal=normalize(directions[x%8]+vec3(float(x/8)*.015,0,0));
	material.Metallic=.25;
	material.Roughness=control.parameters.x;
	material.AO=.7;
	pixelpos=vec4(0,0,0,1);
	uCameraPos=vec4(.15,.25,1,1);
	uDynLightColor=vec4(.11,.07,.03,0);
	SunDir=vec3(0,0,1); SunColor=vec3(0); SunIntensity=0;
	diagTaps=uvec4(uLightProbeIndex,0,0,0);
	diagWeights=vec4(1,0,0,0);
	ProcessMaterialLight(material,vec3(.23,.19,.17),0.0);
	if(band==0) Result=vec4(diagIrradiance,1);
	else if(band==1) Result=vec4(diagPrefiltered,1);
	else if(band==2) Result=vec4(diagDiffuse,1);
	else if(band==3) Result=vec4(diagSpecular,1);
	else if(band==4) Result=vec4(diagLo,1);
	else if(band==5) Result=vec4(diagFinal,1);
	else if(band==6) Result=vec4(diagN,material.Roughness);
	else if(band==7) Result=vec4(diagR,float(uLightProbeIndex));
	else if(band==8) Result=vec4(diagTaps);
	else Result=diagWeights;
}
)GLSL";
		return sourceText;
	}

	static uint16_t ExactHalf(float value)
	{
		// Fixtures use positive binary fractions representable exactly in half.
		uint32_t bits;
		std::memcpy(&bits, &value, sizeof(bits));
		const int exponent = int((bits >> 23) & 255) - 127 + 15;
		Require(value > 0 && exponent > 0 && exponent < 31 && (bits & 0x1fff) == 0,
			"Diagnostic cube value is not exactly binary16 representable");
		return uint16_t((unsigned(exponent) << 10) | ((bits & 0x7fffff) >> 13));
	}

	void Upload(VkTextureImage& image, const void* data, size_t bytes, const std::vector<VkBufferImageCopy>& regions,
		int mips, int layers)
	{
		auto staging = BufferBuilder().Size(bytes).Usage(VK_BUFFER_USAGE_TRANSFER_SRC_BIT, VMA_MEMORY_USAGE_CPU_ONLY)
			.DebugName("PF113.ImmutableUpload").Create(fb->GetDevice());
		void* mapped = staging->Map(0, bytes);
		Require(mapped, "Diagnostic upload map failed");
		std::memcpy(mapped, data, bytes);
		staging->Unmap();
		auto commands = fb->GetCommands()->GetDrawCommands();
		VkImageTransition().AddImage(&image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, false, 0, mips, 0, layers).Execute(commands);
		commands->copyBufferToImage(staging->buffer, image.Image->image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
			unsigned(regions.size()), regions.data());
		VkImageTransition().AddImage(&image, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL, false, 0, mips, 0, layers).Execute(commands);
		fb->GetCommands()->DrawDeleteList->Add(std::move(staging));
	}

	void MakeCube(unsigned number)
	{
		const bool irradiance = number % 2 == 0;
		const int size = irradiance ? 32 : 128, mips = irradiance ? 1 : 5;
		auto& image = cubes[number];
		image.Image = ImageBuilder().Size(size, size, mips, 6).Format(VK_FORMAT_R16G16B16A16_SFLOAT)
			.Flags(VK_IMAGE_CREATE_CUBE_COMPATIBLE_BIT).Usage(VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT)
			.DebugName("PF113.PrivateSpatialCube").Create(fb->GetDevice());
		image.View = ImageViewBuilder().Type(VK_IMAGE_VIEW_TYPE_CUBE).Image(image.Image.get(), VK_FORMAT_R16G16B16A16_SFLOAT)
			.DebugName("PF113.PrivateSpatialCubeView").Create(fb->GetDevice());
		std::vector<uint16_t> pixels;
		std::vector<VkBufferImageCopy> regions;
		for (int face = 0; face < 6; ++face)
			for (int mip = 0; mip < mips; ++mip)
			{
				const int extent = size >> mip;
				VkBufferImageCopy region = {};
				region.bufferOffset = pixels.size() * 2;
				region.imageSubresource = { VK_IMAGE_ASPECT_COLOR_BIT, unsigned(mip), unsigned(face), 1 };
				region.imageExtent = { unsigned(extent), unsigned(extent), 1 };
				regions.push_back(region);
				for (int y = 0; y < extent; ++y) for (int x = 0; x < extent; ++x) for (int c = 0; c < 4; ++c)
				{
					const float value = c == 3 ? 1.0f : .125f * float(number + 1) + float(c + face) / 32.0f +
						float(x) / 256.0f + float(y) / 512.0f + float(mip) / 16.0f;
					pixels.push_back(ExactHalf(value));
				}
			}
		Write(prefix + "-cube" + std::to_string(number) + ".rgba16f", pixels.data(), pixels.size() * 2);
		Upload(image, pixels.data(), pixels.size() * 2, regions, mips, 6);
		auto sampler = irradiance ? fb->GetSamplerManager()->IrradiancemapSampler.get() : fb->GetSamplerManager()->PrefiltermapSampler.get();
		CubeContract(image, sampler, irradiance);
		fb->GetDescriptorSetManager()->SetBindlessTexture(slots[number < 2 ? 0 : 2] + int(number % 2), image.View.get(), sampler);
	}

	void Setup()
	{
		VkFormatProperties floatProperties = {}, cubeProperties = {};
		vkGetPhysicalDeviceFormatProperties(fb->GetDevice()->PhysicalDevice.Device, VK_FORMAT_R32G32B32A32_SFLOAT, &floatProperties);
		vkGetPhysicalDeviceFormatProperties(fb->GetDevice()->PhysicalDevice.Device, VK_FORMAT_R16G16B16A16_SFLOAT, &cubeProperties);
		Check((floatProperties.optimalTilingFeatures & VK_FORMAT_FEATURE_COLOR_ATTACHMENT_BIT) != 0,
			"Native adapter does not support the private float attachment");
		Check((cubeProperties.optimalTilingFeatures & (VK_FORMAT_FEATURE_SAMPLED_IMAGE_BIT | VK_FORMAT_FEATURE_SAMPLED_IMAGE_FILTER_LINEAR_BIT)) ==
			(VK_FORMAT_FEATURE_SAMPLED_IMAGE_BIT | VK_FORMAT_FEATURE_SAMPLED_IMAGE_FILTER_LINEAR_BIT), "Native sampled linear cube format unsupported");
		fixedBefore = FixedJson(fb);
		auto manager = fb->GetDescriptorSetManager();
		slots[0] = manager->AllocBindlessSlot(2);
		slots[1] = manager->AllocBindlessSlot(3); // deliberately nonordinal/unpublished gap; dynamically unused
		slots[2] = manager->AllocBindlessSlot(2);
		slots[3] = manager->AllocBindlessSlot(1);
		for (unsigned i = 0; i < slots.size(); ++i)
		{
			Check(slots[i] >= manager->GetBindlessDynamicStart(), "Private slot must be allocator-backed dynamic identity");
			identities[i] = manager->GetBindlessIdentity(slots[i]);
			Check(manager->ValidateBindlessIdentity(identities[i]), "Private allocation must be live");
		}
		Check(slots[2] != slots[0] + 2 && slots[0] != 1 && slots[2] != 3, "Nonordinal separated pairs required");
		for (unsigned i = 0; i < cubes.size(); ++i) MakeCube(i);
		map.Image = ImageBuilder().Size(2, 2).Format(VK_FORMAT_R16_UINT)
			.Usage(VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT).DebugName("PF113.PrivateProbeMap").Create(fb->GetDevice());
		map.View = ImageViewBuilder().Image(map.Image.get(), VK_FORMAT_R16_UINT).DebugName("PF113.PrivateProbeMapView").Create(fb->GetDevice());
		// UINT textures require nearest filtering. textureGather keeps the actual
		// production coordinate/coefficient route and ignores min/mag selection.
		auto nearest = fb->GetSamplerManager()->Get(CLAMP_NOFILTER_XY);
		const auto& nearestArgs = nearest->GetCreationArguments();
		Check(nearestArgs.Captured && nearestArgs.MinFilter == VK_FILTER_NEAREST && nearestArgs.MagFilter == VK_FILTER_NEAREST,
			"Integer map sampler must be nearest");
		manager->SetBindlessTexture(slots[3], map.View.get(), nearest);
		color.Image = ImageBuilder().Size(ControlWidth, ControlHeight).Format(VK_FORMAT_R32G32B32A32_SFLOAT)
			.Usage(VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT)
			.DebugName("PF113.PrivateTermsTarget").Create(fb->GetDevice());
		color.View = ImageViewBuilder().Image(color.Image.get(), VK_FORMAT_R32G32B32A32_SFLOAT)
			.DebugName("PF113.PrivateTermsView").Create(fb->GetDevice());
		Check(fb->DepthStencilFormat != VK_FORMAT_UNDEFINED, "Native depth/stencil capability unavailable");
		depth.AspectMask = VK_IMAGE_ASPECT_DEPTH_BIT | VK_IMAGE_ASPECT_STENCIL_BIT;
		depth.Image = ImageBuilder().Size(ControlWidth, ControlHeight).Format(fb->DepthStencilFormat)
			.Usage(VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT).DebugName("PF113.PrivateDepth").Create(fb->GetDevice());
		depth.View = ImageViewBuilder().Image(depth.Image.get(), fb->DepthStencilFormat, depth.AspectMask).Create(fb->GetDevice());
		pass = RenderPassBuilder()
			.AddAttachment(VK_FORMAT_R32G32B32A32_SFLOAT, VK_SAMPLE_COUNT_1_BIT, VK_ATTACHMENT_LOAD_OP_CLEAR,
				VK_ATTACHMENT_STORE_OP_STORE, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL)
			.AddDepthStencilAttachment(fb->DepthStencilFormat, VK_SAMPLE_COUNT_1_BIT, VK_ATTACHMENT_LOAD_OP_CLEAR,
				VK_ATTACHMENT_STORE_OP_DONT_CARE, VK_ATTACHMENT_LOAD_OP_CLEAR, VK_ATTACHMENT_STORE_OP_DONT_CARE,
				VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL, VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL)
			.AddSubpass().AddSubpassColorAttachmentRef(0, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL)
			.AddSubpassDepthStencilAttachmentRef(1, VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL)
			.DebugName("PF113.PrivateRenderPass").Create(fb->GetDevice());
		color.PPFramebuffer = FramebufferBuilder().RenderPass(pass.get()).AddAttachment(color.View.get()).AddAttachment(depth.View.get())
			.Size(ControlWidth, ControlHeight).Create(fb->GetDevice());
		layout = PipelineLayoutBuilder().AddSetLayout(manager->GetFixedLayout()).AddSetLayout(manager->GetRSBufferLayout())
			.AddSetLayout(manager->GetBindlessLayout()).AddPushConstantRange(VK_SHADER_STAGE_FRAGMENT_BIT, 0, 32).Create(fb->GetDevice());
		const std::string vertexSource = "#version 460\nvoid main(){vec2 p=vec2((gl_VertexIndex<<1)&2,gl_VertexIndex&2);gl_Position=vec4(p*2.0-1.0,0,1);}\n";
		auto vert = GLSLCompiler().Type(ShaderType::Vertex).AddSource("PF113.PrivateVertex", vertexSource).Compile(fb->GetDevice());
		Check(!vert.empty() && vert[0] == 0x07230203u, "Compiled diagnostic vertex SPIR-V missing");
		Write(prefix + "-control.vert.spv", vert.data(), vert.size() * 4);
		Write(prefix + "-control.vert.glsl", vertexSource);
		for (int variant = 0; variant < 2; ++variant)
		{
			const std::string shader = ShaderSource(variant != 0);
			auto frag = GLSLCompiler().Type(ShaderType::Fragment).AddSource("PF113.PackagedPbrControl", shader).Compile(fb->GetDevice());
			Check(!frag.empty() && frag[0] == 0x07230203u, "Compiled diagnostic fragment SPIR-V missing");
			const std::string stem = prefix + (variant ? "-original-uniform" : "-candidate");
			Write(stem + ".frag.spv", frag.data(), frag.size() * 4);
			Write(stem + ".frag.glsl", shader);
			auto pipeline = GraphicsPipelineBuilder().Layout(layout.get()).RenderPass(pass.get())
				.Topology(VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST).Viewport(0, 0, ControlWidth, ControlHeight)
				.Scissor(0, 0, ControlWidth, ControlHeight).Cull(VK_CULL_MODE_NONE, VK_FRONT_FACE_COUNTER_CLOCKWISE)
				.DepthStencilEnable(false, false, false).AddColorBlendAttachment(ColorBlendAttachmentBuilder().Create())
				.AddVertexShader(vert).AddFragmentShader(frag).DebugName("PF113.PrivatePbrTerms").Create(fb->GetDevice());
			if (variant) original = std::move(pipeline); else candidate = std::move(pipeline);
		}
		Write(prefix + "-packaged-pbr.glsl", Load("shaders/scene/lightmodel_pbr.glsl"));
		shadersCompiled = true;
		Write(prefix + "-packaged-calibration.glsl", Load("shaders/scene/lightmodel_shared.glsl"));
		std::ostringstream resource;
		resource << "{\"pairA\":" << slots[0] << ",\"pairB\":" << slots[2] << ",\"unusedGap\":" << slots[1]
			<< ",\"probeMap\":" << slots[3] << ",\"ownedCubeViews\":[";
		for (unsigned i = 0; i < cubes.size(); ++i) { if (i) resource << ','; resource << ViewJson(cubes[i].View.get()); }
		resource << "],\"irradianceSampler\":" << SamplerJson(fb->GetSamplerManager()->IrradiancemapSampler.get())
			<< ",\"prefilterSampler\":" << SamplerJson(fb->GetSamplerManager()->PrefiltermapSampler.get())
			<< ",\"mapView\":" << ViewJson(map.View.get()) << ",\"mapSampler\":" << SamplerJson(nearest)
			<< ",\"target\":" << ViewJson(color.View.get()) << ",\"depth\":" << ViewJson(depth.View.get()) << '}';
		resourcesJson = resource.str();
	}

	void Draw(const std::string& name, unsigned mode, float roughness, const std::array<uint16_t, 4>& taps, bool reference = false)
	{
		Check(!reference || (mode == 4 && roughness == .375f), "Original GPU comparison must be uniform live only");
		VkBufferImageCopy mapRegion = {};
		mapRegion.imageSubresource = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1 };
		mapRegion.imageExtent = { 2, 2, 1 };
		Upload(map, taps.data(), taps.size() * 2, { mapRegion }, 1, 1);
		Write(prefix + "-" + name + ".probe-map-r16", taps.data(), taps.size() * 2);
		auto commands = fb->GetCommands()->GetDrawCommands();
		VkImageTransition().AddImage(&color, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL, false)
			.AddImage(&depth, VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL, false).Execute(commands);
		RenderPassBegin().RenderPass(pass.get()).Framebuffer(color.PPFramebuffer.get()).RenderArea(0, 0, ControlWidth, ControlHeight)
			.AddClearColor(0, 0, 0, 0).AddClearDepthStencil(1, 0).Execute(commands);
		passOpen = true;
		commands->bindPipeline(VK_PIPELINE_BIND_POINT_GRAPHICS, reference ? original.get() : candidate.get());
		commands->bindDescriptorSet(VK_PIPELINE_BIND_POINT_GRAPHICS, layout.get(), 2, fb->GetDescriptorSetManager()->GetBindlessSet());
		struct Constants { uint32_t Slots[4]; float Parameters[4]; } constants = {
			{ unsigned(name.find("-b") != std::string::npos ? slots[2] : slots[0]), unsigned(slots[2]), unsigned(slots[3]), mode },
			{ roughness, 0, 0, 0 }
		};
		commands->pushConstants(layout.get(), VK_SHADER_STAGE_FRAGMENT_BIT, 0, sizeof(constants), &constants);
		commands->draw(3, 1, 0, 0);
		commands->endRenderPass();
		passOpen = false;
		VkImageTransition().AddImage(&color, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, false).Execute(commands);
		const size_t bytes = ControlWidth * ControlHeight * 4 * sizeof(float);
		auto staging = BufferBuilder().Size(bytes).Usage(VK_BUFFER_USAGE_TRANSFER_DST_BIT, VMA_MEMORY_USAGE_GPU_TO_CPU)
			.DebugName("PF113.TermsReadback").Create(fb->GetDevice());
		VkBufferImageCopy copy = {};
		copy.imageSubresource = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1 };
		copy.imageExtent = { ControlWidth, ControlHeight, 1 };
		commands->copyImageToBuffer(color.Image->image, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, staging->buffer, 1, &copy);
		fb->GetCommands()->WaitForCommands(false);
		auto mapped = static_cast<const float*>(staging->Map(0, bytes));
		Check(mapped != nullptr, "Native float readback mapping failed");
		fb->GetDevice()->CheckVulkanError(vmaInvalidateAllocation(fb->GetDevice()->allocator, staging->allocation, 0, bytes),
			"Could not invalidate PF113 GPU-to-CPU readback allocation");
		std::vector<float> values(mapped, mapped + ControlWidth * ControlHeight * 4);
		staging->Unmap();
		for (float value : values) Check(std::isfinite(value), "Native PBR result contains NaN/Inf");
		Write(prefix + "-" + name + ".rgba32f", values.data(), bytes);
		results[name] = std::move(values);
		std::ostringstream out;
		out << "{\"name\":" << Quote(name) << ",\"file\":" << Quote(prefix + "-" + name + ".rgba32f")
			<< ",\"mapFile\":" << Quote(prefix + "-" + name + ".probe-map-r16") << ",\"mode\":" << mode
			<< ",\"roughness\":" << roughness << ",\"referenceUniformOriginal\":" << (reference ? "true" : "false")
			<< ",\"drawVertices\":3,\"normalFenceWaited\":true,\"bytes\":" << bytes << '}';
		cases.push_back(out.str());
	}

	float At(const std::string& name, int band, int x, int c) const
	{
		return results.at(name)[size_t((band * ControlWidth + x) * 4 + c)];
	}
	void Compare()
	{
		for (int x = 0; x < ControlWidth; ++x)
		{
			for (const char* name : { "uniform-zero", "gather-allzero" })
				for (int band = 0; band < 4; ++band) for (int c = 0; c < 3; ++c)
				{
					Check(At(name, band, x, c) == 0.0f, "Missing IBL must have zero irradiance/prefilter/diffuse/specular");
					++zeroSamples;
				}
			for (const char* name : { "uniform-zero", "gather-allzero", "quad-zero-live" })
				for (int c = 0; c < 3; ++c)
				{
					Check(At(name, 4, x, c) > 0 && std::abs(At(name, 4, x, c) - At("uniform-live-a", 4, x, c)) <= Tolerance,
						"Missing IBL must preserve actual independent ambient/direct Lo");
					if (std::string(name) != "quad-zero-live" || x % 3 == 0)
						Check(std::abs(At(name, 5, x, c) - At(name, 4, x, c)) <= Tolerance, "Zero IBL final must equal retained positive Lo");
				}
			for (const char* suffix : { "a", "b" })
				for (int band = 0; band < 8; ++band) for (int c = 0; c < 3; ++c)
				{
					const float error = std::abs(At(std::string("uniform-live-") + suffix, band, x, c) -
						At(std::string("original-uniform-") + suffix, band, x, c));
					maxLiveParity = std::max(maxLiveParity, error);
					Check(error <= Tolerance, "Current explicit-LOD live output differs from legal original uniform sampling");
					if (band == 0 || band == 1) { Check(At(std::string("uniform-live-") + suffix, band, x, c) > 0, "Live spatial sampling must be positive"); ++positiveLiveSamples; }
				}
			for (const char* name : { "gather-mixed", "gather-live" })
				for (int band = 0; band < 2; ++band) for (int c = 0; c < 3; ++c)
				{
					float expected = 0;
					for (int tap = 0; tap < 4; ++tap)
					{
						const int token = int(At(name, 8, x, tap));
						Check(token == 0 || token == identities[0].Index || token == identities[2].Index, "Native gathered token has wrong owner");
						const float weight = At(name, 9, x, tap);
						static constexpr std::array<float, 4> golden = { .30f, .10f, .45f, .15f };
						Check(std::abs(weight - golden[tap]) < .000001f, "Native original four coefficients changed");
						if (token) expected += At(token == identities[0].Index ? "uniform-live-a" : "uniform-live-b", band, x, c) * weight;
					}
					const float error = std::abs(expected - At(name, band, x, c));
					maxMixedError = std::max(maxMixedError, error);
					Check(error <= Tolerance, "Gather output changed weights/order or substituted/renormalized zero taps");
				}
			for (const char* name : { "quad-zero-live", "quad-live-live" })
				for (int band = 0; band < 8; ++band) for (int c = 0; c < 3; ++c)
				{
					const bool zero = std::string(name) == "quad-zero-live" && x % 3 == 0;
					const char* expectedName = zero ? "uniform-zero" :
						(std::string(name) == "quad-live-live" && x % 3 == 0 ? "uniform-live-b" : "uniform-live-a");
					Check(std::abs(At(name, band, x, c) - At(expectedName, band, x, c)) <= Tolerance,
						"Adjacent/divergent pair fragment differs from corresponding legal uniform control");
					if (band < 2 && c == 0) ++divergenceWitnesses;
				}
		}
		Check(maxLiveParity <= Tolerance && maxMixedError <= Tolerance && zeroSamples > 0 && positiveLiveSamples > 0 && divergenceWitnesses > 0,
			"Required native zero/live/spatial/mixed witnesses are incomplete");
		float lodDelta = 0, spatialDelta = 0, pairDelta = 0;
		for (int x = 0; x < ControlWidth; ++x) for (int c = 0; c < 3; ++c)
		{
			lodDelta = std::max(lodDelta, std::abs(At("roughness-zero-live-a", 1, x, c) - At("roughness-one-live-a", 1, x, c)));
			spatialDelta = std::max(spatialDelta, std::abs(At("uniform-live-a", 0, x, c) - At("uniform-live-a", 0, 0, c)));
			pairDelta = std::max(pairDelta, std::abs(At("uniform-live-a", 0, x, c) - At("uniform-live-b", 0, x, c)));
		}
		Check(lodDelta > .05f && spatialDelta > .01f && pairDelta > .1f, "Spatial face, roughness LOD and differing live cube controls must be nonconstant");
	}

	void Execute()
	{
		FreshPrefix(prefix);
		Check(Observer.Enabled && Observer.Error.empty(), "The fresh startup observer is mandatory");
		PrivateBoundary boundary(fb);
		// The current fixture reaches these states naturally. Never force an
		// extra publication, reset, probe generation or producer substitution.
		SaveObserver(fb);
		Setup();
		Check(slots[0] <= 65535 && slots[2] <= 65535, "Private UINT map identities must fit the actual R16 contract");
		const auto a = uint16_t(slots[0]), b = uint16_t(slots[2]);
		const std::array<uint16_t, 4> none = { 0, 0, 0, 0 }, mixed = { a, 0, b, 0 }, live = { a, b, a, b };
		Draw("uniform-zero", 0, .375f, none);
		Draw("gather-allzero", 1, .375f, none);
		Draw("gather-mixed", 1, .375f, mixed);
		Draw("gather-live", 1, .375f, live);
		Draw("uniform-live-a", 4, .375f, none);
		Draw("uniform-live-b", 4, .375f, none);
		Draw("quad-zero-live", 2, .375f, none);
		Draw("quad-live-live", 3, .375f, none);
		Draw("roughness-zero-live-a", 4, 0.0f, none);
		Draw("roughness-one-live-a", 4, 1.0f, none);
		Draw("original-uniform-a", 4, .375f, none, true);
		Draw("original-uniform-b", 4, .375f, none, true);
		Compare();
		fixedAfter = FixedJson(fb);
		Check(fixedAfter == fixedBefore, "Fixed 2D null/BRDF owners must remain unchanged");
		Retire();
		for (const auto& identity : identities)
			Check(!fb->GetDescriptorSetManager()->ValidateBindlessIdentity(identity), "Retired private token must become stale");
		fb->GetCommands()->WaitForCommands(false);
		Check(cases.size() == 12, "Native control inventory incomplete");
		retirementFenceCompleted = true;
	}

	std::string Json(bool success, const std::string& error) const
	{
		std::ostringstream out;
		out << "{\"schema\":\"shadedoomvk-pf113-native-probe-controls/v1\",\"status\":" << Quote(success ? "PASS" : "FAIL")
			<< ",\"settings\":{\"rendererMode\":" << int(vid_rendermode) << ",\"globalTextureFilter\":" << int(gl_texture_filter)
			<< ",\"lightProbeEnabled\":" << (gl_lightprobe ? "true" : "false") << ",\"levelMesh\":" << (gl_levelmesh ? "true" : "false")
			<< ",\"uberShaders\":" << (gl_ubershaders ? "true" : "false") << ",\"lightShadows\":" << int(gl_light_shadows)
			<< ",\"clientExtent\":[" << fb->GetWidth() << ',' << fb->GetHeight() << "],\"renderExtent\":["
			<< fb->GetBuffers()->GetWidth() << ',' << fb->GetBuffers()->GetHeight() << "]}"
			<< ",\"error\":" << Quote(error) << ",\"checks\":" << checks << ",\"width\":" << ControlWidth << ",\"height\":" << ControlHeight
			<< ",\"format\":\"rgba32float-little-endian\",\"rows\":[\"irradiance\",\"prefiltered\",\"diffuse\",\"specular\",\"Lo\",\"final\",\"N+roughness\",\"R+runtime\",\"taps\",\"weights\"],"
			<< "\"startupReceipt\":" << Quote(Observer.Prefix + ".json") << ",\"tolerance\":" << Tolerance
			<< ",\"maximumLiveParityError\":" << maxLiveParity << ",\"maximumMixedError\":" << maxMixedError
			<< ",\"zeroSamples\":" << zeroSamples << ",\"positiveLiveSamples\":" << positiveLiveSamples
			<< ",\"divergenceWitnesses\":" << divergenceWitnesses << ",\"normalPrivateRetirement\":" << (retired ? "true" : "false")
			<< ",\"retirementFenceCompleted\":" << (retirementFenceCompleted ? "true" : "false")
			<< ",\"resources\":" << (resourcesJson.empty() ? "{}" : resourcesJson) << ",\"fixedBefore\":" << (fixedBefore.empty() ? "{}" : fixedBefore)
			<< ",\"fixedAfter\":" << (fixedAfter.empty() ? "{}" : fixedAfter) << ",\"cases\":[";
		for (size_t i = 0; i < cases.size(); ++i) { if (i) out << ','; out << cases[i]; }
		out << "],\"scope\":\"explicit bounded private fragment readbacks; actual packaged helper and full ProcessMaterialLight body with observation-only term exports; separate real scene observer\","
			<< "\"limits\":\"no unsafe original zero/divergent draw; no full bake robustness, main output parity, performance or P400 qualification\","
			<< "\"spirv\":{\"candidate\":" << Quote(prefix + "-candidate.frag.spv") << ",\"legalOriginalUniform\":" << Quote(prefix + "-original-uniform.frag.spv")
			<< ",\"vertex\":" << Quote(prefix + "-control.vert.spv") << ",\"compiledByEngine\":" << (shadersCompiled ? "true" : "false")
			<< ",\"externalStructuralValidation\":\"runner-required\"}}";
		return out.str();
	}
};
} // namespace

CCMD(pf113_probe_diag)
{
	if (argv.argc() != 2 || !argv[1][0]) { Printf("Usage: pf113_probe_diag <fresh-existing-directory/output-prefix>\n"); return; }
	if (!screen || !screen->IsVulkan()) { Printf("PF113 FAIL: an initialized Vulkan backend is required.\n"); return; }
	const std::string prefix = argv[1];
	try { FreshPrefix(prefix); }
	catch (const std::exception& e) { Printf("PF113 FAIL: %s\n", e.what()); return; }
	NativeControls run{ static_cast<VulkanRenderDevice*>(screen), prefix };
	bool success = false;
	std::string error;
	try { run.Execute(); success = true; }
	catch (const std::exception& e) { error = e.what(); }
	try { Write(prefix + ".json", run.Json(success, error)); }
	catch (const std::exception& e) { success = false; error = e.what(); }
	Printf("PF113 %s: %u checks, %u retained controls; %s%s%s\n", success ? "PASS" : "FAIL",
		run.checks, unsigned(run.cases.size()), (prefix + ".json").c_str(), error.empty() ? "" : "; ", error.c_str());
}
