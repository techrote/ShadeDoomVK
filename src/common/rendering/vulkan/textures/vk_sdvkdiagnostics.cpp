// SDVK-002: read-only snapshots of the actual immediate draw and live owners.
#include "diagnostics/hw_sdvkdiagnostics.h"
#include "diagnostics/hw_sdvkdiagnosticcore.h"
#include "vulkan/vk_renderdevice.h"
#include "vulkan/vk_renderstate.h"
#include "vulkan/vk_levelmesh.h"
#include "vulkan/buffers/vk_buffer.h"
#include "vulkan/buffers/vk_rsbuffers.h"
#include "vulkan/textures/vk_hwtexture.h"
#include "vulkan/textures/vk_texture.h"
#include "vulkan/descriptorsets/vk_descriptorset.h"
#include "vulkan/samplers/vk_samplers.h"
#include "g_levellocals.h"
#include "hw_cvars.h"
#include "hw_levelmesh.h"
#include "hwrenderer/doom_levelmesh.h"
#include "diagnostics/hw_specialsurfacecontract.h"
#include <cstring>

namespace
{
using namespace SdvkObservation;

std::string Receipt(const RectPackerAllocation& value)
{
    return Object().Int("owner", value.Owner).Int("incarnation", value.Incarnation).Int("slot", value.Slot).Json();
}

std::string SurfaceLightmap(LevelMesh* mesh, int tileIndex, int vertexPage, uint64_t epoch, size_t vulkanPages)
{
    Object result;
    result.Bool("eligible", tileIndex >= 0).Int("tile", tileIndex).Int("page", vertexPage).Int("epoch", epoch);
    if (tileIndex < 0)
        return result.Bool("valid", false).Raw("receipt", Receipt({})).Json();
    if (!mesh || size_t(tileIndex) >= mesh->Lightmap.Tiles.Size())
        return result.Bool("valid", false).Raw("receipt", Receipt({})).Json();
    const auto& tile = mesh->Lightmap.Tiles[tileIndex];
    const bool valid = mesh->Lightmap.AtlasPacker && tile.HasValidAtlasRegion(*mesh->Lightmap.AtlasPacker,
        mesh->Lightmap.TextureSize, mesh->Lightmap.TextureCount) && vertexPage == tile.AtlasLocation.ArrayIndex
        && vertexPage >= 0 && size_t(vertexPage) < vulkanPages;
    return result.Bool("valid", valid).Raw("receipt", Receipt(tile.AtlasLocation.Allocation)).Json();
}

std::string TileCensus(LevelMesh* mesh, size_t vulkanPages)
{
    std::string result = "[";
    unsigned count = 0;
    for (unsigned index = 0; index < mesh->Lightmap.Tiles.Size(); ++index)
    {
        const auto& tile = mesh->Lightmap.Tiles[index];
        if (tile.UseCount <= 0) continue;
        if (++count > 64) throw std::runtime_error("SDVK-161 current tile census exceeds its 64-tile bound");
        if (count > 1) result += ',';
        result += Object().Int("tile", index).Int("page", tile.AtlasLocation.ArrayIndex)
            .Raw("receipt", Receipt(tile.AtlasLocation.Allocation))
            .Raw("binding", Object().Int("type", tile.Binding.Type).Int("type_index", tile.Binding.TypeIndex)
                .Int("control_sector", tile.Binding.ControlSector == 0xffffffff ? -1 : int(tile.Binding.ControlSector)).Json())
            .Bool("valid", mesh->Lightmap.AtlasPacker && tile.HasValidAtlasRegion(*mesh->Lightmap.AtlasPacker,
                mesh->Lightmap.TextureSize, mesh->Lightmap.TextureCount) && tile.AtlasLocation.ArrayIndex >= 0
                && size_t(tile.AtlasLocation.ArrayIndex) < vulkanPages)
            .Raw("dirty", Object().Bool("initial", tile.NeedsInitialBake).Bool("geometry", tile.GeometryUpdate)
                .Bool("light", tile.ReceivedNewLight).Json()).Json();
    }
    return result + ']';
}

std::string PlaneJson(const double* plane)
{
    return '[' + Number(plane[0]) + ',' + Number(plane[1]) + ',' + Number(plane[2]) + ',' + Number(plane[3]) + ']';
}

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

std::string LightmapLifecycle(LevelMesh* mesh, size_t vulkanPages, int frameTileUpdates, int frameTileCompletions)
{
    if (!mesh || !mesh->Lightmap.AtlasPacker)
        return Unavailable("no live level-mesh lightmap atlas owner");

    uint64_t live = 0, valid = 0, invalid = 0;
    uint64_t initialDirty = 0, geometryDirty = 0, lightDirty = 0;
    std::vector<uint64_t> pageTiles(std::max(mesh->Lightmap.TextureCount, 0), 0);
    for (const auto& tile : mesh->Lightmap.Tiles)
    {
        if (tile.UseCount <= 0) continue;
        ++live;
        if (tile.NeedsInitialBake) ++initialDirty;
        if (tile.GeometryUpdate) ++geometryDirty;
        if (tile.ReceivedNewLight) ++lightDirty;
        if (!tile.HasValidAtlasRegion(*mesh->Lightmap.AtlasPacker,
                mesh->Lightmap.TextureSize, mesh->Lightmap.TextureCount))
        {
            ++invalid;
            continue;
        }
        ++valid;
        ++pageTiles[tile.AtlasLocation.ArrayIndex];
    }

    std::string pages = "[";
    for (size_t i = 0; i < pageTiles.size(); ++i)
    {
        if (i) pages += ',';
        pages += std::to_string(pageTiles[i]);
    }
    pages += ']';

    Object result;
    result.Bool("available", true).Str("map", level.MapName.GetChars())
        .Int("texture_size", mesh->Lightmap.TextureSize).Int("texture_count", mesh->Lightmap.TextureCount)
        .Int("vulkan_page_count", vulkanPages).Int("used_tiles", mesh->Lightmap.UsedTiles)
        .Int("retained_tiles_loaded", mesh->Lightmap.RetainedTilesLoaded)
        .Int("frame_tile_updates", frameTileUpdates).Int("frame_tile_completions", frameTileCompletions)
        .Int("live_tiles", live).Int("valid_live_tiles", valid).Int("invalid_live_tiles", invalid)
        .Int("initial_dirty", initialDirty).Int("geometry_dirty", geometryDirty).Int("light_dirty", lightDirty)
        .Bool("all_clean", initialDirty == 0 && geometryDirty == 0 && lightDirty == 0)
        .Bool("page_count_match", size_t(std::max(mesh->Lightmap.TextureCount, 0)) == vulkanPages)
        .Bool("sampling_page_bounds_ok", invalid == 0).Raw("page_live_tiles", pages)
        .Str("scope", "current live tile receipts and atlas page ownership; actual pixels remain image evidence");
    if (SdvkDiagnostics::SpecialSurfaceEnabled())
        result.Raw("tile_receipts", TileCensus(mesh, vulkanPages)).Int("authored_probe_count", level.lightProbes.Size());
    return result.Json();
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
    static std::string SurfaceProbe(VulkanRenderDevice* fb, const SurfaceUniforms& uniforms, int authored, bool mesh)
    {
        const int runtime = uniforms.uLightProbeIndex;
        return SdvkObservation::Object().Int("authored_index", authored).Int("runtime_irradiance_index", runtime)
            .Str("authored_scope", mesh ? "not stored in mesh; no authored target claim" : "current immediate authored uniform selector")
            .Bool("fallback", runtime == 0).Int("probe_epoch", fb->GetTextureManager()->GetLightProbeEpoch().Generation)
            .Str("mode", mesh ? "mesh-uniform-with-lightmap-gather" : "uniform-environment-pair")
            .Raw("lightmap_texel_selection", SdvkObservation::Unavailable("not read back; never inferred from a mesh or immediate uniform"))
            .Str("scope", "actual current stored surface uniform; no per-texel probe claim").Json();
    }

    static std::string Material(VulkanRenderDevice* fb, const FMaterialState& materialState,
        const SurfaceUniforms& uniforms, const std::string& context)
    {
        using namespace SdvkObservation;
        auto material = static_cast<VkMaterial*>(materialState.mMaterial);
        if (!material) return Object().Raw("context", context).Raw("material", Unavailable("draw has no material")).Json();
        const std::string name = material->Source() ? material->Source()->GetName().GetChars() : "";
        const VkMaterial::DescriptorEntry* entry = nullptr;
        for (const auto& candidate : material->mDescriptorSets)
            if (candidate.bindlessIndex == uniforms.uTextureIndex) { entry = &candidate; break; }
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
        return Object().Raw("context", context).Str("semantic_key", name).Str("name", name)
            .Int("scale_flags", material->GetScaleFlags()).Int("shader", material->GetShaderIndex()).Int("translation", materialState.mTranslation)
            .Int("resolved_clamp", entry->clampmode).Bool("palette_mode", materialState.mPaletteMode).Bool("red_is_alpha", entry->redIsAlpha)
            .Raw("global_shader", Object().Int("number", entry->globalShaderAddr.num).Int("type", entry->globalShaderAddr.type)
                .Str("scope_name", entry->globalShaderAddr.type == 1 || entry->globalShaderAddr.type == 2 ? FName(ENamedName(entry->globalShaderAddr.name)).GetChars() : "global").Json())
            .Raw("resource", Identity(fb->GetDescriptorSetManager()->GetBindlessIdentity(uniforms.uTextureIndex)))
            .Int("height_texture_index", uniforms.uHeightTextureIndex)
            .Raw("layers", layers).Json();
    }

    static void LevelMeshDraw(VkRenderState* state, int firstIndex, int count, LevelMeshDrawSurface surface)
    {
        using namespace SdvkObservation;
        // ApplyLevelMeshPipeline has already stored the final overridden key.
        // Mesh batches do not consume the immediate material/surface uniforms.
        SdvkDiagnostics::Emit("pipeline", Object().Raw("context", SdvkDiagnostics::CurrentContextJson())
            .Str("producer", "levelmesh-indexed-range").Str("surface", surface == LevelMeshDrawSurface::Side ? "side" : "flat")
            .Raw("key", Pipeline(state->mPipelineKey)).Bool("indexed", true).Int("first_index", firstIndex).Int("draw_count", count)
            .Int("target_width", state->mRenderTarget.Width).Int("target_height", state->mRenderTarget.Height)
            .Int("target_format", int(state->mRenderTarget.Format)).Int("target_samples", int(state->mRenderTarget.Samples))
            .Int("draw_buffers", state->mRenderTarget.DrawBuffers).Bool("depth_stencil", state->mRenderTarget.DepthStencil != nullptr)
            .Str("basis", "bound pipeline and submitted LevelMesh indexed range; no per-surface material/probe or executed-shader claim").Json(), true);
        if (SdvkDiagnostics::SpecialSurfaceFrameSelected()) LevelMeshSurfaces(state, firstIndex, count);
    }

    static void LevelMeshSurfaces(VkRenderState* state, int firstIndex, int count)
    {
        using namespace SdvkObservation;
        auto mesh = level.levelMesh;
        if (!mesh || state->fb->GetLevelMesh()->GetMesh() != mesh)
            throw std::runtime_error("SDVK-161 submitted mesh is not the current map owner");
        const auto& data = mesh->Mesh;
        if (firstIndex % 3 || count % 3 || !SdvkSurfaceObservation::Contains(data.Indexes.Size(), firstIndex, count)
            || !SdvkSurfaceObservation::Contains(size_t(data.IndexCount), firstIndex, count))
            throw std::runtime_error("SDVK-161 submitted mesh range is outside occupied triangle storage");
        const auto& key = state->mPipelineKey;
        // A depth-only/masked prepass is retained by the parent pipeline row;
        // it must never masquerade as a material-shaded color submission.
        if (key.ShaderKey.NoFragmentShader || key.ShaderKey.AlphaTestOnly || !key.ColorMask) return;
        const auto context = SdvkDiagnostics::CurrentContextJson();
        const auto pipeline = Pipeline(key);
        const auto textures = state->fb->GetTextureManager();
        for (int cursor = firstIndex; cursor < firstIndex + count;)
        {
            SdvkSurfaceObservation::Triangle start;
            if (!SdvkSurfaceObservation::ResolveTriangle(data, cursor, start))
                throw std::runtime_error("SDVK-161 submitted triangle has a stale surface/vertex/uniform mapping");
            int end = cursor + 3;
            while (end < firstIndex + count)
            {
                SdvkSurfaceObservation::Triangle next;
                if (!SdvkSurfaceObservation::ResolveTriangle(data, end, next))
                    throw std::runtime_error("SDVK-161 submitted triangle has a stale surface/vertex/uniform mapping");
                if (next.Surface != start.Surface || next.Uniform != start.Uniform) break;
                end += 3;
            }
            const auto& surface = data.Surfaces[start.Surface];
            const auto info = mesh->GetSurfaceInfoForObservation(start.Surface);
            if (!info) throw std::runtime_error("SDVK-161 submitted surface has no semantic owner");
            const auto& materialState = data.Materials[start.Uniform];
            const auto material = materialState.mMaterial;
            const char* name = material && material->Source() ? material->Source()->GetName().GetChars() : "";
            const bool target = strncmp(name, "S161", 4) == 0;
            if (target)
            {
                int vertexPage = -1;
                float vertexZMin = 0, vertexZMax = 0;
                bool mapping = true;
                const LightmapTile* currentTile = nullptr;
                if (surface.LightmapTileIndex >= 0 && size_t(surface.LightmapTileIndex) < mesh->Lightmap.Tiles.Size()
                    && mesh->Lightmap.AtlasPacker)
                {
                    const auto& candidate = mesh->Lightmap.Tiles[surface.LightmapTileIndex];
                    if (candidate.HasValidAtlasRegion(*mesh->Lightmap.AtlasPacker,
                        mesh->Lightmap.TextureSize, mesh->Lightmap.TextureCount)) currentTile = &candidate;
                }
                bool currentUV = currentTile != nullptr;
                const double plane[4] = {surface.Plane.X, surface.Plane.Y, surface.Plane.Z, surface.Plane.W};
                for (int index = cursor; index < end; ++index)
                {
                    const auto& vertex = data.Vertices[data.Indexes[index]];
                    if (index == cursor)
                    {
                        if (vertex.lindex < -1.0f || vertex.lindex > float(mesh->Lightmap.TextureCount))
                            throw std::runtime_error("SDVK-161 submitted vertex lightmap page is outside current atlas storage");
                        vertexPage = int(vertex.lindex);
                        vertexZMin = vertexZMax = vertex.z;
                    }
                    vertexZMin = std::min(vertexZMin, vertex.z);
                    vertexZMax = std::max(vertexZMax, vertex.z);
                    mapping = mapping && vertex.lindex == float(vertexPage)
                        && std::abs(plane[0] * vertex.x + plane[1] * vertex.y + plane[2] * vertex.z - plane[3]) < 0.01;
                    currentUV = currentUV && SdvkSurfaceObservation::CurrentVertexUV(*currentTile, mesh->Lightmap.TextureSize, vertex);
                }
                const int side = info->Side ? info->Side->Index() : -1;
                const int sector = info->Side ? info->Side->sector->Index()
                    : info->Subsector ? info->Subsector->sector->Index() : -1;
                const int control = info->ControlSector ? info->ControlSector->Index() : -1;
                const bool reflected = control < 0 && sector >= 0 && info->Type == ST_FLOOR
                    && level.sectors[sector].GetReflect(sector_t::floor) > 0;
                const char* klass = control >= 0 ? side >= 0 ? "three-d-floor-side"
                    : info->Type == ST_CEILING ? "three-d-floor-ceiling" : "three-d-floor-floor"
                    : reflected ? "reflective-floor" : side >= 0 ? "wall" : "flat";
                const auto& uniforms = data.Uniforms[start.Uniform];
                if (size_t(start.Uniform) >= data.LightUniforms.Size())
                    throw std::runtime_error("SDVK-161 bound mesh light uniform is unavailable");
                SdvkDiagnostics::Emit("surface", Object().Raw("context", context)
                    .Str("producer", "levelmesh-surface-range").Str("class", klass).Raw("key", pipeline)
                    .Bool("indexed", true).Int("batch_first_index", firstIndex).Int("batch_index_count", count)
                    .Int("first_index", cursor).Int("index_count", end - cursor).Int("draw_count", end - cursor)
                    .Int("surface_index", start.Surface).Int("uniform_index", start.Uniform)
                    .Int("texture_index", uniforms.uTextureIndex).Int("mesh_epoch", mesh->GetResourceEpoch().Generation)
                    .Num("alpha", data.LightUniforms[start.Uniform].uVertexColor.W)
                    .Raw("material", Material(state->fb, materialState, uniforms, context))
                    .Raw("owner", Object().Int("type", info->Type).Int("type_index", info->TypeIndex).Int("side", side)
                        .Int("sector", sector).Int("control_sector", control)
                        .Int("portal_group", sector >= 0 ? level.sectors[sector].PortalGroup : -1).Json())
                    .Raw("lightmap", SurfaceLightmap(mesh, surface.LightmapTileIndex, vertexPage,
                        textures->GetLightmapEpoch().Generation, textures->Lightmaps.size()))
                    .Raw("geometry", Object().Bool("triangle_mapping_valid", mapping).Raw("plane", PlaneJson(plane))
                        .Bool("current_uv_valid", currentUV).Num("current_uv_tolerance", SdvkSurfaceObservation::CurrentUvTolerance)
                        .Num("vertex_z_min", vertexZMin).Num("vertex_z_max", vertexZMax)
                        .Str("uv_scope", "actual submitted CPU mesh vertex lu/lv compared to the current tile transform; not GPU readback")
                        .Int("portal_index", surface.PortalIndex).Int("mesh_sector_group", surface.SectorGroup)
                        .Bool("is_sky", surface.IsSky).Json())
                    .Raw("probe", SurfaceProbe(state->fb, uniforms, -1, true))
                    .Str("scope", "intersection of actual submitted indexed range with current CPU surface/uniform/vertex owners; not GPU byte readback").Json(), true);
            }
            cursor = end;
        }
    }

    static void ImmediateSpecialSurface(VkRenderState* state, int count, bool indexed, int firstIndex)
    {
        using namespace SdvkObservation;
        const auto& source = SdvkDiagnostics::CurrentSpecialSurfaceMetadata();
        if (!source.Class || !source.HasPlane) return;
        const auto context = SdvkDiagnostics::CurrentContextJson();
        auto mesh = level.levelMesh;
        auto textures = state->fb->GetTextureManager();
        const bool portal = strcmp(source.Class, "horizon") == 0 || strcmp(source.Class, "mirror") == 0
            || strcmp(source.Class, "line-to-line-portal") == 0;
        const bool mapping = !indexed && source.VertexFirst >= 0 && source.VertexCount > 0 && firstIndex >= source.VertexFirst
            && count > 0 && uint64_t(firstIndex) + uint64_t(count) <= uint64_t(source.VertexFirst) + uint64_t(source.VertexCount);
        bool currentUV = false;
        // This TU is compiled with precise math. Producer code may use fast
        // math, so finite/UV validation belongs here rather than in the writer.
        if (mapping && source.Tile >= 0 && source.WrittenUV.Tile == source.Tile
            && source.WrittenUV.First == source.VertexFirst
            && source.WrittenUV.Vertices.size() == size_t(source.VertexCount) && mesh
            && size_t(source.Tile) < mesh->Lightmap.Tiles.Size() && mesh->Lightmap.AtlasPacker)
        {
            const auto& tile = mesh->Lightmap.Tiles[source.Tile];
            currentUV = tile.HasValidAtlasRegion(*mesh->Lightmap.AtlasPacker,
                mesh->Lightmap.TextureSize, mesh->Lightmap.TextureCount)
                && SdvkSurfaceObservation::CurrentWrittenUV<FFlatVertex>(source.WrittenUV, tile,
                    mesh->Lightmap.TextureSize, firstIndex, count);
        }
        if (!portal && (state->mPipelineKey.ShaderKey.NoFragmentShader
            || state->mPipelineKey.ShaderKey.AlphaTestOnly || !state->mPipelineKey.ColorMask)) return;
        // Portal stencils deliberately disable material shading. Do not label
        // a material left in immediate state as a texture sampled by a stencil.
        SdvkDiagnostics::Emit("surface", Object().Raw("context", context)
            .Str("producer", "immediate-special-surface").Str("class", source.Class)
            .Raw("key", Pipeline(state->mPipelineKey)).Bool("indexed", indexed)
            .Int("first_index", firstIndex).Int("index_count", count).Int("draw_count", count)
            .Int("batch_first_index", firstIndex).Int("batch_index_count", count)
            .Int("surface_index", -1).Int("uniform_index", -1)
            .Int("texture_index", portal ? -1 : state->mSurfaceUniforms.uTextureIndex)
            .Int("mesh_epoch", mesh ? mesh->GetResourceEpoch().Generation : 0).Num("alpha", state->mSurfaceUniforms.uVertexColor.W)
            .Raw("material", portal ? Object().Raw("material", Unavailable("portal stencil does not shade a material")).Json()
                : Material(state->fb, state->mMaterial, state->mSurfaceUniforms, context))
            .Raw("owner", Object().Int("type", source.Type).Int("type_index", source.Side)
                .Int("side", source.Side).Int("sector", source.Sector).Int("control_sector", source.ControlSector)
                .Int("portal_group", source.PortalGroup).Json())
            .Raw("lightmap", SurfaceLightmap(mesh, source.Tile, source.VertexLightmapPage,
                textures->GetLightmapEpoch().Generation, textures->Lightmaps.size()))
            .Raw("geometry", Object().Bool("triangle_mapping_valid", mapping).Raw("plane", PlaneJson(source.Plane))
                .Bool("current_uv_valid", currentUV)
                .Num("current_uv_tolerance", SdvkSurfaceObservation::CurrentUvTolerance).Str("uv_scope", source.UvScope)
                .Int("vertex_first", source.VertexFirst).Int("vertex_count", source.VertexCount)
                .Str("mapping_scope", "actual nonindexed draw contained in the current producer-owned vertex span; no mesh triangle table").Json())
            .Raw("probe", portal ? Unavailable("portal stencil does not sample environment probes")
                : SurfaceProbe(state->fb, state->mSurfaceUniforms, state->mLightProbeIndex, false))
            .Str("scope", "actual immediate Vulkan submission with scoped producer ownership; no independent decal receiver or GPU byte readback").Json(), true);
    }

    static void Draw(VkRenderState* state, int count, bool indexed, int firstIndex)
    {
        using namespace SdvkObservation;
        if (SdvkDiagnostics::SpecialSurfaceFrameSelected()) ImmediateSpecialSurface(state, count, indexed, firstIndex);
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
            const auto& rp = state->mSurfaceUniforms.uSpriteReliefParams;
            const auto& rb = state->mSurfaceUniforms.uSpriteReliefBounds;
            const int height = state->mSurfaceUniforms.uHeightTextureIndex;
            const int shader = material ? material->GetShaderIndex() : -1;
            const bool candidate = rp.W > 0.5f;
            const bool eligible = candidate && normal.W > 0.5f && height >= 0 &&
                (shader == 0 || shader == 3 || shader == 4);
            // Draw-bound shader eligibility, NOT an unmeasured fragment count
            // or physical GPU cost. Per-pixel grazing/alpha may still fall back.
            SdvkDiagnostics::Emit("sprite-relief", Object().Raw("context", context)
                .Raw("surface", spriteSurface).Str("material", name)
                .Int("shader", shader).Int("height_texture_index", height)
                .Raw("uv_bounds", '[' + Number(rb.X) + ',' + Number(rb.Y) + ',' + Number(rb.Z) + ',' + Number(rb.W) + ']')
                .Num("depth", rp.X).Int("quality", int(rp.Y))
                .Bool("candidate", candidate).Bool("eligible_draw", eligible)
                .Bool("basis_valid", normal.W > 0.5f)
                .Int("height_reads_max", eligible ? (rp.Y < 1.5f ? 10 : (rp.Y < 2.5f ? 15 : 23)) : 0)
                .Str("measurement", "shader-sample-upper-bound-not-actual-fragment-work")
                .Str("uniform_scope", "emitted-vulkan-draw-after-apply-surface-uniforms").Json(), true);
        }
        SdvkDiagnostics::Emit("pipeline", Object().Raw("context", context).Str("material", name)
            .Raw("key", pipeline).Bool("indexed", indexed).Int("draw_count", count)
            .Int("target_width", state->mRenderTarget.Width).Int("target_height", state->mRenderTarget.Height)
            .Int("target_format", int(state->mRenderTarget.Format)).Int("target_samples", int(state->mRenderTarget.Samples))
            .Int("draw_buffers", state->mRenderTarget.DrawBuffers).Bool("depth_stencil", state->mRenderTarget.DepthStencil != nullptr)
            .Str("basis", "canonical field state of the emitted immediate draw; no executed-shader claim").Json(), true);

        SdvkDiagnostics::Emit("material", Material(fb, state->mMaterial, state->mSurfaceUniforms, context), true);

        const int runtimeProbe = state->mSurfaceUniforms.uLightProbeIndex;
        const auto actorProbe = SdvkDiagnostics::CurrentActorProbeSelectionJson();
        const auto actorSun = SdvkDiagnostics::CurrentActorSunJson();
        auto textures = fb->GetTextureManager();
        SdvkDiagnostics::Emit("probe", Object().Raw("context", context).Str("material", name)
            .Str("mode", "uniform-environment-pair").Int("authored_index", state->mLightProbeIndex).Int("runtime_irradiance_index", runtimeProbe)
            .Bool("fallback", runtimeProbe == 0)
            .Raw("actor_selection", actorProbe.empty() ? Unavailable("not an actor sprite card") : actorProbe)
            .Raw("actor_sunlight", actorSun.empty() ? Unavailable("not an actor sprite card") : actorSun)
            .Int("probe_epoch", textures->GetLightProbeEpoch().Generation)
            .Raw("resource", runtimeProbe ? Identity(fb->GetDescriptorSetManager()->GetBindlessIdentity(runtimeProbe)) : Unavailable("zero is the no-probe sentinel"))
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
void VulkanLevelMeshDraw(VkRenderState* state, int firstIndex, int count, LevelMeshDrawSurface surface)
{
    if (!StateEnabled()) return;
    if (SpecialSurfaceEnabled() && !SpecialSurfaceFrameSelected()) return;
    try { FSdvkDiagnosticAccess::LevelMeshDraw(state, firstIndex, count, surface); }
    catch (const std::exception& error) { Fail(error.what()); }
}

void VulkanDraw(VkRenderState* state, int count, bool indexed, int firstIndex)
{
    if (!StateEnabled()) return;
    if (SpecialSurfaceEnabled() && !SpecialSurfaceFrameSelected()) return;
    if (SpecialSurfaceEnabled())
    {
        const auto& source = CurrentSpecialSurfaceMetadata();
        if (source.FirstDrawOnly && firstIndex != source.VertexFirst) return;
    }
    try { FSdvkDiagnosticAccess::Draw(state, count, indexed, firstIndex); }
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
                .Int("portals", epochs.Portals).Int("lightmap_probe", epochs.LightmapProbe).Int("resets", epochs.Resets).Json())
                .Raw("lightmap_state", LightmapLifecycle(level.levelMesh, textures->Lightmaps.size(),
                    device->GetFrameTileUpdates(), device->GetFrameTileCompletions()));
        }
        else result.Raw("levelmesh", Unavailable("no active level mesh"));
        result.Raw("sun", Object().Num("intensity", level.SunIntensity).Raw("direction", '[' + Number(level.SunDirection.X) + ',' + Number(level.SunDirection.Y) + ',' + Number(level.SunDirection.Z) + ']')
            .Str("scope", "current level authored sun state, not per-surface visibility or physical radiometry").Json());
        Emit("resource", result.Json());
    }
    catch (const std::exception& error) { Fail(error.what()); }
}
}
