// SDVK-002: read-only snapshots of the actual immediate draw and live owners.
#include "diagnostics/hw_sdvkdiagnostics.h"
#include "diagnostics/hw_sdvkdiagnosticcore.h"
#include "vulkan/vk_renderdevice.h"
#include "vulkan/vk_renderstate.h"
#include "vulkan/buffers/vk_buffer.h"
#include "vulkan/buffers/vk_rsbuffers.h"
#include "vulkan/textures/vk_hwtexture.h"
#include "vulkan/textures/vk_texture.h"
#include "vulkan/descriptorsets/vk_descriptorset.h"
#include "vulkan/samplers/vk_samplers.h"
#include "g_levellocals.h"
#include "hw_cvars.h"
#include "hw_levelmesh.h"

namespace
{
using namespace SdvkObservation;

std::string Identity(FRendererResourceIdentity value)
{
    if (!value.IsSet()) return Unavailable("no live dynamic block token for this descriptor index");
    return Object().Bool("available", true).Int("index", value.Index).Int("generation", value.Generation)
        .Int("epoch", value.Epoch).Int("span", value.Span).Json();
}

std::string Lifetime(const FRendererLifetimeStats& value)
{
    return Object().Int("activations", value.Activations).Int("retirements", value.Retirements)
        .Int("resets", value.Resets).Int("stale_rejects", value.StaleRejects)
        .Int("invalid_retires", value.InvalidRetires).Int("duplicate_activations", value.DuplicateActivations).Json();
}

std::string Sampler(VulkanSampler* sampler)
{
    if (!sampler || !sampler->GetCreationArguments().Captured)
        return Unavailable("selected sampler has no captured successful creation arguments");
    const auto& s = sampler->GetCreationArguments();
    return Object().Bool("available", true).Int("min_filter", int(s.MinFilter)).Int("mag_filter", int(s.MagFilter))
        .Int("mipmap_mode", int(s.MipmapMode)).Int("address_u", int(s.AddressU)).Int("address_v", int(s.AddressV)).Int("address_w", int(s.AddressW))
        .Num("lod_bias", s.MipLodBias).Num("min_lod", s.MinLod).Num("max_lod", s.MaxLod)
        .Bool("anisotropy", s.AnisotropyEnable != VK_FALSE).Num("max_anisotropy", s.MaxAnisotropy)
        .Str("basis", "immutable arguments of the successfully created selected Vulkan sampler").Json();
}

std::string Shader(const VkKeyIdentity::ShaderState& key)
{
    Object result;
#define SDVK_SHADER_FIELD(name) result.Int(#name, key.name)
    SDVK_SHADER_FIELD(Simple2D); SDVK_SHADER_FIELD(TextureMode); SDVK_SHADER_FIELD(ClampY);
    SDVK_SHADER_FIELD(Brightmap); SDVK_SHADER_FIELD(Detailmap); SDVK_SHADER_FIELD(Glowmap);
    SDVK_SHADER_FIELD(UseShadowmap); SDVK_SHADER_FIELD(UseRaytrace); SDVK_SHADER_FIELD(ShadowmapFilter);
    SDVK_SHADER_FIELD(FogBeforeLights); SDVK_SHADER_FIELD(FogAfterLights); SDVK_SHADER_FIELD(FogRadial);
    SDVK_SHADER_FIELD(SWLightRadial); SDVK_SHADER_FIELD(SWLightBanded); SDVK_SHADER_FIELD(LightMode);
    SDVK_SHADER_FIELD(LightBlendMode); SDVK_SHADER_FIELD(LightAttenuationMode); SDVK_SHADER_FIELD(PaletteMode);
    SDVK_SHADER_FIELD(FogBalls); SDVK_SHADER_FIELD(NoFragmentShader); SDVK_SHADER_FIELD(DepthFadeThreshold);
    SDVK_SHADER_FIELD(AlphaTestOnly); SDVK_SHADER_FIELD(LightNoNormals); SDVK_SHADER_FIELD(UseSpriteCenter);
    SDVK_SHADER_FIELD(SpecialEffect); SDVK_SHADER_FIELD(EffectState); SDVK_SHADER_FIELD(VertexFormat);
    SDVK_SHADER_FIELD(AlphaTest); SDVK_SHADER_FIELD(Simple); SDVK_SHADER_FIELD(Simple3D);
    SDVK_SHADER_FIELD(GBufferPass); SDVK_SHADER_FIELD(UseLevelMesh); SDVK_SHADER_FIELD(ShadeVertex);
    SDVK_SHADER_FIELD(UseRaytracePrecise);
#undef SDVK_SHADER_FIELD
    return result.Json();
}

std::string Pipeline(const VkPipelineKey& value)
{
    const auto key = value.CanonicalState();
    Object result;
#define SDVK_PIPELINE_FIELD(name) result.Int(#name, key.name)
    SDVK_PIPELINE_FIELD(DrawType); SDVK_PIPELINE_FIELD(CullMode); SDVK_PIPELINE_FIELD(ColorMask);
    SDVK_PIPELINE_FIELD(DepthWrite); SDVK_PIPELINE_FIELD(DepthTest); SDVK_PIPELINE_FIELD(DepthClamp);
    SDVK_PIPELINE_FIELD(DepthBias); SDVK_PIPELINE_FIELD(DepthFunc); SDVK_PIPELINE_FIELD(StencilTest);
    SDVK_PIPELINE_FIELD(StencilPassOp); SDVK_PIPELINE_FIELD(DrawLine); SDVK_PIPELINE_FIELD(IsGeneralized);
#undef SDVK_PIPELINE_FIELD
    result.Raw("shader", Shader(key.ShaderKey)).Raw("render_style", Object().Int("blend_op", key.RenderStyle.BlendOp)
        .Int("source_alpha", key.RenderStyle.SrcAlpha).Int("destination_alpha", key.RenderStyle.DestAlpha)
        .Int("flags", key.RenderStyle.Flags).Json());
    return result.Json();
}
}

