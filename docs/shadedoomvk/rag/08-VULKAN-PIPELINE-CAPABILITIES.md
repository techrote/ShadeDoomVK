# Vulkan pipeline, descriptor and capability map

Baseline-SHA: `09634479ab5bf9adf691074fffe85a006a398cd0`  
Status: active with optional/experimental paths; PF-007 capability registry implemented  
Primary issues: PF-002, PF-003, PF-006, PF-007, PF-019, SDVK-003, SDVK-016

## Primary source areas

- `src/common/rendering/vulkan/vk_renderdevice.*`
- `src/common/rendering/vulkan/vk_capabilities.h`
- `src/common/rendering/vulkan/vk_devicequirks.h`
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

PF-007 records graphics-pipeline-library extension and enabled-feature state in `VulkanCapabilities`; `VkRenderPassSetup` consumes `SupportsGraphicsPipelineLibrary()`. `gl_ubershaders` remains a separate runtime policy switch and still forces the inherited non-library fallback when disabled.

The on-disk `pipelinecache.zdpc` contains the Vulkan driver cache blob returned by `VulkanPipelineCache::GetCacheData()` and restored through `PipelineCacheBuilder::InitialData()`. Renderer C++ key objects are not serialized into that file, so PF-006 introduces no renderer-key disk-cache migration.

PF-019 may optimize lookup/worker overhead only after key identity is frozen.

## Descriptor sets

The Vulkan renderer has distinct descriptor layouts/sets for fixed resources, bindless textures, LevelMesh, render-state buffers, light tiles and Z-min/max resources.

Bindless textures use update-after-bind/partially-bound/variable-count descriptor features.

PF-003 makes the required feature contract explicit: partially-bound, variable descriptor count, sampled-image update-after-bind, runtime descriptor array and non-uniform sampled-image indexing must all be enabled before bindless set creation.

PF-007 records those enabled feature bits and all PF-003 capacity-planning limits once in `VulkanCapabilities`. `VkDescriptorSetManager::CreateBindlessSet()` now consumes `GetCapabilities().BindlessLimits` rather than re-reading physical-device properties. The capacity planner and its reservations are unchanged.

Capacity remains device-aware and configurable through `vk_max_bindless_textures`. It is clamped against the relevant mixed normal/update-after-bind sampler + sampled-image pipeline-layout limits, `maxPerStageUpdateAfterBindResources` and `maxUpdateAfterBindDescriptorsInAllPools`, after reserving the fixed non-bindless scene descriptors.

The bindless address space reserves 3 fixed descriptors plus 256 descriptors for 128 lightmap/probe-page pairs. Dynamic allocations begin at descriptor 259 and use generation-aware exact-size free buckets. See `PF-003-BINDLESS-CONTRACT.md`.

## Ray query / acceleration structures

Optional Vulkan acceleration-structure/ray-query capability is used by LevelMesh/lightmapper/shadow paths where enabled. Shader-side fallback traversal exists for relevant world-trace work when ray query is unavailable.

PF-007 records ray-query extension/feature state and acceleration-structure extension/feature state independently. `SupportsRayQuery()` deliberately preserves the inherited activation predicate (ray-query extension plus physical ray-query feature) rather than silently adding a new requirement. `vk_rayquery` remains runtime policy, and the fixed descriptor set still selects the storage-buffer fallback when ray query is disabled.

Do not make PF correctness depend on ray-query hardware unless the issue explicitly targets the optional high-end path and preserves a fallback.

## Samplers and device quirks

PF-007 moves Intel PCI device-ID/driver classification out of `vk_samplers.cpp` into `vk_devicequirks.h` and stores the result in the single `VulkanCapabilities` snapshot.

The inherited behavior is frozen:

- legacy Intel devices, and listed current-driver devices below `0.405.1286`, disable anisotropy when nearest minification or magnification is selected;
- other Intel devices remap filter mode 6 to 5 and use the inherited `NearestMipLinear` nearest-minification workaround;
- non-Intel devices receive neither Intel sampler workaround;
- the AMD ray-query guard remains vendor `0x1002` with `VK_VERSION_MAJOR(driverVersion) < 10`, still controlled by `vk_amd_driver_check` and still falling back to the non-ray-query path.

The integrated/discrete default anisotropy choice, explicit anisotropy CVAR, and texture-filter selection remain sampler quality policy rather than capability-registry policy. Workaround rationale and boundaries are recorded in `PF-007-VULKAN-CAPABILITY-CONTRACT.md`.

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

PF-007 records the intersection of sampled color/depth/stencil sample-count support and routes the existing `gl_multisample` request through `VulkanCapabilities::BestSceneSampleCount()`. The clamping and best-supported-count algorithm are unchanged.

Depth/stencil and normal-buffer format probes are performed once while populating the registry, using the inherited 1x-then-4x support test. Preference order remains D24S8 then D32S8 for depth/stencil, and A2R10G10B10 then RGBA8 for normals.

See `09-POSTPROCESS-HDR-FUTURE-SEAMS.md` and `10-KNOWN-TRAPS-DORMANT-PATHS.md` for active/dormant distinctions.

## PF-007 capability registry

`VulkanCapabilities`, owned by `VulkanRenderDevice`, is the named descriptive snapshot for the audited feature/limit/quirk categories:

- required bindless descriptor-indexing feature bits;
- PF-003 descriptor/update-after-bind limits;
- ray-query and acceleration-structure support state;
- graphics-pipeline-library support state;
- shader clip-distance feature state;
- supported scene sample counts;
- depth/normal target support and selected fallback formats;
- vendor/device/type/driver identity;
- named Intel sampler and AMD ray-query driver quirks.

`PrintStartupLog()` exposes capability, enabled-ray-query, quirk, descriptor-limit, sample-count and format-selection diagnostics. Quality/configuration policy is intentionally absent from the snapshot: `vk_rayquery`, `vk_amd_driver_check`, `gl_ubershaders`, `gl_multisample`, `gl_texture_filter_anisotropic`, filter mode and `vk_max_bindless_textures` remain explicit consumer inputs.

Adversarial/boundary verification lives in `tools/pf_oracle/tests/vulkan_capabilities_fixture.cpp` and `test_vulkan_capabilities_contract.py`, including the Intel `0.405.1286` edge, AMD major-10 edge, every required bindless bit, ray-query-disabled fallback state, pipeline-library conjunction, sparse MSAA masks and format fallback/unsupported cases.

## Invariants

1. Capability queries are descriptive; quality policy remains separate.
2. Vendor/driver workaround extraction may not silently remove old workarounds.
3. Pipeline/shader/render-pass key equality/order depends only on explicitly named renderer state; packed shader specialization ABI remains separate from C++ cache identity.
4. Runtime descriptor capacity must respect physical-device limits.
5. Optional Vulkan features need explicit non-feature/fallback behavior rather than unexplained failure.
6. PF-007 does not alter gameplay/tic, material, palette/translation, sprite, portal, audio, demo-determinism, source-ownership or provenance semantics.
