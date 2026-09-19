# Vulkan pipeline, descriptor and capability map

Baseline-SHA: `09634479ab5bf9adf691074fffe85a006a398cd0`  
Status: active with optional/experimental paths  
Primary issues: PF-002, PF-003, PF-006, PF-007, PF-019, SDVK-003, SDVK-016

## Primary source areas

- `src/common/rendering/vulkan/vk_renderdevice.*`
- `src/common/rendering/vulkan/vk_renderstate.*`
- `src/common/rendering/vulkan/pipelines/*`
- `src/common/rendering/vulkan/shaders/*`
- `src/common/rendering/vulkan/descriptorsets/*`
- `src/common/rendering/vulkan/samplers/*`
- `src/common/rendering/vulkan/textures/*`
- `libraries/ZVulkan/*`

## Render/pipeline keying

PF-006 replaces whole-object `memcmp`/padding identity for `VkPipelineKey`, `VkRenderPassKey` and `VkShaderKey` with explicit semantic state in `src/common/rendering/vulkan/vk_keyidentity.h`.

- `VkKeyIdentity::ShaderState` names every meaningful shader specialization/layout field.
- `VkKeyIdentity::RenderStyleState` names `FRenderStyle`'s `BlendOp`, `SrcAlpha`, `DestAlpha` and `Flags` bytes directly.
- `VkKeyIdentity::PipelineState` names the meaningful graphics-pipeline fields plus canonical shader and render-style state.
- `VkKeyIdentity::RenderPassState` names depth/stencil presence, sample count, draw-buffer count and draw-buffer format.
- The Vulkan key classes build these states through `CanonicalState()` and use them for ordered-map equality/order.
- Padding, tail padding and shader/pipeline reserved/unused bitfields are no longer cache identity.

`FRenderStyle`'s existing four-byte identity partition is preserved exactly, including all `Flags` bits, without making `AsDWORD` or union packing part of the pipeline-key contract.

`VkShaderKey::AsQWORD` remains the packed specialization-constant ABI used by the shaders; PF-006 does not reorder or reinterpret its meaningful bits. The generalized shader cache preserves the inherited narrower partition through explicit layout/effect/user-shader/vertex-format serialization rather than raw `Layout.AsDWORD` object representation.

PF-006 deliberately retains `std::map` lookup topology and makes no lookup-performance claim. PF-019 may optimize cache/worker overhead only after this semantic identity is frozen. See `PF-006-PIPELINE-KEY-CONTRACT.md`.

## Pipeline compilation/caching

The renderer supports generalized/specialized pipelines, graphics-pipeline libraries where available, Vulkan pipeline cache and background worker threads for pipeline work.

PF-006 preserves the specialized/generalized maps, vertex-input/vertex-shader/fragment-shader/fragment-output library decomposition, priority/precache worker queues and main-thread installation semantics.

The on-disk `pipelinecache.zdpc` contains the Vulkan driver cache blob returned by `VulkanPipelineCache::GetCacheData()` and restored through `PipelineCacheBuilder::InitialData()`. Renderer C++ key objects are not serialized into that file, so PF-006 introduces no renderer-key disk-cache migration.

PF-019 may optimize lookup/worker overhead only after key identity is frozen.

## Descriptor sets

The Vulkan renderer has distinct descriptor layouts/sets for fixed resources, bindless textures, LevelMesh, render-state buffers, light tiles and Z-min/max resources.

Bindless textures use update-after-bind/partially-bound/variable-count descriptor features.

PF-003 now makes the required feature contract explicit: partially-bound, variable descriptor count, sampled-image update-after-bind, runtime descriptor array and non-uniform sampled-image indexing must all be enabled before bindless set creation.

Capacity is device-aware and configurable through `vk_max_bindless_textures`. It is clamped against the relevant mixed normal/update-after-bind sampler + sampled-image pipeline-layout limits, `maxPerStageUpdateAfterBindResources` and `maxUpdateAfterBindDescriptorsInAllPools`, after reserving the fixed non-bindless scene descriptors.

The bindless address space reserves 3 fixed descriptors plus 256 descriptors for 128 lightmap/probe-page pairs. Dynamic allocations begin at descriptor 259 and use generation-aware exact-size free buckets. See `PF-003-BINDLESS-CONTRACT.md`.

## Ray query / acceleration structures

Optional Vulkan acceleration-structure/ray-query capability is used by LevelMesh/lightmapper/shadow paths where enabled. Shader-side fallback traversal exists for relevant world-trace work when ray query is unavailable.

Do not make PF correctness depend on ray-query hardware unless the issue explicitly targets the optional high-end path and preserves a fallback.

## Samplers and device quirks

`vk_samplers.cpp` contains policy for texture filters, anisotropy and Intel device/driver-specific workarounds. Large explicit Intel device ID tables and driver-version rules live directly inside sampler creation.

PF-007 extracts a central capability/quirk query surface. The first refactor must preserve current effective behavior; policy changes require separate evidence.

## Render buffers

Vulkan scene resources include:

- `SceneColor` HDR 16F;
- depth/stencil and depth-only view;
- normal buffer;
- fog buffer;
- linear depth;
- postprocess HDR pipeline images;
- Z-min/max pyramid images;
- light-tile storage buffer.

See `09-POSTPROCESS-HDR-FUTURE-SEAMS.md` and `10-KNOWN-TRAPS-DORMANT-PATHS.md` for active/dormant distinctions.

## Capability categories PF-007 should expose

At minimum use named queries/data rather than scattered vendor tests for:

- ray-query / acceleration-structure support;
- graphics pipeline library support/use;
- descriptor indexing/update-after-bind relevant limits;
- supported sample counts;
- anisotropy/filter quirks;
- clip-distance/fallback needs where applicable;
- depth/normal target format decisions;
- known vendor/driver overrides with provenance/reason.

## Invariants

1. Capability queries are descriptive; quality policy remains separate.
2. Vendor/driver workaround extraction may not silently remove old workarounds.
3. Pipeline/shader/render-pass key equality/order depends only on explicitly named renderer state; packed shader specialization ABI remains separate from C++ cache identity.
4. Runtime descriptor capacity must respect physical-device limits.
5. Optional Vulkan features need explicit non-feature/fallback behavior rather than unexplained failure.