// These friends read an existing descriptor entry selected by the emitted
// surface index. They must never call GetDescriptorEntry/GetImage/ValidateTexture
// or resolve a new probe merely to collect evidence.
struct FSdvkDiagnosticAccess
{
    static void Draw(VkRenderState* state, int count, bool indexed)
    {
        using namespace SdvkObservation;
        auto fb = state->fb;
        const auto context = SdvkDiagnostics::CurrentContextJson();
        const auto material = static_cast<VkMaterial*>(state->mMaterial.mMaterial);
        const std::string name = material && material->Source() ? material->Source()->GetName().GetChars() : "";
        const auto pipeline = Pipeline(state->mPipelineKey);
        const auto spriteSurface = SdvkDiagnostics::CurrentSpriteBasisJson();
        if (!spriteSurface.empty())
        {
            // Emitted draw's uploaded SurfaceUniforms, rather than merely
            // an offline/generated tangent value.
            const auto& tangent = state->mSurfaceUniforms.uSpriteTangent;
            const auto& normal = state->mSurfaceUniforms.uSpriteNormal;
            SdvkDiagnostics::Emit("sprite-basis", Object().Raw("context", context)
                .Raw("surface", spriteSurface)
                .Raw("tangent", '[' + Number(tangent.X) + ',' + Number(tangent.Y) + ',' + Number(tangent.Z) + ']')
                .Raw("normal", '[' + Number(normal.X) + ',' + Number(normal.Y) + ',' + Number(normal.Z) + ']')
                .Num("handedness", tangent.W).Bool("explicit", normal.W > 0.5f)
                .Str("material", name).Int("shader", material ? material->GetShaderIndex() : -1)
                .Int("height_texture_index", state->mSurfaceUniforms.uHeightTextureIndex)
                .Int("light_index", state->mPushConstants.uLightIndex)
                .Bool("indexed", indexed).Int("draw_count", count)
                .Str("uniform_scope", "emitted-vulkan-draw-after-apply-surface-uniforms").Json(), true);
        }
        SdvkDiagnostics::Emit("pipeline", Object().Raw("context", context).Str("material", name)
            .Raw("key", pipeline).Bool("indexed", indexed).Int("draw_count", count)
            .Int("target_width", state->mRenderTarget.Width).Int("target_height", state->mRenderTarget.Height)
            .Int("target_format", int(state->mRenderTarget.Format)).Int("target_samples", int(state->mRenderTarget.Samples))
            .Int("draw_buffers", state->mRenderTarget.DrawBuffers).Bool("depth_stencil", state->mRenderTarget.DepthStencil != nullptr)
            .Str("basis", "canonical field state of the emitted immediate draw; no executed-shader claim").Json(), true);

        if (material)
        {
            const VkMaterial::DescriptorEntry* entry = nullptr;
            for (const auto& candidate : material->mDescriptorSets)
                if (candidate.bindlessIndex == state->mSurfaceUniforms.uTextureIndex) { entry = &candidate; break; }
            if (!entry) throw std::runtime_error("Emitted SDVK material index has no existing descriptor entry");
            if (material->NumLayers() > 256) throw std::runtime_error("SDVK material layer observation limit reached");
            const auto& global = *GetGlobalShader(entry->globalShaderAddr);
            const bool indexedMaterial = (material->GetScaleFlags() & CTF_Indexed) != 0;
            const int authoredCount = indexedMaterial ? 1 : global ? material->NumNonMaterialLayers() : material->NumLayers();
            std::string layers = "[";
            for (int i = 0; i < authoredCount; ++i)
            {
                MaterialLayerDiagnostic layer;
                if (!material->GetLayerDiagnostic(i, layer)) throw std::runtime_error("SDVK bound material layer is unavailable");
                const bool fallbackPlaceholder = layer.sourceTexture && layer.sourceTexture->GetSourceLump() == 0 &&
                    layer.sourceTexture->GetWidth() == 1 && layer.sourceTexture->GetHeight() == 1;
                if (i) layers += ',';
                layers += Object().Int("binding", i).Str("semantic", MaterialLayerSemanticName(layer.semantic))
                    .Int("custom_index", layer.customIndex).Int("scale_flags", layer.scaleFlags).Int("layer_clamp_flags", layer.clampflags)
                    .Int("requested_sampling", int(layer.sampling)).Raw("sampler", Sampler(fb->GetSamplerManager()->Get(layer.sampling, entry->clampmode)))
                    .Raw("source", layer.sourceTexture ? Object().Int("lump", layer.sourceTexture->GetSourceLump())
                        .Int("width", layer.sourceTexture->GetWidth()).Int("height", layer.sourceTexture->GetHeight()).Json() : Unavailable("placeholder/no source texture"))
                    .Str("role", fallbackPlaceholder ? "fallback-placeholder" : "authored-layer").Json();
            }
            if (indexedMaterial)
            {
                layers += ',' + Object().Int("binding", 1).Str("semantic", "auxiliary-palette-row")
                    .Str("role", "shader-required auxiliary resource, not an authored semantic layer")
                    .Raw("sampler", Sampler(fb->GetSamplerManager()->Get(CLAMP_NOFILTER_XY))).Json();
            }
            else if (global)
            {
                int binding = authoredCount;
                for (size_t i = 0; i < MAX_CUSTOM_HW_SHADER_TEXTURES; ++i)
                {
                    if (!global.CustomShaderTextures[i].get()) continue;
                    if (binding >= 256) throw std::runtime_error("SDVK custom layer observation limit reached");
                    if (layers.size() > 1) layers += ',';
                    layers += Object().Int("binding", binding++).Str("semantic", "global-custom").Int("custom_index", i)
                        .Int("requested_sampling", int(global.CustomShaderTextureSampling[i])).Str("role", "global-custom")
                        .Raw("sampler", Sampler(fb->GetSamplerManager()->Get(global.CustomShaderTextureSampling[i], entry->clampmode))).Json();
                }

                if (entry->heightLayerIndex >= 0)
                {
                    MaterialLayerDiagnostic height;
                    const int sourceHeight = material->FindLayer(MaterialLayerSemantic::Height);
                    if (!material->GetLayerDiagnostic(sourceHeight, height)) throw std::runtime_error("SDVK height layer is unavailable");
                    if (layers.size() > 1) layers += ',';
                    layers += Object().Int("binding", entry->heightLayerIndex).Str("semantic", "height")
                        .Int("custom_index", -1).Int("scale_flags", height.scaleFlags).Int("layer_clamp_flags", height.clampflags)
                        .Int("requested_sampling", int(height.sampling)).Raw("sampler", Sampler(fb->GetSamplerManager()->Get(height.sampling, entry->clampmode)))
                        .Raw("source", height.sourceTexture ? Object().Int("lump", height.sourceTexture->GetSourceLump())
                            .Int("width", height.sourceTexture->GetWidth()).Int("height", height.sourceTexture->GetHeight()).Json() : Unavailable("height source unavailable"))
                        .Str("role", "authored-layer").Json();
                }
            }
            layers += ']';
            SdvkDiagnostics::Emit("material", Object().Raw("context", context).Str("semantic_key", name).Str("name", name)
                .Int("scale_flags", material->GetScaleFlags()).Int("shader", material->GetShaderIndex()).Int("translation", state->mMaterial.mTranslation)
                .Int("resolved_clamp", entry->clampmode).Bool("palette_mode", state->mMaterial.mPaletteMode).Bool("red_is_alpha", entry->redIsAlpha)
                .Raw("global_shader", Object().Int("number", entry->globalShaderAddr.num).Int("type", entry->globalShaderAddr.type)
                    .Str("scope_name", entry->globalShaderAddr.type == 1 || entry->globalShaderAddr.type == 2 ? FName(ENamedName(entry->globalShaderAddr.name)).GetChars() : "global").Json())
                .Raw("resource", Identity(fb->GetDescriptorSetManager()->GetBindlessIdentity(state->mSurfaceUniforms.uTextureIndex)))
                .Int("height_texture_index", state->mSurfaceUniforms.uHeightTextureIndex)
                .Raw("layers", layers).Json(), true);
        }
        else SdvkDiagnostics::Emit("material", Object().Raw("context", context).Raw("material", Unavailable("draw has no material")).Json(), true);

        const int runtimeProbe = state->mSurfaceUniforms.uLightProbeIndex;
        auto textures = fb->GetTextureManager();
        SdvkDiagnostics::Emit("probe", Object().Raw("context", context).Str("material", name)
            .Str("mode", "uniform-environment-pair").Int("authored_index", state->mLightProbeIndex).Int("runtime_irradiance_index", runtimeProbe)
            .Bool("fallback", runtimeProbe == 0).Raw("resource", runtimeProbe ? Identity(fb->GetDescriptorSetManager()->GetBindlessIdentity(runtimeProbe)) : Unavailable("zero is the no-probe sentinel"))
            .Int("published_irradiance", textures->Irradiancemaps.size()).Int("published_prefilter", textures->Prefiltermaps.size())
            .Raw("irradiance_sampler", Sampler(fb->GetSamplerManager()->IrradiancemapSampler.get()))
            .Raw("prefilter_sampler", Sampler(fb->GetSamplerManager()->PrefiltermapSampler.get()))
            .Raw("lightmap_texel_selection", Unavailable("per-texel gathered probe mapping is covered by the retained PF native fixture, not inferred from this uniform"))
            .Str("scope", "actual surface uniform at immediate draw emission; shader consumption remains path-dependent").Json(), true);
        const auto& shader = state->mPipelineKey.ShaderKey;
        SdvkDiagnostics::Emit("shadow", Object().Raw("context", context).Str("material", name).Str("caster", "world-geometry")
            .Str("mode", shader.UseRaytrace ? shader.Layout.UseRaytracePrecise ? "world-trace-precise" : "world-trace" : shader.UseShadowmap ? "dynamic-1d-shadow-map" : "disabled")
            .Bool("hardware_ray_query", fb->IsRayQueryEnabled()).Int("filter", uint64_t(shader.ShadowmapFilter))
            .Str("scope", "actual immediate draw shader policy; no sprite silhouette geometry claim").Json(), true);
    }
};

