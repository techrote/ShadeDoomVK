# Vulkan pipeline, descriptor and capability map

Baseline-SHA: `09634479ab5bf9adf691074fffe85a006a398cd0`  
Status: active with optional/experimental paths; PF-003 descriptor and PF-005 upload ownership hardening active  
Primary issues: PF-002, PF-003, PF-005, PF-006, PF-007, PF-019, SDVK-003, SDVK-016

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

`VkPipelineKey`, `VkRenderPassKey` and `VkShaderKey` encode pipeline/shader state. Baseline equality/ordering uses `memcmp` over whole C++ objects and relies on explicit padding plus `static_assert` size checks.

This is fast to implement but fragile as ShadeDoomVK adds states/permutations. PF-006 replaces object-representation identity with explicit canonical fields/equality/hash while preserving the exact baseline state partition.

## Pipeline compilation/caching

The renderer supports generalized/specialized pipelines, graphics-pipeline libraries where available, Vulkan pipeline cache and background worker threads for pipeline work.

PF-006 must not destroy background/precache behavior while changing keys. PF-019 may optimize lookup/worker overhead only after key identity is frozen.

## Descriptor sets

The Vulkan renderer has distinct descriptor layouts/sets for fixed resources, bindless textures, LevelMesh, render-state buffers, light tiles and Z-min/max resources.

Bindless textures use update-after-bind/partially-bound/variable-count descriptor features.

PF-003 now makes the required feature contract explicit: partially-bound, variable descriptor count, sampled-image update-after-bind, runtime descriptor array and non-uniform sampled-image indexing must all be enabled before bindless set creation.

Capacity is device-aware and configurable through `vk_max_bindless_textures`. It is clamped against the relevant mixed normal/update-after-bind sampler + sampled-image pipeline-layout limits, `maxPerStageUpdateAfterBindResources` and `maxUpdateAfterBindDescriptorsInAllPools`, after reserving the fixed non-bindless scene descriptors.

The bindless address space reserves 3 fixed descriptors plus 256 descriptors for 128 lightmap/probe-page pairs. Dynamic allocations begin at descriptor 259 and use generation-aware exact-size free buckets. See `PF-003-BINDLESS-CONTRACT.md`.

## Texture upload staging after PF-005

Ordinary `VkHardwareTexture` uploads no longer create one CPU-only `VulkanBuffer` per image. `VkTextureManager` owns a lazily-created 64 MiB persistent transfer-source buffer and `VkTextureUploadArenaPlanner` assigns 16-byte-aligned, non-overlapping slices.

The Vulkan copy contract remains conventional:

```text
CPU texture bytes
  → mapped arena slice
  → vkCmdCopyBufferToImage(bufferOffset = slice.Offset)
  → existing image layout transition / mip generation
```

Safety is intentionally conservative. Arena offsets advance monotonically while transfer commands may be in flight. When a request fits the arena but not the remaining tail, the renderer waits at the existing upload-only `WaitForCommands(false, true)` completion boundary; only after that wait returns does the planner reset to offset zero. No submitted transfer can therefore observe overwritten arena bytes.

Uploads larger than 64 MiB use the inherited dedicated transfer-buffer/deferred-delete path instead of growing persistent staging without bound. This preserves a bounded persistent-memory contract.

The arena records logical requests/acquisitions, high-water, waits, resets, reuse and oversized fallbacks. The manager separately records actual persistent backing-buffer allocations and dedicated fallbacks. The deterministic PF-005 burst fixture demonstrates allocation-count reduction without claiming synthetic GPU timing.

PF-005 does not change texture format, dimensions, mip-count/mip-generation policy, sampling/filtering or image-layout semantics. See `PF-005-TEXTURE-UPLOAD-CONTRACT.md`.

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
3. Pipeline-key refactor must map every old key state to one and only one equivalent new key.
4. Runtime descriptor capacity must respect physical-device limits.
5. Optional Vulkan features need explicit non-feature/fallback behavior rather than unexplained failure.
6. Persistent upload storage may not be reused until all submitted transfer reads from that storage are complete.
7. Texture-upload optimization may not change content, format, mip or sampling policy.