namespace SdvkDiagnostics
{
void VulkanDraw(VkRenderState* state, int count, bool indexed)
{
    if (!StateEnabled()) return;
    try { FSdvkDiagnosticAccess::Draw(state, count, indexed); }
    catch (const std::exception& error) { Fail(error.what()); }
}

std::string VulkanBuild(VulkanRenderDevice* device)
{
    using namespace SdvkObservation;
    const auto& caps = device->GetCapabilities();
    return Object().Bool("available", true).Int("vendor_id", caps.VendorID).Int("device_id", caps.DeviceID)
        .Int("driver_version_raw", caps.DriverVersion).Str("driver", std::to_string(caps.DriverVersion))
        .Int("device_type", int(caps.DeviceType)).Bool("ray_query_enabled", device->IsRayQueryEnabled())
        .Bool("graphics_pipeline_library", caps.SupportsGraphicsPipelineLibrary()).Json();
}

void VulkanResources(VulkanRenderDevice* device)
{
    using namespace SdvkObservation;
    if (!Enabled()) return;
    try
    {
        const auto descriptors = device->GetDescriptorSetManager();
        const auto textures = device->GetTextureManager();
        const auto& allocation = descriptors->GetBindlessAllocationStats();
        const auto& plan = descriptors->GetBindlessCapacityPlan();
        const auto& uploads = textures->GetAsyncUploadStats();
        const auto& staging = textures->GetUploadStagingPlannerStats();
        const auto rsbuffers = device->GetBufferManager()->GetRSBuffers();
        const auto& lightUploads = rsbuffers->Lightbuffer.Observation;
        Object result;
        result.Str("scope", "renderer-owner snapshot after RenderView; allocation counters are cumulative")
            .Int("descriptor_requested", plan.Requested).Int("descriptor_device_limit", plan.DeviceLimit).Int("descriptor_capacity", plan.Effective)
            .Int("descriptor_dynamic_start", descriptors->GetBindlessDynamicStart()).Int("descriptor_current", allocation.CurrentDescriptors)
            .Int("descriptor_high_water", allocation.HighWaterDescriptors).Int("descriptor_allocations", allocation.Allocations)
            .Int("descriptor_reuses", allocation.Reuses).Int("descriptor_frees", allocation.Frees).Int("descriptor_failures", allocation.Failures)
            .Int("descriptor_invalid_frees", allocation.InvalidFrees).Str("descriptor_limit_source", VkBindlessLimitSourceName(plan.DeviceLimitSource))
            .Raw("lifetime", Lifetime(descriptors->GetBindlessLifetimeStats()))
            .Int("texture_epoch", textures->GetTextureEpoch().Generation).Int("lightmap_epoch", textures->GetLightmapEpoch().Generation)
            .Int("probe_epoch", textures->GetLightProbeEpoch().Generation).Int("async_upload_epoch", textures->GetAsyncUploadEpoch().Generation)
            .Int("hardware_textures", textures->GetHWTextureCount()).Int("lightmap_pages", textures->Lightmaps.size())
            .Int("irradiance_maps", textures->Irradiancemaps.size()).Int("prefilter_maps", textures->Prefiltermaps.size())
            .Raw("async_uploads", Object().Int("queued", uploads.JobsQueued).Int("completed", uploads.JobsCompleted)
                .Int("cancelled", uploads.PendingCancellations).Int("missing_ticket_rejects", uploads.MissingTicketRejects)
                .Int("manager_epoch_rejects", uploads.ManagerEpochRejects).Int("target_epoch_rejects", uploads.TargetEpochRejects).Json())
            .Raw("staging", Object().Int("requests", staging.Requests).Int("bytes", staging.BytesRequested).Int("high_water", staging.HighWater)
                .Int("reuses", staging.Reuses).Int("wrap_waits", staging.WrapWaits).Int("dedicated", staging.DedicatedRequests).Json())
            .Raw("light_uploads", StateEnabled() ? Object().Bool("available", true)
                .Int("range_capacity", rsbuffers->Lightbuffer.Count).Int("record_capacity", rsbuffers->Lightbuffer.Count)
                .Int("range_capacity_bytes", uint64_t(rsbuffers->Lightbuffer.Count) * sizeof(int) * 4)
                .Int("record_capacity_bytes", uint64_t(rsbuffers->Lightbuffer.Count) * sizeof(FDynLightInfo))
                .Int("range_entries_used", rsbuffers->Lightbuffer.UploadIndex).Int("records_used", rsbuffers->Lightbuffer.DataIndex)
                .Int("attempts", lightUploads.Attempts).Int("successful", lightUploads.Successful).Int("failed", lightUploads.Failed)
                .Int("index_capacity_failures", lightUploads.IndexCapacityFailures).Int("data_capacity_failures", lightUploads.DataCapacityFailures)
                .Int("normal_records", lightUploads.NormalRecords).Int("subtractive_records", lightUploads.SubtractiveRecords)
                .Int("additive_records", lightUploads.AdditiveRecords).Int("uploaded_bytes", lightUploads.UploadedBytes)
                .Int("peak_records_per_upload", lightUploads.PeakRecordsPerUpload)
                .Raw("records_per_upload_histogram", Object().Int("empty", lightUploads.EmptyUploads)
                    .Int("1_4", lightUploads.Uploads1To4).Int("5_16", lightUploads.Uploads5To16)
                    .Int("17_64", lightUploads.Uploads17To64).Int("65_256", lightUploads.Uploads65To256)
                    .Int("257_plus", lightUploads.Uploads257Plus).Json())
                .Str("scope", "state-mode immediate Vulkan dynamic-light range/data uploads for this render frame; LevelMesh tile buffers are separate").Json()
                : Unavailable("light upload counters are state-mode only to keep timing mode free of per-upload bookkeeping"));
        if (level.levelMesh)
        {
            const auto& epochs = level.levelMesh->GetMutationEpochs();
            result.Raw("levelmesh", Object().Int("epoch", level.levelMesh->GetResourceEpoch().Generation)
                .Int("geometry", epochs.Geometry).Int("surface", epochs.Surface).Int("lights", epochs.Lights).Int("query", epochs.Query)
                .Int("portals", epochs.Portals).Int("lightmap_probe", epochs.LightmapProbe).Int("resets", epochs.Resets).Json());
        }
        else result.Raw("levelmesh", Unavailable("no active level mesh"));
        result.Raw("sun", Object().Num("intensity", level.SunIntensity).Raw("direction", '[' + Number(level.SunDirection.X) + ',' + Number(level.SunDirection.Y) + ',' + Number(level.SunDirection.Z) + ']')
            .Str("scope", "current level authored sun state, not per-surface visibility or physical radiometry").Json());
        Emit("resource", result.Json());
    }
    catch (const std::exception& error) { Fail(error.what()); }
}
}
